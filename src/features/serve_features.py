"""正手發球教學動作 MVP 的可解釋 2D Pose 特徵。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot
from statistics import mean, pstdev
from typing import Any, Sequence

from src.features.dominant_hand import DominantHandTracker


def _point(landmark: Any) -> tuple[float, float]:
    return float(landmark.x), float(landmark.y)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


@dataclass
class ServeFeatureTracker:
    """逐幀收集發球 MVP 所需特徵。"""

    samples: list[dict[str, float]] = field(default_factory=list)
    dominant_hand_tracker: DominantHandTracker = field(
        default_factory=DominantHandTracker
    )

    def observe(self, landmarks: Sequence[Any], timestamp_ms: int) -> None:
        self.dominant_hand_tracker.observe(landmarks, timestamp_ms)

        left_shoulder = _point(landmarks[11])
        right_shoulder = _point(landmarks[12])
        left_hip = _point(landmarks[23])
        right_hip = _point(landmarks[24])
        left_wrist = _point(landmarks[15])
        right_wrist = _point(landmarks[16])

        shoulder_center = _midpoint(left_shoulder, right_shoulder)
        hip_center = _midpoint(left_hip, right_hip)
        torso_dx = shoulder_center[0] - hip_center[0]
        torso_dy = hip_center[1] - shoulder_center[1]
        torso_lean = degrees(atan2(torso_dx, max(abs(torso_dy), 1e-6)))

        left_wrist_radius = _distance(left_wrist, left_shoulder)
        right_wrist_radius = _distance(right_wrist, right_shoulder)
        active_side = "right" if right_wrist_radius >= left_wrist_radius else "left"
        active_wrist = right_wrist if active_side == "right" else left_wrist
        active_shoulder = right_shoulder if active_side == "right" else left_shoulder

        self.samples.append(
            {
                "timestamp_ms": float(timestamp_ms),
                "shoulder_center_x": shoulder_center[0],
                "shoulder_center_y": shoulder_center[1],
                "hip_center_x": hip_center[0],
                "hip_center_y": hip_center[1],
                "torso_lean_degrees": torso_lean,
                "active_wrist_x": active_wrist[0],
                "active_wrist_y": active_wrist[1],
                "wrist_shoulder_distance": _distance(
                    active_wrist,
                    active_shoulder,
                ),
                "active_side_right": 1.0 if active_side == "right" else 0.0,
            }
        )

    def build(self) -> dict[str, Any]:
        dominant_hand = self.dominant_hand_tracker.build()

        if len(self.samples) < 3:
            return {
                "status": "NOT_EVALUATED",
                "feature_version": "serve-feature-v0.2",
                "sample_count": len(self.samples),
                "reason": "INSUFFICIENT_POSE_SAMPLES",
                "dominant_hand": dominant_hand,
            }

        sample_count = len(self.samples)
        prep_count = max(3, int(sample_count * 0.2))
        prep = self.samples[:prep_count]

        hip_x = [sample["hip_center_x"] for sample in prep]
        hip_y = [sample["hip_center_y"] for sample in prep]
        prep_stability = pstdev(hip_x) + pstdev(hip_y)

        wrist_path = [
            _distance(
                (first["active_wrist_x"], first["active_wrist_y"]),
                (second["active_wrist_x"], second["active_wrist_y"]),
            )
            for first, second in zip(self.samples, self.samples[1:])
        ]
        swing_path_length = sum(wrist_path)

        max_extension = max(
            sample["wrist_shoulder_distance"]
            for sample in self.samples
        )
        min_extension = min(
            sample["wrist_shoulder_distance"]
            for sample in self.samples
        )
        extension_range = max_extension - min_extension

        torso_values = [
            sample["torso_lean_degrees"]
            for sample in self.samples
        ]
        torso_change = max(torso_values) - min(torso_values)

        speeds: list[float] = []
        for first, second in zip(self.samples, self.samples[1:]):
            dt = (
                second["timestamp_ms"]
                - first["timestamp_ms"]
            ) / 1000.0
            if dt <= 0:
                continue

            displacement = _distance(
                (first["active_wrist_x"], first["active_wrist_y"]),
                (second["active_wrist_x"], second["active_wrist_y"]),
            )
            speeds.append(displacement / dt)

        mean_speed = mean(speeds) if speeds else 0.0
        speed_variation = (
            pstdev(speeds) / mean_speed
            if speeds and mean_speed > 1e-9
            else None
        )

        active_side = (
            "right"
            if mean(
                sample["active_side_right"]
                for sample in self.samples
            ) >= 0.5
            else "left"
        )

        return {
            "status": "EXTRACTED",
            "feature_version": "serve-feature-v0.2",
            "sample_count": sample_count,
            "active_side_estimate": active_side,
            "dominant_hand": dominant_hand,
            "preparation_stability_index": round(prep_stability, 6),
            "swing_path_length": round(swing_path_length, 6),
            "wrist_extension_range": round(extension_range, 6),
            "torso_change_degrees": round(torso_change, 4),
            "wrist_speed_variation": (
                None
                if speed_variation is None
                else round(speed_variation, 6)
            ),
            "limitations": [
                "Uses one-camera 2D MediaPipe landmarks.",
                "Designed for a visible forehand serve teaching motion.",
                "Active racket arm is estimated from wrist movement only.",
                "Dominant hand is estimated from wrist-motion evidence and does not use racket detection.",
                "Does not evaluate backhand serve technique, grip, finger action, racket, shuttle, impact point, or service legality.",
            ],
        }
