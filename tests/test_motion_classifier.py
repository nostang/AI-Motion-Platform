from __future__ import annotations

import unittest
from math import cos, radians, sin

from src.classification.motion_classifier import (
    MotionClassifier,
    MotionDirection,
)
from src.config import (
    CALIBRATION_CONFIG_VERSION,
    DIRECTION_LEFT_BACK_BOUNDARY_DEGREES,
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

    def test_calibrated_left_back_boundary_corrects_natural_reach(self) -> None:
        classifier = MotionClassifier(
            mirror_x=False,
            x_scale=1.0,
            y_scale=1.0,
            min_vector_length=0.035,
            min_confidence=0.3,
            left_back_boundary_degrees=DIRECTION_LEFT_BACK_BOUNDARY_DEGREES,
        )

        result = classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=self.reach_point(-165.19120760822864),
        )

        self.assertEqual(result.direction, MotionDirection.LEFT_BACK)
        self.assertTrue(result.valid)
        self.assertTrue(result.boundary_ambiguous)

    def test_calibrated_left_back_boundary_is_explicit_on_both_sides(self) -> None:
        classifier = MotionClassifier(
            mirror_x=False,
            x_scale=1.0,
            y_scale=1.0,
            min_vector_length=0.035,
            min_confidence=0.3,
            left_back_boundary_degrees=DIRECTION_LEFT_BACK_BOUNDARY_DEGREES,
        )

        left = classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=self.reach_point(-168.751),
        )
        left_back = classifier.classify(
            center_reference=(0.0, 0.0),
            reach_point=self.reach_point(-168.749),
        )

        self.assertEqual(left.direction, MotionDirection.LEFT)
        self.assertEqual(left_back.direction, MotionDirection.LEFT_BACK)

    def test_calibrated_left_back_boundary_keeps_other_direction_centers(self) -> None:
        classifier = MotionClassifier(
            mirror_x=False,
            x_scale=1.0,
            y_scale=1.0,
            min_vector_length=0.035,
            min_confidence=0.3,
            left_back_boundary_degrees=DIRECTION_LEFT_BACK_BOUNDARY_DEGREES,
        )
        expected = {
            0.0: MotionDirection.RIGHT,
            45.0: MotionDirection.RIGHT_FRONT,
            90.0: MotionDirection.FRONT,
            135.0: MotionDirection.LEFT_FRONT,
            179.0: MotionDirection.LEFT,
            -135.0: MotionDirection.LEFT_BACK,
            -90.0: MotionDirection.BACK,
            -45.0: MotionDirection.RIGHT_BACK,
        }

        for angle, direction in expected.items():
            with self.subTest(angle=angle):
                result = classifier.classify(
                    center_reference=(0.0, 0.0),
                    reach_point=self.reach_point(angle),
                )
                self.assertEqual(result.direction, direction)

    def test_production_boundary_is_versioned(self) -> None:
        self.assertEqual(DIRECTION_LEFT_BACK_BOUNDARY_DEGREES, -168.75)
        self.assertEqual(CALIBRATION_CONFIG_VERSION, "footwork-calibration-v1.4")


if __name__ == "__main__":
    unittest.main()
