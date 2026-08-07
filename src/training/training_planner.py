"""AI Training Planner V1.

Consumes AI Coach JSON and produces a structured rule-based training plan.

This layer does not:
- re-run motion analysis
- change motion scores
- change competency results
- generate a playing-level conclusion
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class AITrainingPlanner:
    def __init__(self, rules: Mapping[str, Any]) -> None:
        self.rules = dict(rules)

    @classmethod
    def from_file(cls, path: Path) -> "AITrainingPlanner":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def build(
        self,
        coach: Mapping[str, Any],
    ) -> dict[str, Any]:
        if coach.get("status") != "READY":
            return {
                "schema_version": "1.0",
                "plan_version": "training-plan-v1.0",
                "rule_version": self.rules["rule_version"],
                "status": "NOT_READY",
                "player_id": coach.get("player_id"),
                "estimated_training_sessions": 0,
                "training_plan": [],
                "maintenance_plan": [],
                "reassessment": {
                    "recommended": False,
                    "after_priority_sessions": 0,
                    "recommended_motion": None,
                },
                "limitations": list(self.rules["limitations"]),
            }

        allocation = self.rules["session_allocation"]
        recommendations = list(
            coach.get("training_recommendations", [])
        )

        training_plan: list[dict[str, Any]] = []
        maintenance_plan: list[dict[str, Any]] = []

        for item in recommendations:
            if not isinstance(item, Mapping):
                continue

            priority = str(
                item.get("priority", "")
            ).strip().upper()

            motion_type = item.get("motion_type")
            recommendation = item.get("recommendation")
            source = item.get("source")

            sessions = allocation.get(priority)
            if sessions is None:
                continue

            plan_item = {
                "motion_type": motion_type,
                "priority": priority,
                "goal": recommendation,
                "recommended_sessions": int(sessions),
                "source": dict(source)
                if isinstance(source, Mapping)
                else {},
            }

            if priority == "MAINTAIN":
                maintenance_plan.append(plan_item)
            else:
                training_plan.append(plan_item)

        priority_sessions = sum(
            item["recommended_sessions"]
            for item in training_plan
        )

        recommended_motion = (
            training_plan[0]["motion_type"]
            if training_plan
            else None
        )

        reassessment_enabled = bool(
            self.rules["reassessment"]["enabled"]
        )

        return {
            "schema_version": "1.0",
            "plan_version": "training-plan-v1.0",
            "rule_version": self.rules["rule_version"],
            "status": "READY",
            "player_id": coach.get("player_id"),
            "coach_version": coach.get("coach_version"),
            "estimated_training_sessions": priority_sessions,
            "training_plan": training_plan,
            "maintenance_plan": maintenance_plan,
            "reassessment": {
                "recommended": bool(
                    reassessment_enabled
                    and training_plan
                ),
                "after_priority_sessions": priority_sessions,
                "recommended_motion": recommended_motion,
            },
            "limitations": list(self.rules["limitations"]),
        }
