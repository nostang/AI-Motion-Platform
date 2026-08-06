from __future__ import annotations

import unittest

from src.coach.feature_coach import build_feature_feedback


class FeatureCoachTests(unittest.TestCase):
    def test_feature_levels_generate_explainable_feedback(self) -> None:
        result = build_feature_feedback(
            [
                {
                    "feature_id": "MF001_shoulder_tilt",
                    "level": "POOR",
                    "aggregate_value": 14.3,
                    "unit": "degrees",
                    "input_statistic": "mean_absolute_degrees",
                    "valid_event_count": 8,
                    "provisional": True,
                },
                {
                    "feature_id": "MF003_torso_lean",
                    "level": "EXCELLENT",
                    "aggregate_value": 3.3,
                    "unit": "degrees",
                    "input_statistic": "mean_absolute_degrees",
                    "valid_event_count": 8,
                    "provisional": True,
                },
            ]
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["coach_id"], "CF001")
        self.assertEqual(result[0]["level"], "POOR")
        self.assertIsNotNone(result[0]["training_suggestion"])
        self.assertEqual(result[1]["coach_id"], "CF003")
        self.assertEqual(result[1]["level"], "EXCELLENT")
        self.assertIsNone(result[1]["training_suggestion"])

    def test_unknown_feature_is_ignored(self) -> None:
        result = build_feature_feedback(
            [{"feature_id": "MF999_unknown", "level": "POOR"}]
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

class FeatureCoachIntegrationTests(unittest.TestCase):
    def test_coach_and_report_include_feature_feedback(self) -> None:
        from src.coach.coach_engine import CoachEngine
        from src.report.report_builder import ReportBuilder

        events = [
            {"completed": True, "returned_to_center": True}
            for _ in range(8)
        ]
        assessment = {
            "schema_version": "1.4",
            "assessment_id": "fa_test",
            "assessment_type": "footwork",
            "engine_version": "test",
            "config_version": "test",
            "analysis_status": "completed",
            "test_completed": True,
            "generated_at": "2026-08-06T00:00:00+00:00",
            "events": events,
            "event_count": 8,
            "expected_event_count": 8,
            "event_count_valid": True,
            "all_events_returned_to_center": True,
            "direction_coverage_complete": True,
            "direction_coverage": {},
            "missing_directions": [],
            "duplicate_directions": {},
            "unknown_direction_count": 0,
            "system_confidence": 1.0,
            "failure_reasons": [],
            "pose_detection": {"detection_rate": 1.0},
            "recovery_speed": {
                "metric_id": "AR002",
                "status": "EVALUATED",
                "result": "PASS",
                "score": 25,
                "max_score": 25,
            },
            "direction_coverage_assessment": {
                "metric_id": "AR003",
                "status": "EVALUATED",
                "result": "PASS",
                "score": 25,
                "max_score": 25,
            },
            "body_stability": {
                "metric_id": "AR004",
                "status": "EVALUATED",
                "result": "NEEDS_REVIEW",
                "level": "POOR",
                "score": 12,
                "max_score": 25,
                "feature_levels": [
                    {
                        "feature_id": "MF001_shoulder_tilt",
                        "level": "POOR",
                        "aggregate_value": 14.3,
                        "unit": "degrees",
                        "input_statistic": "mean_absolute_degrees",
                        "valid_event_count": 8,
                        "provisional": True,
                    },
                    {
                        "feature_id": "MF002_hip_tilt",
                        "level": "POOR",
                        "aggregate_value": 10.3,
                        "unit": "degrees",
                        "input_statistic": "mean_absolute_degrees",
                        "valid_event_count": 8,
                        "provisional": True,
                    },
                    {
                        "feature_id": "MF003_torso_lean",
                        "level": "EXCELLENT",
                        "aggregate_value": 3.3,
                        "unit": "degrees",
                        "input_statistic": "mean_absolute_degrees",
                        "valid_event_count": 8,
                        "provisional": True,
                    },
                ],
            },
        }

        coach = CoachEngine().evaluate(assessment)
        self.assertEqual(len(coach["feature_feedback"]), 3)

        report = ReportBuilder().build(assessment, coach)
        self.assertEqual(len(report["feature_feedback"]), 3)
        suggestion_codes = {
            item["code"] for item in report["training_suggestions"]
        }
        self.assertIn("T004", suggestion_codes)
        self.assertIn("T005", suggestion_codes)
        self.assertNotIn("T006", suggestion_codes)
