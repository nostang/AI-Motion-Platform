"""Internal representative Pose snapshots for the High Clear motion."""

from __future__ import annotations

import json
from math import ceil, hypot
from pathlib import Path
from typing import Any, Mapping, Sequence


VERSION = "clear-explainable-pose-v0.1"
MINIMUM_SAMPLE_COUNT = 5

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


def _base_artifact(
    racket_side: str,
    sample_count: int,
) -> dict[str, Any]:
    return {
        "status": "NOT_READY",
        "version": VERSION,
        "motion_type": "clear",
        "racket_side": racket_side,
        "sample_count": sample_count,
        "snapshots": [],
    }


def _representative_sample(
    samples: Sequence[Mapping[str, float]],
) -> Mapping[str, float]:
    return samples[len(samples) // 2]


def _swing_sample(
    samples: Sequence[Mapping[str, float]],
    racket_side: str,
) -> Mapping[str, float] | None:
    wrist_x_key = f"{racket_side}_wrist_x"
    wrist_y_key = f"{racket_side}_wrist_y"
    fastest: tuple[float, Mapping[str, float]] | None = None

    for previous, current in zip(samples, samples[1:]):
        delta_ms = current["timestamp_ms"] - previous["timestamp_ms"]
        if delta_ms <= 0:
            continue

        displacement = hypot(
            current[wrist_x_key] - previous[wrist_x_key],
            current[wrist_y_key] - previous[wrist_y_key],
        )
        speed = displacement / (delta_ms / 1000.0)

        if fastest is None or speed > fastest[0]:
            # The current sample represents the observed end of this
            # maximum-speed wrist movement interval.
            fastest = (speed, current)

    return None if fastest is None else fastest[1]


def _landmarks(sample: Mapping[str, float]) -> dict[str, dict[str, float]]:
    return {
        name: {
            "x": float(sample[f"{name}_x"]),
            "y": float(sample[f"{name}_y"]),
        }
        for name in LANDMARK_NAMES
    }


def _timestamp_ms(sample: Mapping[str, float]) -> int | float:
    timestamp = float(sample["timestamp_ms"])
    return int(timestamp) if timestamp.is_integer() else timestamp


def _frame_index(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    frame_index = int(value)
    if frame_index < 0 or float(frame_index) != float(value):
        return None
    return frame_index


def _snapshot(
    stage: str,
    label: str,
    focus: str,
    sample: Mapping[str, float],
) -> dict[str, Any]:
    snapshot = {
        "stage": stage,
        "label": label,
        "timestamp_ms": _timestamp_ms(sample),
        "focus": focus,
        "landmarks": _landmarks(sample),
    }
    for key in ("analysis_frame_index", "source_frame_index"):
        frame_index = _frame_index(sample.get(key))
        if frame_index is not None:
            snapshot[key] = frame_index
    return snapshot


def build_clear_pose_visualization(
    samples: Sequence[Mapping[str, float]],
    *,
    racket_side: str,
) -> dict[str, Any]:
    """Build three representative snapshots without detecting motion phases."""

    artifact = _base_artifact(racket_side, len(samples))

    if len(samples) < MINIMUM_SAMPLE_COUNT:
        artifact["reason"] = "INSUFFICIENT_POSE_SAMPLES"
        return artifact

    if racket_side not in {"left", "right"}:
        artifact["reason"] = "RACKET_SIDE_NOT_AVAILABLE"
        return artifact

    required_keys = {"timestamp_ms"}
    for name in LANDMARK_NAMES:
        required_keys.update({f"{name}_x", f"{name}_y"})

    if any(not required_keys.issubset(sample) for sample in samples):
        artifact["reason"] = "INCOMPLETE_LANDMARK_SAMPLES"
        return artifact

    phase_sample_count = max(1, ceil(len(samples) * 0.25))
    preparation = _representative_sample(samples[:phase_sample_count])
    finish = _representative_sample(samples[-phase_sample_count:])
    swing = _swing_sample(samples, racket_side)

    if swing is None:
        artifact["reason"] = "INSUFFICIENT_WRIST_MOTION_SAMPLES"
        return artifact

    snapshot_specs = (
        ("preparation", "準備姿勢", "sideways_preparation", preparation),
        ("swing", "揮拍階段", "swing_smoothness", swing),
        ("finish", "動作完成", "weight_transfer", finish),
    )

    artifact.update(
        {
            "status": "READY",
            "snapshots": [
                _snapshot(stage, label, focus, sample)
                for stage, label, focus, sample in snapshot_specs
            ],
            "limitations": [
                "Snapshots are representative visualization samples, "
                "not biomechanical phase detection.",
                "The swing snapshot represents observed peak "
                "racket-side wrist speed, not contact with a shuttle.",
            ],
        }
    )
    return artifact


def save_clear_pose_visualization(
    artifact: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
