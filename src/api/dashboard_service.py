"""User Dashboard aggregation for AI Motion Platform.

This layer only summarizes persisted VIDEO_ANALYSES records.
It does not recompute motion scores or modify assessment results.
"""

from __future__ import annotations

from typing import Any


_REQUIRED_MOTIONS = {"footwork", "serve", "clear"}


def build_user_dashboard(
    *,
    user_id: int,
    analyses: list[dict[str, Any]],
) -> dict[str, Any]:
    completed = [
        item
        for item in analyses
        if (
            item.get("status") == "completed"
            and isinstance(item.get("overall_score"), (int, float))
            and not isinstance(item.get("overall_score"), bool)
        )
    ]

    latest = completed[0] if completed else None

    best = (
        max(
            completed,
            key=lambda item: float(item["overall_score"]),
        )
        if completed
        else None
    )

    average_score = (
        round(
            sum(float(item["overall_score"]) for item in completed)
            / len(completed),
            1,
        )
        if completed
        else None
    )

    latest_completed_by_motion: dict[str, dict[str, Any]] = {}
    for item in completed:
        motion_type = str(item.get("assessment_type", "")).strip().lower()
        if (
            motion_type in _REQUIRED_MOTIONS
            and motion_type not in latest_completed_by_motion
        ):
            latest_completed_by_motion[motion_type] = item

    competency_ready = (
        set(latest_completed_by_motion) == _REQUIRED_MOTIONS
    )

    return {
        "schema_version": "1.0",
        "dashboard_version": "user-dashboard-v1.0",
        "user_id": user_id,
        "summary": {
            "completed_analysis_count": len(completed),
            "average_score": average_score,
            "latest_motion": (
                latest.get("assessment_type")
                if latest is not None
                else None
            ),
            "latest_score": (
                latest.get("overall_score")
                if latest is not None
                else None
            ),
            "best_motion": (
                best.get("assessment_type")
                if best is not None
                else None
            ),
            "best_score": (
                best.get("overall_score")
                if best is not None
                else None
            ),
            "competency_ready": competency_ready,
        },
        "latest_by_motion": latest_completed_by_motion,
        "recent_analyses": analyses,
    }
