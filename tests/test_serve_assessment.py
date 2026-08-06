import json
import unittest
from pathlib import Path

from src.assessment.serve_assessment import ServeAssessmentBuilder


class ServeAssessmentTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "src" / "config_data" / "serve_calibration.json"
        self.builder = ServeAssessmentBuilder(json.loads(path.read_text()))

    def test_builds_evaluated_assessment(self):
        features = {
            "status": "EXTRACTED", "sample_count": 30,
            "preparation_stability_index": 0.01,
            "swing_path_length": 1.0,
            "wrist_extension_range": 0.18,
            "torso_change_degrees": 12.0,
            "wrist_speed_variation": 0.7,
        }
        result = self.builder.build(
            video_id="SV_001", source_video="SV_001.mov",
            total_frames=30, detected_frames=30,
            event={"completed": True}, features=features,
        )
        self.assertEqual(result["assessment_type"], "serve")
        self.assertEqual(result["evaluation_status"], "EVALUATED")
        self.assertIsNotNone(result["overall_score"])
        self.assertEqual(len(result["metrics"]), 4)


if __name__ == "__main__":
    unittest.main()
