"""Presentation-only overall-score history for the Summary page."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Sequence


VERSION = "history-trend-v1.1"
MOTION_ORDER = ("footwork", "serve", "clear")


def _score(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    score = float(value)
    if not isfinite(score) or not 0.0 <= score <= 100.0:
        return None
    return score


def _report_score(report: Any) -> float | None:
    if not isinstance(report, Mapping):
        return None

    summary = report.get("summary")
    if isinstance(summary, Mapping):
        if summary.get("completed") is False:
            return None
        if str(summary.get("evaluation_status") or "").upper() == "NOT_EVALUATED":
            return None
        score = _score(summary.get("overall_score"))
        if score is not None:
            return score

    result_summary = report.get("result_summary")
    if isinstance(result_summary, Mapping):
        overall = result_summary.get("overall")
        if isinstance(overall, Mapping):
            if str(overall.get("status") or "").upper() == "NOT_EVALUATED":
                return None
            return _score(overall.get("score"))
    return None


def _timestamp(value: Any) -> tuple[str, float] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return text, parsed.timestamp()


def _series(
    motion_type: str,
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sortable: list[tuple[float, str, dict[str, Any]]] = []
    for item in history:
        if not isinstance(item, Mapping):
            continue
        status = item.get("status")
        if status is not None and str(status).lower() != "completed":
            continue
        item_motion = str(
            item.get("motion_type") or item.get("assessment_type") or ""
        ).strip().lower()
        if item_motion != motion_type:
            continue
        assessment_id = str(item.get("assessment_id") or "").strip()
        score = _score(item.get("overall_score"))
        report_score = _report_score(item.get("report"))
        created = _timestamp(item.get("created_at"))
        completed = _timestamp(item.get("completed_at"))
        effective = completed or created
        if (
            not assessment_id
            or score is None
            or report_score is None
            or effective is None
        ):
            continue
        point = {
            "assessment_id": assessment_id,
            "motion_type": motion_type,
            "overall_score": score,
            "completed_at": completed[0] if completed is not None else None,
            "created_at": created[0] if created is not None else None,
        }
        sortable.append((effective[1], assessment_id, point))

    sortable.sort(key=lambda entry: (entry[0], entry[1]))
    points = [entry[2] for entry in sortable[-10:]]
    return {
        "motion_type": motion_type,
        "status": "READY" if len(points) >= 2 else "INSUFFICIENT_DATA",
        "point_count": len(points),
        "points": points,
    }


def build_history_trend(
    user_id: int,
    histories: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Build a safe additive contract without recalculating any scores."""

    return {
        "status": "READY",
        "version": VERSION,
        "user_id": user_id,
        "motions": [
            _series(motion_type, histories.get(motion_type, []))
            for motion_type in MOTION_ORDER
        ],
    }
