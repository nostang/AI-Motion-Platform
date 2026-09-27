#!/usr/bin/env python3
"""Compare MediaPipe-only with MediaPipe plus official YOLO racket detections."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import resource
import statistics
import time
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TENNIS_RACKET_CLASS_ID = 38
OFFICIAL_MODEL_SOURCE = "https://github.com/ultralytics/assets/releases/tag/v8.4.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _point_box_distance(x: float, y: float, box: list[float]) -> float:
    x1, y1, x2, y2 = box
    nearest_x = min(max(x, x1), x2)
    nearest_y = min(max(y, y1), y2)
    return math.hypot(x - nearest_x, y - nearest_y)


def _shoulder_width(landmarks: dict[str, dict[str, float]]) -> float:
    left = landmarks["left_shoulder"]
    right = landmarks["right_shoulder"]
    return max(math.hypot(left["x"] - right["x"], left["y"] - right["y"]), 1.0)


def pair_racket_to_wrist(
    boxes: list[dict[str, Any]],
    landmarks: dict[str, dict[str, float]],
    *,
    max_shoulder_widths: float = 2.5,
    min_wrist_visibility: float = 0.5,
) -> dict[str, Any] | None:
    if min(
        landmarks["left_wrist"]["visibility"],
        landmarks["right_wrist"]["visibility"],
    ) < min_wrist_visibility:
        return None
    scale = _shoulder_width(landmarks)
    candidates = []
    for box in boxes:
        xyxy = box["xyxy"]
        distances = {
            side: _point_box_distance(
                landmarks[f"{side}_wrist"]["x"],
                landmarks[f"{side}_wrist"]["y"],
                xyxy,
            )
            / scale
            for side in ("left", "right")
        }
        side = min(distances, key=distances.get)
        if distances[side] <= max_shoulder_widths:
            candidates.append(
                {
                    **box,
                    "paired_side": side,
                    "left_distance_shoulder_widths": round(distances["left"], 4),
                    "right_distance_shoulder_widths": round(distances["right"], 4),
                    "nearest_distance_shoulder_widths": round(distances[side], 4),
                }
            )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            item["nearest_distance_shoulder_widths"],
            -item["confidence"],
        ),
    )


def _sync(device: str) -> None:
    import torch

    if device == "mps" and torch.backends.mps.is_available():
        torch.mps.synchronize()


def _case_decision(frames: list[dict[str, Any]]) -> dict[str, Any]:
    votes = [frame["pairing"]["paired_side"] for frame in frames if frame.get("pairing")]
    counts = {side: votes.count(side) for side in ("left", "right")}
    winning_side = max(counts, key=counts.get) if votes else "unknown"
    winning_count = counts.get(winning_side, 0)
    winning_ratio = winning_count / len(votes) if votes else 0.0
    estimated = winning_side if len(votes) >= 2 and winning_ratio >= 0.6 else "unknown"
    return {
        "estimated": estimated,
        "paired_vote_count": len(votes),
        "vote_counts": counts,
        "winning_ratio": round(winning_ratio, 4),
        "decision_rule": "at least 2 paired frames and at least 60% agreement",
    }


def _draw_evidence(
    frame_path: Path,
    output_path: Path,
    landmarks: dict[str, dict[str, float]],
    pairing: dict[str, Any],
    model_label: str,
) -> None:
    image = cv2.imread(str(frame_path))
    if image is None:
        return
    x1, y1, x2, y2 = [round(value) for value in pairing["xyxy"]]
    cv2.rectangle(image, (x1, y1), (x2, y2), (34, 150, 243), 4)
    for side, color in (("left", (70, 210, 80)), ("right", (230, 90, 40))):
        wrist = landmarks[f"{side}_wrist"]
        cv2.circle(image, (round(wrist["x"]), round(wrist["y"])), 10, color, -1)
        cv2.putText(
            image,
            side.upper(),
            (round(wrist["x"]) + 10, round(wrist["y"]) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
    label = f"{model_label} racket {pairing['confidence']:.2f} -> {pairing['paired_side']}"
    cv2.putText(image, label, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 5, cv2.LINE_AA)
    cv2.putText(image, label, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image, [cv2.IMWRITE_JPEG_QUALITY, 94])


def _evaluate_baseline(cases: list[dict[str, Any]]) -> dict[str, Any]:
    determined = [case for case in cases if case["mediapipe_only"]["estimated"] in {"left", "right"}]
    agreements = sum(
        case["mediapipe_only"]["estimated"] == case["human_racket_side"] for case in cases
    )
    determined_agreements = sum(
        case["mediapipe_only"]["estimated"] == case["human_racket_side"]
        for case in determined
    )
    return {
        "case_count": len(cases),
        "determined_case_count": len(determined),
        "coverage_rate": round(len(determined) / len(cases), 4),
        "right_hand_case_agreement_rate_all_cases": round(agreements / len(cases), 4),
        "right_hand_case_agreement_rate_when_determined": round(
            determined_agreements / len(determined), 4
        ) if determined else None,
        "balanced_accuracy_not_available": True,
    }


def _evaluate_model(
    model_name: str,
    weights_path: Path,
    cases: list[dict[str, Any]],
    device: str,
    image_size: int,
    confidence: float,
    evidence_dir: Path,
) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(weights_path))
    first_frame = next(
        frame
        for case in cases
        for frame in case["frames"]
        if frame.get("frame_path") and frame.get("pose_detected")
    )
    model.predict(
        str(PROJECT_ROOT / first_frame["frame_path"]),
        imgsz=image_size,
        conf=confidence,
        classes=[TENNIS_RACKET_CLASS_ID],
        device=device,
        verbose=False,
    )
    _sync(device)

    evaluated_cases = []
    inference_times = []
    raw_detection_frames = 0
    paired_frames = 0
    pose_valid_frames = 0
    for case in cases:
        evaluated_frames = []
        evidence_written = False
        for frame in case["frames"]:
            if not frame.get("frame_path") or not frame.get("pose_detected"):
                evaluated_frames.append({**frame, "boxes": [], "pairing": None})
                continue
            pose_valid_frames += 1
            frame_path = PROJECT_ROOT / frame["frame_path"]
            started = time.perf_counter()
            result = model.predict(
                str(frame_path),
                imgsz=image_size,
                conf=confidence,
                classes=[TENNIS_RACKET_CLASS_ID],
                device=device,
                verbose=False,
            )[0]
            _sync(device)
            elapsed = time.perf_counter() - started
            inference_times.append(elapsed)
            boxes = [
                {
                    "confidence": round(float(score), 6),
                    "xyxy": [round(float(value), 3) for value in box],
                }
                for box, score in zip(result.boxes.xyxy, result.boxes.conf)
            ]
            raw_detection_frames += int(bool(boxes))
            pairing = pair_racket_to_wrist(boxes, frame["landmarks"])
            paired_frames += int(pairing is not None)
            evaluated_frames.append(
                {
                    "sample_index": frame["sample_index"],
                    "timestamp_ms": frame["timestamp_ms"],
                    "frame_path": frame["frame_path"],
                    "inference_wall_seconds": round(elapsed, 6),
                    "boxes": boxes,
                    "pairing": pairing,
                }
            )
            if pairing is not None and not evidence_written:
                _draw_evidence(
                    frame_path,
                    evidence_dir / model_name / f"{case['case_id']}.jpg",
                    frame["landmarks"],
                    pairing,
                    model_name,
                )
                evidence_written = True
        decision = _case_decision(evaluated_frames)
        evaluated_cases.append(
            {
                "case_id": case["case_id"],
                "human_racket_side": case["human_racket_side"],
                "decision": decision,
                "agreement": decision["estimated"] == case["human_racket_side"],
                "frames": evaluated_frames,
            }
        )

    determined = [case for case in evaluated_cases if case["decision"]["estimated"] != "unknown"]
    agreements = sum(case["agreement"] for case in evaluated_cases)
    determined_agreements = sum(case["agreement"] for case in determined)
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = max_rss / (1024 * 1024) if platform.system() == "Darwin" else max_rss / 1024
    return {
        "model": model_name,
        "weights_path": str(weights_path),
        "weights_size_bytes": weights_path.stat().st_size,
        "weights_sha256": _sha256(weights_path),
        "parameter_count": sum(parameter.numel() for parameter in model.model.parameters()),
        "official_model_source": OFFICIAL_MODEL_SOURCE,
        "pretrained_task": "COCO tennis racket class used as badminton-racket proxy",
        "fine_tuned_on_project_data": False,
        "case_count": len(evaluated_cases),
        "pose_valid_frame_count": pose_valid_frames,
        "raw_detection_frame_count": raw_detection_frames,
        "raw_detection_frame_rate": round(raw_detection_frames / pose_valid_frames, 4),
        "paired_frame_count": paired_frames,
        "paired_frame_rate": round(paired_frames / pose_valid_frames, 4),
        "determined_case_count": len(determined),
        "coverage_rate": round(len(determined) / len(evaluated_cases), 4),
        "right_hand_case_agreement_rate_all_cases": round(agreements / len(evaluated_cases), 4),
        "right_hand_case_agreement_rate_when_determined": round(
            determined_agreements / len(determined), 4
        ) if determined else None,
        "balanced_accuracy_not_available": True,
        "latency": {
            "mean_wall_seconds_per_frame": round(statistics.fmean(inference_times), 6),
            "p50_wall_seconds_per_frame": round(statistics.median(inference_times), 6),
            "p95_wall_seconds_per_frame": round(
                sorted(inference_times)[round((len(inference_times) - 1) * 0.95)], 6
            ),
        },
        "process_peak_rss_mb_after_model": round(peak_rss_mb, 2),
        "cases": evaluated_cases,
    }


def main() -> None:
    import torch
    import ultralytics

    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model", action="append", nargs=2, metavar=("NAME", "WEIGHTS"), required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--image-size", type=int, default=1280)
    parser.add_argument("--confidence", type=float, default=0.15)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but unavailable")
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    cases = corpus["cases"]
    models = [
        _evaluate_model(
            name,
            Path(weights),
            cases,
            args.device,
            args.image_size,
            args.confidence,
            args.evidence_dir,
        )
        for name, weights in args.model
    ]
    payload = {
        "experiment": "mediapipe-only-vs-mediapipe-plus-official-yolo-racket-hand",
        "claim_scope": "right-hand-only-agreement-and-proxy-detection-baseline_not_balanced_accuracy_or_map",
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "ultralytics": ultralytics.__version__,
            "device": args.device,
            "image_size": args.image_size,
            "confidence_threshold": args.confidence,
        },
        "dataset": corpus["dataset"],
        "mediapipe_only": _evaluate_baseline(cases),
        "models": models,
        "limitations": [
            "All six human-confirmed test cases are right-handed, so left-hand behavior and balanced accuracy remain untested.",
            "There are no human racket boxes, so proxy detection rate is not object-detection precision, recall, or mAP.",
            "YOLO models use pretrained COCO tennis-racket weights and were not fine-tuned on project frames.",
            "The experiment measures whether object evidence can complement the existing wrist-motion heuristic, not replace MediaPipe.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "mediapipe_only": payload["mediapipe_only"],
                "models": [
                    {key: value for key, value in model.items() if key not in {"cases"}}
                    for model in models
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
