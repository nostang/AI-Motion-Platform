from dataclasses import dataclass
import unittest

from src.features.motion_features import MotionFeatureTracker


@dataclass
class Point:
    x: float
    y: float
    visibility: float = 1.0


class MotionFeatureTrackerTests(unittest.TestCase):
    def _landmarks(self):
        points = [Point(0.0, 0.0) for _ in range(33)]
        points[11] = Point(0.4, 0.3)
        points[12] = Point(0.6, 0.32)
        points[23] = Point(0.44, 0.62)
        points[24] = Point(0.56, 0.62)
        return points

    def test_extracts_descriptive_features(self):
        tracker = MotionFeatureTracker()
        landmarks = self._landmarks()

        tracker.observe(
            event_id=1,
            previous_state="READY",
            current_state="MOVE",
            landmarks=landmarks,
            timestamp_ms=1000,
        )
        tracker.observe(
            event_id=1,
            previous_state="MOVE",
            current_state="RECOVER",
            landmarks=landmarks,
            timestamp_ms=1100,
        )
        result = tracker.finalize_event(1)

        self.assertEqual(result["status"], "EXTRACTED")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["valid_sample_count"], 2)
        self.assertIn("MF001_shoulder_tilt", result["features"])
        self.assertIn("MF003_torso_lean", result["features"])

    def test_low_visibility_is_not_used_as_valid_sample(self):
        tracker = MotionFeatureTracker(min_visibility=0.5)
        landmarks = self._landmarks()
        landmarks[11].visibility = 0.2

        tracker.observe(
            event_id=2,
            previous_state="READY",
            current_state="MOVE",
            landmarks=landmarks,
            timestamp_ms=1000,
        )
        result = tracker.finalize_event(2)

        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["valid_sample_count"], 0)


if __name__ == "__main__":
    unittest.main()
