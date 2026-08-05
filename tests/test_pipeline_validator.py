"""Pipeline Validator Module smoke tests。"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from src.validator import PipelineValidationError, PipelineValidator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


class PipelineValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assessment = cls._load("footwork_assessment.json")
        cls.coach = cls._load("coach_evaluation.json")
        cls.report = cls._load("footwork_analysis_report.json")
        cls.review = cls._load("footwork_review_package.json")
        cls.validator = PipelineValidator()

    @staticmethod
    def _load(name: str) -> dict:
        return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))

    def test_current_pipeline_outputs_pass(self) -> None:
        result = self.validator.validate(
            self.assessment,
            self.coach,
            self.report,
            self.review,
            raise_on_error=True,
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual(0, result["summary"]["error_count"])

    def test_assessment_id_mismatch_fails(self) -> None:
        coach = copy.deepcopy(self.coach)
        coach["assessment_id"] = "mismatch"
        result = self.validator.validate(
            self.assessment,
            coach,
            self.report,
            self.review,
        )
        self.assertEqual("FAIL", result["status"])
        self.assertTrue(
            any(issue["field"] == "assessment_id" for issue in result["issues"])
        )

    def test_missing_required_field_raises_when_enabled(self) -> None:
        report = copy.deepcopy(self.report)
        del report["summary"]
        with self.assertRaises(PipelineValidationError):
            self.validator.validate(
                self.assessment,
                self.coach,
                report,
                self.review,
                raise_on_error=True,
            )

    def test_review_event_mismatch_fails(self) -> None:
        review = copy.deepcopy(self.review)
        review["events"] = review["events"][:-1]
        result = self.validator.validate(
            self.assessment,
            self.coach,
            self.report,
            review,
        )
        self.assertTrue(any(issue["code"] == "PV504" for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
