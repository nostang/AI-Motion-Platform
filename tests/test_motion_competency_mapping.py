from __future__ import annotations

import unittest

from src.competency.motion_competency_mapping import (
    build_motion_competency_axes,
    build_motion_competency_comparison,
)


class MotionCompetencyMappingTests(unittest.TestCase):
    def test_builds_five_ready_axes_with_traceable_evidence(self) -> None:
        reports = {
            "footwork": {
                "skill_score": {
                    "movement_completion": {"score": 25, "max_score": 25},
                    "recovery_speed": {"score": 18, "max_score": 25},
                    "motion_quality": {"score": 22, "max_score": 25},
                    "body_stability": {"score": 12, "max_score": 25},
                },
                "assessment_metrics": {
                    "direction_coverage": {
                        "score": 18.75,
                        "max_score": 25,
                    },
                },
            },
            "serve": {
                "score_breakdown": {
                    "preparation_stability": {"score": 25, "max_score": 25},
                    "swing_completeness": {"score": 22, "max_score": 25},
                    "body_coordination": {"score": 20, "max_score": 25},
                    "motion_smoothness": {"score": 7, "max_score": 25},
                },
            },
            "clear": {
                "score_breakdown": {
                    "sideways_preparation": {"score": 25, "max_score": 25},
                    "weight_transfer": {"score": 25, "max_score": 25},
                    "non_racket_arm_balance": {"score": 20, "max_score": 25},
                    "swing_smoothness": {"score": 16, "max_score": 25},
                },
            },
        }

        result = build_motion_competency_axes(reports)

        self.assertEqual(result["status"], "READY")
        self.assertEqual(len(result["axes"]), 5)
        self.assertEqual(
            result["radar_chart"]["labels"],
            ["移動能力", "準備品質", "揮拍機制", "身體協調", "動作穩定"],
        )
        self.assertEqual(
            result["radar_chart"]["scores"],
            [83.8, 100.0, 76.0, 86.7, 38.0],
        )
        self.assertIsNone(result["overall_score"])

        progress = {
            motion_type: {
                "status": "READY",
                "comparison_status": "COMPARABLE",
            }
            for motion_type in ("footwork", "serve", "clear")
        }

        comparison = build_motion_competency_comparison(
            reports,
            reports,
            progress,
        )

        self.assertEqual(
            comparison["comparison_status"],
            "COMPARABLE",
        )
        self.assertEqual(len(comparison["changes"]), 5)
        self.assertTrue(
            all(
                item["change"] == 0
                and item["direction"] == "UNCHANGED"
                for item in comparison["changes"]
            )
        )

    def test_missing_source_keeps_axis_incomplete(self) -> None:
        result = build_motion_competency_axes({})

        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertTrue(
            all(axis["score"] is None for axis in result["axes"])
        )


if __name__ == "__main__":
    unittest.main()
