"""Task-scoped Explainable Pose response for the single motion report."""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote


VERSION = "clear-explainable-pose-v0.1"
SEQUENCE_VERSION = "clear-motion-sequence-v1.1"
SERVE_SEQUENCE_VERSION = "serve-motion-sequence-v1.1"
SEQUENCE_FRAME_COUNT = 6

LANDMARK_NAMES = (
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

STAGE_SPECS = (
    ("preparation", "準備姿勢", "sideways_preparation"),
    ("swing", "揮拍階段", "swing_smoothness"),
    ("finish", "動作完成", "weight_transfer"),
)


def explainable_pose_state(
    motion_type: str | None,
    *,
    status: str,
    reason: str,
) -> dict[str, Any]:
    """Return a stable empty visualization state without changing reports."""

    return {
        "status": status,
        "version": VERSION,
        "motion_type": motion_type,
        "racket_side": "unknown",
        "snapshots": [],
        "reason": reason,
    }


def _safe_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _safe_landmarks(value: Any) -> dict[str, dict[str, float]]:
    if not isinstance(value, Mapping):
        return {}

    landmarks: dict[str, dict[str, float]] = {}
    for name in LANDMARK_NAMES:
        point = value.get(name)
        if not isinstance(point, Mapping):
            continue
        x = _safe_number(point.get("x"))
        y = _safe_number(point.get("y"))
        if x is None or y is None or not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            continue
        landmarks[name] = {"x": x, "y": y}
    return landmarks


def load_explainable_pose(
    task_dir: Path,
    motion_type: str | None,
) -> dict[str, Any]:
    """Load and sanitize the artifact belonging to one assessment task."""

    if motion_type != "clear":
        return explainable_pose_state(
            motion_type,
            status="NOT_AVAILABLE",
            reason="UNSUPPORTED_MOTION",
        )

    artifact_path = task_dir / "output" / "clear_pose_visualization.json"
    if not artifact_path.is_file():
        return explainable_pose_state(
            motion_type,
            status="NOT_READY",
            reason="ARTIFACT_NOT_READY",
        )

    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return explainable_pose_state(
            motion_type,
            status="NOT_READY",
            reason="ARTIFACT_INVALID",
        )

    return sanitize_explainable_pose(artifact, motion_type)


def sanitize_explainable_pose(
    artifact: Any,
    motion_type: str | None,
) -> dict[str, Any]:
    """Sanitize either a local artifact or its durable private copy."""

    if motion_type != "clear":
        return explainable_pose_state(
            motion_type,
            status="NOT_AVAILABLE",
            reason="UNSUPPORTED_MOTION",
        )

    if not isinstance(artifact, Mapping) or artifact.get("status") != "READY":
        return explainable_pose_state(
            motion_type,
            status="NOT_READY",
            reason="ARTIFACT_NOT_READY",
        )

    racket_side = artifact.get("racket_side")
    if racket_side not in {"left", "right"}:
        return explainable_pose_state(
            motion_type,
            status="NOT_READY",
            reason="RACKET_SIDE_NOT_AVAILABLE",
        )

    raw_snapshots = artifact.get("snapshots")
    if not isinstance(raw_snapshots, list):
        return explainable_pose_state(
            motion_type,
            status="NOT_READY",
            reason="SNAPSHOTS_NOT_READY",
        )

    by_stage = {
        snapshot.get("stage"): snapshot
        for snapshot in raw_snapshots
        if isinstance(snapshot, Mapping)
    }
    snapshots: list[dict[str, Any]] = []

    for stage, label, focus in STAGE_SPECS:
        source = by_stage.get(stage)
        if not isinstance(source, Mapping):
            return explainable_pose_state(
                motion_type,
                status="NOT_READY",
                reason="SNAPSHOTS_NOT_READY",
            )

        timestamp_ms = _safe_number(source.get("timestamp_ms"))
        if timestamp_ms is None or timestamp_ms < 0:
            return explainable_pose_state(
                motion_type,
                status="NOT_READY",
                reason="SNAPSHOTS_NOT_READY",
            )

        snapshots.append(
            {
                "stage": stage,
                "label": label,
                "timestamp_ms": (
                    int(timestamp_ms)
                    if timestamp_ms.is_integer()
                    else timestamp_ms
                ),
                "focus": focus,
                "landmarks": _safe_landmarks(source.get("landmarks")),
            }
        )

    return {
        "status": "READY",
        "version": VERSION,
        "motion_type": "clear",
        "racket_side": racket_side,
        "snapshots": snapshots,
    }


def add_keyframe_references(
    visualization: dict[str, Any],
    assessment_id: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Add presentation-safe image references without exposing Storage paths."""

    if visualization.get("status") != "READY":
        return visualization

    raw_entries = manifest.get("keyframes") if isinstance(manifest, Mapping) else []
    entries = raw_entries if isinstance(raw_entries, list) else []
    by_stage = {
        entry.get("stage"): entry
        for entry in entries
        if isinstance(entry, Mapping)
    }
    safe_assessment_id = quote(str(assessment_id), safe="")

    for snapshot in visualization.get("snapshots", []):
        stage = snapshot.get("stage")
        entry = by_stage.get(stage)
        width = entry.get("width") if isinstance(entry, Mapping) else None
        height = entry.get("height") if isinstance(entry, Mapping) else None
        ready = (
            isinstance(entry, Mapping)
            and entry.get("status") == "READY"
            and entry.get("storage_status") == "READY"
            and isinstance(width, int)
            and not isinstance(width, bool)
            and width > 0
            and isinstance(height, int)
            and not isinstance(height, bool)
            and height > 0
        )
        snapshot["keyframe"] = (
            {
                "status": "READY",
                "url": (
                    f"/api/v1/motion-assessments/{safe_assessment_id}/"
                    f"visualization/keyframes/{stage}"
                ),
                "width": width,
                "height": height,
            }
            if ready
            else {"status": "NOT_READY"}
        )
    return visualization


def motion_sequence_state(
    motion_type: str | None,
    *,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "version": (
            SERVE_SEQUENCE_VERSION
            if motion_type == "serve"
            else SEQUENCE_VERSION
        ),
        "motion_type": motion_type,
        "frame_count": SEQUENCE_FRAME_COUNT,
        "frames": [],
        "reason": reason,
    }


def load_motion_sequence(
    task_dir: Path,
    motion_type: str | None,
) -> dict[str, Any]:
    if motion_type not in {"clear", "serve"}:
        return motion_sequence_state(
            motion_type,
            status="NOT_AVAILABLE",
            reason="UNSUPPORTED_MOTION",
        )
    artifact_path = (
        task_dir
        / "output"
        / f"{motion_type}_motion_sequence.json"
    )
    if not artifact_path.is_file():
        return motion_sequence_state(
            motion_type,
            status="NOT_READY",
            reason="SEQUENCE_ARTIFACT_NOT_READY",
        )
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return motion_sequence_state(
            motion_type,
            status="NOT_READY",
            reason="SEQUENCE_ARTIFACT_INVALID",
        )
    return sanitize_motion_sequence(artifact, motion_type)


def sanitize_motion_sequence(
    artifact: Any,
    motion_type: str | None,
) -> dict[str, Any]:
    if motion_type not in {"clear", "serve"}:
        return motion_sequence_state(
            motion_type,
            status="NOT_AVAILABLE",
            reason="UNSUPPORTED_MOTION",
        )
    if not isinstance(artifact, Mapping) or artifact.get("status") != "READY":
        return motion_sequence_state(
            motion_type,
            status="NOT_READY",
            reason="SEQUENCE_ARTIFACT_NOT_READY",
        )
    racket_side = artifact.get("racket_side")
    if racket_side not in {"left", "right"}:
        return motion_sequence_state(
            motion_type,
            status="NOT_READY",
            reason="RACKET_SIDE_NOT_AVAILABLE",
        )
    raw_frames = artifact.get("frames")
    if not isinstance(raw_frames, list) or len(raw_frames) != SEQUENCE_FRAME_COUNT:
        return motion_sequence_state(
            motion_type,
            status="NOT_READY",
            reason="SEQUENCE_FRAMES_NOT_READY",
        )

    by_index = {
        frame.get("index"): frame
        for frame in raw_frames
        if isinstance(frame, Mapping)
    }
    frames: list[dict[str, Any]] = []
    for index in range(1, SEQUENCE_FRAME_COUNT + 1):
        source = by_index.get(index)
        if not isinstance(source, Mapping):
            return motion_sequence_state(
                motion_type,
                status="NOT_READY",
                reason="SEQUENCE_FRAMES_NOT_READY",
            )
        timestamp = _safe_number(source.get("timestamp_ms"))
        landmarks = _safe_landmarks(source.get("landmarks"))
        if (
            timestamp is None
            or timestamp < 0
            or len(landmarks) != len(LANDMARK_NAMES)
        ):
            return motion_sequence_state(
                motion_type,
                status="NOT_READY",
                reason="SEQUENCE_FRAMES_NOT_READY",
            )
        frames.append(
            {
                "index": index,
                "timestamp_ms": int(timestamp) if timestamp.is_integer() else timestamp,
                "landmarks": landmarks,
            }
        )

    return {
        "status": "READY",
        "version": (
            SERVE_SEQUENCE_VERSION
            if motion_type == "serve"
            else SEQUENCE_VERSION
        ),
        "motion_type": motion_type,
        "racket_side": racket_side,
        "frame_count": SEQUENCE_FRAME_COUNT,
        "frames": frames,
    }


def add_motion_sequence_references(
    sequence: dict[str, Any],
    assessment_id: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if sequence.get("status") != "READY":
        return sequence
    raw_entries = manifest.get("frames") if isinstance(manifest, Mapping) else []
    entries = raw_entries if isinstance(raw_entries, list) else []
    by_index = {
        entry.get("index"): entry
        for entry in entries
        if isinstance(entry, Mapping)
    }
    safe_assessment_id = quote(str(assessment_id), safe="")

    for frame in sequence.get("frames", []):
        index = frame.get("index")
        entry = by_index.get(index)
        width = entry.get("width") if isinstance(entry, Mapping) else None
        height = entry.get("height") if isinstance(entry, Mapping) else None
        ready = (
            isinstance(entry, Mapping)
            and entry.get("status") == "READY"
            and entry.get("storage_status") == "READY"
            and isinstance(width, int)
            and not isinstance(width, bool)
            and width > 0
            and isinstance(height, int)
            and not isinstance(height, bool)
            and height > 0
        )
        frame["image"] = (
            {
                "status": "READY",
                "url": (
                    f"/api/v1/motion-assessments/{safe_assessment_id}/"
                    f"visualization/sequence/{index}"
                ),
                "width": width,
                "height": height,
            }
            if ready
            else {"status": "NOT_READY"}
        )
    return sequence
