"""Stable L3 result summary contract.

This layer only organizes evaluated Assessment and Coach outputs. It does not
recalculate motion measurements, calibration levels, assessment scores, or
coach rules.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


SUMMARY_CONTRACT_VERSION = "1.0"

_METRIC_IDS = {
    "movement_completion": "AR001",
    "recovery_speed": "AR002",
    "direction_coverage": "AR003",
    "body_stability": "AR004",
    "motion_quality": "AR005",
}


class SummaryContractError(ValueError):
    """Raised when summary inputs do not satisfy the frozen L3 contract."""


class SummaryBuilder:
    """Build the frozen L3 summary without re-evaluating any result."""

    def build(
        self,
        *,
        assessment: Mapping[str, Any],
        coach_evaluation: Mapping[str, Any],
        skill_score: Mapping[str, Mapping[str, Any]],
        assessment_metrics: Mapping[str, Mapping[str, Any]],
    ) -> Dict[str, Any]:
        overall_score = self._complete_score(skill_score)
        overall_max = self._complete_max_score(skill_score)
        confidence = self._number_or_none(assessment.get("system_confidence"))
        coach_status = coach_evaluation.get("overall_status")

        generated_from = [
            metric_id
            for name, metric_id in _METRIC_IDS.items()
            if name in skill_score and skill_score[name].get("score") is not None
        ]

        return {
            "contract_version": SUMMARY_CONTRACT_VERSION,
            "overall": {
                "score": overall_score,
                "max_score": overall_max,
                "level": self._score_level(overall_score, overall_max),
                "confidence": confidence,
                "status": coach_status,
                "generated_from": generated_from,
            },
            "score_breakdown": self._score_breakdown(
                skill_score,
                assessment_metrics,
            ),
            "highlights": {
                "strengths": self._strengths(skill_score),
                "improvement_priorities": self._improvement_priorities(
                    skill_score
                ),
                "review_required": self._review_required(coach_evaluation),
            },
        }

    @staticmethod
    def _number_or_none(value: Any) -> Optional[float]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return round(float(value), 4)

    @staticmethod
    def _complete_score(
        skill_score: Mapping[str, Mapping[str, Any]],
    ) -> Optional[float]:
        scores = [item.get("score") for item in skill_score.values()]
        if not scores or any(
            isinstance(score, bool) or not isinstance(score, (int, float))
            for score in scores
        ):
            return None
        return round(float(sum(scores)), 2)

    @staticmethod
    def _complete_max_score(
        skill_score: Mapping[str, Mapping[str, Any]],
    ) -> Optional[int]:
        if not skill_score or any(
            item.get("score") is None for item in skill_score.values()
        ):
            return None
        return int(sum(item.get("max_score", 0) for item in skill_score.values()))

    @staticmethod
    def _score_level(
        score: Optional[float],
        max_score: Optional[int],
    ) -> Optional[str]:
        if score is None or not max_score:
            return None
        ratio = score / max_score
        if ratio >= 0.90:
            return "EXCELLENT"
        if ratio >= 0.75:
            return "GOOD"
        if ratio >= 0.60:
            return "FAIR"
        return "POOR"

    @staticmethod
    def _score_breakdown(
        skill_score: Mapping[str, Mapping[str, Any]],
        assessment_metrics: Mapping[str, Mapping[str, Any]],
    ) -> Dict[str, Any]:
        breakdown: Dict[str, Any] = {}
        for name, item in skill_score.items():
            breakdown[name] = {
                "score": item.get("score"),
                "max_score": item.get("max_score"),
                "status": item.get("status"),
                "source_metric_id": _METRIC_IDS.get(name),
                "source_rule_id": item.get("source_rule_id"),
                "included_in_overall": True,
            }
        for name, item in assessment_metrics.items():
            breakdown[name] = {
                "score": item.get("score"),
                "max_score": item.get("max_score"),
                "status": item.get("status"),
                "source_metric_id": _METRIC_IDS.get(name),
                "source_rule_id": item.get("source_rule_id"),
                "included_in_overall": False,
            }
        return breakdown

    @staticmethod
    def _evaluated_items(
        skill_score: Mapping[str, Mapping[str, Any]],
    ) -> list[tuple[str, float]]:
        output: list[tuple[str, float]] = []
        for name, item in skill_score.items():
            score = item.get("score")
            max_score = item.get("max_score")
            if (
                isinstance(score, (int, float))
                and not isinstance(score, bool)
                and isinstance(max_score, (int, float))
                and not isinstance(max_score, bool)
                and max_score > 0
            ):
                output.append((name, float(score) / float(max_score)))
        return output

    def _strengths(
        self,
        skill_score: Mapping[str, Mapping[str, Any]],
    ) -> list[str]:
        items = self._evaluated_items(skill_score)
        if not items:
            return []
        best = max(ratio for _, ratio in items)
        return [name for name, ratio in items if ratio == best]

    def _improvement_priorities(
        self,
        skill_score: Mapping[str, Mapping[str, Any]],
    ) -> list[str]:
        items = self._evaluated_items(skill_score)
        if not items:
            return []
        worst = min(ratio for _, ratio in items)
        return [name for name, ratio in items if ratio == worst]

    @staticmethod
    def _review_required(
        coach_evaluation: Mapping[str, Any],
    ) -> list[Dict[str, Any]]:
        output: list[Dict[str, Any]] = []
        for rule in coach_evaluation.get("rules", []):
            if not isinstance(rule, Mapping):
                continue
            if rule.get("result") != "NEEDS_REVIEW":
                continue
            output.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "display_name": rule.get("display_name"),
                }
            )
        return output
