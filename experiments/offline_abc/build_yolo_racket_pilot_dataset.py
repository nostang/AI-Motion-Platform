#!/usr/bin/env python3
"""Build an AI-assisted single-class racket dataset from teacher consensus.

This is deliberately a learning/pipeline dataset, not human ground truth.  It
uses agreement between YOLO26s and YOLO26m predictions to prelabel one racket
box per frame, then splits whole source videos across train/val/test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPLIT_BY_CASE = {
    "R-SV-01": "train",
    "R-SV-02": "train",
    "R-SV-03": "train",
    "R-SV-04": "val",
    "R-SV-05": "train",
    "R-SV-06": "test",
}


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


def _frames_by_path(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        frame["frame_path"]: frame
        for case in payload["models"][0]["cases"]
        for frame in case["frames"]
    }


def _best_consensus(
    first_boxes: list[dict[str, Any]],
    second_boxes: list[dict[str, Any]],
    *,
    minimum_iou: float,
    minimum_confidence: float,
) -> dict[str, Any] | None:
    candidates = []
    for first in first_boxes:
        if first["confidence"] < minimum_confidence:
            continue
        for second in second_boxes:
            if second["confidence"] < minimum_confidence:
                continue
            iou = box_iou(first["xyxy"], second["xyxy"])
            if iou < minimum_iou:
                continue
            confidence = (first["confidence"] + second["confidence"]) / 2
            averaged = [
                (first_value + second_value) / 2
                for first_value, second_value in zip(first["xyxy"], second["xyxy"])
            ]
            candidates.append(
                {
                    "xyxy": averaged,
                    "teacher_iou": iou,
                    "mean_teacher_confidence": confidence,
                    "teacher_boxes": {"YOLO26s": first, "YOLO26m": second},
                }
            )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item["teacher_iou"], item["mean_teacher_confidence"]),
    )


def _yolo_line(box: list[float], width: int, height: int) -> str:
    x1, y1, x2, y2 = box
    center_x = ((x1 + x2) / 2) / width
    center_y = ((y1 + y2) / 2) / height
    box_width = (x2 - x1) / width
    box_height = (y2 - y1) / height
    values = [min(max(value, 0.0), 1.0) for value in (center_x, center_y, box_width, box_height)]
    return "0 " + " ".join(f"{value:.8f}" for value in values) + "\n"


def build_dataset(
    corpus_path: Path,
    teacher_s_path: Path,
    teacher_m_path: Path,
    workspace: Path,
    *,
    minimum_iou: float = 0.4,
    minimum_confidence: float = 0.2,
) -> dict[str, Any]:
    workspace = workspace if workspace.is_absolute() else PROJECT_ROOT / workspace
    workspace = workspace.resolve()
    allowed_root = (PROJECT_ROOT / "experiments" / "offline_abc" / "results").resolve()
    if allowed_root not in workspace.parents:
        raise ValueError(f"workspace must be a child of {allowed_root}")
    dataset_root = workspace / "dataset"
    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    teacher_s = json.loads(teacher_s_path.read_text(encoding="utf-8"))
    teacher_m = json.loads(teacher_m_path.read_text(encoding="utf-8"))
    frames_s = _frames_by_path(teacher_s)
    frames_m = _frames_by_path(teacher_m)

    records = []
    rejected = []
    for case in corpus["cases"]:
        case_id = case["case_id"]
        split = SPLIT_BY_CASE[case_id]
        for frame in case["frames"]:
            source_relative = frame["frame_path"]
            source = PROJECT_ROOT / source_relative
            image = cv2.imread(str(source))
            if image is None:
                raise RuntimeError(f"cannot read source frame: {source}")
            height, width = image.shape[:2]
            consensus = _best_consensus(
                frames_s[source_relative]["boxes"],
                frames_m[source_relative]["boxes"],
                minimum_iou=minimum_iou,
                minimum_confidence=minimum_confidence,
            )
            if consensus is None:
                rejected.append(
                    {
                        "case_id": case_id,
                        "sample_index": frame["sample_index"],
                        "frame_path": source_relative,
                        "reason": "no_teacher_consensus",
                        "teacher_s_box_count": len(frames_s[source_relative]["boxes"]),
                        "teacher_m_box_count": len(frames_m[source_relative]["boxes"]),
                    }
                )
                continue

            destination_name = f"{case_id}_{source.name}"
            image_destination = workspace / "dataset" / "images" / split / destination_name
            label_destination = workspace / "dataset" / "labels" / split / f"{Path(destination_name).stem}.txt"
            image_destination.parent.mkdir(parents=True, exist_ok=True)
            label_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, image_destination)
            label_destination.write_text(
                _yolo_line(consensus["xyxy"], width, height),
                encoding="utf-8",
            )
            tier = "strict_consensus" if (
                consensus["teacher_iou"] >= 0.65
                and consensus["mean_teacher_confidence"] >= 0.4
            ) else "consensus"
            records.append(
                {
                    "case_id": case_id,
                    "sample_index": frame["sample_index"],
                    "timestamp_ms": frame["timestamp_ms"],
                    "split": split,
                    "source_frame_path": source_relative,
                    "source_sha256": _sha256(source),
                    "dataset_image": str(image_destination.relative_to(PROJECT_ROOT)),
                    "dataset_label": str(label_destination.relative_to(PROJECT_ROOT)),
                    "image_width": width,
                    "image_height": height,
                    "class_name": "racket",
                    "box_xyxy": [round(value, 3) for value in consensus["xyxy"]],
                    "teacher_iou": round(consensus["teacher_iou"], 6),
                    "mean_teacher_confidence": round(consensus["mean_teacher_confidence"], 6),
                    "quality_tier": tier,
                    "annotation_source": "YOLO26s_YOLO26m_consensus_not_human_ground_truth",
                    "teacher_boxes": consensus["teacher_boxes"],
                }
            )

    yaml_path = workspace / "dataset.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                f"path: {dataset_root}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "names:",
                "  0: racket",
                "",
            ]
        ),
        encoding="utf-8",
    )
    split_counts = {
        split: sum(record["split"] == split for record in records)
        for split in ("train", "val", "test")
    }
    manifest = {
        "experiment": "ai-assisted-yolo26n-racket-finetune-pilot",
        "annotation_status": "provisional_ai_assisted_not_human_ground_truth",
        "teachers": [teacher_s["models"][0]["model"], teacher_m["models"][0]["model"]],
        "teacher_sources": [str(teacher_s_path), str(teacher_m_path)],
        "selection": {
            "minimum_teacher_iou": minimum_iou,
            "minimum_teacher_confidence": minimum_confidence,
            "one_consensus_box_maximum_per_frame": True,
        },
        "split_policy": {
            "unit": "source_video_case",
            "case_to_split": SPLIT_BY_CASE,
            "leakage_prevention": "A source case appears in exactly one split.",
        },
        "counts": {
            "source_frames": sum(len(case["frames"]) for case in corpus["cases"]),
            "included_consensus_frames": len(records),
            "rejected_frames": len(rejected),
            "split_frames": split_counts,
            "strict_consensus_frames": sum(record["quality_tier"] == "strict_consensus" for record in records),
        },
        "records": records,
        "rejected": rejected,
        "limitations": [
            "Labels are model-consensus prelabels, not independent human ground truth.",
            "All source cases are right-handed and contain only six source videos.",
            "Only consensus-positive frames are included, so negative-image false-positive behavior is not measured.",
            "Metrics from this dataset demonstrate training workflow behavior, not production accuracy.",
        ],
    }
    manifest_path = workspace / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--teacher-s", type=Path, required=True)
    parser.add_argument("--teacher-m", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--minimum-iou", type=float, default=0.4)
    parser.add_argument("--minimum-confidence", type=float, default=0.2)
    args = parser.parse_args()
    manifest = build_dataset(
        args.corpus,
        args.teacher_s,
        args.teacher_m,
        args.workspace,
        minimum_iou=args.minimum_iou,
        minimum_confidence=args.minimum_confidence,
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
