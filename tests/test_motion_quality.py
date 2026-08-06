from __future__ import annotations

import unittest

from src.assessment.motion_quality import evaluate_motion_quality


class FakeCalibrationResult:
    unit = "index"
    level = "GOOD"
    calibration_version = "motion-feature-calibration-v1.1"
    provisional = True


class FakeCalibrationEngine:
    config_version = "motion-feature-calibration-v1.1"
    status = "PROVISIONAL"

    def get_rule(self, feature_id):
        return {"input_statistic": "combined_smoothness_index"}

    def evaluate(self, *, feature_id, value):
        return FakeCalibrationResult()


class MotionQualityTests(unittest.TestCase):
    def test_evaluates_six_events(self):
        events = [
            {
                "motion_features": {
                    "status": "EXTRACTED",
                    "features": {
                        "MF005_motion_smoothness": {
                            "status": "EXTRACTED",
                            "combined_smoothness_index": 0.4 + index * 0.01,
                        }
                    },
                }
            }
            for index in range(6)
        ]
        result = evaluate_motion_quality(
            events=events,
            calibration_engine=FakeCalibrationEngine(),
        )
        self.assertEqual(result["status"], "EVALUATED")
        self.assertEqual(result["level"], "GOOD")
        self.assertEqual(result["score"], 22)

    def test_insufficient_events(self):
        result = evaluate_motion_quality(
            events=[],
            calibration_engine=FakeCalibrationEngine(),
        )
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
