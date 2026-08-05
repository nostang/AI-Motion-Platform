"""Pipeline Validator 的穩定契約規則。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


SUPPORTED_ASSESSMENT_TYPE = "footwork"
VALID_COACH_STATUSES = {"PASS", "FAIL", "NEEDS_REVIEW", "NOT_EVALUATED"}
VALID_REVIEW_STATUSES = {"PENDING", "IN_REVIEW", "COMPLETED"}
VALID_RULE_RESULTS = {"PASS", "FAIL", "NEEDS_REVIEW", "NOT_EVALUATED"}

ASSESSMENT_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "schema_version": str,
    "assessment_id": str,
    "assessment_type": str,
    "engine_version": str,
    "config_version": str,
    "generated_at": str,
    "analysis_status": str,
    "test_completed": bool,
    "event_count": int,
    "expected_event_count": int,
    "events": list,
}

COACH_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "schema_version": str,
    "coach_engine_version": str,
    "generated_at": str,
    "assessment_id": str,
    "assessment_type": str,
    "engine_version": str,
    "config_version": str,
    "assessment_analysis_status": str,
    "test_completed": bool,
    "rules": list,
    "checklist_summary": dict,
    "overall_status": str,
    "expert_review_recommended": bool,
}

REPORT_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "assessment_id": str,
    "assessment_type": str,
    "report_version": str,
    "generated_at": str,
    "summary": dict,
    "observation": dict,
    "skill_score": dict,
    "feedback": list,
    "training_suggestions": list,
    "radar_chart": dict,
    "review": dict,
    "meta": dict,
}

REVIEW_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "schema_version": str,
    "assessment_id": str,
    "assessment_type": str,
    "engine_version": str,
    "config_version": str,
    "source_video": str,
    "review_status": str,
    "review_policy": dict,
    "events": list,
}

ASSESSMENT_EVENT_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "event_id": int,
    "direction": str,
    "completed": bool,
    "returned_to_center": bool,
}

COACH_RULE_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "rule_id": str,
    "name": str,
    "display_name": str,
    "result": str,
    "evidence": dict,
    "explanation": str,
    "limitations": list,
}

REVIEW_EVENT_REQUIRED_FIELDS: Mapping[str, type | tuple[type, ...]] = {
    "event_id": int,
    "system_result": dict,
    "review_form": dict,
}


def is_instance_of_expected(value: Any, expected: type | tuple[type, ...]) -> bool:
    """避免 bool 被 Python 當成 int 接受。"""

    if expected is int and isinstance(value, bool):
        return False
    if isinstance(expected, tuple) and int in expected and isinstance(value, bool):
        return bool in expected
    return isinstance(value, expected)


def expected_type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " | ".join(item.__name__ for item in expected)
    return expected.__name__


def unique_non_empty_strings(values: Sequence[Any]) -> bool:
    return (
        all(isinstance(value, str) and bool(value.strip()) for value in values)
        and len(set(values)) == len(values)
    )
