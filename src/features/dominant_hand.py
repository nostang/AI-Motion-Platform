"""MediaPipe Pose 慣用手推估。

只根據左右手腕在影片中的運動特徵進行推估，不參與動作評分。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from statistics import mean
from typing import Any, Sequence

LEFT_WRIST_INDEX = 15
RIGHT_WRIST_INDEX = 16
MIN_VISIBILITY = 0.5
MIN_SAMPLES = 12
EPSILON = 1e-9


def _point(landmark: Any) -> tuple[float, float]:
    return float(landmark.x), float(landmark.y)


def _visibility(landmark: Any) -> float:
    return float(getattr(landmark, "visibility", 1.0))


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(b[0] - a[0], b[1] - a[1])


def _vote(left_value: float, right_value: float) -> str:
    if abs(left_value - right_value) <= EPSILON:
        return "tie"
    return "right" if right_value > left_value else "left"


def _separation(left_value: float, right_value: float) -> float:
    maximum = max(abs(left_value), abs(right_value), EPSILON)
    return min(1.0, abs(right_value - left_value) / maximum)


@dataclass
class DominantHandTracker:
    """逐幀收集左右手腕運動，推估主要使用手。"""

    min_visibility: float = MIN_VISIBILITY
    samples: list[dict[str, float]] = field(default_factory=list)

    def observe(self, landmarks: Sequence[Any], timestamp_ms: int) -> None:
        if len(landmarks) <= RIGHT_WRIST_INDEX:
            return

        left_wrist = landmarks[LEFT_WRIST_INDEX]
        right_wrist = landmarks[RIGHT_WRIST_INDEX]

        if min(_visibility(left_wrist), _visibility(right_wrist)) < self.min_visibility:
            return

        left_x, left_y = _point(left_wrist)
        right_x, right_y = _point(right_wrist)

        self.samples.append(
            {
                "timestamp_ms": float(timestamp_ms),
                "left_x": left_x,
                "left_y": left_y,
                "right_x": right_x,
                "right_y": right_y,
            }
        )

    def build(self) -> dict[str, Any]:
        if len(self.samples) < MIN_SAMPLES:
            return {
                "status": "NOT_EVALUATED",
                "feature_version": "dominant-hand-v0.1",
                "sample_count": len(self.samples),
                "estimated": "unknown",
                "confidence": 0.0,
                "reason": "INSUFFICIENT_POSE_SAMPLES",
            }

        left_distances: list[float] = []
        right_distances: list[float] = []
        left_speeds: list[float] = []
        right_speeds: list[float] = []

        for previous, current in zip(self.samples, self.samples[1:]):
            dt = (current["timestamp_ms"] - previous["timestamp_ms"]) / 1000.0
            if dt <= 0:
                continue

            left_distance = _distance(
                (previous["left_x"], previous["left_y"]),
                (current["left_x"], current["left_y"]),
            )
            right_distance = _distance(
                (previous["right_x"], previous["right_y"]),
                (current["right_x"], current["right_y"]),
            )

            left_distances.append(left_distance)
            right_distances.append(right_distance)
            left_speeds.append(left_distance / dt)
            right_speeds.append(right_distance / dt)

        if not left_speeds or not right_speeds:
            return {
                "status": "NOT_EVALUATED",
                "feature_version": "dominant-hand-v0.1",
                "sample_count": len(self.samples),
                "estimated": "unknown",
                "confidence": 0.0,
                "reason": "INSUFFICIENT_MOTION_SAMPLES",
            }

        left_path = sum(left_distances)
        right_path = sum(right_distances)
        left_mean_speed = mean(left_speeds)
        right_mean_speed = mean(right_speeds)
        left_max_speed = max(left_speeds)
        right_max_speed = max(right_speeds)

        global_max_speed = max(left_max_speed, right_max_speed, EPSILON)
        active_threshold = global_max_speed * 0.2
        left_active_frames = sum(speed >= active_threshold for speed in left_speeds)
        right_active_frames = sum(speed >= active_threshold for speed in right_speeds)

        evidence = {
            "path_length": _vote(left_path, right_path),
            "mean_speed": _vote(left_mean_speed, right_mean_speed),
            "max_speed": _vote(left_max_speed, right_max_speed),
            "active_frames": _vote(float(left_active_frames), float(right_active_frames)),
        }

        left_votes = sum(value == "left" for value in evidence.values())
        right_votes = sum(value == "right" for value in evidence.values())
        estimated = (
            "unknown"
            if left_votes == right_votes
            else ("right" if right_votes > left_votes else "left")
        )

        agreement = max(left_votes, right_votes) / len(evidence)
        separation = mean(
            [
                _separation(left_path, right_path),
                _separation(left_mean_speed, right_mean_speed),
                _separation(left_max_speed, right_max_speed),
                _separation(float(left_active_frames), float(right_active_frames)),
            ]
        )
        confidence = round(agreement * 0.6 + separation * 0.4, 4)

        if estimated == "unknown" or confidence < 0.6:
            status = "UNCERTAIN"
            estimated = "unknown"
        else:
            status = "ESTIMATED"

        return {
            "status": status,
            "feature_version": "dominant-hand-v0.1",
            "sample_count": len(self.samples),
            "estimated": estimated,
            "confidence": confidence,
            "evidence": evidence,
            "measurements": {
                "left": {
                    "path_length": round(left_path, 6),
                    "mean_speed": round(left_mean_speed, 6),
                    "max_speed": round(left_max_speed, 6),
                    "active_frames": left_active_frames,
                },
                "right": {
                    "path_length": round(right_path, 6),
                    "mean_speed": round(right_mean_speed, 6),
                    "max_speed": round(right_max_speed, 6),
                    "active_frames": right_active_frames,
                },
                "active_speed_threshold": round(active_threshold, 6),
            },
            "limitations": [
                "Uses one-camera 2D MediaPipe wrist landmarks.",
                "Estimates the active hand in this video, which may differ from the user's long-term dominant hand.",
                "Mirrored video, occlusion, two-handed drills, or non-dominant-hand practice may reduce reliability.",
                "Racket detection is not used in this version.",
            ],
        }
