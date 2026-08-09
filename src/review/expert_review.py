"""建立給 Web 審查頁使用的 Expert Review Package。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DIRECTION_OPTIONS = [
    "RIGHT_FRONT",
    "LEFT_FRONT",
    "RIGHT_BACK",
    "LEFT_BACK",
    "RIGHT",
    "LEFT",
    "FRONT",
    "BACK",
    "UNKNOWN",
]


def build_expert_review_package(
    assessment: dict[str, Any],
    *,
    minimum_reviewers: int,
    consensus_votes_required: int,
) -> dict[str, Any]:
    events = []
    for event in assessment.get("events", []):
        events.append(
            {
                "event_id": event["event_id"],
                "clip_start_ms": event.get("clip_start_ms"),
                "clip_end_ms": event.get("clip_end_ms"),
                "reach_at_ms": event.get("reach_at_ms"),
                "system_result": {
                    "direction": event.get("direction", "UNKNOWN"),
                    "classification_confidence": event.get(
                        "classification_confidence"
                    ),
                    "boundary_ambiguous": event.get(
                        "boundary_ambiguous",
                        False,
                    ),
                    "returned_to_center": event.get(
                        "returned_to_center", False
                    ),
                    "completed": event.get("completed", False),
                },
                "review_form": {
                    "actual_direction": None,
                    "returned_to_center": None,
                    "motion_continuous": None,
                    "cannot_judge": False,
                    "comment": "",
                },
            }
        )

    return {
        "schema_version": "1.0",
        "assessment_id": assessment["assessment_id"],
        "assessment_type": assessment["assessment_type"],
        "engine_version": assessment["engine_version"],
        "config_version": assessment["config_version"],
        "source_video": assessment["source_video"],
        "review_status": "PENDING",
        "review_policy": {
            "minimum_reviewers": minimum_reviewers,
            "consensus_votes_required": consensus_votes_required,
            "direction_options": DIRECTION_OPTIONS,
            "note": (
                "審查者只提供人工標註，不直接修改 Calibration 參數。"
            ),
        },
        "events": events,
    }


def save_expert_review_package(
    package: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
