"""Serve Assessment MVP。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _level_lower(value: float | None, thresholds: dict[str, float]) -> str | None:
    if value is None:
        return None
    if value <= thresholds["excellent"]:
        return "EXCELLENT"
    if value <= thresholds["good"]:
        return "GOOD"
    if value <= thresholds["fair"]:
        return "FAIR"
    return "POOR"


def _level_higher(value: float | None, thresholds: dict[str, float]) -> str | None:
    if value is None:
        return None
    if value >= thresholds["excellent"]:
        return "EXCELLENT"
    if value >= thresholds["good"]:
        return "GOOD"
    if value >= thresholds["fair"]:
        return "FAIR"
    return "POOR"


_LEVEL_SCORE = {"EXCELLENT": 25, "GOOD": 20, "FAIR": 14, "POOR": 7}


class ServeAssessmentBuilder:
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
        detection_rate = detected_frames / total_frames if total_frames else 0.0
        enough_pose = (
            detection_rate >= self.calibration["minimum_pose_detection_rate"]
            and features.get("sample_count", 0) >= self.calibration["minimum_pose_samples"]
            and features.get("status") == "EXTRACTED"
        )

        metrics: dict[str, Any] = {}
        if enough_pose:
            t = self.calibration["thresholds"]
            prep_level = _level_lower(features.get("preparation_stability_index"), t["preparation_stability_index"])
            path_level = _level_higher(features.get("swing_path_length"), t["swing_path_length"])
            extension_level = _level_higher(features.get("wrist_extension_range"), t["wrist_extension_range"])
            torso_level = _level_higher(features.get("torso_change_degrees"), t["torso_change_degrees"])
            smooth_level = _level_lower(features.get("wrist_speed_variation"), t["wrist_speed_variation"])
            completeness_score = round((_LEVEL_SCORE[path_level] + _LEVEL_SCORE[extension_level]) / 2)
            metrics = {
                "preparation_stability": {"score": _LEVEL_SCORE[prep_level], "max_score": 25, "level": prep_level},
                "swing_completeness": {"score": completeness_score, "max_score": 25, "level": path_level, "extension_level": extension_level},
                "body_coordination": {"score": _LEVEL_SCORE[torso_level], "max_score": 25, "level": torso_level},
                "motion_smoothness": {"score": _LEVEL_SCORE[smooth_level], "max_score": 25, "level": smooth_level},
            }
            overall_score = round(sum(m["score"] for m in metrics.values()) / 100 * 100, 1)
            test_completed = bool(event.get("completed"))
            status = "EVALUATED"
        else:
            overall_score = None
            test_completed = False
            status = "NOT_EVALUATED"

        return {
            "schema_version": "0.1",
            "assessment_id": f"sa_{uuid4().hex[:16]}",
            "assessment_type": "serve",
            "serve_type": "forehand",
            "test_mode": "FOREHAND_SERVE_TEACHING",
            "engine_version": "forehand-serve-mvp-v0.2",
            "config_version": self.calibration["config_version"],
            "calibration_status": self.calibration.get("status"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "video_id": video_id,
            "source_video": source_video,
            "analysis_status": "completed",
            "test_completed": test_completed,
            "evaluation_status": status,
            "pose_detection": {
                "total_frames": total_frames,
                "detected_frames": detected_frames,
                "detection_rate": round(detection_rate, 4),
            },
            "event": event,
            "features": features,
            "metrics": metrics,
            "overall_score": overall_score,
            "system_confidence": round(min(1.0, detection_rate) * (1.0 if enough_pose else 0.5), 4),
            "limitations": [
                "This MVP evaluates a forehand serve teaching motion using one-camera 2D MediaPipe landmarks.",
                "The result evaluates visible body-motion quality, not shuttle outcome or official service legality.",
                "Backhand serve technique, grip, finger action, racket face, shuttle trajectory, contact point, and service height are not evaluated.",
            ],
        }

    @staticmethod
    def save(result: dict[str, Any], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
