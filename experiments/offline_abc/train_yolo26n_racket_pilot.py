#!/usr/bin/env python3
"""Fine-tune YOLO26n on the AI-assisted racket pilot dataset.

The experiment intentionally separates source videos across train/val/test.
Its labels are teacher-consensus prelabels, not human ground truth, so the
reported metrics describe this provisional dataset only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import shutil
import statistics
import time
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRETRAINED_RACKET_CLASS_ID = 38


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def box_iou(first: list[float], second: list[float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def interpolated_ap(recalls: list[float], precisions: list[float]) -> float:
    """Return COCO-style 101-point interpolated average precision."""
    if not recalls:
        return 0.0
    return sum(
        max((precision for recall, precision in zip(recalls, precisions) if recall >= threshold), default=0.0)
        for threshold in (index / 100 for index in range(101))
    ) / 101


def _ap_at_iou(
    predictions: list[dict[str, Any]],
    ground_truth_by_image: dict[str, list[list[float]]],
    threshold: float,
) -> float:
    matched = {image: set() for image in ground_truth_by_image}
    true_positives = 0
    false_positives = 0
    recalls: list[float] = []
    precisions: list[float] = []
    total_ground_truth = sum(len(boxes) for boxes in ground_truth_by_image.values())
    for prediction in sorted(predictions, key=lambda item: item["confidence"], reverse=True):
        image_key = prediction["image"]
        candidates = [
            (box_iou(prediction["xyxy"], box), index)
            for index, box in enumerate(ground_truth_by_image[image_key])
            if index not in matched[image_key]
        ]
        best_iou, best_index = max(candidates, default=(0.0, -1))
        if best_iou >= threshold:
            true_positives += 1
            matched[image_key].add(best_index)
        else:
            false_positives += 1
        recalls.append(true_positives / total_ground_truth if total_ground_truth else 0.0)
        precisions.append(true_positives / (true_positives + false_positives))
    return interpolated_ap(recalls, precisions)


def _sync(device: str) -> None:
    import torch

    if device == "mps" and torch.backends.mps.is_available():
        torch.mps.synchronize()


def _records_for_split(manifest: dict[str, Any], split: str) -> list[dict[str, Any]]:
    return [record for record in manifest["records"] if record["split"] == split]


def _training_curve_summary(results_csv: Path) -> dict[str, Any]:
    with results_csv.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise RuntimeError(f"training result is empty: {results_csv}")
    best = max(rows, key=lambda row: float(row["metrics/mAP50-95(B)"]))
    final = rows[-1]
    return {
        "best_validation_epoch": int(best["epoch"]),
        "best_validation_ap50": round(float(best["metrics/mAP50(B)"]), 6),
        "best_validation_ap50_95": round(float(best["metrics/mAP50-95(B)"]), 6),
        "final_train_box_loss": round(float(final["train/box_loss"]), 6),
        "final_validation_box_loss": round(float(final["val/box_loss"]), 6),
    }


def _evaluate(
    weights: Path,
    records: list[dict[str, Any]],
    *,
    class_id: int,
    device: str,
    image_size: int,
    decision_confidence: float,
    latency_repeats: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    from ultralytics import YOLO

    model = YOLO(str(weights))
    ground_truth_by_image = {
        record["dataset_image"]: [record["box_xyxy"]]
        for record in records
    }
    first_image = PROJECT_ROOT / records[0]["dataset_image"]
    model.predict(
        str(first_image),
        imgsz=image_size,
        conf=0.001,
        classes=[class_id],
        device=device,
        verbose=False,
    )
    _sync(device)

    predictions: list[dict[str, Any]] = []
    predictions_by_image: dict[str, list[dict[str, Any]]] = {}
    latency_samples: list[float] = []
    for record in records:
        image_key = record["dataset_image"]
        image_path = PROJECT_ROOT / image_key
        result = model.predict(
            str(image_path),
            imgsz=image_size,
            conf=0.001,
            classes=[class_id],
            device=device,
            verbose=False,
        )[0]
        image_predictions = [
            {
                "image": image_key,
                "confidence": float(confidence),
                "xyxy": [float(value) for value in box],
            }
            for box, confidence in zip(result.boxes.xyxy, result.boxes.conf)
        ]
        predictions.extend(image_predictions)
        predictions_by_image[image_key] = image_predictions
        for _ in range(latency_repeats):
            started = time.perf_counter()
            model.predict(
                str(image_path),
                imgsz=image_size,
                conf=decision_confidence,
                classes=[class_id],
                device=device,
                verbose=False,
            )
            _sync(device)
            latency_samples.append(time.perf_counter() - started)

    selected = [prediction for prediction in predictions if prediction["confidence"] >= decision_confidence]
    matched_by_image = {image: set() for image in ground_truth_by_image}
    true_positives = 0
    false_positives = 0
    for prediction in sorted(selected, key=lambda item: item["confidence"], reverse=True):
        image_key = prediction["image"]
        candidates = [
            (box_iou(prediction["xyxy"], box), index)
            for index, box in enumerate(ground_truth_by_image[image_key])
            if index not in matched_by_image[image_key]
        ]
        best_iou, best_index = max(candidates, default=(0.0, -1))
        if best_iou >= 0.5:
            true_positives += 1
            matched_by_image[image_key].add(best_index)
        else:
            false_positives += 1
    total_ground_truth = sum(len(boxes) for boxes in ground_truth_by_image.values())
    false_negatives = total_ground_truth - true_positives
    precision = true_positives / (true_positives + false_positives) if selected else 0.0
    recall = true_positives / total_ground_truth if total_ground_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    thresholds = [0.5 + index * 0.05 for index in range(10)]
    aps = [_ap_at_iou(predictions, ground_truth_by_image, threshold) for threshold in thresholds]
    latency_sorted = sorted(latency_samples)
    p95_index = math.ceil(len(latency_sorted) * 0.95) - 1
    frames_with_detection = len({prediction["image"] for prediction in selected})
    metrics = {
        "weights_path": str(weights.relative_to(PROJECT_ROOT)) if PROJECT_ROOT in weights.parents else str(weights),
        "weights_size_bytes": weights.stat().st_size,
        "weights_sha256": _sha256(weights),
        "test_frames": len(records),
        "test_ground_truth_boxes": total_ground_truth,
        "decision_confidence": decision_confidence,
        "iou_for_precision_recall": 0.5,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "ap50": round(aps[0], 6),
        "ap50_95": round(statistics.fmean(aps), 6),
        "frames_with_detection": frames_with_detection,
        "frame_detection_rate": round(frames_with_detection / len(records), 6),
        "latency_sample_count": len(latency_samples),
        "p50_wall_seconds_per_frame": round(statistics.median(latency_samples), 6),
        "p95_wall_seconds_per_frame": round(latency_sorted[p95_index], 6),
        "mean_wall_seconds_per_frame": round(statistics.fmean(latency_samples), 6),
    }
    return metrics, predictions_by_image


def _draw_comparison(
    records: list[dict[str, Any]],
    baseline: dict[str, list[dict[str, Any]]],
    tuned: dict[str, list[dict[str, Any]]],
    output: Path,
    decision_confidence: float,
) -> None:
    tiles = []
    for record in records[: min(6, len(records))]:
        image_key = record["dataset_image"]
        source = cv2.imread(str(PROJECT_ROOT / image_key))
        if source is None:
            continue
        panels = []
        for title, predictions in (("PRETRAINED", baseline), ("FINETUNED", tuned)):
            image = source.copy()
            x1, y1, x2, y2 = [round(value) for value in record["box_xyxy"]]
            cv2.rectangle(image, (x1, y1), (x2, y2), (45, 180, 70), 3)
            for prediction in predictions[image_key]:
                if prediction["confidence"] < decision_confidence:
                    continue
                px1, py1, px2, py2 = [round(value) for value in prediction["xyxy"]]
                cv2.rectangle(image, (px1, py1), (px2, py2), (230, 120, 30), 3)
                cv2.putText(
                    image,
                    f"{prediction['confidence']:.2f}",
                    (px1, max(22, py1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (230, 120, 30),
                    2,
                    cv2.LINE_AA,
                )
            cv2.putText(image, title, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 4, cv2.LINE_AA)
            cv2.putText(image, title, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 40, 60), 2, cv2.LINE_AA)
            panels.append(image)
        tiles.append(cv2.hconcat(panels))
    if not tiles:
        return
    target_width = max(tile.shape[1] for tile in tiles)
    resized = [
        cv2.resize(tile, (target_width, round(tile.shape[0] * target_width / tile.shape[1])))
        if tile.shape[1] != target_width else tile
        for tile in tiles
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), cv2.vconcat(resized), [cv2.IMWRITE_JPEG_QUALITY, 92])


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    import ultralytics
    from ultralytics import YOLO

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but unavailable")
    workspace = args.workspace.resolve()
    allowed_root = (PROJECT_ROOT / "experiments" / "offline_abc" / "results").resolve()
    if allowed_root not in workspace.parents:
        raise ValueError(f"workspace must be a child of {allowed_root}")
    runs_dir = workspace / "training_runs"
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    train_records = _records_for_split(manifest, "train")
    val_records = _records_for_split(manifest, "val")
    test_records = _records_for_split(manifest, "test")
    source_cases = {
        split: sorted({record["case_id"] for record in records})
        for split, records in (("train", train_records), ("val", val_records), ("test", test_records))
    }
    if set(source_cases["train"]) & set(source_cases["val"] + source_cases["test"]):
        raise RuntimeError("source case leakage detected")

    baseline_metrics, baseline_predictions = _evaluate(
        args.base_weights,
        test_records,
        class_id=PRETRAINED_RACKET_CLASS_ID,
        device=args.device,
        image_size=args.image_size,
        decision_confidence=args.confidence,
        latency_repeats=args.latency_repeats,
    )

    smoke_started = time.perf_counter()
    smoke_model = YOLO(str(args.base_weights))
    smoke_result = smoke_model.train(
        data=str(args.dataset_yaml),
        epochs=args.smoke_epochs,
        imgsz=args.image_size,
        batch=args.batch,
        device=args.device,
        workers=0,
        seed=args.seed,
        deterministic=True,
        project=str(runs_dir),
        name="smoke",
        exist_ok=True,
        plots=True,
        verbose=False,
        cache=False,
    )
    _sync(args.device)
    smoke_wall_seconds = time.perf_counter() - smoke_started

    formal_started = time.perf_counter()
    formal_model = YOLO(str(args.base_weights))
    formal_result = formal_model.train(
        data=str(args.dataset_yaml),
        epochs=args.epochs,
        imgsz=args.image_size,
        batch=args.batch,
        device=args.device,
        workers=0,
        seed=args.seed,
        deterministic=True,
        project=str(runs_dir),
        name="formal",
        exist_ok=True,
        plots=True,
        verbose=False,
        cache=False,
    )
    _sync(args.device)
    formal_wall_seconds = time.perf_counter() - formal_started
    best_weights = Path(formal_result.save_dir) / "weights" / "best.pt"
    if not best_weights.exists():
        raise RuntimeError(f"best weights not found: {best_weights}")
    curve_summary = _training_curve_summary(Path(formal_result.save_dir) / "results.csv")

    tuned_metrics, tuned_predictions = _evaluate(
        best_weights,
        test_records,
        class_id=0,
        device=args.device,
        image_size=args.image_size,
        decision_confidence=args.confidence,
        latency_repeats=args.latency_repeats,
    )
    evidence_path = workspace / "test_pretrained_vs_finetuned.jpg"
    _draw_comparison(
        test_records,
        baseline_predictions,
        tuned_predictions,
        evidence_path,
        args.confidence,
    )

    payload = {
        "schema_version": "ai-motion-dashboard-experiment-v1",
        "experiment": "yolo26n-ai-assisted-racket-finetune-pilot",
        "status": "completed",
        "claim_scope": "pipeline_learning_and_provisional_teacher_consensus_metrics_not_production_accuracy",
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "ultralytics": ultralytics.__version__,
            "device": args.device,
            "image_size": args.image_size,
            "batch": args.batch,
            "seed": args.seed,
        },
        "dataset": {
            **manifest["counts"],
            "annotation_status": manifest["annotation_status"],
            "selection": manifest["selection"],
            "split_source_cases": source_cases,
            "source_case_leakage": False,
        },
        "training": {
            "method": "transfer_learning_from_official_pretrained_yolo26n",
            "smoke_epochs": args.smoke_epochs,
            "smoke_wall_seconds": round(smoke_wall_seconds, 3),
            "smoke_run_directory": str(Path(smoke_result.save_dir).relative_to(PROJECT_ROOT)),
            "epochs_requested": args.epochs,
            "epochs_completed": args.epochs,
            "wall_seconds": round(formal_wall_seconds, 3),
            **curve_summary,
            "formal_run_directory": str(Path(formal_result.save_dir).relative_to(PROJECT_ROOT)),
            "best_weights_path": str(best_weights.relative_to(PROJECT_ROOT)),
            "best_weights_size_bytes": best_weights.stat().st_size,
            "best_weights_sha256": _sha256(best_weights),
        },
        "evaluation": {
            "protocol": "held-out_source_video_test; IoU>=0.50 for fixed-threshold P/R/F1; 101-point AP",
            "baseline_pretrained_yolo26n": baseline_metrics,
            "finetuned_yolo26n": tuned_metrics,
        },
        "evidence": {
            "annotation_audit_directory": str((workspace / "audit").relative_to(PROJECT_ROOT)),
            "training_curve": str((Path(formal_result.save_dir) / "results.png").relative_to(PROJECT_ROOT)),
            "test_pretrained_vs_finetuned": str(evidence_path.relative_to(PROJECT_ROOT)),
        },
        "decision": {
            "training_experience_completed": True,
            "changes_mvp_architecture": False,
            "mvp_recommendation": "MediaPipe remains sufficient when the user confirms racket hand.",
            "future_option": "YOLO26n may be retrained after human boxes, left-hand videos, negatives, and mirror metadata are added.",
        },
        "limitations": manifest["limitations"] + [
            "The same model family helped create the labels, so teacher-student agreement can inflate apparent gains.",
            "The held-out test contains one source video and only positive frames.",
            "Visual audit found several coarse boxes; the strict consensus filter reduces but does not remove label noise.",
            "No result here changes the A-over-B LLM deployment decision or proves real-world racket accuracy.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-yaml", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-weights", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--smoke-epochs", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--confidence", type=float, default=0.15)
    parser.add_argument("--latency-repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=26)
    args = parser.parse_args()
    payload = run_experiment(args)
    print(json.dumps({"dataset": payload["dataset"], "training": payload["training"], "evaluation": payload["evaluation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
