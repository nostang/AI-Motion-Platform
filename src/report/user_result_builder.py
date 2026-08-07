"""Build compact single-motion results for Web/App clients."""

from __future__ import annotations

from typing import Any, Mapping


LABELS: dict[str, dict[str, str]] = {
    "footwork": {
        "movement_completion": "移動完成度",
        "recovery_speed": "回位速度",
        "motion_quality": "動作流暢度",
        "body_stability": "身體穩定度",
    },
    "serve": {
        "preparation_stability": "準備穩定度",
        "swing_completeness": "揮拍完整度",
        "body_coordination": "身體協調度",
        "motion_smoothness": "動作流暢度",
    },
    "clear": {
        "sideways_preparation": "側身準備",
        "weight_transfer": "重心轉移",
        "non_racket_arm_balance": "非持拍手平衡",
        "swing_smoothness": "揮拍流暢度",
    },
}

ORDER: dict[str, tuple[str, ...]] = {
    "footwork": (
        "movement_completion",
        "recovery_speed",
        "motion_quality",
        "body_stability",
    ),
    "serve": (
        "preparation_stability",
        "swing_completeness",
        "body_coordination",
        "motion_smoothness",
    ),
    "clear": (
        "sideways_preparation",
        "weight_transfer",
        "non_racket_arm_balance",
        "swing_smoothness",
    ),
}


def build_user_result(report: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a full Analysis Report into a compact user-facing result."""

    motion_type = str(report.get("assessment_type") or "").strip().lower()
    if motion_type not in ORDER:
        raise ValueError(f"Unsupported assessment_type: {motion_type}")

    score = _overall_score(report)
    level = score_to_level(score)
    breakdown_source = _score_breakdown(report, motion_type)

    breakdown: list[dict[str, Any]] = []

    for key in ORDER[motion_type]:
        item = breakdown_source.get(key)
        if not isinstance(item, Mapping):
            continue

        score_value = item.get("score")
        max_score = item.get("max_score")
        if score_value is None or max_score is None:
            continue

        breakdown.append(
            {
                "key": key,
                "label": LABELS[motion_type].get(key, key),
                "score": float(score_value),
                "max_score": float(max_score),
            }
        )

    return {
        "assessment_id": report.get("assessment_id"),
        "motion_type": motion_type,
        "status": "READY",
        "score": float(score) if score is not None else None,
        "max_score": 100.0,
        "level": level,
        "breakdown": breakdown,
    }


def score_to_level(score: float | None) -> str | None:
    """Map a 0-100 score to the user-facing presentation level."""
    if score is None:
        return None
    if score >= 95:
        return "EXCELLENT"
    if score >= 90:
        return "WONDERFUL"
    if score >= 80:
        return "GREAT"
    if score >= 70:
        return "GOOD"
    if score >= 60:
        return "NICE"
    return "FAIR"


def _overall_score(report: Mapping[str, Any]) -> float | None:
    result_summary = report.get("result_summary")
    if isinstance(result_summary, Mapping):
        overall = result_summary.get("overall")
        if isinstance(overall, Mapping):
            value = overall.get("score")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)

    summary = report.get("summary")
    if isinstance(summary, Mapping):
        value = summary.get("overall_score")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)

    return None



def _score_breakdown(
    report: Mapping[str, Any],
    motion_type: str,
) -> Mapping[str, Any]:
    if motion_type == "footwork":
        result_summary = report.get("result_summary")
        if isinstance(result_summary, Mapping):
            value = result_summary.get("score_breakdown")
            if isinstance(value, Mapping):
                return value
        return {}

    value = report.get("score_breakdown")
    if isinstance(value, Mapping):
        return value

    return {}
