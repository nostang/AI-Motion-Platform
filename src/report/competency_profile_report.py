"""Competency Profile Report V1.1。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_MOTION_LABELS = {
    "footwork": "Footwork",
    "serve": "Serve",
    "clear": "High Clear",
}


def _available_motions(profile: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    motions = profile.get("motions")
    if not isinstance(motions, Mapping):
        return []

    result: list[tuple[str, Mapping[str, Any]]] = []
    for motion_type, item in motions.items():
        if not isinstance(item, Mapping) or item.get("status") != "AVAILABLE":
            continue
        score = item.get("overall_score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            continue
        result.append((str(motion_type), item))
    return result


def _motion_card(motion_type: str, item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "motion_type": motion_type,
        "label": _MOTION_LABELS.get(motion_type, motion_type.replace("_", " ").title()),
        "score": round(float(item["overall_score"]), 1),
        "coach_status": item.get("coach_status"),
    }


def _priority_sort_key(pair: tuple[str, Mapping[str, Any]]) -> tuple[int, float]:
    _, item = pair
    review_rank = 0 if item.get("coach_status") == "NEEDS_REVIEW" else 1
    return review_rank, float(item["overall_score"])


def build_competency_profile_report(profile: Mapping[str, Any]) -> dict[str, Any]:
    available = _available_motions(profile)
    score_descending = sorted(
        available,
        key=lambda pair: float(pair[1]["overall_score"]),
        reverse=True,
    )

    strengths = [
        _motion_card(motion_type, item)
        for motion_type, item in score_descending
        if float(item["overall_score"]) >= 80.0
        and item.get("coach_status") != "NEEDS_REVIEW"
    ]

    priority_candidates = [
        pair
        for pair in available
        if float(pair[1]["overall_score"]) < 80.0
        or pair[1].get("coach_status") == "NEEDS_REVIEW"
    ]
    priority_candidates.sort(key=_priority_sort_key)
    priorities = [_motion_card(motion_type, item) for motion_type, item in priority_candidates]

    radar_order = ["footwork", "serve", "clear"]
    motion_map = {motion_type: item for motion_type, item in available}
    radar_labels = [_MOTION_LABELS[motion_type] for motion_type in radar_order]
    radar_scores = [
        round(float(motion_map[motion_type]["overall_score"]), 1)
        if motion_type in motion_map else None
        for motion_type in radar_order
    ]

    strongest_motion = strengths[0] if strengths else (
        _motion_card(score_descending[0][0], score_descending[0][1])
        if score_descending else None
    )
    priority_motion = priorities[0] if priorities else None

    return {
        "schema_version": "1.0",
        "report_version": "competency-profile-report-v1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "player_id": profile.get("player_id"),
        "profile_status": profile.get("profile_status"),
        "available_motion_count": profile.get("available_motion_count", 0),
        "expected_motion_count": profile.get("expected_motion_count", 3),
        "summary": {
            "strongest_motion": strongest_motion,
            "priority_motion": priority_motion,
            "cross_motion_overall_score": None,
        },
        "strengths": strengths,
        "improvement_priorities": priorities,
        "radar_chart": {
            "labels": radar_labels,
            "scores": radar_scores,
            "max_score": 100,
        },
        "motions": profile.get("motions", {}),
        "limitations": [
            "This report directly uses scores from the Competency Profile.",
            "No cross-motion overall score is calculated.",
            "Strength and priority labels are descriptive dashboard helpers, not new assessments.",
        ],
    }


def save_competency_profile_report(result: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
