from __future__ import annotations

import unittest

from src.progress.progress_engine import ProgressEngine


def footwork_report(
    *,
    recovery: float | None = 20.0,
    recovery_level: str | None = "GOOD",
    body: float | None = 19.756,
    body_level: str | None = "FAIR",
) -> dict:
    return {
        "skill_score": {
            "recovery_speed": {
                "score": recovery,
                "max_score": 25,
                "level": recovery_level,
            },
            "body_stability": {
                "score": body,
                "max_score": 25,
                "level": body_level,
            },
        },
        "assessment_metrics": {
            "direction_coverage": {
                "score": 21.0,
                "max_score": 25,
                "level": "GOOD",
            },
        },
    }


def history_item(
    assessment_id: str,
    *,
    overall_score: float,
    report: dict,
    created_at: str,
    model_version: str = "footwork-v1",
    rule_version: str = "footwork-calibration-v1.3",
) -> dict:
    return {
        "assessment_id": assessment_id,
        "assessment_type": "footwork",
        "overall_score": overall_score,
        "report": report,
        "created_at": created_at,
        "model_version": model_version,
        "rule_version": rule_version,
    }


class ProgressEngineV2ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ProgressEngine()

    def test_v1_overall_comparison_remains_compatible(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report=footwork_report(),
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report=footwork_report(),
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["change"], 4.5)
        self.assertEqual(result["direction"], "IMPROVED")

    def test_v2_extracts_footwork_dimensions(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report=footwork_report(
                    recovery=18.0,
                    recovery_level="FAIR",
                    body=18.4,
                    body_level="FAIR",
                ),
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report=footwork_report(
                    recovery=21.0,
                    recovery_level="GOOD",
                    body=19.756,
                    body_level="FAIR",
                ),
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        dimensions = result["dimensions"]

        self.assertIn("recovery_speed", dimensions)
        self.assertIn("body_stability", dimensions)
        self.assertIn("direction_coverage", dimensions)

    def test_v2_compares_dimension_scores(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report=footwork_report(
                    recovery=18.0,
                    body=18.4,
                ),
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report=footwork_report(
                    recovery=21.0,
                    body=19.756,
                ),
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        recovery = result["dimensions"]["recovery_speed"]
        body = result["dimensions"]["body_stability"]

        self.assertEqual(recovery["current"]["score"], 21.0)
        self.assertEqual(recovery["reference"]["score"], 18.0)
        self.assertEqual(recovery["change"], 3.0)
        self.assertEqual(recovery["direction"], "IMPROVED")

        self.assertAlmostEqual(
            body["current"]["score"],
            19.756,
            places=6,
        )
        self.assertAlmostEqual(
            body["reference"]["score"],
            18.4,
            places=6,
        )
        self.assertAlmostEqual(
            body["change"],
            1.356,
            places=6,
        )
        self.assertEqual(body["direction"], "IMPROVED")

    def test_v2_preserves_continuous_score_and_fair_level(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report=footwork_report(body=18.4),
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report=footwork_report(
                    body=19.756,
                    body_level="FAIR",
                ),
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        body = result["dimensions"]["body_stability"]

        self.assertAlmostEqual(
            body["current"]["score"],
            19.756,
            places=6,
        )
        self.assertEqual(
            body["current"]["level"],
            "FAIR",
        )

    def test_v2_missing_dimension_is_not_interpreted(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report=footwork_report(body=None, body_level=None),
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report=footwork_report(body=19.756),
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        body = result["dimensions"]["body_stability"]

        self.assertEqual(
            body["comparison_status"],
            "NOT_COMPARABLE",
        )
        self.assertIsNone(body["change"])
        self.assertEqual(
            body["direction"],
            "NOT_INTERPRETED",
        )

    def test_v2_version_mismatch_does_not_interpret_dimension_delta(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report=footwork_report(body=18.4),
                created_at="2026-08-01T00:00:00+00:00",
                rule_version="footwork-calibration-v1.2",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report=footwork_report(body=19.756),
                created_at="2026-08-18T00:00:00+00:00",
                rule_version="footwork-calibration-v1.3",
            ),
        ]

        result = self.engine.compare(history)

        body = result["dimensions"]["body_stability"]

        self.assertAlmostEqual(
            body["change"],
            1.356,
            places=6,
        )
        self.assertEqual(
            body["comparison_status"],
            "COMPARISON_VERSION_MISMATCH",
        )
        self.assertEqual(
            body["direction"],
            "NOT_INTERPRETED",
        )


    def test_v2_extracts_clear_score_breakdown(self) -> None:
        report = {
            "assessment_type": "clear",
            "score_breakdown": {
                "sideways_preparation": {
                    "score": 16,
                    "max_score": 25,
                    "level": "POOR",
                },
                "weight_transfer": {
                    "score": 14,
                    "max_score": 25,
                    "level": "FAIR",
                },
            },
        }

        dimensions = self.engine._extract_dimensions(report)

        self.assertEqual(
            dimensions["sideways_preparation"],
            {
                "score": 16.0,
                "max_score": 25.0,
                "level": "POOR",
            },
        )
        self.assertEqual(
            dimensions["weight_transfer"]["score"],
            14.0,
        )

    def test_v2_extracts_serve_score_breakdown(self) -> None:
        report = {
            "assessment_type": "serve",
            "score_breakdown": {
                "preparation_stability": {
                    "score": 18,
                    "max_score": 25,
                    "level": "FAIR",
                },
                "motion_smoothness": {
                    "score": 22,
                    "max_score": 25,
                    "level": "GOOD",
                },
            },
        }

        dimensions = self.engine._extract_dimensions(report)

        self.assertEqual(
            dimensions["preparation_stability"]["score"],
            18.0,
        )
        self.assertEqual(
            dimensions["preparation_stability"]["level"],
            "FAIR",
        )
        self.assertEqual(
            dimensions["motion_smoothness"]["score"],
            22.0,
        )
        self.assertEqual(
            dimensions["motion_smoothness"]["level"],
            "GOOD",
        )

    def test_v2_primary_dimension_section_has_precedence(self) -> None:
        report = {
            "skill_score": {
                "body_stability": {
                    "score": 19.756,
                    "max_score": 25,
                    "level": "FAIR",
                },
            },
            "score_breakdown": {
                "body_stability": {
                    "score": 12,
                    "max_score": 25,
                    "level": "POOR",
                },
            },
        }

        dimensions = self.engine._extract_dimensions(report)

        self.assertEqual(
            dimensions["body_stability"]["score"],
            19.756,
        )
        self.assertEqual(
            dimensions["body_stability"]["level"],
            "FAIR",
        )


    def test_v2_highlights_largest_improvement(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report={
                    "skill_score": {
                        "recovery_speed": {
                            "score": 18.0,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                        "body_stability": {
                            "score": 18.4,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                    },
                },
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=84.5,
                report={
                    "skill_score": {
                        "recovery_speed": {
                            "score": 21.0,
                            "max_score": 25,
                            "level": "GOOD",
                        },
                        "body_stability": {
                            "score": 19.756,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                    },
                },
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        highlight = result["highlights"]["largest_improvement"]

        self.assertEqual(
            highlight["dimension_id"],
            "recovery_speed",
        )
        self.assertEqual(highlight["change"], 3.0)
        self.assertEqual(highlight["direction"], "IMPROVED")
        self.assertEqual(highlight["reference_score"], 18.0)
        self.assertEqual(highlight["current_score"], 21.0)

    def test_v2_highlights_largest_decline(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=82.0,
                report={
                    "skill_score": {
                        "recovery_speed": {
                            "score": 20.0,
                            "max_score": 25,
                            "level": "GOOD",
                        },
                        "body_stability": {
                            "score": 21.0,
                            "max_score": 25,
                            "level": "GOOD",
                        },
                    },
                },
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=80.0,
                report={
                    "skill_score": {
                        "recovery_speed": {
                            "score": 19.0,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                        "body_stability": {
                            "score": 17.5,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                    },
                },
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        highlight = result["highlights"]["largest_decline"]

        self.assertEqual(
            highlight["dimension_id"],
            "body_stability",
        )
        self.assertEqual(highlight["change"], -3.5)
        self.assertEqual(highlight["direction"], "DECLINED")
        self.assertEqual(highlight["reference_score"], 21.0)
        self.assertEqual(highlight["current_score"], 17.5)

    def test_v2_unchanged_dimension_is_not_a_highlight(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report={
                    "skill_score": {
                        "body_stability": {
                            "score": 19.756,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                    },
                },
                created_at="2026-08-01T00:00:00+00:00",
            ),
            history_item(
                "ma_new",
                overall_score=80.0,
                report={
                    "skill_score": {
                        "body_stability": {
                            "score": 19.756,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                    },
                },
                created_at="2026-08-18T00:00:00+00:00",
            ),
        ]

        result = self.engine.compare(history)

        self.assertIsNone(
            result["highlights"]["largest_improvement"]
        )
        self.assertIsNone(
            result["highlights"]["largest_decline"]
        )

    def test_v2_version_mismatch_dimensions_are_not_highlighted(self) -> None:
        history = [
            history_item(
                "ma_old",
                overall_score=80.0,
                report={
                    "skill_score": {
                        "body_stability": {
                            "score": 12.0,
                            "max_score": 25,
                            "level": "POOR",
                        },
                    },
                },
                created_at="2026-08-01T00:00:00+00:00",
                rule_version="footwork-calibration-v1.2",
            ),
            history_item(
                "ma_new",
                overall_score=84.0,
                report={
                    "skill_score": {
                        "body_stability": {
                            "score": 19.756,
                            "max_score": 25,
                            "level": "FAIR",
                        },
                    },
                },
                created_at="2026-08-18T00:00:00+00:00",
                rule_version="footwork-calibration-v1.3",
            ),
        ]

        result = self.engine.compare(history)

        self.assertEqual(
            result["dimensions"]["body_stability"]["direction"],
            "NOT_INTERPRETED",
        )
        self.assertIsNone(
            result["highlights"]["largest_improvement"]
        )
        self.assertIsNone(
            result["highlights"]["largest_decline"]
        )


if __name__ == "__main__":
    unittest.main()
