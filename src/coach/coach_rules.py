"""Coach Module V1 規則庫。

本模組只使用 Footwork Assessment JSON 已存在的客觀資料，
不重新計算 Pose、Measurement、Event 或方向分類。
"""

from __future__ import annotations

from typing import Any, Literal


RuleResult = Literal["PASS", "FAIL", "NEEDS_REVIEW", "NOT_EVALUATED"]

RULE_COUNT = 7


def build_rule(
    *,
    rule_id: str,
    name: str,
    display_name: str,
    result: RuleResult,
    evidence: dict[str, Any],
    explanation: str,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    """建立固定格式、可追溯的 Coach Rule 結果。"""

    return {
        "rule_id": rule_id,
        "name": name,
        "display_name": display_name,
        "result": result,
        "evidence": evidence,
        "explanation": explanation,
        "limitations": limitations or [],
    }


def evaluate_eight_event_completion(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR001：檢查是否剛好完成預期數量的 Event。"""

    events = assessment.get("events") or []
    expected_count = int(assessment.get("expected_event_count", 8))
    detected_count = int(assessment.get("event_count", len(events)))
    completed_count = sum(bool(event.get("completed")) for event in events)

    passed = (
        detected_count == expected_count
        and completed_count == expected_count
    )

    return build_rule(
        rule_id="CR001",
        name="EIGHT_EVENT_COMPLETION",
        display_name="八次動作完成",
        result="PASS" if passed else "FAIL",
        evidence={
            "detected_event_count": detected_count,
            "completed_event_count": completed_count,
            "expected_event_count": expected_count,
        },
        explanation=(
            "已剛好完成八次有效動作。"
            if passed
            else "本次偵測到的完整動作次數不是八次。"
        ),
    )


def evaluate_return_to_center(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR002：區分嚴格回中心、Base Zone 與未完成。"""

    events = assessment.get("events") or []
    expected_count = int(
        assessment.get("expected_event_count", 8)
    )
    detected_count = int(
        assessment.get("event_count", len(events))
    )

    strict_center_count = sum(
        bool(event.get("returned_to_center"))
        or event.get("completion_reason")
        == "STRICT_CENTER"
        for event in events
    )

    base_zone_count = sum(
        event.get("completion_reason")
        == "BASE_ZONE"
        for event in events
    )

    completed_return_count = (
        strict_center_count + base_zone_count
    )

    incomplete_event_count = max(
        0,
        detected_count - completed_return_count,
    )

    if (
        detected_count != expected_count
        or incomplete_event_count > 0
    ):
        result: RuleResult = "FAIL"
        explanation = (
            "至少有一次動作未完成返回中心或基準區。"
        )
    elif strict_center_count == expected_count:
        result = "PASS"
        explanation = "每次移動後皆有返回原始中心。"
    else:
        result = "NEEDS_REVIEW"
        explanation = (
            f"{strict_center_count} 次回到原始中心，"
            f"{base_zone_count} 次回到基準區後轉向；"
            "測驗流程已完成，但回位精準度需人工複核。"
        )

    return build_rule(
        rule_id="CR002",
        name="RETURN_TO_CENTER_COMPLETION",
        display_name="回中心完成",
        result=result,
        evidence={
            "strict_center_count": strict_center_count,
            "base_zone_count": base_zone_count,
            "completed_return_count": (
                completed_return_count
            ),
            "incomplete_event_count": (
                incomplete_event_count
            ),
            "expected_event_count": expected_count,
            "all_events_returned_to_center": bool(
                assessment.get(
                    "all_events_returned_to_center",
                    False,
                )
            ),
        },
        explanation=explanation,
        limitations=[
            (
                "BASE_ZONE 表示回到基準區後直接轉向"
                "下一次移動，不等同精準回到原始中心。"
            ),
            (
                "Base Zone 門檻目前仍為暫定值，"
                "需要更多影片與人工標註驗證。"
            ),
        ],
    )


def evaluate_direction_coverage(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR003：轉譯 Assessment AR003 方向覆蓋評估。"""

    metric = assessment.get("direction_coverage_assessment") or {}
    coverage_complete = bool(
        assessment.get("direction_coverage_complete", False)
    )
    result: RuleResult = metric.get(
        "result",
        "PASS" if coverage_complete else "NEEDS_REVIEW",
    )

    return build_rule(
        rule_id="CR003",
        name="DIRECTION_COVERAGE",
        display_name="八方向覆蓋",
        result=result,
        evidence={
            "assessment_metric_id": metric.get("metric_id", "AR003"),
            "score": metric.get("score"),
            "max_score": metric.get("max_score", 25),
            "observed_direction_count": metric.get(
                "observed_direction_count"
            ),
            "expected_direction_count": metric.get(
                "expected_direction_count", 8
            ),
            "coverage_ratio": metric.get("coverage_ratio"),
            "direction_coverage": assessment.get("direction_coverage", {}),
            "missing_directions": list(
                assessment.get("missing_directions") or []
            ),
            "duplicate_directions": dict(
                assessment.get("duplicate_directions") or {}
            ),
            "unknown_direction_count": int(
                assessment.get("unknown_direction_count", 0)
            ),
            "system_confidence": assessment.get("system_confidence"),
            "config_version": metric.get("config_version"),
        },
        explanation=metric.get(
            "explanation",
            "系統方向分類未完整覆蓋八方向，需人工確認。",
        ),
        limitations=list(metric.get("limitations") or [
            "方向分類仍需 Expert Review 與 Calibration 驗證。",
            "NEEDS_REVIEW 不等同於使用者動作錯誤。",
        ]),
    )


def evaluate_motion_continuity(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR004：依現有 Event 完整性與 Pose 偵測率判斷流程連續性。"""

    events = assessment.get("events") or []
    detected_count = int(assessment.get("event_count", len(events)))
    completed_count = sum(bool(event.get("completed")) for event in events)
    pose_detection = assessment.get("pose_detection") or {}
    detection_rate = float(pose_detection.get("detection_rate", 0.0))
    event_count_valid = bool(assessment.get("event_count_valid", False))
    all_completed = completed_count == detected_count and detected_count > 0

    if detection_rate < 0.9:
        result: RuleResult = "NEEDS_REVIEW"
        explanation = "Pose 偵測率不足，無法可靠確認完整連續性。"
    elif not event_count_valid or not all_completed:
        result = "FAIL"
        explanation = "動作次數或 Event 完整性不符合測驗流程。"
    else:
        result = "PASS"
        explanation = "八次 Event 均完整結束，且未以速度作為通過條件。"

    return build_rule(
        rule_id="CR004",
        name="MOTION_CONTINUITY",
        display_name="動作流程連續性",
        result=result,
        evidence={
            "event_count_valid": event_count_valid,
            "completed_event_count": completed_count,
            "detected_event_count": detected_count,
            "pose_detection_rate": detection_rate,
            "analysis_failure_reasons": list(
                assessment.get("failure_reasons") or []
            ),
        },
        explanation=explanation,
        limitations=[
            "V1 尚未評估停頓時長、碎步、啟動步與腳部時序。",
            "時間資料僅保存，不用於 V1 通過或失敗判斷。",
        ],
    )


def evaluate_recovery_speed(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR005：轉譯 Assessment 已完成的 Recovery Speed 評估。"""

    recovery = assessment.get("recovery_speed") or {}
    status = recovery.get("status")
    result = recovery.get("result", "NOT_EVALUATED")

    if status != "EVALUATED":
        result = "NOT_EVALUATED"

    return build_rule(
        rule_id="CR005",
        name="RECOVERY_SPEED",
        display_name="回位速度",
        result=result,
        evidence={
            "assessment_metric_id": recovery.get("metric_id", "AR002"),
            "valid_event_count": recovery.get("valid_event_count", 0),
            "required_event_count": recovery.get("required_event_count"),
            "average_seconds": recovery.get("average_seconds"),
            "median_seconds": recovery.get("median_seconds"),
            "fastest_seconds": recovery.get("fastest_seconds"),
            "slowest_seconds": recovery.get("slowest_seconds"),
            "score": recovery.get("score"),
            "max_score": recovery.get("max_score", 25),
            "config_version": recovery.get("config_version"),
            "thresholds": recovery.get("thresholds", {}),
        },
        explanation=recovery.get(
            "explanation",
            "Recovery Speed 尚未完成評估。",
        ),
        limitations=list(recovery.get("limitations") or []),
    )


def evaluate_body_stability(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR006：轉譯 Assessment AR004 身體穩定度評估。"""

    metric = assessment.get("body_stability") or {}
    status = metric.get("status")
    result: RuleResult = metric.get("result", "NOT_EVALUATED")
    if status != "EVALUATED":
        result = "NOT_EVALUATED"

    return build_rule(
        rule_id="CR006",
        name="BODY_STABILITY",
        display_name="身體穩定度",
        result=result,
        evidence={
            "assessment_metric_id": metric.get("metric_id", "AR004"),
            "level": metric.get("level"),
            "score": metric.get("score"),
            "max_score": metric.get("max_score", 25),
            "weighted_level_points": metric.get("weighted_level_points"),
            "feature_levels": list(metric.get("feature_levels") or []),
            "config_version": metric.get("config_version"),
            "calibration_version": metric.get("calibration_version"),
            "calibration_status": metric.get("calibration_status"),
        },
        explanation=metric.get(
            "explanation",
            "Body Stability 尚未完成評估。",
        ),
        limitations=list(metric.get("limitations") or []),
    )


def evaluate_motion_quality(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR007：轉譯 Assessment AR005 動作品質評估。"""

    metric = assessment.get("motion_quality") or {}
    status = metric.get("status")
    result: RuleResult = metric.get("result", "NOT_EVALUATED")
    if status != "EVALUATED":
        result = "NOT_EVALUATED"

    return build_rule(
        rule_id="CR007",
        name="MOTION_QUALITY",
        display_name="動作品質",
        result=result,
        evidence={
            "assessment_metric_id": metric.get("metric_id", "AR005"),
            "level": metric.get("level"),
            "score": metric.get("score"),
            "max_score": metric.get("max_score", 25),
            "feature_id": metric.get("feature_id"),
            "input_statistic": metric.get("input_statistic"),
            "aggregate_value": metric.get("aggregate_value"),
            "valid_event_count": metric.get("valid_event_count"),
            "required_event_count": metric.get("required_event_count"),
            "config_version": metric.get("config_version"),
            "calibration_version": metric.get("calibration_version"),
            "calibration_status": metric.get("calibration_status"),
        },
        explanation=metric.get(
            "explanation",
            "Motion Quality 尚未完成評估。",
        ),
        limitations=list(metric.get("limitations") or []),
    )


COACH_RULES = (
    evaluate_eight_event_completion,
    evaluate_return_to_center,
    evaluate_direction_coverage,
    evaluate_motion_continuity,
    evaluate_recovery_speed,
    evaluate_body_stability,
    evaluate_motion_quality,
)
