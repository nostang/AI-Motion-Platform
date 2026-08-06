"""Serve MVP Report。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_serve_report(assessment: dict[str, Any], coach: dict[str, Any]) -> dict[str, Any]:
    metrics = assessment.get("metrics") or {}
    ordered = ["preparation_stability", "swing_completeness", "body_coordination", "motion_smoothness"]
    scores = [metrics.get(key, {}).get("score") for key in ordered]
    evaluated = [(key, metrics[key]) for key in ordered if key in metrics]
    strengths = [key for key, item in evaluated if item.get("score", 0) >= 20]
    improvements = [key for key, item in evaluated if item.get("score", 25) < 20]

    return {
        "report_version": "serve-report-v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assessment_id": assessment["assessment_id"],
        "assessment_type": "serve",
        "serve_type": assessment.get("serve_type", "forehand"),
        "video_id": assessment.get("video_id"),
        "summary": {
            "completed": assessment.get("test_completed", False),
            "evaluation_status": assessment.get("evaluation_status"),
            "overall_score": assessment.get("overall_score"),
            "system_confidence": assessment.get("system_confidence"),
            "coach_status": coach.get("overall_status"),
        },
        "score_breakdown": metrics,
        "highlights": {"strengths": strengths, "improvement_priorities": improvements},
        "coach": {"overall_message": coach.get("overall_message"), "feedback": coach.get("feedback", [])},
        "radar_chart": {
            "labels": ["Preparation Stability", "Swing Completeness", "Body Coordination", "Motion Smoothness"],
            "scores": scores,
            "max_score": 25,
        },
        "features": assessment.get("features"),
        "limitations": assessment.get("limitations", []),
        "meta": {
            "engine_version": assessment.get("engine_version"),
            "config_version": assessment.get("config_version"),
            "calibration_status": assessment.get("calibration_status"),
        },
    }


def save_serve_report(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
