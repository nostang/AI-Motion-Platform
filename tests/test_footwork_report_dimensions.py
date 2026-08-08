from __future__ import annotations

import unittest

from src.coach.coach_engine import CoachEngine
from src.report.report_builder import ReportBuilder


def assessment_fixture() -> dict:
    events = [
        {
            "event_id": index + 1,
            "completed": True,
            "returned_to_center": True,
        }
        for index in range(8)
    ]

    return {
        "schema_version": "1.4",
        "assessment_id": "fa_dimension_contract",
        "assessment_type": "footwork",
        "engine_version": "0.5.1",
        "config_version": "footwork-calibration-v1",
        "analysis_status": "completed",
        "test_completed": True,
        "generated_at": "2026-08-08T00:00:00+00:00",
        "events": events,
        "event_count": 8,
        "expected_event_count": 8,
        "event_count_valid": True,
        "all_events_returned_to_center": True,
        "direction_coverage_complete": False,
        "direction_coverage": {},
        "missing_directions": ["LEFT_BACK", "RIGHT"],
        "duplicate_directions": {},
        "unknown_direction_count": 0,
        "system_confidence": 0.9,
        "failure_reasons": [],
        "pose_detection": {"detection_rate": 1.0},
        "recovery_speed": {
            "metric_id": "AR002",
            "status": "EVALUATED",
            "result": "PASS",
            "score": 18,
            "max_score": 25,
        },
        "direction_coverage_assessment": {
            "metric_id": "AR003",
            "status": "EVALUATED",
            "result": "NEEDS_REVIEW",
            "score": 18.75,
            "max_score": 25,
        },
        "motion_quality": {
            "metric_id": "AR005",
            "status": "EVALUATED",
            "result": "PASS",
            "level": "GOOD",
            "score": 22,
            "max_score": 25,
        },
        "body_stability": {
            "metric_id": "AR004",
            "status": "EVALUATED",
            "result": "NEEDS_REVIEW",
            "level": "POOR",
            "score": 12,
            "max_score": 25,
            "feature_levels": [],
        },
    }


class FootworkReportDimensionContractTests(unittest.TestCase):
    def test_report_provides_all_five_dimension_levels(self) -> None:
        assessment = assessment_fixture()
        coach = CoachEngine().evaluate(assessment)
        report = ReportBuilder().build(assessment, coach)

        self.assertEqual(
            report["skill_score"]["movement_completion"]["level"],
            "EXCELLENT",
        )
        self.assertEqual(
            report["skill_score"]["recovery_speed"]["level"],
            "GOOD",
        )
        self.assertEqual(
            report["assessment_metrics"]["direction_coverage"]["level"],
            "GOOD",
        )
        self.assertEqual(
            report["skill_score"]["motion_quality"]["level"],
            "GOOD",
        )
        self.assertEqual(
            report["skill_score"]["body_stability"]["level"],
            "POOR",
        )


if __name__ == "__main__":
    unittest.main()
