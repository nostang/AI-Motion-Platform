from __future__ import annotations

import unittest
from math import cos, radians, sin

from src.classification.motion_classifier import (
    MotionClassifier,
    MotionDirection,
)


class MotionClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = MotionClassifier(
            mirror_x=False,
            x_scale=1.0,
            y_scale=1.0,
            min_vector_length=0.035,
            min_confidence=0.3,
        )

    @staticmethod
    def reach_point(
        angle_degrees: float,
        length: float = 0.2,
    ) -> tuple[float, float]:
        angle = radians(angle_degrees)
        return (
            cos(angle) * length,
            sin(angle) * length,
        )

    def test_boundary_direction_is_retained_below_boundary(self) -> None:
        result = self.classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=self.reach_point(22.498),
        )

        self.assertEqual(result.direction, MotionDirection.RIGHT)
        self.assertTrue(result.valid)
        self.assertTrue(result.boundary_ambiguous)
        self.assertLess(result.confidence, 0.3)

    def test_boundary_direction_is_retained_above_boundary(self) -> None:
        result = self.classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=self.reach_point(22.502),
        )

        self.assertEqual(
            result.direction,
            MotionDirection.RIGHT_FRONT,
        )
        self.assertTrue(result.valid)
        self.assertTrue(result.boundary_ambiguous)
        self.assertLess(result.confidence, 0.3)

    def test_sector_center_is_not_boundary_ambiguous(self) -> None:
        result = self.classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=self.reach_point(45.0),
        )

        self.assertEqual(
            result.direction,
            MotionDirection.RIGHT_FRONT,
        )
        self.assertTrue(result.valid)
        self.assertFalse(result.boundary_ambiguous)
        self.assertGreaterEqual(result.confidence, 0.3)

    def test_short_vector_remains_unknown(self) -> None:
        result = self.classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=(0.01, 0.0),
        )

        self.assertEqual(
            result.direction,
            MotionDirection.UNKNOWN,
        )
        self.assertFalse(result.valid)
        self.assertFalse(result.boundary_ambiguous)


if __name__ == "__main__":
    unittest.main()
