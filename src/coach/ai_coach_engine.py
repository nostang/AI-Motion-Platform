"""AI Coach Engine V1.

Consumes:
- Competency Profile
- Competency Interpretation

Produces:
- Coach JSON

This layer does not:
- re-score motions
- calculate cross-motion scores
- determine an official playing level
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class AICoachEngine:
    def __init__(self, rules: Mapping[str, Any]) -> None:
        self.rules = dict(rules)

    @classmethod
    def from_file(cls, path: Path) -> "AICoachEngine":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def generate(
        self,
        profile: Mapping[str, Any],
        interpretation: Mapping[str, Any],
    ) -> dict[str, Any]:

        strengths = list(interpretation.get("strengths", []))
        priorities = list(
            interpretation.get("improvement_priorities", [])
        )

        training = []

        rule_map = self.rules["training_recommendations"]

        for item in priorities:
            motion = item.get("motion_type")
            if motion not in rule_map:
                continue

            training.append(
                {
                    "motion_type": motion,
                    "priority": "HIGH",
                    "recommendation": rule_map[motion][
                        "priority_message"
                    ],
                    "source": {
                        "score": item.get("score"),
                        "coach_status": item.get(
                            "coach_status"
                        ),
                        "assessment_id": item.get(
                            "assessment_id"
                        ),
                    },
                }
            )

        for item in strengths:
            motion = item.get("motion_type")
            if motion not in rule_map:
                continue

            training.append(
                {
                    "motion_type": motion,
                    "priority": "MAINTAIN",
                    "recommendation": rule_map[motion][
                        "maintain_message"
                    ],
                    "source": {
                        "score": item.get("score"),
                        "coach_status": item.get(
                            "coach_status"
                        ),
                        "assessment_id": item.get(
                            "assessment_id"
                        ),
                    },
                }
            )

        return {
            "schema_version": "1.0",
            "coach_version": "ai-coach-v1.0",
            "rule_version": self.rules["rule_version"],
            "status": "READY",
            "player_id": profile.get("player_id"),
            "profile_version": profile.get("profile_version"),
            "strengths": strengths,
            "improvement_priorities": priorities,
            "training_recommendations": training,
            "suggested_playing_level": {
                "status": self.rules[
                    "suggested_playing_level"
                ]["status_when_disabled"],
                "suggested_range": None,
                "confidence": None,
            },
            "limitations": self.rules["limitations"],
        }
