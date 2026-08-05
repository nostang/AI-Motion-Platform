import json
import tempfile
import unittest
from pathlib import Path

from src.api.repository import AssessmentRepository


class ApiRepositoryTests(unittest.TestCase):
    def test_task_and_report_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = AssessmentRepository(Path(tmp))
            task = {"assessment_id": "ma_test", "status": "uploaded"}
            repo.save(task)
            self.assertEqual(repo.get("ma_test"), task)
            output = repo.task_dir("ma_test") / "output"
            output.mkdir(parents=True)
            (output / "footwork_analysis_report.json").write_text(
                json.dumps({"assessment_id": "fa_test"}), encoding="utf-8"
            )
            self.assertEqual(repo.report("ma_test")["assessment_id"], "fa_test")

    def test_missing_task_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = AssessmentRepository(Path(tmp))
            self.assertIsNone(repo.get("ma_missing"))


if __name__ == "__main__":
    unittest.main()
