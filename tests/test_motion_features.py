from dataclasses import dataclass
import unittest

from src.features.motion_features import (
    MotionFeatureTracker,
    _normalize_undirected_line_angle,
)


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

    def test_normalizes_angle_wraparound_for_undirected_lines(self):
        self.assertAlmostEqual(_normalize_undirected_line_angle(179.0), -1.0)
        self.assertAlmostEqual(_normalize_undirected_line_angle(-179.0), 1.0)
        self.assertAlmostEqual(_normalize_undirected_line_angle(-160.0), 20.0)
        self.assertAlmostEqual(_normalize_undirected_line_angle(170.0), -10.0)
        self.assertAlmostEqual(_normalize_undirected_line_angle(90.0), -90.0)

    def test_reversed_landmark_order_keeps_same_physical_tilt(self):
        tracker = MotionFeatureTracker()
        landmarks = self._landmarks()

        # Reverse shoulder and hip point ordering. Raw atan2 angles move close
        # to +/-180 degrees, but normalized tilt must remain near the original.
        landmarks[11], landmarks[12] = landmarks[12], landmarks[11]
        landmarks[23], landmarks[24] = landmarks[24], landmarks[23]

        tracker.observe(
            event_id=3,
            previous_state="READY",
            current_state="MOVE",
            landmarks=landmarks,
            timestamp_ms=1000,
        )
        result = tracker.finalize_event(3)

        shoulder = result["features"]["MF001_shoulder_tilt"]
        hip = result["features"]["MF002_hip_tilt"]

        self.assertLess(abs(shoulder["mean_degrees"]), 10.0)
        self.assertLess(abs(shoulder["mean_absolute_degrees"]), 10.0)
        self.assertAlmostEqual(hip["mean_degrees"], 0.0, places=4)
        self.assertAlmostEqual(hip["mean_absolute_degrees"], 0.0, places=4)

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
