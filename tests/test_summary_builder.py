from __future__ import annotations

import unittest

from src.report.summary_builder import SummaryBuilder


class SummaryBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assessment = {"system_confidence": 0.8341}
        self.coach = {
            "overall_status": "NEEDS_REVIEW",
            "rules": [
                {
                    "rule_id": "CR003",
                    "display_name": "八方向覆蓋",
                    "result": "NEEDS_REVIEW",
                },
                {
                    "rule_id": "CR006",
                    "display_name": "身體穩定度",
                    "result": "NEEDS_REVIEW",
                },
            ],
        }
        self.skill_score = {
            "movement_completion": {
                "score": 25,
                "max_score": 25,
                "status": "EVALUATED",
                "source_rule_id": "CR001",
            },
            "recovery_speed": {
                "score": 18,
                "max_score": 25,
                "status": "EVALUATED",
                "source_rule_id": "CR005",
            },
            "motion_quality": {
                "score": 22,
                "max_score": 25,
                "status": "EVALUATED",
                "source_rule_id": "CR007",
            },
            "body_stability": {
                "score": 12,
                "max_score": 25,
                "status": "EVALUATED",
                "source_rule_id": "CR006",
            },
        }
        self.metrics = {
            "direction_coverage": {
                "score": 18.75,
                "max_score": 25,
                "status": "EVALUATED",
                "source_rule_id": "CR003",
            }
        }

    def test_builds_frozen_overall_contract(self) -> None:
        result = SummaryBuilder().build(
            assessment=self.assessment,
            coach_evaluation=self.coach,
            skill_score=self.skill_score,
            assessment_metrics=self.metrics,
        )

        self.assertEqual(result["contract_version"], "1.0")
        self.assertEqual(result["overall"]["score"], 77.0)
        self.assertEqual(result["overall"]["max_score"], 100)
        self.assertEqual(result["overall"]["level"], "GOOD")
        self.assertEqual(result["overall"]["confidence"], 0.8341)
        self.assertEqual(
            result["overall"]["generated_from"],
            ["AR001", "AR002", "AR004", "AR005"],
        )

    def test_direction_coverage_is_excluded_from_overall(self) -> None:
        result = SummaryBuilder().build(
            assessment=self.assessment,
            coach_evaluation=self.coach,
            skill_score=self.skill_score,
            assessment_metrics=self.metrics,
        )

        direction = result["score_breakdown"]["direction_coverage"]
        self.assertFalse(direction["included_in_overall"])
        self.assertEqual(direction["source_metric_id"], "AR003")
        self.assertEqual(result["overall"]["score"], 77.0)

    def test_highlights_only_organize_existing_results(self) -> None:
        result = SummaryBuilder().build(
            assessment=self.assessment,
            coach_evaluation=self.coach,
            skill_score=self.skill_score,
            assessment_metrics=self.metrics,
        )

        self.assertEqual(
            result["highlights"]["strengths"], ["movement_completion"]
        )
        self.assertEqual(
            result["highlights"]["improvement_priorities"],
            ["body_stability"],
        )
        self.assertEqual(
            [item["rule_id"] for item in result["highlights"]["review_required"]],
            ["CR003", "CR006"],
        )

    def test_incomplete_skill_scores_do_not_create_overall(self) -> None:
        incomplete = dict(self.skill_score)
        incomplete["body_stability"] = {
            "score": None,
            "max_score": 25,
            "status": "NOT_EVALUATED",
            "source_rule_id": None,
        }

        result = SummaryBuilder().build(
            assessment=self.assessment,
            coach_evaluation=self.coach,
            skill_score=incomplete,
            assessment_metrics=self.metrics,
        )

        self.assertIsNone(result["overall"]["score"])
        self.assertIsNone(result["overall"]["max_score"])
        self.assertIsNone(result["overall"]["level"])


if __name__ == "__main__":
    unittest.main()
