"""Competency Profile V1。

整合既有 Footwork、Serve、Clear Analysis Report。
本層不重新評分、不改權重，也不產生新的綜合能力分數。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _read_overall_score(
    report: Mapping[str, Any],
) -> tuple[float | None, str | None]:
    """讀取不同 Motion Report 的既有 Overall Contract。"""

    summary = report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}

    # Serve / Clear contract
    summary_score = summary.get("overall_score")
    if (
        isinstance(summary_score, (int, float))
        and not isinstance(summary_score, bool)
    ):
        return float(summary_score), "summary.overall_score"

    # Footwork stable L3 contract
    result_summary = report.get("result_summary")
    result_summary = (
        result_summary
        if isinstance(result_summary, Mapping)
        else {}
    )
    overall = result_summary.get("overall")
    overall = overall if isinstance(overall, Mapping) else {}

    result_score = overall.get("score")
    if (
        isinstance(result_score, (int, float))
        and not isinstance(result_score, bool)
    ):
        return float(result_score), "result_summary.overall.score"

    return None, None


def _read_evaluation_status(
    report: Mapping[str, Any],
    overall_score: float | None,
) -> str | None:
    summary = report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}

    explicit_status = summary.get("evaluation_status")
    if isinstance(explicit_status, str):
        return explicit_status

    # Footwork report does not expose summary.evaluation_status.
    if overall_score is not None and summary.get("completed") is True:
        return "EVALUATED"

    return None


def _extract_motion(
    motion_type: str,
    report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        return {
            "motion_type": motion_type,
            "status": "MISSING",
            "overall_score": None,
            "score_source": None,
            "evaluation_status": None,
            "coach_status": None,
            "assessment_id": None,
            "report_version": None,
        }

    summary = report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}

    overall_score, score_source = _read_overall_score(report)
    evaluation_status = _read_evaluation_status(
        report,
        overall_score,
    )

    evaluated = (
        evaluation_status == "EVALUATED"
        and overall_score is not None
    )

    return {
        "motion_type": motion_type,
        "status": "AVAILABLE" if evaluated else "NOT_EVALUATED",
        "overall_score": (
            round(overall_score, 1)
            if evaluated and overall_score is not None
            else None
        ),
        "score_source": score_source,
        "evaluation_status": evaluation_status,
        "coach_status": summary.get("coach_status"),
        "assessment_id": report.get("assessment_id"),
        "report_version": report.get("report_version"),
    }


def build_competency_profile(
    *,
    player_id: str,
    footwork_report: Mapping[str, Any] | None = None,
    serve_report: Mapping[str, Any] | None = None,
    clear_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """建立三項測驗的 Competency Profile。

    V1 僅整合各 Motion Report 的既有 overall_score。
    不重新加權，也不計算跨動作總分。
    """

    motions = {
        "footwork": _extract_motion(
            "footwork",
            footwork_report,
        ),
        "serve": _extract_motion(
            "serve",
            serve_report,
        ),
        "clear": _extract_motion(
            "clear",
            clear_report,
        ),
    }

    available_count = sum(
        item["status"] == "AVAILABLE"
        for item in motions.values()
    )

    if available_count == len(motions):
        profile_status = "COMPLETE"
    elif available_count > 0:
        profile_status = "PARTIAL"
    else:
        profile_status = "NOT_AVAILABLE"

    return {
        "schema_version": "1.0",
        "profile_version": "competency-profile-v1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "player_id": player_id,
        "profile_status": profile_status,
        "available_motion_count": available_count,
        "expected_motion_count": len(motions),
        "motions": motions,
        "overall_score": None,
        "limitations": [
            "V1 directly reuses each motion report overall score.",
            "V1 does not calculate a cross-motion overall score.",
            "Scores are comparable only within the current provisional L3 calibration contracts.",
        ],
    }


def save_competency_profile(
    result: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            dict(result),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
