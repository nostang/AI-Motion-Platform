"""Motion Feature Library V1.

This module extracts descriptive, two-dimensional pose features from MediaPipe
landmarks. It does not score technique or body stability.

V1 features:
- MF001 shoulder tilt
- MF002 hip tilt
- MF003 torso lean relative to image vertical
- MF004 shoulder/hip visibility quality

All angles use image-normalized coordinates and are intended for later
calibration and expert review. They are not biomechanical ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import statistics
from typing import Any


MIN_VISIBILITY = 0.5


def _visibility(point: Any) -> float:
    return float(getattr(point, "visibility", 1.0))


def _line_tilt_degrees(left: Any, right: Any) -> float:
    """Return signed line tilt relative to the image horizontal axis."""
    return math.degrees(
        math.atan2(
            float(right.y) - float(left.y),
            float(right.x) - float(left.x),
        )
    )


def _torso_lean_degrees(
    left_shoulder: Any,
    right_shoulder: Any,
    left_hip: Any,
    right_hip: Any,
) -> float:
    """Return signed torso lean relative to image vertical.

    Positive values mean the shoulder midpoint is to the right of the hip
    midpoint in image coordinates; negative values mean left.
    """
    shoulder_x = (float(left_shoulder.x) + float(right_shoulder.x)) / 2.0
    shoulder_y = (float(left_shoulder.y) + float(right_shoulder.y)) / 2.0
    hip_x = (float(left_hip.x) + float(right_hip.x)) / 2.0
    hip_y = (float(left_hip.y) + float(right_hip.y)) / 2.0

    delta_x = shoulder_x - hip_x
    delta_y = hip_y - shoulder_y

    if abs(delta_x) < 1e-12 and abs(delta_y) < 1e-12:
        return 0.0

    return math.degrees(math.atan2(delta_x, delta_y))


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "sample_count": 0,
            "mean_degrees": None,
            "mean_absolute_degrees": None,
            "max_absolute_degrees": None,
            "standard_deviation_degrees": None,
        }

    absolute_values = [abs(value) for value in values]
    standard_deviation = statistics.pstdev(values) if len(values) > 1 else 0.0

    return {
        "sample_count": len(values),
        "mean_degrees": round(statistics.fmean(values), 4),
        "mean_absolute_degrees": round(statistics.fmean(absolute_values), 4),
        "max_absolute_degrees": round(max(absolute_values), 4),
        "standard_deviation_degrees": round(standard_deviation, 4),
    }


@dataclass
class _EventSamples:
    event_id: int
    shoulder_tilt: list[float] = field(default_factory=list)
    hip_tilt: list[float] = field(default_factory=list)
    torso_lean: list[float] = field(default_factory=list)
    visibility_scores: list[float] = field(default_factory=list)
    move_sample_count: int = 0
    recovery_sample_count: int = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None


class MotionFeatureTracker:
    """Collect and aggregate descriptive pose features for each footwork event."""

    feature_version = "motion-feature-v1"

    def __init__(self, *, min_visibility: float = MIN_VISIBILITY) -> None:
        self.min_visibility = max(0.0, min(1.0, float(min_visibility)))
        self._events: dict[int, _EventSamples] = {}

    def observe(
        self,
        *,
        event_id: int,
        previous_state: str,
        current_state: str,
        landmarks: list[Any],
        timestamp_ms: int,
    ) -> None:
        """Record one frame while an event is moving or recovering."""
        phase = None
        if current_state in {"MOVE", "RECOVER"}:
            phase = current_state
        elif previous_state == "RECOVER" and current_state == "READY":
            phase = "RECOVER"

        if event_id <= 0 or phase is None or len(landmarks) < 25:
            return

        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_hip = landmarks[23]
        right_hip = landmarks[24]

        visibility_values = [
            _visibility(left_shoulder),
            _visibility(right_shoulder),
            _visibility(left_hip),
            _visibility(right_hip),
        ]
        minimum_visibility = min(visibility_values)

        samples = self._events.setdefault(event_id, _EventSamples(event_id=event_id))
        samples.first_timestamp_ms = (
            timestamp_ms if samples.first_timestamp_ms is None else samples.first_timestamp_ms
        )
        samples.last_timestamp_ms = timestamp_ms
        samples.visibility_scores.append(minimum_visibility)

        if phase == "MOVE":
            samples.move_sample_count += 1
        else:
            samples.recovery_sample_count += 1

        if minimum_visibility < self.min_visibility:
            return

        samples.shoulder_tilt.append(
            _line_tilt_degrees(left_shoulder, right_shoulder)
        )
        samples.hip_tilt.append(_line_tilt_degrees(left_hip, right_hip))
        samples.torso_lean.append(
            _torso_lean_degrees(
                left_shoulder,
                right_shoulder,
                left_hip,
                right_hip,
            )
        )

    def finalize_event(self, event_id: int) -> dict[str, Any]:
        samples = self._events.pop(event_id, None)

        if samples is None:
            return self._empty_result(event_id)

        total_frames = samples.move_sample_count + samples.recovery_sample_count
        valid_samples = len(samples.torso_lean)
        valid_ratio = valid_samples / total_frames if total_frames > 0 else 0.0
        minimum_visibility = (
            min(samples.visibility_scores) if samples.visibility_scores else None
        )
        average_visibility = (
            statistics.fmean(samples.visibility_scores)
            if samples.visibility_scores
            else None
        )

        return {
            "feature_version": self.feature_version,
            "event_id": event_id,
            "status": "EXTRACTED" if valid_samples > 0 else "INSUFFICIENT_DATA",
            "sample_count": total_frames,
            "valid_sample_count": valid_samples,
            "valid_sample_ratio": round(valid_ratio, 4),
            "phase_samples": {
                "move": samples.move_sample_count,
                "recovery": samples.recovery_sample_count,
            },
            "time_range_ms": {
                "start": samples.first_timestamp_ms,
                "end": samples.last_timestamp_ms,
            },
            "pose_quality": {
                "minimum_visibility": (
                    round(minimum_visibility, 4)
                    if minimum_visibility is not None
                    else None
                ),
                "average_visibility": (
                    round(average_visibility, 4)
                    if average_visibility is not None
                    else None
                ),
                "minimum_required_visibility": self.min_visibility,
            },
            "features": {
                "MF001_shoulder_tilt": _summary(samples.shoulder_tilt),
                "MF002_hip_tilt": _summary(samples.hip_tilt),
                "MF003_torso_lean": _summary(samples.torso_lean),
            },
            "limitations": [
                "Angles are derived from 2D image-normalized landmarks.",
                "Camera angle and perspective can affect the values.",
                "V1 stores descriptive features only and does not score body stability.",
            ],
        }

    def _empty_result(self, event_id: int) -> dict[str, Any]:
        return {
            "feature_version": self.feature_version,
            "event_id": event_id,
            "status": "INSUFFICIENT_DATA",
            "sample_count": 0,
            "valid_sample_count": 0,
            "valid_sample_ratio": 0.0,
            "phase_samples": {"move": 0, "recovery": 0},
            "time_range_ms": {"start": None, "end": None},
            "pose_quality": {
                "minimum_visibility": None,
                "average_visibility": None,
                "minimum_required_visibility": self.min_visibility,
            },
            "features": {
                "MF001_shoulder_tilt": _summary([]),
                "MF002_hip_tilt": _summary([]),
                "MF003_torso_lean": _summary([]),
            },
            "limitations": [
                "No valid feature samples were collected for this event."
            ],
        }
