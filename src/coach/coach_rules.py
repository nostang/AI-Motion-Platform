"""Coach Module V1 規則庫。

本模組只使用 Footwork Assessment JSON 已存在的客觀資料，
不重新計算 Pose、Measurement、Event 或方向分類。
"""

from __future__ import annotations

from typing import Any, Literal


RuleResult = Literal["PASS", "FAIL", "NEEDS_REVIEW", "NOT_EVALUATED"]

RULE_COUNT = 4


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
    """CR002：檢查每個納入測驗的 Event 是否返回中心。"""

    events = assessment.get("events") or []
    expected_count = int(assessment.get("expected_event_count", 8))
    detected_count = int(assessment.get("event_count", len(events)))
    returned_count = sum(
        bool(event.get("returned_to_center")) for event in events
    )

    passed = (
        detected_count == expected_count
        and returned_count == expected_count
    )

    return build_rule(
        rule_id="CR002",
        name="RETURN_TO_CENTER_COMPLETION",
        display_name="回中心完成",
        result="PASS" if passed else "FAIL",
        evidence={
            "returned_to_center_count": returned_count,
            "expected_event_count": expected_count,
            "all_events_returned_to_center": bool(
                assessment.get("all_events_returned_to_center", False)
            ),
        },
        explanation=(
            "每次移動後皆有返回中心。"
            if passed
            else "至少有一次動作未完成返回中心。"
        ),
    )


def evaluate_direction_coverage(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """CR003：檢查系統辨識結果是否完整覆蓋八方向。"""

    coverage_complete = bool(
        assessment.get("direction_coverage_complete", False)
    )

    return build_rule(
        rule_id="CR003",
        name="DIRECTION_COVERAGE",
        display_name="八方向覆蓋",
        result="PASS" if coverage_complete else "NEEDS_REVIEW",
        evidence={
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
        },
        explanation=(
            "系統辨識到八個方向各一次。"
            if coverage_complete
            else "目前系統方向分類未完整覆蓋八方向，需由人工標註確認。"
        ),
        limitations=[
            "方向分類仍需 Expert Review 與 Calibration 驗證。",
            "NEEDS_REVIEW 不等同於使用者動作錯誤。",
        ],
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


COACH_RULES = (
    evaluate_eight_event_completion,
    evaluate_return_to_center,
    evaluate_direction_coverage,
    evaluate_motion_continuity,
)
