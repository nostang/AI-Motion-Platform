"""High Clear Teaching Assessment MVP。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


_LEVEL_SCORE = {
    "EXCELLENT": 25,
    "GOOD": 20,
    "FAIR": 14,
    "POOR": 7,
}


def _level_higher(
    value: float | None,
    thresholds: dict[str, float],
) -> str | None:
    if value is None:
        return None
    if value >= thresholds["excellent"]:
        return "EXCELLENT"
    if value >= thresholds["good"]:
        return "GOOD"
    if value >= thresholds["fair"]:
        return "FAIR"
    return "POOR"


def _level_lower(
    value: float | None,
    thresholds: dict[str, float],
) -> str | None:
    if value is None:
        return None
    if value <= thresholds["excellent"]:
        return "EXCELLENT"
    if value <= thresholds["good"]:
        return "GOOD"
    if value <= thresholds["fair"]:
        return "FAIR"
    return "POOR"


def _safe_score(level: str | None) -> int:
    return _LEVEL_SCORE.get(level, 0)


def _combine_levels(
    levels: list[str | None],
) -> tuple[int, str | None]:
    valid_levels = [level for level in levels if level is not None]
    if not valid_levels:
        return 0, None

    score = round(
        sum(_safe_score(level) for level in valid_levels)
        / len(valid_levels)
    )

    level_order = {
        "EXCELLENT": 4,
        "GOOD": 3,
        "FAIR": 2,
        "POOR": 1,
    }

    overall_level = min(
        valid_levels,
        key=lambda level: level_order[level],
    )

    return score, overall_level


class ClearAssessmentBuilder:
    def __init__(self, calibration: dict[str, Any]) -> None:
        self.calibration = calibration

    def build(
        self,
        *,
        video_id: str,
        source_video: str,
        total_frames: int,
        detected_frames: int,
        event: dict[str, Any],
        features: dict[str, Any],
    ) -> dict[str, Any]:
        detection_rate = (
            detected_frames / total_frames
            if total_frames
            else 0.0
        )

        enough_pose = (
            detection_rate
            >= self.calibration["minimum_pose_detection_rate"]
            and features.get("sample_count", 0)
            >= self.calibration["minimum_pose_samples"]
            and features.get("status") == "EXTRACTED"
        )

        metrics: dict[str, Any] = {}

        if enough_pose:
            thresholds = self.calibration["thresholds"]

            sideways = features.get("sideways_preparation", {})
            weight = features.get("weight_transfer", {})
            non_racket_arm = features.get("non_racket_arm_balance", {})
            swing = features.get("swing_smoothness", {})

            sideways_ratio_level = _level_lower(
                sideways.get("minimum_shoulder_hip_ratio"),
                thresholds["sideways_preparation"][
                    "minimum_shoulder_hip_ratio"
                ],
            )

            shoulder_angle_level = _level_higher(
                sideways.get("shoulder_angle_range_degrees"),
                thresholds["sideways_preparation"][
                    "shoulder_angle_range_degrees"
                ],
            )

            sideways_score, sideways_level = _combine_levels(
                [sideways_ratio_level, shoulder_angle_level]
            )

            weight_level = _level_higher(
                weight.get("hip_center_shift"),
                thresholds["weight_transfer"]["hip_center_shift"],
            )

            arm_elevation_level = _level_higher(
                non_racket_arm.get("maximum_arm_elevation"),
                thresholds["non_racket_arm_balance"][
                    "maximum_arm_elevation"
                ],
            )

            arm_duration_level = _level_higher(
                non_racket_arm.get("elevated_sample_ratio"),
                thresholds["non_racket_arm_balance"][
                    "elevated_sample_ratio"
                ],
            )

            arm_score, arm_level = _combine_levels(
                [arm_elevation_level, arm_duration_level]
            )

            wrist_path_level = _level_higher(
                swing.get("wrist_path_length"),
                thresholds["swing_smoothness"]["wrist_path_length"],
            )

            speed_variation_level = _level_lower(
                swing.get("wrist_speed_variation"),
                thresholds["swing_smoothness"][
                    "wrist_speed_variation"
                ],
            )

            swing_score, swing_level = _combine_levels(
                [wrist_path_level, speed_variation_level]
            )

            metrics = {
                "sideways_preparation": {
                    "score": sideways_score,
                    "max_score": 25,
                    "level": sideways_level,
                    "measurement_levels": {
                        "minimum_shoulder_hip_ratio":
                            sideways_ratio_level,
                        "shoulder_angle_range_degrees":
                            shoulder_angle_level,
                    },
                },
                "weight_transfer": {
                    "score": _safe_score(weight_level),
                    "max_score": 25,
                    "level": weight_level,
                    "measurement_levels": {
                        "hip_center_shift": weight_level,
                    },
                },
                "non_racket_arm_balance": {
                    "score": arm_score,
                    "max_score": 25,
                    "level": arm_level,
                    "measurement_levels": {
                        "maximum_arm_elevation":
                            arm_elevation_level,
                        "elevated_sample_ratio":
                            arm_duration_level,
                    },
                },
                "swing_smoothness": {
                    "score": swing_score,
                    "max_score": 25,
                    "level": swing_level,
                    "measurement_levels": {
                        "wrist_path_length": wrist_path_level,
                        "wrist_speed_variation":
                            speed_variation_level,
                    },
                },
            }

            overall_score = round(
                sum(metric["score"] for metric in metrics.values()),
                1,
            )
            test_completed = bool(event.get("completed"))
            evaluation_status = "EVALUATED"
        else:
            overall_score = None
            test_completed = False
            evaluation_status = "NOT_EVALUATED"

        return {
            "schema_version": "0.1",
            "assessment_id": f"ca_{uuid4().hex[:16]}",
            "assessment_type": "clear",
            "clear_type": "high_clear",
            "test_mode": "HIGH_CLEAR_TEACHING",
            "engine_version": "high-clear-mvp-v0.2",
            "config_version": self.calibration["config_version"],
            "calibration_status": self.calibration.get("status"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "video_id": video_id,
            "source_video": source_video,
            "analysis_status": "completed",
            "test_completed": test_completed,
            "evaluation_status": evaluation_status,
            "pose_detection": {
                "total_frames": total_frames,
                "detected_frames": detected_frames,
                "detection_rate": round(detection_rate, 4),
            },
            "event": event,
            "features": features,
            "metrics": metrics,
            "overall_score": overall_score,
            "system_confidence": round(
                min(1.0, detection_rate)
                * (1.0 if enough_pose else 0.5),
                4,
            ),
            "limitations": [
                "This MVP evaluates visible high-clear teaching motion using one-camera 2D MediaPipe landmarks.",
                "The result evaluates body-motion quality, not shuttle outcome.",
                "Sideways preparation and weight transfer use provisional 2D proxy measurements.",
                "Racket, shuttle, grip, contact point, trajectory, speed, and landing position are not evaluated.",
                "Thresholds are provisional and require multi-video and coach calibration.",
            ],
        }

    @staticmethod
    def save(
        result: dict[str, Any],
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
