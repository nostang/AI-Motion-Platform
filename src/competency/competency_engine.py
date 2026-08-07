"""Competency Engine V1。

Consumes an existing Competency Profile and produces rule-based,
explainable competency interpretation.

Important:
- Does not recalculate motion scores.
- Does not create a cross-motion overall score.
- Does not assign badminton level until a formal mapping rule exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class CompetencyEngine:
    def __init__(self, rules: Mapping[str, Any]) -> None:
        self.rules = dict(rules)

    @classmethod
    def from_file(cls, path: Path) -> "CompetencyEngine":
        rules = json.loads(path.read_text(encoding="utf-8"))
        return cls(rules)

    def evaluate(
        self,
        profile: Mapping[str, Any],
    ) -> dict[str, Any]:
        motions = profile.get("motions")
        motions = motions if isinstance(motions, Mapping) else {}

        available: list[dict[str, Any]] = []

        for motion_type, item in motions.items():
            if not isinstance(item, Mapping):
                continue
            if item.get("status") != "AVAILABLE":
                continue

            score = item.get("overall_score")
            if (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
            ):
                continue

            available.append(
                {
                    "motion_type": str(motion_type),
                    "score": float(score),
                    "coach_status": item.get("coach_status"),
                    "assessment_id": item.get("assessment_id"),
                }
            )

        if not available:
            return {
                "schema_version": "1.0",
                "engine_version": "competency-engine-v1.0",
                "status": "NOT_AVAILABLE",
                "player_id": profile.get("player_id"),
                "strengths": [],
                "improvement_priorities": [],
                "overall_level": None,
                "mapping_status": "NOT_CONFIGURED",
                "cross_motion_overall_score": None,
            }

        strength_min_score = float(
            self.rules["interpretation"]["strength_min_score"]
        )
        priority_score_below = float(
            self.rules["interpretation"]["priority_score_below"]
        )
        needs_review_first = bool(
            self.rules["interpretation"]["needs_review_first"]
        )

        strengths = [
            item
            for item in sorted(
                available,
                key=lambda x: x["score"],
                reverse=True,
            )
            if (
                item["score"] >= strength_min_score
                and item.get("coach_status") != "NEEDS_REVIEW"
            )
        ]

        priorities = [
            item
            for item in available
            if (
                item["score"] < priority_score_below
                or item.get("coach_status") == "NEEDS_REVIEW"
            )
        ]

        if needs_review_first:
            priorities.sort(
                key=lambda x: (
                    0 if x.get("coach_status") == "NEEDS_REVIEW" else 1,
                    x["score"],
                )
            )
        else:
            priorities.sort(key=lambda x: x["score"])

        mapping_enabled = bool(
            self.rules["mapping"]["enabled"]
        )

        return {
            "schema_version": "1.0",
            "engine_version": "competency-engine-v1.0",
            "rule_version": self.rules["rule_version"],
            "status": "READY",
            "player_id": profile.get("player_id"),
            "profile_version": profile.get("profile_version"),
            "profile_status": profile.get("profile_status"),
            "strengths": strengths,
            "improvement_priorities": priorities,
            "overall_level": None,
            "mapping_status": (
                "READY"
                if mapping_enabled
                else "NOT_CONFIGURED"
            ),
            "cross_motion_overall_score": None,
            "limitations": [
                "This engine interprets existing motion scores only.",
                "It does not recalculate Footwork, Serve, or Clear scores.",
                "Cross-motion overall scoring is intentionally disabled.",
                "Badminton level mapping remains disabled until formal mapping rules are defined.",
            ],
        }
