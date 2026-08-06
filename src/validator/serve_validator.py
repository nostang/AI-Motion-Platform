"""Serve MVP JSON 契約驗證。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_serve_pipeline(
    assessment: dict[str, Any], coach: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if assessment.get("assessment_type") != "serve":
        errors.append("ASSESSMENT_TYPE_NOT_SERVE")
    if assessment.get("serve_type") != "forehand":
        errors.append("SERVE_TYPE_NOT_FOREHAND")
    if coach.get("assessment_id") != assessment.get("assessment_id"):
        errors.append("COACH_ASSESSMENT_ID_MISMATCH")
    if report.get("assessment_id") != assessment.get("assessment_id"):
        errors.append("REPORT_ASSESSMENT_ID_MISMATCH")
    if assessment.get("evaluation_status") != "EVALUATED":
        warnings.append("SERVE_NOT_EVALUATED")
    return {
        "validator_version": "serve-validator-v0.1",
        "status": "PASS" if not errors else "FAIL",
        "summary": {"error_count": len(errors), "warning_count": len(warnings)},
        "errors": errors,
        "warnings": warnings,
    }


def save_serve_validation(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
