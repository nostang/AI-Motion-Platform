"""AI Motion Report Module.

The Report layer converts Assessment and Coach Evaluation outputs into one
UI-independent report contract. It does not recompute Pose, Measurement,
Event, classification, or Coach rules.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional


REPORT_VERSION = "1.2"
RADAR_LABELS = [
    "Movement Completion",
    "Recovery Speed",
    "Direction Coverage",
    "Footwork Technique",
    "Body Stability",
]


class ReportContractError(ValueError):
    """Raised when Assessment and Coach inputs do not satisfy the contract."""


class ReportBuilder:
    """Build and save a Footwork Analysis Report."""

    def __init__(self, version: str = REPORT_VERSION) -> None:
        self.version = version

    def build(
        self,
        assessment: Mapping[str, Any],
        coach_evaluation: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Build one report without recalculating technical measurements."""

        self._validate_inputs(assessment, coach_evaluation)

        rules = {
            rule["rule_id"]: rule
            for rule in coach_evaluation.get("rules", [])
            if isinstance(rule, Mapping) and "rule_id" in rule
        }

        completion_rule = rules.get("CR001", {})
        return_center_rule = rules.get("CR002", {})
        direction_rule = rules.get("CR003", {})
        continuity_rule = rules.get("CR004", {})
        recovery_rule = rules.get("CR005", {})

        movement_score = self._pass_only_score(completion_rule)
        recovery_score = self._rule_numeric_score(recovery_rule)
        direction_score = self._rule_numeric_score(direction_rule)
        technique_score = self._numeric_or_none(
            coach_evaluation.get("technique_score")
        )

        skill_score = {
            "movement_completion": self._score_item(
                score=movement_score,
                max_score=25,
                source_rule_id="CR001",
            ),
            "recovery_speed": self._score_item(
                score=recovery_score,
                max_score=25,
                source_rule_id="CR005" if recovery_score is not None else None,
            ),
            "footwork_technique": self._score_item(
                score=technique_score,
                max_score=25,
                source_rule_id=None,
            ),
            "body_stability": self._score_item(
                score=None,
                max_score=25,
                source_rule_id=None,
            ),
        }

        assessment_metrics = {
            "direction_coverage": self._score_item(
                score=direction_score,
                max_score=25,
                source_rule_id="CR003" if direction_score is not None else None,
            ),
        }

        radar_scores = [
            skill_score["movement_completion"]["score"],
            skill_score["recovery_speed"]["score"],
            assessment_metrics["direction_coverage"]["score"],
            skill_score["footwork_technique"]["score"],
            skill_score["body_stability"]["score"],
        ]

        feedback = self._build_feedback(rules)
        training_suggestions = self._build_training_suggestions(feedback)

        return {
            "assessment_id": assessment["assessment_id"],
            "assessment_type": assessment["assessment_type"],
            "report_version": self.version,
            "analyzed_at": assessment.get("generated_at"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "motion": assessment["assessment_type"],
                "completed": bool(assessment.get("test_completed", False)),
                "overall_score": self._overall_score(skill_score),
                "evaluated_score": self._evaluated_score(skill_score),
                "evaluated_max_score": self._evaluated_max_score(skill_score),
                "score_coverage": self._score_coverage(skill_score),
                "coach_status": coach_evaluation.get("overall_status"),
            },
            "observation": {
                "return_center": self._pass_fail_or_none(return_center_rule),
                "recovery_time": self._recovery_observation(recovery_rule),
                "footwork_correct": self._pass_fail_or_none(direction_rule),
                "extra_steps": None,
                "body_stable": None,
                "motion_continuous": self._pass_fail_or_none(continuity_rule),
                "direction_coverage_complete": assessment.get(
                    "direction_coverage_complete"
                ),
                "missing_directions": list(
                    assessment.get("missing_directions", [])
                ),
                "system_confidence": assessment.get("system_confidence"),
            },
            "skill_score": skill_score,
            "assessment_metrics": assessment_metrics,
            "feedback": feedback,
            "training_suggestions": training_suggestions,
            "radar_chart": {
                "labels": list(RADAR_LABELS),
                "scores": radar_scores,
                "max_score": 25,
            },
            "review": {
                "recommended": bool(
                    coach_evaluation.get("expert_review_recommended", False)
                ),
                "needs_review_count": coach_evaluation.get(
                    "checklist_summary", {}
                ).get("needs_review_count", 0),
                "limitations": self._collect_limitations(
                    coach_evaluation.get("rules", [])
                ),
            },
            "meta": {
                "model_name": "MediaPipe Pose Landmarker",
                "assessment_schema_version": assessment.get("schema_version"),
                "engine_version": assessment.get("engine_version"),
                "config_version": assessment.get("config_version"),
                "coach_engine_version": coach_evaluation.get(
                    "coach_engine_version"
                ),
                "timing_used_for_score": bool(
                    coach_evaluation.get("timing_used_for_score", False)
                ),
                "not_evaluated": list(
                    coach_evaluation.get("not_evaluated", [])
                ),
            },
        }

    def save(self, report: Mapping[str, Any], output_path: Path) -> None:
        """Save report JSON using UTF-8 and stable indentation."""

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _validate_inputs(
        self,
        assessment: Mapping[str, Any],
        coach_evaluation: Mapping[str, Any],
    ) -> None:
        required_assessment = {
            "assessment_id",
            "assessment_type",
            "analysis_status",
            "test_completed",
        }
        required_coach = {
            "assessment_id",
            "assessment_type",
            "overall_status",
            "rules",
            "checklist_summary",
        }

        self._require_keys(
            assessment,
            required_assessment,
            source_name="assessment",
        )
        self._require_keys(
            coach_evaluation,
            required_coach,
            source_name="coach_evaluation",
        )

        if assessment["assessment_id"] != coach_evaluation["assessment_id"]:
            raise ReportContractError(
                "Assessment 與 Coach Evaluation 的 assessment_id 不一致。"
            )

        if assessment["assessment_type"] != coach_evaluation["assessment_type"]:
            raise ReportContractError(
                "Assessment 與 Coach Evaluation 的 assessment_type 不一致。"
            )

        if assessment["assessment_type"] != "footwork":
            raise ReportContractError(
                "Report V1 僅支援 assessment_type=footwork。"
            )

        if assessment["analysis_status"] != "completed":
            raise ReportContractError(
                "Assessment 尚未 completed，不得產生正式 Report。"
            )

    @staticmethod
    def _require_keys(
        source: Mapping[str, Any],
        required: Iterable[str],
        source_name: str,
    ) -> None:
        missing = sorted(key for key in required if key not in source)
        if missing:
            raise ReportContractError(
                f"{source_name} 缺少必要欄位：{', '.join(missing)}"
            )

    @staticmethod
    def _numeric_or_none(value: Any) -> Optional[float]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @staticmethod
    def _rule_numeric_score(rule: Mapping[str, Any]) -> Optional[float]:
        evidence = rule.get("evidence") or {}
        value = evidence.get("score")
        if rule.get("result") == "NOT_EVALUATED":
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @staticmethod
    def _recovery_observation(rule: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        evidence = rule.get("evidence") or {}
        average = evidence.get("average_seconds")
        if isinstance(average, bool) or not isinstance(average, (int, float)):
            return None
        return {
            "average_seconds": average,
            "median_seconds": evidence.get("median_seconds"),
            "fastest_seconds": evidence.get("fastest_seconds"),
            "slowest_seconds": evidence.get("slowest_seconds"),
            "valid_event_count": evidence.get("valid_event_count"),
            "config_version": evidence.get("config_version"),
        }

    @staticmethod
    def _pass_only_score(rule: Mapping[str, Any]) -> Optional[int]:
        if rule.get("result") == "PASS":
            return 25
        if rule.get("result") == "FAIL":
            return 0
        return None

    @staticmethod
    def _score_item(
        score: Optional[float],
        max_score: int,
        source_rule_id: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "score": score,
            "max_score": max_score,
            "status": "EVALUATED" if score is not None else "NOT_EVALUATED",
            "source_rule_id": source_rule_id,
        }

    @staticmethod
    def _pass_fail_or_none(rule: Mapping[str, Any]) -> Optional[bool]:
        result = rule.get("result")
        if result == "PASS":
            return True
        if result == "FAIL":
            return False
        return None

    @staticmethod
    def _overall_score(skill_score: Mapping[str, Mapping[str, Any]]) -> Optional[float]:
        """Return a 100-point overall score only after all four dimensions exist."""
        scores = [item.get("score") for item in skill_score.values()]
        if any(score is None for score in scores):
            return None
        return float(sum(scores))

    @staticmethod
    def _evaluated_score(skill_score: Mapping[str, Mapping[str, Any]]) -> float:
        return float(
            sum(
                item.get("score")
                for item in skill_score.values()
                if item.get("score") is not None
            )
        )

    @staticmethod
    def _evaluated_max_score(skill_score: Mapping[str, Mapping[str, Any]]) -> int:
        return int(
            sum(
                item.get("max_score", 0)
                for item in skill_score.values()
                if item.get("score") is not None
            )
        )

    @staticmethod
    def _score_coverage(skill_score: Mapping[str, Mapping[str, Any]]) -> float:
        total = len(skill_score)
        if total == 0:
            return 0.0
        evaluated = sum(
            item.get("score") is not None
            for item in skill_score.values()
        )
        return round(evaluated / total, 4)

    @staticmethod
    def _build_feedback(
        rules: Mapping[str, Mapping[str, Any]],
    ) -> list[Dict[str, str]]:
        feedback: list[Dict[str, str]] = []

        return_center = rules.get("CR002", {})
        recovery_speed = rules.get("CR005", {})
        if return_center.get("result") == "FAIL":
            feedback.append(
                {
                    "code": "F001",
                    "message": "尚未完全回到中心位置。",
                    "source_rule_id": "CR002",
                }
            )

        if recovery_speed.get("result") == "NEEDS_REVIEW":
            evidence = recovery_speed.get("evidence") or {}
            average = evidence.get("average_seconds")
            score = evidence.get("score")
            feedback.append(
                {
                    "code": "F002",
                    "message": (
                        f"平均回位時間 {average:.2f} 秒，"
                        f"Recovery Speed 得分 {score}/25，建議持續觀察。"
                        if isinstance(average, (int, float))
                        and isinstance(score, (int, float))
                        else "回位速度需要進一步確認。"
                    ),
                    "source_rule_id": "CR005",
                }
            )

        return feedback

    @staticmethod
    def _build_training_suggestions(
        feedback: Iterable[Mapping[str, Any]],
    ) -> list[Dict[str, Any]]:
        codes = {item.get("code") for item in feedback}
        suggestions: list[Dict[str, Any]] = []

        if "F001" in codes:
            suggestions.append(
                {
                    "code": "T001",
                    "title": "回中心練習",
                    "description": "加強米字步回中心練習。",
                    "sets": 5,
                    "repetitions_per_set": 20,
                    "source_feedback_code": "F001",
                }
            )

        if "F002" in codes:
            suggestions.append(
                {
                    "code": "T002",
                    "title": "回位節奏練習",
                    "description": "以穩定回中心為優先，進行低強度米字步並記錄每次回位時間。",
                    "sets": 3,
                    "repetitions_per_set": 8,
                    "source_feedback_code": "F002",
                }
            )

        return suggestions

    @staticmethod
    def _collect_limitations(rules: Iterable[Mapping[str, Any]]) -> list[str]:
        limitations: list[str] = []
        for rule in rules:
            for item in rule.get("limitations", []):
                if item not in limitations:
                    limitations.append(item)
        return limitations
