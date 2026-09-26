#!/usr/bin/env python3
"""Train and validate the authors' YOLOv12 on a tiny synthetic dataset.

This is deliberately a pipeline feasibility proof, not an accuracy benchmark.
The dataset and checkpoints remain under the ignored local workspace.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import resource
import statistics
import subprocess
import time
from pathlib import Path


OFFICIAL_REMOTE = "https://github.com/sunsmarterjie/yolov12.git"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _verify_official_repo(repo: Path) -> dict[str, str]:
    remote = _git(repo, "remote", "get-url", "origin")
    normalized = remote.removesuffix("/").removesuffix(".git")
    expected = OFFICIAL_REMOTE.removesuffix(".git")
    if normalized != expected:
        raise RuntimeError(f"Refusing non-official YOLOv12 source: {remote}")
    return {"remote": remote, "commit": _git(repo, "rev-parse", "HEAD")}


def _make_dataset(root: Path, train_count: int = 12, val_count: int = 4, image_size: int = 160) -> Path:
    import cv2
    import numpy as np

    rng = random.Random(20260926)
    for split, count in (("train", train_count), ("val", val_count)):
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            image = np.full((image_size, image_size, 3), rng.randint(20, 55), dtype=np.uint8)
            width = rng.randint(28, 62)
            height = rng.randint(24, 58)
            left = rng.randint(8, image_size - width - 8)
            top = rng.randint(8, image_size - height - 8)
            right, bottom = left + width, top + height
            color = (rng.randint(40, 100), rng.randint(120, 230), rng.randint(180, 255))
            cv2.rectangle(image, (left, top), (right, bottom), color, thickness=-1)
            stem = f"{split}_{index:03d}"
            cv2.imwrite(str(image_dir / f"{stem}.jpg"), image)
            cx = (left + right) / 2 / image_size
            cy = (top + bottom) / 2 / image_size
            normalized_width = width / image_size
            normalized_height = height / image_size
            (label_dir / f"{stem}.txt").write_text(
                f"0 {cx:.6f} {cy:.6f} {normalized_width:.6f} {normalized_height:.6f}\n"
            )

    yaml_path = root / "dataset.yaml"
    yaml_path.write_text(
        f"path: {root.resolve()}\ntrain: images/train\nval: images/val\nnames:\n  0: synthetic_target\n"
    )
    return yaml_path


def _sync_device(torch, device: str) -> None:
    if device == "mps" and torch.backends.mps.is_available():
        torch.mps.synchronize()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--inference-repeats", type=int, default=5)
    args = parser.parse_args()

    if args.epochs < 1 or args.inference_repeats < 1:
        raise ValueError("epochs and inference repeats must be positive")

    os.environ.setdefault("YOLO_CONFIG_DIR", str(args.workspace / "config"))
    os.environ.setdefault("MPLCONFIGDIR", str(args.workspace / "matplotlib"))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    import torch
    import ultralytics
    from ultralytics import YOLO

    source = _verify_official_repo(args.repo)
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but unavailable")

    dataset_root = args.workspace / "dataset"
    dataset_yaml = _make_dataset(dataset_root)
    run_root = args.workspace / "runs"
    model_yaml = args.repo / "ultralytics" / "cfg" / "models" / "v12" / "yolov12n.yaml"

    model = YOLO(str(model_yaml))
    train_started = time.perf_counter()
    train_result = model.train(
        data=str(dataset_yaml),
        epochs=args.epochs,
        imgsz=160,
        batch=4,
        device=args.device,
        workers=0,
        project=str(run_root),
        name="tiny-single-class",
        exist_ok=True,
        pretrained=False,
        plots=False,
        val=True,
        cache=False,
        deterministic=True,
        seed=7,
        verbose=False,
    )
    _sync_device(torch, args.device)
    train_seconds = time.perf_counter() - train_started

    best_path = run_root / "tiny-single-class" / "weights" / "best.pt"
    if not best_path.exists():
        raise RuntimeError(f"Training did not produce {best_path}")

    trained = YOLO(str(best_path))
    val_result = trained.val(
        data=str(dataset_yaml),
        imgsz=160,
        batch=4,
        device=args.device,
        workers=0,
        plots=False,
        verbose=False,
    )
    sample = sorted((dataset_root / "images" / "val").glob("*.jpg"))[0]
    trained.predict(str(sample), imgsz=160, device=args.device, verbose=False)
    inference_seconds = []
    prediction_counts = []
    for _ in range(args.inference_repeats):
        started = time.perf_counter()
        predictions = trained.predict(str(sample), imgsz=160, device=args.device, verbose=False)
        _sync_device(torch, args.device)
        inference_seconds.append(time.perf_counter() - started)
        prediction_counts.append(len(predictions[0].boxes))

    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = max_rss / (1024 * 1024) if platform.system() == "Darwin" else max_rss / 1024
    train_metrics = getattr(train_result, "results_dict", {}) or {}
    payload = {
        "benchmark": "official-yolov12-tiny-single-class-feasibility",
        "claim_scope": "pipeline_feasibility_only_not_model_accuracy",
        "source": source,
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "ultralytics_from_official_repo": ultralytics.__version__,
            "device": args.device,
        },
        "dataset": {
            "kind": "deterministic_synthetic_rectangles",
            "classes": 1,
            "train_images": 12,
            "validation_images": 4,
            "image_size": 160,
        },
        "training": {
            "epochs": args.epochs,
            "wall_seconds": round(train_seconds, 4),
            "model_size_bytes": best_path.stat().st_size,
            "peak_process_rss_mb": round(peak_rss_mb, 2),
            "metrics": {key: round(float(value), 6) for key, value in train_metrics.items() if isinstance(value, (int, float))},
        },
        "validation": {
            "map50": round(float(val_result.box.map50), 6),
            "map50_95": round(float(val_result.box.map), 6),
            "precision": round(float(val_result.box.mp), 6),
            "recall": round(float(val_result.box.mr), 6),
        },
        "inference": {
            "sample": sample.name,
            "repeat_count": len(inference_seconds),
            "mean_wall_seconds": round(statistics.fmean(inference_seconds), 6),
            "min_wall_seconds": round(min(inference_seconds), 6),
            "max_wall_seconds": round(max(inference_seconds), 6),
            "prediction_counts": prediction_counts,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
