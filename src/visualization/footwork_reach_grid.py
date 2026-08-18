"""Internal nine-cell Movement Reach Grid for Footwork."""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.assessment.footwork_assessment import EXPECTED_DIRECTIONS
from src.visualization.clear_pose_visualization import LANDMARK_NAMES


VERSION = "footwork-reach-grid-v1.0"
GRID_CELL_COUNT = 9

GRID_SPECS = (
    ("LEFT_FRONT", "左前", 1, 1, "direction"),
    ("FRONT", "前", 1, 2, "direction"),
    ("RIGHT_FRONT", "右前", 1, 3, "direction"),
    ("LEFT", "左", 2, 1, "direction"),
    ("CENTER", "中心", 2, 2, "center"),
    ("RIGHT", "右", 2, 3, "direction"),
    ("LEFT_BACK", "左後", 3, 1, "direction"),
    ("BACK", "後", 3, 2, "direction"),
    ("RIGHT_BACK", "右後", 3, 3, "direction"),
)

CELL_SLUGS = {
    "LEFT_FRONT": "left-front",
    "FRONT": "front",
    "RIGHT_FRONT": "right-front",
    "LEFT": "left",
    "CENTER": "center",
    "RIGHT": "right",
    "LEFT_BACK": "left-back",
    "BACK": "back",
    "RIGHT_BACK": "right-back",
}

LANDMARK_INDICES = {
    "nose": 0,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


def capture_footwork_pose_sample(
    landmarks: Sequence[Any],
    timestamp_ms: int,
    *,
    analysis_frame_index: int,
    source_frame_index: int,
) -> dict[str, Any] | None:
    """Capture visualization-only landmarks and exact frame identity."""

    if len(landmarks) < 33:
        return None
    sample: dict[str, Any] = {
        "timestamp_ms": float(timestamp_ms),
        "analysis_frame_index": int(analysis_frame_index),
        "source_frame_index": int(source_frame_index),
    }
    for name, index in LANDMARK_INDICES.items():
        sample[f"{name}_x"] = float(landmarks[index].x)
        sample[f"{name}_y"] = float(landmarks[index].y)
    return sample


def _frame_index(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    index = int(value)
    if index < 0 or float(index) != float(value):
        return None
    return index


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _valid_sample(sample: Mapping[str, Any]) -> bool:
    if _frame_index(sample.get("analysis_frame_index")) is None:
        return False
    if _frame_index(sample.get("source_frame_index")) is None:
        return False
    timestamp = _number(sample.get("timestamp_ms"))
    if timestamp is None or timestamp < 0:
        return False
    for name in LANDMARK_NAMES:
        x = _number(sample.get(f"{name}_x"))
        y = _number(sample.get(f"{name}_y"))
        if x is None or y is None or not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return False
    return True


def _landmarks(sample: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    return {
        name: {
            "x": float(sample[f"{name}_x"]),
            "y": float(sample[f"{name}_y"]),
        }
        for name in LANDMARK_NAMES
    }


def _empty_cell(
    key: str,
    label: str,
    row: int,
    column: int,
    kind: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "row": row,
        "column": column,
        "kind": kind,
        "status": "NOT_READY",
        "reason": reason,
    }


def _ready_cell(
    spec: tuple[str, str, int, int, str],
    sample: Mapping[str, Any],
    *,
    event_id: int | None = None,
) -> dict[str, Any]:
    key, label, row, column, kind = spec
    timestamp = float(sample["timestamp_ms"])
    cell = {
        "key": key,
        "label": label,
        "row": row,
        "column": column,
        "kind": kind,
        "status": "READY",
        "timestamp_ms": int(timestamp) if timestamp.is_integer() else timestamp,
        "analysis_frame_index": int(sample["analysis_frame_index"]),
        "source_frame_index": int(sample["source_frame_index"]),
        "landmarks": _landmarks(sample),
    }
    if event_id is not None:
        cell["event_id"] = event_id
    return cell


def _representative_event(
    events: Sequence[Mapping[str, Any]],
    direction: str,
) -> Mapping[str, Any] | None:
    candidates = [
        event
        for event in events
        if isinstance(event, Mapping)
        and event.get("direction") == direction
        and event.get("completed") is True
        and _frame_index(event.get("reach_frame")) is not None
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda event: (
            _number(event.get("maximum_center_offset")) or 0.0,
            -(_frame_index(event.get("event_id")) or 0),
        ),
    )


def build_footwork_reach_grid(
    samples: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    ready_frame_index: int | None,
) -> dict[str, Any]:
    """Map existing Footwork event evidence to a fixed court-style grid."""

    valid_samples = {
        int(sample["analysis_frame_index"]): sample
        for sample in samples
        if isinstance(sample, Mapping) and _valid_sample(sample)
    }
    cells: list[dict[str, Any]] = []

    for spec in GRID_SPECS:
        key, label, row, column, kind = spec
        if kind == "center":
            sample = valid_samples.get(ready_frame_index)
            cells.append(
                _ready_cell(spec, sample)
                if sample is not None
                else _empty_cell(
                    key,
                    label,
                    row,
                    column,
                    kind,
                    "READY_FRAME_NOT_AVAILABLE",
                )
            )
            continue

        event = _representative_event(events, key)
        reach_frame = (
            _frame_index(event.get("reach_frame"))
            if event is not None
            else None
        )
        sample = valid_samples.get(reach_frame)
        if event is None:
            cells.append(
                _empty_cell(
                    key,
                    label,
                    row,
                    column,
                    kind,
                    "DIRECTION_NOT_COMPLETED",
                )
            )
        elif sample is None:
            cells.append(
                _empty_cell(
                    key,
                    label,
                    row,
                    column,
                    kind,
                    "REACH_FRAME_POSE_NOT_AVAILABLE",
                )
            )
        else:
            cells.append(
                _ready_cell(
                    spec,
                    sample,
                    event_id=_frame_index(event.get("event_id")),
                )
            )

    ready_count = sum(cell["status"] == "READY" for cell in cells)
    status = (
        "READY"
        if ready_count == GRID_CELL_COUNT
        else "PARTIAL"
        if ready_count
        else "NOT_READY"
    )
    return {
        "status": status,
        "version": VERSION,
        "motion_type": "footwork",
        "cell_count": GRID_CELL_COUNT,
        "ready_cell_count": ready_count,
        "sample_count": len(samples),
        "cells": cells,
        "selection": {
            "center": "last_valid_initial_ready_frame",
            "direction": "completed_event_reach_frame_maximum_offset",
            "duplicate_direction": "largest_maximum_center_offset_then_earliest_event",
        },
        "limitations": [
            "Grid cells reuse existing Footwork event evidence and do not reclassify directions."
        ],
    }


def save_footwork_reach_grid(
    artifact: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


assert set(EXPECTED_DIRECTIONS) == {
    key for key, _, _, _, kind in GRID_SPECS if kind == "direction"
}
