"""Motion Feature Library V1.2.

Descriptive, two-dimensional motion features extracted from MediaPipe pose data.
This module does not directly decide coaching results.

Features:
- MF001 shoulder tilt
- MF002 hip tilt
- MF003 torso lean relative to image vertical
- MF005 motion smoothness from offset-change and velocity stability
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import statistics
from typing import Any


MIN_VISIBILITY = 0.5
EPSILON = 1e-9


def _visibility(point: Any) -> float:
    return float(getattr(point, "visibility", 1.0))


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _normalize_undirected_line_angle(angle_degrees: float) -> float:
    normalized = ((float(angle_degrees) + 90.0) % 180.0) - 90.0
    return 0.0 if abs(normalized) < 1e-12 else normalized


def _line_tilt_degrees(left: Any, right: Any) -> float:
    raw_angle = math.degrees(
        math.atan2(
            float(right.y) - float(left.y),
            float(right.x) - float(left.x),
        )
    )
    return _normalize_undirected_line_angle(raw_angle)


def _torso_lean_degrees(
    left_shoulder: Any,
    right_shoulder: Any,
    left_hip: Any,
    right_hip: Any,
) -> float:
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


def _motion_smoothness_summary(
    offsets: list[float],
    speeds: list[float],
) -> dict[str, Any]:
    """Build a descriptive MF005 smoothness metric.

    Offset-change roughness compares second-order changes with ordinary motion
    change. Velocity variation is the coefficient of variation of non-trivial
    pelvis speed. Lower values mean a more stable trajectory and rhythm.
    """
    offset_deltas = [
        offsets[index] - offsets[index - 1]
        for index in range(1, len(offsets))
    ]
    second_differences = [
        offset_deltas[index] - offset_deltas[index - 1]
        for index in range(1, len(offset_deltas))
    ]

    mean_delta = (
        statistics.fmean(abs(value) for value in offset_deltas)
        if offset_deltas
        else None
    )
    path_roughness = (
        statistics.fmean(abs(value) for value in second_differences)
        / max(mean_delta or 0.0, EPSILON)
        if second_differences and mean_delta is not None
        else None
    )

    valid_speeds = [value for value in speeds if value > EPSILON]
    mean_speed = statistics.fmean(valid_speeds) if valid_speeds else None
    velocity_variation = (
        statistics.pstdev(valid_speeds) / max(mean_speed or 0.0, EPSILON)
        if len(valid_speeds) >= 2 and mean_speed is not None
        else None
    )

    components = [
        value
        for value in (path_roughness, velocity_variation)
        if value is not None and math.isfinite(value)
    ]
    combined_index = statistics.fmean(components) if len(components) == 2 else None

    return {
        "sample_count": min(len(offsets), len(speeds)),
        "offset_sample_count": len(offsets),
        "velocity_sample_count": len(valid_speeds),
        "path_roughness_index": (
            round(path_roughness, 4) if path_roughness is not None else None
        ),
        "velocity_variation_index": (
            round(velocity_variation, 4)
            if velocity_variation is not None
            else None
        ),
        "combined_smoothness_index": (
            round(combined_index, 4) if combined_index is not None else None
        ),
        "direction": "lower_is_better",
        "status": "EXTRACTED" if combined_index is not None else "INSUFFICIENT_DATA",
    }


@dataclass
class _EventSamples:
    event_id: int
    shoulder_tilt: list[float] = field(default_factory=list)
    hip_tilt: list[float] = field(default_factory=list)
    torso_lean: list[float] = field(default_factory=list)
    center_offsets: list[float] = field(default_factory=list)
    pelvis_speeds: list[float] = field(default_factory=list)
    visibility_scores: list[float] = field(default_factory=list)
    move_sample_count: int = 0
    recovery_sample_count: int = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None


class MotionFeatureTracker:
    """Collect and aggregate descriptive pose and motion features per event."""

    feature_version = "motion-feature-v1.2"

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
        smoothed_center_offset: float | None = None,
        pelvis_speed: float | None = None,
    ) -> None:
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

        offset = _numeric(smoothed_center_offset)
        if offset is not None:
            samples.center_offsets.append(offset)
        speed = _numeric(pelvis_speed)
        if speed is not None and speed >= 0.0:
            samples.pelvis_speeds.append(speed)

        if minimum_visibility < self.min_visibility:
            return

        samples.shoulder_tilt.append(_line_tilt_degrees(left_shoulder, right_shoulder))
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
        minimum_visibility = min(samples.visibility_scores) if samples.visibility_scores else None
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
                "minimum_visibility": round(minimum_visibility, 4) if minimum_visibility is not None else None,
                "average_visibility": round(average_visibility, 4) if average_visibility is not None else None,
                "minimum_required_visibility": self.min_visibility,
            },
            "features": {
                "MF001_shoulder_tilt": _summary(samples.shoulder_tilt),
                "MF002_hip_tilt": _summary(samples.hip_tilt),
                "MF003_torso_lean": _summary(samples.torso_lean),
                "MF005_motion_smoothness": _motion_smoothness_summary(
                    samples.center_offsets,
                    samples.pelvis_speeds,
                ),
            },
            "limitations": [
                "Angles are derived from 2D image-normalized landmarks.",
                "Camera angle and perspective can affect the values.",
                "V1.2 smoothness uses pelvis-center offset and image-normalized speed.",
                "MF005 does not identify sport-specific footwork technique.",
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
                "MF005_motion_smoothness": _motion_smoothness_summary([], []),
            },
            "limitations": ["No valid feature samples were collected for this event."],
        }
