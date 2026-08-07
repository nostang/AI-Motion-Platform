"""Build compact competency summary results for Web/App clients.

This module does not re-score motion assessments.
It reshapes the latest single-motion results into a stable summary contract.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.report.user_result_builder import build_user_result


MOTION_LABELS = {
    "footwork": "步法",
    "serve": "發球",
    "clear": "高遠球",
}

MOTION_ORDER = ("footwork", "serve", "clear")


def build_summary_result(
    latest: Mapping[str, Mapping[str, Any]],
    progress: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a compact summary from latest repository motion records."""

    motions: list[dict[str, Any]] = []
    radar_labels: list[str] = []
    radar_scores: list[float] = []

    for motion_type in MOTION_ORDER:
        item = latest.get(motion_type)
        if not isinstance(item, Mapping):
            continue

        report = item.get("report")
        if not isinstance(report, Mapping):
            continue

        public_report = dict(report)
        public_report["assessment_id"] = item.get(
            "assessment_id",
            public_report.get("assessment_id"),
        )

        result = build_user_result(public_report)
        score = result.get("score")

        motion_item = {
            "assessment_id": result.get("assessment_id"),
            "motion_type": motion_type,
            "label": MOTION_LABELS[motion_type],
            "score": score,
            "max_score": result.get("max_score", 100.0),
            "level": result.get("level"),
        }

        if progress is not None:
            motion_item["progress"] = dict(
                progress.get(
                    motion_type,
                    {
                        "status": "NOT_READY",
                        "previous_score": None,
                        "change": None,
                        "direction": None,
                    },
                )
            )

        motions.append(motion_item)

        if score is not None:
            radar_labels.append(MOTION_LABELS[motion_type])
            radar_scores.append(float(score))

    missing = [
        motion_type
        for motion_type in MOTION_ORDER
        if motion_type not in latest
    ]

    status = "READY" if not missing and len(motions) == len(MOTION_ORDER) else "INCOMPLETE"

    return {
        "status": status,
        "motions": motions,
        "radar_chart": {
            "labels": radar_labels,
            "scores": radar_scores,
            "max_score": 100.0,
        },
        "missing_motions": missing,
    }
