from __future__ import annotations

import unittest

from src.assessment.recovery_speed import evaluate_recovery_speed
from src.coach.coach_engine import CoachEngine
from src.report.report_builder import ReportBuilder


def assessment_fixture(times):
    return {
        "schema_version": "1.1",
        "assessment_id": "fa_test",
        "engine_version": "0.5.1",
        "config_version": "footwork-calibration-v1",
        "assessment_type": "footwork",
        "generated_at": "2026-08-06T00:00:00+00:00",
        "analysis_status": "completed",
        "test_completed": True,
        "expected_event_count": 8,
        "event_count": len(times),
        "event_count_valid": len(times) == 8,
        "all_events_returned_to_center": True,
        "direction_coverage_complete": True,
        "events": [
            {
                "event_id": index + 1,
                "completed": True,
                "returned_to_center": True,
                "recovery_time_seconds": value,
            }
            for index, value in enumerate(times)
        ],
        "pose_detection": {"detection_rate": 1.0},
        "failure_reasons": [],
        "missing_directions": [],
        "duplicate_directions": {},
        "unknown_direction_count": 0,
        "direction_coverage": {},
        "system_confidence": 0.9,
    }


class RecoverySpeedTests(unittest.TestCase):
    def test_recovery_score_and_report(self):
        assessment = assessment_fixture(
            [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
        )
        assessment["recovery_speed"] = evaluate_recovery_speed(assessment)
        coach = CoachEngine().evaluate(assessment)
        report = ReportBuilder().build(assessment, coach)

        self.assertEqual(assessment["recovery_speed"]["status"], "EVALUATED")
        self.assertIsNotNone(assessment["recovery_speed"]["score"])
        self.assertGreaterEqual(len(coach["rules"]), 5)
        self.assertIsNotNone(report["skill_score"]["recovery_speed"]["score"])
        self.assertIsNone(report["summary"]["overall_score"])

    def test_insufficient_recovery_data(self):
        assessment = assessment_fixture([0.6, 0.7, None])
        assessment["recovery_speed"] = evaluate_recovery_speed(assessment)
        coach = CoachEngine().evaluate(assessment)
        report = ReportBuilder().build(assessment, coach)

        self.assertEqual(
            assessment["recovery_speed"]["status"], "NOT_EVALUATED"
        )
        self.assertEqual(coach["rules"][-1]["result"], "NOT_EVALUATED")
        self.assertIsNone(report["skill_score"]["recovery_speed"]["score"])


if __name__ == "__main__":
    unittest.main()
