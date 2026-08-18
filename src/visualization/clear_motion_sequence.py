"""Internal six-frame Motion Sequence artifacts for racket motions."""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.visualization.clear_pose_visualization import LANDMARK_NAMES


VERSION = "clear-motion-sequence-v1.1"
SERVE_VERSION = "serve-motion-sequence-v1.1"
SEQUENCE_FRAME_COUNT = 6
EDGE_PADDING_RATIO = 0.075


def _version(motion_type: str) -> str:
    return SERVE_VERSION if motion_type == "serve" else VERSION


def _not_ready(
    reason: str,
    sample_count: int,
    *,
    motion_type: str = "clear",
) -> dict[str, Any]:
    return {
        "status": "NOT_READY",
        "version": _version(motion_type),
        "motion_type": motion_type,
        "frame_count": SEQUENCE_FRAME_COUNT,
        "sample_count": sample_count,
        "frames": [],
        "reason": reason,
    }


def _frame_index(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    frame_index = int(value)
    if frame_index < 0 or float(frame_index) != float(value):
        return None
    return frame_index


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _valid_sample(sample: Mapping[str, Any]) -> bool:
    timestamp = _number(sample.get("timestamp_ms"))
    if timestamp is None or timestamp < 0:
        return False
    if _frame_index(sample.get("analysis_frame_index")) is None:
        return False
    if _frame_index(sample.get("source_frame_index")) is None:
        return False
    for name in LANDMARK_NAMES:
        x = _number(sample.get(f"{name}_x"))
        y = _number(sample.get(f"{name}_y"))
        if x is None or y is None or not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return False
    return True


def _ordered_valid_samples(
    samples: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    by_source_frame: dict[int, Mapping[str, Any]] = {}
    for sample in samples:
        if not isinstance(sample, Mapping) or not _valid_sample(sample):
            continue
        source_frame_index = int(sample["source_frame_index"])
        by_source_frame.setdefault(source_frame_index, sample)
    return [by_source_frame[index] for index in sorted(by_source_frame)]


def _usable_samples(
    samples: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    first = int(samples[0]["source_frame_index"])
    last = int(samples[-1]["source_frame_index"])
    padding = int(round((last - first) * EDGE_PADDING_RATIO))
    if padding <= 0:
        return list(samples)
    padded = [
        sample
        for sample in samples
        if first + padding <= int(sample["source_frame_index"]) <= last - padding
    ]
    return padded if len(padded) >= SEQUENCE_FRAME_COUNT else list(samples)


def _nearest_ordered_samples(
    samples: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    start = int(samples[0]["source_frame_index"])
    end = int(samples[-1]["source_frame_index"])
    targets = [
        start + round((end - start) * index / (SEQUENCE_FRAME_COUNT - 1))
        for index in range(SEQUENCE_FRAME_COUNT)
    ]

    selected: list[Mapping[str, Any]] = []
    minimum_position = 0
    for index, target in enumerate(targets):
        remaining = SEQUENCE_FRAME_COUNT - index - 1
        maximum_position = len(samples) - remaining - 1
        position = min(
            range(minimum_position, maximum_position + 1),
            key=lambda candidate: (
                abs(int(samples[candidate]["source_frame_index"]) - target),
                int(samples[candidate]["source_frame_index"]),
            ),
        )
        selected.append(samples[position])
        minimum_position = position + 1
    return selected


def _landmarks(sample: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    return {
        name: {
            "x": float(sample[f"{name}_x"]),
            "y": float(sample[f"{name}_y"]),
        }
        for name in LANDMARK_NAMES
    }


def _build_motion_sequence(
    samples: Sequence[Mapping[str, Any]],
    *,
    racket_side: str,
    motion_type: str,
) -> dict[str, Any]:
    """Select six ordered samples across the valid Pose source-frame window."""

    if racket_side not in {"left", "right"}:
        return _not_ready(
            "RACKET_SIDE_NOT_AVAILABLE",
            len(samples),
            motion_type=motion_type,
        )

    valid = _ordered_valid_samples(samples)
    if len(valid) < SEQUENCE_FRAME_COUNT:
        return _not_ready(
            "INSUFFICIENT_VALID_POSE_SAMPLES",
            len(samples),
            motion_type=motion_type,
        )

    usable = _usable_samples(valid)
    selected = _nearest_ordered_samples(usable)
    source_indices = [int(sample["source_frame_index"]) for sample in selected]
    if len(set(source_indices)) != SEQUENCE_FRAME_COUNT or source_indices != sorted(
        source_indices
    ):
        return _not_ready(
            "SEQUENCE_ORDER_NOT_READY",
            len(samples),
            motion_type=motion_type,
        )

    frames = []
    for index, sample in enumerate(selected, start=1):
        timestamp = float(sample["timestamp_ms"])
        frames.append(
            {
                "index": index,
                "timestamp_ms": int(timestamp) if timestamp.is_integer() else timestamp,
                "analysis_frame_index": int(sample["analysis_frame_index"]),
                "source_frame_index": int(sample["source_frame_index"]),
                "landmarks": _landmarks(sample),
            }
        )

    return {
        "status": "READY",
        "version": _version(motion_type),
        "motion_type": motion_type,
        "racket_side": racket_side,
        "frame_count": SEQUENCE_FRAME_COUNT,
        "sample_count": len(samples),
        "valid_pose_window": {
            "first_source_frame_index": int(valid[0]["source_frame_index"]),
            "last_source_frame_index": int(valid[-1]["source_frame_index"]),
        },
        "usable_pose_window": {
            "first_source_frame_index": int(usable[0]["source_frame_index"]),
            "last_source_frame_index": int(usable[-1]["source_frame_index"]),
        },
        "frames": frames,
        "selection": {
            "method": "equal_source_frame_spacing_nearest_valid_pose",
            "edge_padding_ratio": EDGE_PADDING_RATIO,
        },
        "limitations": [
            "Frames are a time-ordered motion preview, not biomechanical phases."
        ],
    }


def build_clear_motion_sequence(
    samples: Sequence[Mapping[str, Any]],
    *,
    racket_side: str,
) -> dict[str, Any]:
    return _build_motion_sequence(
        samples,
        racket_side=racket_side,
        motion_type="clear",
    )


def build_serve_motion_sequence(
    samples: Sequence[Mapping[str, Any]],
    *,
    racket_side: str,
    analysis_window: Mapping[str, Any],
) -> dict[str, Any]:
    """Select six Serve frames strictly inside its detected analysis window."""

    start = _frame_index(analysis_window.get("start_sample"))
    end = _frame_index(analysis_window.get("end_sample"))
    if (
        start is None
        or end is None
        or end < start
        or end >= len(samples)
    ):
        return _not_ready(
            "ANALYSIS_WINDOW_NOT_READY",
            len(samples),
            motion_type="serve",
        )

    result = _build_motion_sequence(
        samples[start:end + 1],
        racket_side=racket_side,
        motion_type="serve",
    )
    result["total_sample_count"] = len(samples)
    result["analysis_window"] = {
        "start_sample": start,
        "end_sample": end,
    }
    return result


def save_clear_motion_sequence(
    artifact: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
