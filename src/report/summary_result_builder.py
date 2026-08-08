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

    # Player Context V1:
    # racket_hand comes from the latest Clear report's experimental
    # video-level estimator. It is presentation context only and does
    # not participate in scoring or progress comparison.
    player_context = {
        "racket_hand": {
            "status": "NOT_AVAILABLE",
            "estimated": "unknown",
            "confidence": 0.0,
            "source_motion": "clear",
        }
    }

    clear_item = latest.get("clear")
    if isinstance(clear_item, Mapping):
        clear_report = clear_item.get("report")
        if isinstance(clear_report, Mapping):
            features = clear_report.get("features")
            if isinstance(features, Mapping):
                racket_hand = features.get("racket_hand")
                if isinstance(racket_hand, Mapping):
                    estimated = str(
                        racket_hand.get("estimated") or "unknown"
                    ).lower()
                    if estimated not in {"left", "right"}:
                        estimated = "unknown"

                    player_context["racket_hand"] = {
                        "status": racket_hand.get(
                            "status",
                            "NOT_AVAILABLE",
                        ),
                        "estimated": estimated,
                        "confidence": float(
                            racket_hand.get("confidence") or 0.0
                        ),
                        "source_motion": "clear",
                    }

    return {
        "status": status,
        "player_context": player_context,
        "motions": motions,
        "radar_chart": {
            "labels": radar_labels,
            "scores": radar_scores,
            "max_score": 100.0,
        },
        "missing_motions": missing,
    }
