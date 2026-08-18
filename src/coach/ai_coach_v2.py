"""Deterministic, evidence-bound coaching presentation for one assessment.

AI Coach V2 translates stored Report and History Trend evidence. It does not
recalculate features, dimensions, or assessment scores.
"""

from __future__ import annotations

import json
from math import isfinite
from typing import Any, Mapping, Sequence


VERSION = "ai-coach-v2.0"

MOTION_METRICS: dict[str, tuple[str, ...]] = {
    "footwork": (
        "movement_completion",
        "recovery_speed",
        "direction_coverage",
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

METRIC_LABELS = {
    "movement_completion": "移動完成度",
    "recovery_speed": "回位速度",
    "direction_coverage": "方向覆蓋",
    "motion_quality": "動作流暢度",
    "body_stability": "身體穩定度",
    "preparation_stability": "準備姿勢穩定度",
    "swing_completeness": "揮拍完整性",
    "body_coordination": "身體協調",
    "motion_smoothness": "動作流暢度",
    "sideways_preparation": "側身準備",
    "weight_transfer": "重心轉移",
    "non_racket_arm_balance": "非持拍手平衡",
    "swing_smoothness": "揮拍流暢度",
}

RULE_METRICS = {
    "CR001": "movement_completion",
    "CR003": "direction_coverage",
    "CR005": "recovery_speed",
    "CR006": "body_stability",
    "CR007": "motion_quality",
}

DRILLS: dict[str, dict[str, Any]] = {
    "movement_completion": {
        "title": "完整移動練習",
        "instruction": "依序完成指定方向移動並回到準備位置，先求每次動作完整。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "recovery_speed": {
        "title": "回位節奏練習",
        "instruction": "以低強度米字步練習回到中心，保持每次回位節奏一致。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "direction_coverage": {
        "title": "方向覆蓋練習",
        "instruction": "依八個既有方向逐一低速移動並回到中心，確認沒有漏做方向。",
        "sets": 2,
        "repetitions_per_set": 8,
    },
    "motion_quality": {
        "title": "連續步法節奏",
        "instruction": "降低速度完成連續位移，保持動作節奏平順後再逐步加快。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "body_stability": {
        "title": "身體穩定米字步",
        "instruction": "以低速完成米字步，留意肩線、髖線與軀幹在移動時保持穩定。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "preparation_stability": {
        "title": "準備姿勢重複練習",
        "instruction": "每次先穩定完成準備姿勢，再接續完整發球動作。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "swing_completeness": {
        "title": "完整揮拍分解練習",
        "instruction": "放慢速度完成整段揮拍路徑，再逐步連接成連續動作。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "body_coordination": {
        "title": "身體協調分解練習",
        "instruction": "用慢速分解動作，讓軀幹變化與手臂動作保持連續。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "motion_smoothness": {
        "title": "發球節奏練習",
        "instruction": "降低速度連續完成發球動作，保持前後節奏一致。",
        "sets": 3,
        "repetitions_per_set": 8,
    },
    "sideways_preparation": {
        "title": "側身準備練習",
        "instruction": "先以慢速重複側身準備，再銜接完整高遠球揮拍。",
        "sets": 3,
        "repetitions_per_set": 6,
    },
    "weight_transfer": {
        "title": "重心轉移分解練習",
        "instruction": "放慢動作，分段確認準備到揮拍期間的重心轉移。",
        "sets": 3,
        "repetitions_per_set": 6,
    },
    "non_racket_arm_balance": {
        "title": "非持拍手平衡練習",
        "instruction": "以慢速完成動作，留意非持拍手在整段揮拍中的平衡。",
        "sets": 3,
        "repetitions_per_set": 6,
    },
    "swing_smoothness": {
        "title": "揮拍流暢度練習",
        "instruction": "降低速度連續完成揮拍，保持整段動作節奏平順。",
        "sets": 3,
        "repetitions_per_set": 6,
    },
}

UNSUPPORTED_CLAIM_TERMS = (
    "contact",
    "impact",
    "拍面",
    "擊球點",
    "球速",
    "落點",
    "正式 lv",
    "正式球員等級",
    "injury diagnosis",
    "傷害診斷",
)


def _score(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not isfinite(number):
        return None
    return number


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _motion_type(report: Mapping[str, Any]) -> str:
    return str(report.get("assessment_type") or "").strip().lower()


def _report_highlights(report: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = report.get("highlights")
    if isinstance(direct, Mapping):
        return direct
    return _mapping(_mapping(report.get("result_summary")).get("highlights"))


def _breakdown(report: Mapping[str, Any], motion_type: str) -> Mapping[str, Any]:
    if motion_type == "footwork":
        return _mapping(
            _mapping(report.get("result_summary")).get("score_breakdown")
        )
    return _mapping(report.get("score_breakdown"))


def _level_sources(report: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source_name in ("skill_score", "assessment_metrics", "score_breakdown"):
        source = _mapping(report.get(source_name))
        for metric, item in source.items():
            level = str(_mapping(item).get("level") or "").strip().upper()
            if level:
                result[str(metric)] = level
    return result


def _feedback_metrics(report: Mapping[str, Any]) -> set[str]:
    coach = _mapping(report.get("coach"))
    feedback = coach.get("feedback")
    if not isinstance(feedback, list):
        feedback = report.get("feedback")
    result: set[str] = set()
    for item in feedback if isinstance(feedback, list) else []:
        if not isinstance(item, Mapping):
            continue
        metric = str(item.get("metric") or "").strip()
        if metric:
            result.add(metric)
        rule_metric = RULE_METRICS.get(str(item.get("source_rule_id") or ""))
        if rule_metric:
            result.add(rule_metric)
    return result


def _dimensions(report: Mapping[str, Any], motion_type: str) -> dict[str, dict[str, Any]]:
    allowed = MOTION_METRICS[motion_type]
    breakdown = _breakdown(report, motion_type)
    levels = _level_sources(report)
    dimensions: dict[str, dict[str, Any]] = {}
    for metric in allowed:
        item = _mapping(breakdown.get(metric))
        score = _score(item.get("score"))
        maximum = _score(item.get("max_score"))
        status = str(item.get("status") or "EVALUATED").upper()
        if score is None or maximum is None or maximum <= 0 or status == "NOT_EVALUATED":
            continue
        dimensions[metric] = {
            "metric": metric,
            "label": METRIC_LABELS[metric],
            "score": score,
            "max_score": maximum,
            "ratio": score / maximum,
            "level": levels.get(metric) or str(item.get("level") or "").upper() or None,
        }
    return dimensions


def _highlight_metrics(highlights: Mapping[str, Any], key: str) -> list[str]:
    value = highlights.get(key)
    return [str(item) for item in value] if isinstance(value, list) else []


def _review_metrics(highlights: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    reviewed = highlights.get("review_required")
    for item in reviewed if isinstance(reviewed, list) else []:
        if not isinstance(item, Mapping):
            continue
        metric = RULE_METRICS.get(str(item.get("rule_id") or ""))
        if metric and metric not in result:
            result.append(metric)
    return result


def _select_metrics(
    report: Mapping[str, Any],
    motion_type: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dimensions = _dimensions(report, motion_type)
    highlights = _report_highlights(report)
    declared_priorities = _highlight_metrics(highlights, "improvement_priorities")
    reviewed_metrics = _review_metrics(highlights)
    priority_pool = declared_priorities + reviewed_metrics
    priority_pool.extend(
        metric
        for metric, item in dimensions.items()
        if item.get("level") in {"FAIR", "POOR", "NEEDS_REVIEW"}
        or item["ratio"] < 0.8
    )

    priority_rank = {metric: index for index, metric in enumerate(priority_pool)}
    priority_candidates = {
        metric
        for metric in priority_pool
        if metric in dimensions
    }
    priority_keys = sorted(
        priority_candidates,
        key=lambda metric: (
            0 if metric in declared_priorities else 1,
            dimensions[metric]["ratio"],
            priority_rank[metric],
        ),
    )[:2]

    declared_strengths = _highlight_metrics(highlights, "strengths")
    strength_pool = [
        metric
        for metric in declared_strengths
        if metric in dimensions
        and metric not in priority_keys
        and dimensions[metric].get("level") not in {"FAIR", "POOR", "NEEDS_REVIEW"}
    ]
    strength_pool.extend(
        metric
        for metric in dimensions
        if metric not in strength_pool
        and metric not in priority_keys
        and dimensions[metric]["ratio"] >= 0.8
        and dimensions[metric].get("level") not in {"FAIR", "POOR", "NEEDS_REVIEW"}
    )
    strength_keys = sorted(
        strength_pool,
        key=lambda metric: (-dimensions[metric]["ratio"], MOTION_METRICS[motion_type].index(metric)),
    )[:2]

    feedback_metrics = _feedback_metrics(report)

    def presentation(metric: str, kind: str) -> dict[str, Any]:
        item = dimensions[metric]
        evidence_sources = ["score_breakdown"]
        if kind == "strength" and metric in declared_strengths:
            evidence_sources.append("highlights.strengths")
        if kind == "priority" and metric in declared_priorities:
            evidence_sources.append("highlights.improvement_priorities")
        if kind == "priority" and metric in reviewed_metrics:
            evidence_sources.append("highlights.review_required")
        if metric in feedback_metrics:
            evidence_sources.append("coach.feedback")
        return {
            "metric": metric,
            "label": item["label"],
            "score": item["score"],
            "max_score": item["max_score"],
            "level": item["level"],
            "message": (
                f"{item['label']}是本次相對穩定的項目。"
                if kind == "strength"
                else f"{item['label']}是目前較值得優先練習的項目。"
            ),
            "evidence_sources": evidence_sources,
        }

    return (
        [presentation(metric, "strength") for metric in strength_keys],
        [presentation(metric, "priority") for metric in priority_keys],
    )


def _training_plan(priorities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for item in priorities[:3]:
        metric = str(item.get("metric") or "")
        drill = DRILLS.get(metric)
        if drill is None:
            continue
        plan.append(
            {
                "drill_id": f"coach-v2-{metric}",
                "title": drill["title"],
                "instruction": drill["instruction"],
                "sets": drill["sets"],
                "repetitions_per_set": drill["repetitions_per_set"],
                "focus_metric": metric,
                "focus_label": METRIC_LABELS[metric],
                "tracking_status": "SUGGESTED_ONLY",
            }
        )
    return plan


def build_recent_trend(history_series: Mapping[str, Any] | None) -> dict[str, Any]:
    points = history_series.get("points") if isinstance(history_series, Mapping) else []
    points = points if isinstance(points, list) else []
    valid_scores = [
        score
        for item in points if isinstance(item, Mapping)
        if (score := _score(item.get("overall_score"))) is not None
    ]
    if len(valid_scores) < 3:
        return {
            "status": "INSUFFICIENT_DATA",
            "sample_count": len(valid_scores),
            "window_size": min(3, len(valid_scores)),
            "scores": valid_scores[-3:],
            "score_change": None,
            "message": "近期測驗資料不足，完成至少 3 次後再觀察整體變化。",
        }

    recent = valid_scores[-3:]
    change = round(recent[-1] - recent[0], 1)
    if change >= 3.0:
        status = "UPWARD"
        message = "近期整體呈上升趨勢。"
    elif change <= -3.0:
        status = "DOWNWARD"
        message = "近期分數有下降，建議重新確認主要弱項。"
    else:
        status = "STABLE"
        message = "近期整體較穩定。"
    return {
        "status": status,
        "sample_count": len(valid_scores),
        "window_size": 3,
        "scores": recent,
        "score_change": change,
        "message": message,
    }


def _assert_supported_claims(result: Mapping[str, Any]) -> None:
    rendered = json.dumps(result, ensure_ascii=False).lower()
    found = [term for term in UNSUPPORTED_CLAIM_TERMS if term.lower() in rendered]
    if found:
        raise ValueError(f"Unsupported AI Coach V2 claim: {', '.join(found)}")


def build_ai_coach_v2(
    report: Mapping[str, Any],
    history_series: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build five user-facing blocks from stored evidence only."""

    motion_type = _motion_type(report)
    if motion_type not in MOTION_METRICS:
        raise ValueError(f"Unsupported assessment_type: {motion_type}")

    summary = _mapping(report.get("summary"))
    evaluated = (
        summary.get("completed") is True
        and str(summary.get("evaluation_status") or "").upper() == "EVALUATED"
        and _score(summary.get("overall_score")) is not None
    )
    recent_trend = build_recent_trend(history_series)
    if not evaluated:
        result = {
            "status": "NOT_READY",
            "version": VERSION,
            "assessment_id": report.get("assessment_id"),
            "motion_type": motion_type,
            "strengths": [],
            "priorities": [],
            "training_plan": [],
            "next_focus": None,
            "recent_trend": recent_trend,
        }
        _assert_supported_claims(result)
        return result

    strengths, priorities = _select_metrics(report, motion_type)
    next_focus = None
    if priorities:
        priority = priorities[0]
        next_focus = {
            "metric": priority["metric"],
            "label": priority["label"],
            "message": f"下次測驗優先觀察{priority['label']}是否更穩定。",
        }

    result = {
        "status": "READY",
        "version": VERSION,
        "assessment_id": report.get("assessment_id"),
        "motion_type": motion_type,
        "assessment_confidence": _score(summary.get("system_confidence")),
        "strengths": strengths,
        "priorities": priorities,
        "training_plan": _training_plan(priorities),
        "next_focus": next_focus,
        "recent_trend": recent_trend,
    }
    _assert_supported_claims(result)
    return result
