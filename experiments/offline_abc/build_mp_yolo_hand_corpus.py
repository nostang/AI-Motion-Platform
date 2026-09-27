#!/usr/bin/env python3
"""Build a local MediaPipe/YOLO racket-hand comparison corpus from existing videos."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = PROJECT_ROOT / "models" / "pose_landmarker_lite.task"
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_WRIST = 15
RIGHT_WRIST = 16


def _create_cpu_pose_landmarker(model_path: Path) -> vision.PoseLandmarker:
    base_options = python.BaseOptions(
        model_asset_path=str(model_path),
        delegate=python.BaseOptions.Delegate.CPU,
    )
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.PoseLandmarker.create_from_options(options)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(PROJECT_ROOT)) if resolved.is_relative_to(PROJECT_ROOT) else str(resolved)


def _annotation_by_video_hash(assessments_root: Path) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    for annotation_path in sorted(assessments_root.glob("*/human_annotation.json")):
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        racket_side = annotation.get("racket_side")
        if racket_side not in {"left", "right"}:
            continue
        source_candidates = [
            annotation_path.parent / "source.mov",
            annotation_path.parent / "source.mp4",
        ]
        source = next((path for path in source_candidates if path.exists()), None)
        if source is None:
            continue
        source_hash = _sha256(source)
        existing = annotations.get(source_hash)
        if existing is None:
            annotations[source_hash] = {
                "annotation_path": annotation_path,
                "annotation": annotation,
                "duplicate_assessment_ids": [annotation_path.parent.name],
            }
        else:
            existing["duplicate_assessment_ids"].append(annotation_path.parent.name)
    return annotations


def _interior_timestamps(start_ms: int, end_ms: int, count: int) -> list[int]:
    if count < 1 or end_ms <= start_ms:
        raise ValueError("invalid sampling window")
    duration = end_ms - start_ms
    return [round(start_ms + duration * (index + 0.5) / count) for index in range(count)]


def _landmark_payload(landmark: Any, width: int, height: int) -> dict[str, float]:
    return {
        "x": round(float(landmark.x) * width, 3),
        "y": round(float(landmark.y) * height, 3),
        "visibility": round(float(getattr(landmark, "visibility", 0.0) or 0.0), 4),
    }


def _sample_case(
    case: dict[str, Any],
    annotation_record: dict[str, Any],
    frame_root: Path,
    model_path: Path,
    samples_per_video: int,
) -> dict[str, Any]:
    video_path = PROJECT_ROOT / case["video_path"]
    report_path = PROJECT_ROOT / case["report_path"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    automatic = ((report.get("features") or {}).get("dominant_hand") or {}).get(
        "automatic_estimate"
    ) or {}
    annotation = annotation_record["annotation"]
    window = annotation["window"]
    timestamps = _interior_timestamps(
        int(window["start_ms"]), int(window["end_ms"]), samples_per_video
    )

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open {video_path}")
    case_frame_root = frame_root / case["case_id"]
    case_frame_root.mkdir(parents=True, exist_ok=True)
    frames = []
    try:
        with _create_cpu_pose_landmarker(model_path) as landmarker:
            for index, timestamp_ms in enumerate(timestamps, start=1):
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
                success, frame = capture.read()
                if not success:
                    frames.append(
                        {
                            "sample_index": index,
                            "timestamp_ms": timestamp_ms,
                            "frame_read": False,
                            "pose_detected": False,
                        }
                    )
                    continue
                height, width = frame.shape[:2]
                frame_path = case_frame_root / f"frame_{index:02d}_{timestamp_ms:06d}ms.jpg"
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 94])
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms
                )
                landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
                frame_payload: dict[str, Any] = {
                    "sample_index": index,
                    "timestamp_ms": timestamp_ms,
                    "frame_read": True,
                    "frame_path": _relative(frame_path),
                    "width": width,
                    "height": height,
                    "pose_detected": landmarks is not None,
                }
                if landmarks is not None:
                    frame_payload["landmarks"] = {
                        "left_shoulder": _landmark_payload(landmarks[LEFT_SHOULDER], width, height),
                        "right_shoulder": _landmark_payload(landmarks[RIGHT_SHOULDER], width, height),
                        "left_wrist": _landmark_payload(landmarks[LEFT_WRIST], width, height),
                        "right_wrist": _landmark_payload(landmarks[RIGHT_WRIST], width, height),
                    }
                frames.append(frame_payload)
    finally:
        capture.release()

    return {
        "case_id": case["case_id"],
        "video_path": case["video_path"],
        "video_sha256": _sha256(video_path),
        "report_path": case["report_path"],
        "human_racket_side": annotation["racket_side"],
        "action_type": annotation.get("action_type"),
        "window": window,
        "duplicate_assessment_ids": annotation_record["duplicate_assessment_ids"],
        "mediapipe_only": {
            "status": automatic.get("status", "NOT_EVALUATED"),
            "estimated": automatic.get("estimated", "unknown"),
            "confidence": automatic.get("confidence", 0.0),
            "source": "existing pipeline automatic estimate before human override",
        },
        "frames": frames,
    }


def build_corpus(
    corpus_manifest_path: Path,
    assessments_root: Path,
    frame_root: Path,
    model_path: Path,
    samples_per_video: int,
) -> dict[str, Any]:
    manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    annotation_by_hash = _annotation_by_video_hash(assessments_root)
    cases = []
    for case in manifest.get("real_cases") or []:
        if case.get("motion") != "serve" or case.get("status") != "completed":
            continue
        video_path = PROJECT_ROOT / case["video_path"]
        annotation_record = annotation_by_hash.get(_sha256(video_path))
        if annotation_record is None:
            continue
        cases.append(
            _sample_case(
                case,
                annotation_record,
                frame_root,
                model_path,
                samples_per_video,
            )
        )
    side_counts = {
        side: sum(case["human_racket_side"] == side for case in cases)
        for side in ("left", "right")
    }
    return {
        "experiment": "mediapipe-only-vs-mediapipe-plus-yolo-racket-hand-corpus",
        "claim_scope": "real-video-right-hand-baseline-not-balanced-handedness-accuracy",
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "opencv": cv2.__version__,
            "mediapipe": getattr(mp, "__version__", "unknown"),
            "pose_model": _relative(model_path),
        },
        "sampling": {
            "samples_per_video": samples_per_video,
            "strategy": "evenly spaced interior timestamps inside human action window",
            "frame_files_committed": False,
        },
        "dataset": {
            "case_count": len(cases),
            "sampled_frame_count": sum(len(case["frames"]) for case in cases),
            "side_counts": side_counts,
            "limitations": [
                "All available human-confirmed cases are right-handed; left-hand generalization is untested.",
                "No human racket bounding boxes exist, so object precision, recall, and mAP cannot be claimed.",
                "Extracted frame files stay in the ignored local workspace and are not committed.",
            ],
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--assessments-root", type=Path, required=True)
    parser.add_argument("--frame-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--samples-per-video", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_corpus(
        args.corpus_manifest,
        args.assessments_root,
        args.frame_root,
        args.model,
        args.samples_per_video,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["dataset"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
