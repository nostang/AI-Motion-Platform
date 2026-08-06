"""Feature-based Coach feedback for calibrated Motion Features.

This module consumes qualitative Feature Levels already produced by the
Assessment layer. It never recalculates landmarks, angles, calibration, or
Body Stability scores.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


FEATURE_COACH_VERSION = "feature-coach-v1"

_FEATURE_CATALOG: dict[str, dict[str, Any]] = {
    "MF001_shoulder_tilt": {
        "coach_id": "CF001",
        "display_name": "肩線穩定度",
        "messages": {
            "EXCELLENT": "肩線控制穩定，移動與回位過程沒有明顯左右傾斜。",
            "GOOD": "肩線整體穩定，可繼續維持移動時的上半身控制。",
            "FAIR": "肩線有輕微傾斜，建議降低速度並練習保持雙肩平穩。",
            "POOR": "肩線傾斜較明顯，建議以低速米字步練習上半身穩定。",
        },
        "training": {
            "code": "T004",
            "title": "肩線控制練習",
            "description": "以低速完成米字步，目標是在移動與回位時保持雙肩平穩，再逐步增加速度。",
            "sets": 3,
            "repetitions_per_set": 8,
        },
    },
    "MF002_hip_tilt": {
        "coach_id": "CF002",
        "display_name": "髖線穩定度",
        "messages": {
            "EXCELLENT": "髖線控制穩定，重心轉移時骨盆沒有明顯左右傾斜。",
            "GOOD": "髖線整體穩定，可繼續維持骨盆與核心控制。",
            "FAIR": "髖線有輕微傾斜，建議注意骨盆穩定與左右重心轉移。",
            "POOR": "髖線左右傾斜較明顯，建議先降低移動速度並維持骨盆穩定。",
        },
        "training": {
            "code": "T005",
            "title": "骨盆穩定練習",
            "description": "進行低速側向與斜向移動，保持骨盆水平，避免重心過度偏向單側。",
            "sets": 3,
            "repetitions_per_set": 8,
        },
    },
    "MF003_torso_lean": {
        "coach_id": "CF003",
        "display_name": "軀幹傾斜控制",
        "messages": {
            "EXCELLENT": "軀幹傾斜控制良好，移動與回位時保持穩定。",
            "GOOD": "軀幹整體穩定，可繼續維持核心控制。",
            "FAIR": "軀幹有輕微傾斜，建議在跨步時維持核心穩定。",
            "POOR": "軀幹傾斜較明顯，建議縮小動作幅度並先建立穩定控制。",
        },
        "training": {
            "code": "T006",
            "title": "軀幹控制練習",
            "description": "以慢速完成跨步與回位，維持胸口朝向穩定，避免軀幹過度側傾。",
            "sets": 3,
            "repetitions_per_set": 8,
        },
    },
}


def build_feature_feedback(
    feature_levels: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Translate calibrated Feature Levels into explainable Coach feedback."""

    feedback: list[dict[str, Any]] = []
    for item in feature_levels:
        feature_id = str(item.get("feature_id", ""))
        catalog = _FEATURE_CATALOG.get(feature_id)
        if catalog is None:
            continue

        level = str(item.get("level", "NOT_EVALUATED")).upper()
        message = catalog["messages"].get(
            level,
            "此 Feature 尚無法產生教練說明。",
        )
        training = None
        if level in {"FAIR", "POOR"}:
            training = dict(catalog["training"])

        feedback.append(
            {
                "coach_id": catalog["coach_id"],
                "feature_id": feature_id,
                "display_name": catalog["display_name"],
                "level": level,
                "aggregate_value": item.get("aggregate_value"),
                "unit": item.get("unit"),
                "input_statistic": item.get("input_statistic"),
                "valid_event_count": item.get("valid_event_count"),
                "message": message,
                "training_suggestion": training,
                "source_metric_id": "AR004",
                "source_rule_id": "CR006",
                "feature_coach_version": FEATURE_COACH_VERSION,
                "provisional": bool(item.get("provisional", True)),
            }
        )

    return feedback
