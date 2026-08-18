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


def evaluate(
    engine: MotionFeatureCalibrationEngine,
    *,
    shoulder: float,
    hip: float,
    torso: float,
) -> dict:
    events = [
        make_event(shoulder, hip, torso)
        for _ in range(8)
    ]
    return evaluate_body_stability(
        events=events,
        calibration_engine=engine,
    )


class BodyStabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MotionFeatureCalibrationEngine(CALIBRATION)

    def test_good_features_produce_good_pass(self) -> None:
        result = evaluate(
            self.engine,
            shoulder=5.0,
            hip=5.0,
            torso=8.0,
        )
        self.assertEqual(result["status"], "EVALUATED")
        self.assertEqual(result["level"], "GOOD")
        self.assertEqual(result["result"], "PASS")

    def test_fair_features_need_review(self) -> None:
        result = evaluate(
            self.engine,
            shoulder=9.0,
            hip=8.0,
            torso=14.0,
        )
        self.assertEqual(result["level"], "FAIR")
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

    # ------------------------------------------------------------------
    # Body Stability V2 production-candidate contract tests.
    #
    # These tests intentionally express the candidate behavior before
    # production implementation. Some are expected to fail against V1.
    # ------------------------------------------------------------------

    def test_v2_boundary_variation_does_not_create_large_score_jump(self) -> None:
        """Normalization-scale perturbation should not amplify into +6 points."""

        original = evaluate(
            self.engine,
            shoulder=15.5245,
            hip=10.5511,
            torso=3.3624,
        )
        normalized = evaluate(
            self.engine,
            shoulder=13.3181,
            hip=9.4668,
            torso=3.2920,
        )

        self.assertEqual(original["status"], "EVALUATED")
        self.assertEqual(normalized["status"], "EVALUATED")

        delta = abs(
            float(normalized["score"])
            - float(original["score"])
        )

        # Candidate robustness contract:
        # the real FW001 perturbation must remain below 2 points.
        self.assertLess(
            delta,
            2.0,
            msg=(
                "Body Stability boundary amplification detected: "
                f"score delta={delta:.3f}"
            ),
        )

    def test_v2_score_preserves_continuous_information(self) -> None:
        """Nearby measurement profiles should not collapse to one fixed score."""

        sample_a = evaluate(
            self.engine,
            shoulder=14.3409,
            hip=10.2795,
            torso=3.3406,
        )
        sample_b = evaluate(
            self.engine,
            shoulder=19.1776,
            hip=10.9829,
            torso=6.0503,
        )

        self.assertNotEqual(
            float(sample_a["score"]),
            float(sample_b["score"]),
            msg=(
                "Distinct Body Stability measurement profiles "
                "collapsed to the same score."
            ),
        )

    def test_v2_score_is_monotonic_for_worsening_measurements(self) -> None:
        """Clearly worse measurements must not receive a better score."""

        better = evaluate(
            self.engine,
            shoulder=8.0,
            hip=7.0,
            torso=8.0,
        )
        worse = evaluate(
            self.engine,
            shoulder=16.0,
            hip=13.0,
            torso=15.0,
        )

        self.assertGreaterEqual(
            float(better["score"]),
            float(worse["score"]),
        )

    def test_v2_fair_result_remains_needs_review(self) -> None:
        """FAIR remains reviewable in the candidate contract."""

        result = evaluate(
            self.engine,
            shoulder=9.0,
            hip=8.0,
            torso=14.0,
        )

        self.assertEqual(result["level"], "FAIR")
        self.assertEqual(result["result"], "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
