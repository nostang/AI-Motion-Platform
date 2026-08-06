"""高遠球教學動作 MVP 的可解釋 2D Pose 特徵。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot
from statistics import mean, median, pstdev
from typing import Any, Sequence

from src.features.racket_hand import estimate_racket_hand


def _point(landmark: Any) -> tuple[float, float]:
    return float(landmark.x), float(landmark.y)


def _distance(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    return hypot(
        point_a[0] - point_b[0],
        point_a[1] - point_b[1],
    )


def _midpoint(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> tuple[float, float]:
    return (
        (point_a[0] + point_b[0]) / 2.0,
        (point_a[1] + point_b[1]) / 2.0,
    )


def _line_angle(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    return degrees(
        atan2(
            point_b[1] - point_a[1],
            point_b[0] - point_a[0],
        )
    )


def _axis_angle(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    return _line_angle(point_a, point_b) % 180.0


def _axis_angle_distance(
    angle_a: float,
    angle_b: float,
) -> float:
    difference = abs(angle_a - angle_b) % 180.0
    return min(difference, 180.0 - difference)


def _path_length(
    points: Sequence[tuple[float, float]],
) -> float:
    return sum(
        _distance(point_a, point_b)
        for point_a, point_b in zip(points, points[1:])
    )


@dataclass
class ClearFeatureTracker:
    """逐幀收集高遠球教學動作所需的 Pose Measurements。"""

    samples: list[dict[str, float]] = field(default_factory=list)
    expected_racket_side: str | None = "right"

    def observe(
        self,
        landmarks: Sequence[Any],
        timestamp_ms: int,
    ) -> None:
        if len(landmarks) < 33:
            return

        left_shoulder = _point(landmarks[11])
        right_shoulder = _point(landmarks[12])
        left_elbow = _point(landmarks[13])
        right_elbow = _point(landmarks[14])
        left_wrist = _point(landmarks[15])
        right_wrist = _point(landmarks[16])
        left_hip = _point(landmarks[23])
        right_hip = _point(landmarks[24])
        left_ankle = _point(landmarks[27])
        right_ankle = _point(landmarks[28])

        shoulder_center = _midpoint(left_shoulder, right_shoulder)
        hip_center = _midpoint(left_hip, right_hip)

        shoulder_width = _distance(left_shoulder, right_shoulder)
        hip_width = _distance(left_hip, right_hip)
        torso_length = _distance(shoulder_center, hip_center)
        body_scale = max(
            shoulder_width,
            hip_width,
            torso_length,
            1e-6,
        )

        self.samples.append(
            {
                "timestamp_ms": float(timestamp_ms),
                "left_shoulder_x": left_shoulder[0],
                "left_shoulder_y": left_shoulder[1],
                "right_shoulder_x": right_shoulder[0],
                "right_shoulder_y": right_shoulder[1],
                "left_elbow_x": left_elbow[0],
                "left_elbow_y": left_elbow[1],
                "right_elbow_x": right_elbow[0],
                "right_elbow_y": right_elbow[1],
                "left_wrist_x": left_wrist[0],
                "left_wrist_y": left_wrist[1],
                "right_wrist_x": right_wrist[0],
                "right_wrist_y": right_wrist[1],
                "left_hip_x": left_hip[0],
                "left_hip_y": left_hip[1],
                "right_hip_x": right_hip[0],
                "right_hip_y": right_hip[1],
                "left_ankle_x": left_ankle[0],
                "left_ankle_y": left_ankle[1],
                "right_ankle_x": right_ankle[0],
                "right_ankle_y": right_ankle[1],
                "shoulder_center_x": shoulder_center[0],
                "shoulder_center_y": shoulder_center[1],
                "hip_center_x": hip_center[0],
                "hip_center_y": hip_center[1],
                "shoulder_width": shoulder_width,
                "hip_width": hip_width,
                "torso_length": torso_length,
                "body_scale": body_scale,
                "shoulder_line_angle": _axis_angle(
                    left_shoulder,
                    right_shoulder,
                ),
                "hip_line_angle": _axis_angle(
                    left_hip,
                    right_hip,
                ),
            }
        )

    def _estimate_racket_side(self) -> str:
        if self.expected_racket_side in {"left", "right"}:
            return self.expected_racket_side

        left_wrist_points = [
            (sample["left_wrist_x"], sample["left_wrist_y"])
            for sample in self.samples
        ]
        right_wrist_points = [
            (sample["right_wrist_x"], sample["right_wrist_y"])
            for sample in self.samples
        ]

        return (
            "right"
            if _path_length(right_wrist_points)
            >= _path_length(left_wrist_points)
            else "left"
        )

    def build(self) -> dict[str, Any]:
        if len(self.samples) < 5:
            return {
                "status": "NOT_EVALUATED",
                "feature_version": "clear-feature-v0.3",
                "sample_count": len(self.samples),
                "reason": "INSUFFICIENT_POSE_SAMPLES",
                "racket_hand": estimate_racket_hand(self.samples),
            }

        sample_count = len(self.samples)
        racket_side = self._estimate_racket_side()
        non_racket_side = "left" if racket_side == "right" else "right"
        racket_hand = estimate_racket_hand(self.samples)

        phase_sample_count = max(3, int(sample_count * 0.25))
        preparation_samples = self.samples[:phase_sample_count]
        finish_samples = self.samples[-phase_sample_count:]

        reference_body_scale = median(
            sample["body_scale"]
            for sample in self.samples
        )

        shoulder_hip_ratios = [
            sample["shoulder_width"] / max(sample["hip_width"], 1e-6)
            for sample in preparation_samples
        ]
        minimum_shoulder_hip_ratio = min(shoulder_hip_ratios)
        mean_shoulder_hip_ratio = mean(shoulder_hip_ratios)

        shoulder_angles = [
            sample["shoulder_line_angle"]
            for sample in self.samples
        ]
        preparation_angle = median(
            sample["shoulder_line_angle"]
            for sample in preparation_samples
        )
        shoulder_angle_range = max(
            _axis_angle_distance(angle, preparation_angle)
            for angle in shoulder_angles
        )

        preparation_hip_x = mean(
            sample["hip_center_x"]
            for sample in preparation_samples
        )
        finish_hip_x = mean(
            sample["hip_center_x"]
            for sample in finish_samples
        )
        hip_center_shift = abs(
            finish_hip_x - preparation_hip_x
        ) / max(reference_body_scale, 1e-6)

        hip_x_values = [
            sample["hip_center_x"]
            for sample in self.samples
        ]
        hip_center_range = (
            max(hip_x_values) - min(hip_x_values)
        ) / max(reference_body_scale, 1e-6)

        non_racket_wrist_y_key = f"{non_racket_side}_wrist_y"
        non_racket_shoulder_y_key = f"{non_racket_side}_shoulder_y"
        non_racket_arm_elevations = [
            (
                sample[non_racket_shoulder_y_key]
                - sample[non_racket_wrist_y_key]
            )
            / max(reference_body_scale, 1e-6)
            for sample in self.samples
        ]
        maximum_non_racket_arm_elevation = max(
            non_racket_arm_elevations
        )
        elevated_sample_ratio = sum(
            elevation > 0
            for elevation in non_racket_arm_elevations
        ) / sample_count

        non_racket_wrist_points = [
            (
                sample[f"{non_racket_side}_wrist_x"],
                sample[f"{non_racket_side}_wrist_y"],
            )
            for sample in self.samples
        ]
        non_racket_arm_path_length = (
            _path_length(non_racket_wrist_points)
            / max(reference_body_scale, 1e-6)
        )

        racket_wrist_points = [
            (
                sample[f"{racket_side}_wrist_x"],
                sample[f"{racket_side}_wrist_y"],
            )
            for sample in self.samples
        ]
        racket_wrist_path_length = (
            _path_length(racket_wrist_points)
            / max(reference_body_scale, 1e-6)
        )

        wrist_speeds: list[float] = []
        for previous, current in zip(
            self.samples,
            self.samples[1:],
        ):
            delta_time = (
                current["timestamp_ms"]
                - previous["timestamp_ms"]
            ) / 1000.0
            if delta_time <= 0:
                continue

            previous_wrist = (
                previous[f"{racket_side}_wrist_x"],
                previous[f"{racket_side}_wrist_y"],
            )
            current_wrist = (
                current[f"{racket_side}_wrist_x"],
                current[f"{racket_side}_wrist_y"],
            )
            normalized_displacement = (
                _distance(previous_wrist, current_wrist)
                / max(reference_body_scale, 1e-6)
            )
            wrist_speeds.append(
                normalized_displacement / delta_time
            )

        mean_wrist_speed = mean(wrist_speeds) if wrist_speeds else 0.0
        wrist_speed_variation = (
            pstdev(wrist_speeds) / mean_wrist_speed
            if len(wrist_speeds) >= 2
            and mean_wrist_speed > 1e-9
            else None
        )

        if wrist_speeds and mean_wrist_speed > 1e-9:
            low_speed_threshold = mean_wrist_speed * 0.15
            wrist_low_speed_ratio = sum(
                speed <= low_speed_threshold
                for speed in wrist_speeds
            ) / len(wrist_speeds)
        else:
            wrist_low_speed_ratio = None

        return {
            "status": "EXTRACTED",
            "feature_version": "clear-feature-v0.3",
            "sample_count": sample_count,
            "racket_side_estimate": racket_side,
            "non_racket_side_estimate": non_racket_side,
            "racket_hand": racket_hand,
            "reference_body_scale": round(reference_body_scale, 6),
            "sideways_preparation": {
                "minimum_shoulder_hip_ratio": round(
                    minimum_shoulder_hip_ratio,
                    6,
                ),
                "mean_shoulder_hip_ratio": round(
                    mean_shoulder_hip_ratio,
                    6,
                ),
                "shoulder_angle_range_degrees": round(
                    shoulder_angle_range,
                    4,
                ),
            },
            "weight_transfer": {
                "hip_center_shift": round(hip_center_shift, 6),
                "hip_center_range": round(hip_center_range, 6),
            },
            "non_racket_arm_balance": {
                "maximum_arm_elevation": round(
                    maximum_non_racket_arm_elevation,
                    6,
                ),
                "elevated_sample_ratio": round(
                    elevated_sample_ratio,
                    6,
                ),
                "arm_path_length": round(
                    non_racket_arm_path_length,
                    6,
                ),
            },
            "swing_smoothness": {
                "wrist_path_length": round(
                    racket_wrist_path_length,
                    6,
                ),
                "mean_wrist_speed": round(mean_wrist_speed, 6),
                "wrist_speed_variation": (
                    None
                    if wrist_speed_variation is None
                    else round(wrist_speed_variation, 6)
                ),
                "wrist_low_speed_ratio": (
                    None
                    if wrist_low_speed_ratio is None
                    else round(wrist_low_speed_ratio, 6)
                ),
            },
            "limitations": [
                "Uses one-camera 2D MediaPipe landmarks.",
                "Designed for a high-clear teaching swing, not shuttle outcome analysis.",
                "L3 assessment still uses the configured racket side.",
                "Experimental racket-hand estimation is output for validation only.",
                "Shoulder projection ratio is only a proxy for sideways preparation.",
                "Hip-center displacement is only a proxy for weight transfer.",
                "Does not evaluate racket, shuttle, grip, contact point, trajectory, or landing position.",
            ],
        }
