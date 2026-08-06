"""Serve Assessment。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _level_lower(
    value: float | None,
    thresholds: dict[str, Any],
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


def _level_higher(
    value: float | None,
    thresholds: dict[str, Any],
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


class ServeAssessmentBuilder:
    def __init__(self, calibration: dict[str, Any]) -> None:
        self.calibration = calibration
        self.level_scores = calibration["level_scores"]

    def _safe_score(self, level: str | None) -> int:
        return int(self.level_scores.get(level, 0))

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

            preparation_level = _level_lower(
                features.get("preparation_stability_index"),
                thresholds["preparation_stability_index"],
            )
            path_level = _level_higher(
                features.get("swing_path_length"),
                thresholds["swing_path_length"],
            )
            extension_level = _level_higher(
                features.get("wrist_extension_range"),
                thresholds["wrist_extension_range"],
            )
            torso_level = _level_higher(
                features.get("torso_change_degrees"),
                thresholds["torso_change_degrees"],
            )
            smoothness_level = _level_lower(
                features.get("wrist_speed_variation"),
                thresholds["wrist_speed_variation"],
            )

            completeness_score = round(
                (
                    self._safe_score(path_level)
                    + self._safe_score(extension_level)
                )
                / 2
            )

            metrics = {
                "preparation_stability": {
                    "score": self._safe_score(preparation_level),
                    "max_score": 25,
                    "level": preparation_level,
                    "measurement_levels": {
                        "preparation_stability_index": preparation_level,
                    },
                },
                "swing_completeness": {
                    "score": completeness_score,
                    "max_score": 25,
                    "level": path_level,
                    "measurement_levels": {
                        "swing_path_length": path_level,
                        "wrist_extension_range": extension_level,
                    },
                },
                "body_coordination": {
                    "score": self._safe_score(torso_level),
                    "max_score": 25,
                    "level": torso_level,
                    "measurement_levels": {
                        "torso_change_degrees": torso_level,
                    },
                },
                "motion_smoothness": {
                    "score": self._safe_score(smoothness_level),
                    "max_score": 25,
                    "level": smoothness_level,
                    "measurement_levels": {
                        "wrist_speed_variation": smoothness_level,
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
            "schema_version": "0.2",
            "assessment_id": f"sa_{uuid4().hex[:16]}",
            "assessment_type": "serve",
            "serve_type": "forehand",
            "test_mode": "FOREHAND_SERVE_TEACHING",
            "engine_version": "forehand-serve-mvp-v0.3",
            "config_version": self.calibration["config_version"],
            "rubric_version": self.calibration["rubric_version"],
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
                "This version evaluates a visible forehand serve teaching motion using one-camera 2D MediaPipe landmarks.",
                "The result evaluates visible body-motion quality, not shuttle outcome or official service legality.",
                "Backhand serve technique, grip, finger action, racket face, shuttle trajectory, contact point, and service height are not evaluated.",
                "Thresholds and level scores are provisional and require multi-video and coach calibration."
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
