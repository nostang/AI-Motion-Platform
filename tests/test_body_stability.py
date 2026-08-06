from __future__ import annotations

import unittest

from src.assessment.body_stability import evaluate_body_stability
from src.calibration import MotionFeatureCalibrationEngine


CALIBRATION = {
    "schema_version": "1.0",
    "config_version": "test-calibration-v1",
    "status": "PROVISIONAL",
    "features": {
        "MF001_shoulder_tilt": {
            "input_statistic": "mean_absolute_degrees",
            "unit": "degrees",
            "direction": "lower_is_better",
            "thresholds": {"EXCELLENT": 3, "GOOD": 6, "FAIR": 12},
        },
        "MF002_hip_tilt": {
            "input_statistic": "mean_absolute_degrees",
            "unit": "degrees",
            "direction": "lower_is_better",
            "thresholds": {"EXCELLENT": 3, "GOOD": 6, "FAIR": 10},
        },
        "MF003_torso_lean": {
            "input_statistic": "mean_absolute_degrees",
            "unit": "degrees",
            "direction": "lower_is_better",
            "thresholds": {"EXCELLENT": 5, "GOOD": 10, "FAIR": 18},
        },
    },
}


def make_event(shoulder: float, hip: float, torso: float) -> dict:
    return {
        "motion_features": {
            "status": "EXTRACTED",
            "features": {
                "MF001_shoulder_tilt": {
                    "mean_absolute_degrees": shoulder,
                },
                "MF002_hip_tilt": {
                    "mean_absolute_degrees": hip,
                },
                "MF003_torso_lean": {
                    "mean_absolute_degrees": torso,
                },
            },
        }
    }


class BodyStabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MotionFeatureCalibrationEngine(CALIBRATION)

    def test_good_features_produce_good_pass(self) -> None:
        events = [make_event(5.0, 5.0, 8.0) for _ in range(8)]
        result = evaluate_body_stability(
            events=events,
            calibration_engine=self.engine,
        )
        self.assertEqual(result["status"], "EVALUATED")
        self.assertEqual(result["level"], "GOOD")
        self.assertEqual(result["score"], 22)
        self.assertEqual(result["result"], "PASS")

    def test_fair_features_need_review(self) -> None:
        events = [make_event(9.0, 8.0, 14.0) for _ in range(8)]
        result = evaluate_body_stability(
            events=events,
            calibration_engine=self.engine,
        )
        self.assertEqual(result["level"], "FAIR")
        self.assertEqual(result["score"], 18)
        self.assertEqual(result["result"], "NEEDS_REVIEW")

    def test_insufficient_events_are_not_evaluated(self) -> None:
        events = [make_event(5.0, 5.0, 8.0) for _ in range(5)]
        result = evaluate_body_stability(
            events=events,
            calibration_engine=self.engine,
        )
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertIsNone(result["score"])
        self.assertEqual(len(result["missing_features"]), 3)


if __name__ == "__main__":
    unittest.main()
