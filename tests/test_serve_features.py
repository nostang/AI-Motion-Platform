import unittest
from types import SimpleNamespace

from src.features.serve_features import ServeFeatureTracker


def landmarks(frame):
    points = [SimpleNamespace(x=0.5, y=0.5) for _ in range(33)]
    points[11] = SimpleNamespace(x=0.42, y=0.30)
    points[12] = SimpleNamespace(x=0.58, y=0.30)
    points[23] = SimpleNamespace(x=0.45, y=0.60)
    points[24] = SimpleNamespace(x=0.55, y=0.60)
    points[15] = SimpleNamespace(x=0.35, y=0.50)
    points[16] = SimpleNamespace(x=0.58 + frame * 0.02, y=0.48 - frame * 0.015)
    return points


class ServeFeatureTests(unittest.TestCase):
    def test_extracts_features(self):
        tracker = ServeFeatureTracker()
        for i in range(12):
            tracker.observe(landmarks(i), i * 33)
        result = tracker.build()
        self.assertEqual(result["status"], "EXTRACTED")
        self.assertGreater(result["swing_path_length"], 0)
        self.assertIn("wrist_speed_variation", result)


if __name__ == "__main__":
    unittest.main()
