import json
from pathlib import Path
import tempfile
import unittest

from src.calibration import MotionFeatureCalibrationEngine
from src.calibration_settings import load_footwork_calibration


class MotionFeatureCalibrationEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schema_version": "1.0",
            "config_version": "test-calibration-v1",
            "status": "PROVISIONAL",
            "features": {
                "MF001_shoulder_tilt": {
                    "input_statistic": "mean_absolute_degrees",
                    "unit": "degrees",
                    "direction": "lower_is_better",
                    "thresholds": {
                        "EXCELLENT": 3.0,
                        "GOOD": 6.0,
                        "FAIR": 12.0,
                    },
                }
            },
        }
        self.engine = MotionFeatureCalibrationEngine(self.config)

    def test_returns_expected_levels_at_boundaries(self):
        cases = [
            (2.0, "EXCELLENT"),
            (3.0, "EXCELLENT"),
            (4.8, "GOOD"),
            (6.0, "GOOD"),
            (8.0, "FAIR"),
            (12.0, "FAIR"),
            (18.0, "POOR"),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                result = self.engine.evaluate(
                    feature_id="MF001_shoulder_tilt",
                    value=value,
                )
                self.assertEqual(result.level, expected)
                self.assertTrue(result.provisional)
                self.assertEqual(result.calibration_version, "test-calibration-v1")

    def test_uses_absolute_value_for_signed_tilt(self):
        positive = self.engine.evaluate(
            feature_id="MF001_shoulder_tilt",
            value=5.0,
        )
        negative = self.engine.evaluate(
            feature_id="MF001_shoulder_tilt",
            value=-5.0,
        )
        self.assertEqual(positive.level, negative.level)

    def test_rejects_unknown_feature_and_nonfinite_value(self):
        with self.assertRaises(KeyError):
            self.engine.evaluate(feature_id="MF999", value=1.0)
        with self.assertRaises(ValueError):
            self.engine.evaluate(
                feature_id="MF001_shoulder_tilt",
                value=float("nan"),
            )

    def test_rejects_invalid_threshold_order(self):
        invalid = json.loads(json.dumps(self.config))
        invalid["features"]["MF001_shoulder_tilt"]["thresholds"] = {
            "EXCELLENT": 6.0,
            "GOOD": 3.0,
            "FAIR": 12.0,
        }
        with self.assertRaises(ValueError):
            MotionFeatureCalibrationEngine(invalid)

    def test_loader_validates_and_builds_engine(self):
        root_config = {
            "schema_version": "1.1",
            "config_version": "footwork-test-v1",
            "center": {"calibration_seconds": 1.0, "region_radius": 0.06},
            "event": {
                "move_offset_threshold": 0.08,
                "return_offset_threshold": 0.05,
            },
            "direction": {},
            "review": {},
            "feature_calibration": self.config,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "calibration.json"
            path.write_text(
                json.dumps(root_config, ensure_ascii=False),
                encoding="utf-8",
            )
            settings = load_footwork_calibration(path)
            engine = settings.create_feature_calibration_engine()
            result = engine.evaluate(
                feature_id="MF001_shoulder_tilt",
                value=2.5,
            )
            self.assertEqual(result.level, "EXCELLENT")


if __name__ == "__main__":
    unittest.main()
