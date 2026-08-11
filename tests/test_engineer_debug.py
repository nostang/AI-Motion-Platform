from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.api.engineer_debug import build_engineer_debug


class EngineerDebugTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "output").mkdir()
        self.config_root = self.root / "config"
        self.config_root.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_json(self, relative: str, value: dict) -> None:
        (self.root / relative).write_text(
            json.dumps(value),
            encoding="utf-8",
        )

    def build(self, motion_type: str) -> dict:
        return build_engineer_debug(
            assessment_id="ma_test",
            motion_type=motion_type,
            task={"status": "completed"},
            task_dir=self.root,
            config_root=self.config_root,
        )

    def test_serve_preserves_manual_and_automatic_side(self) -> None:
        self.write_json(
            "human_annotation.json",
            {
                "window": {"start_ms": 1000, "end_ms": 5000, "duration_ms": 4000},
                "racket_side": "right",
                "action_type": "FOREHAND_SERVE",
                "calibration_eligibility": "INCLUDED",
            },
        )
        self.write_json(
            "output/serve_assessment.json",
            {
                "assessment_type": "serve",
                "pose_detection": {"total_frames": 100, "detected_frames": 95, "detection_rate": .95},
                "event": {"start_ms": 0, "end_ms": 4000},
                "features": {
                    "feature_version": "serve-feature-test",
                    "active_side_estimate": "right",
                    "dominant_hand": {
                        "estimated": "right",
                        "source": "HUMAN_ANNOTATION",
                        "automatic_estimate": {"estimated": "left", "confidence": .8},
                    },
                    "analysis_window": {"start_ms": 1500, "end_ms": 2900},
                    "swing_path_length": 1.2,
                },
                "metrics": {"swing_completeness": {"score": 25, "level": "EXCELLENT"}},
                "overall_score": 80,
            },
        )
        result = self.build("serve")
        self.assertEqual(result["analysis_window"]["start_ms"], 1000)
        self.assertEqual(result["internal_motion_window"]["window"]["start_ms"], 1500)
        self.assertEqual(result["active_side"]["automatic_estimate"]["estimated"], "left")
        self.assertEqual(result["active_side"]["effective_side"], "right")
        self.assertEqual(result["active_side"]["effective_source"], "MANUAL")
        self.assertEqual(result["features"]["raw"]["swing_path_length"], 1.2)
        self.assertEqual(result["scoring_evidence"]["overall_score"], 80)
        self.assertEqual(result["presentation"]["detail"]["kind"], "WINDOWS")
        self.assertEqual(result["presentation"]["score_rows"][0]["score"], 25)
        overview = result["presentation"]["overview_rows"]
        self.assertEqual(len(overview), 6)
        self.assertEqual(overview[0]["value"], "正手發球")
        self.assertEqual(overview[1]["value"], "80 / 100")
        self.assertEqual(overview[2]["value"], "右手 · 人工")

    def test_clear_reports_event_as_internal_window(self) -> None:
        self.write_json(
            "output/clear_assessment.json",
            {
                "assessment_type": "clear",
                "pose_detection": {"total_frames": 50, "detected_frames": 40, "detection_rate": .8},
                "event": {"start_ms": 0, "end_ms": 1800},
                "features": {
                    "feature_version": "clear-feature-test",
                    "racket_side_estimate": "right",
                    "racket_hand": {"estimated": "right", "confidence": .9},
                    "weight_transfer": {"hip_center_shift": .4},
                },
                "metrics": {"weight_transfer": {"score": 14, "level": "FAIR"}},
                "overall_score": 64,
            },
        )
        result = self.build("clear")
        self.assertEqual(result["internal_motion_window"]["kind"], "CLEAR_EVENT_WINDOW")
        self.assertEqual(result["active_side"]["effective_source"], "AUTO")
        self.assertEqual(result["pose_quality"]["detected_frames"], 40)
        self.assertEqual(result["features"]["raw"]["weight_transfer"]["hip_center_shift"], .4)
        self.assertEqual(
            result["presentation"]["score_rows"][0]["measurements"][0]["value"],
            .4,
        )

    def test_footwork_exposes_events_and_stored_scores(self) -> None:
        self.write_json(
            "output/footwork_assessment.json",
            {
                "assessment_type": "footwork",
                "pose_detection": {"total_frames": 80, "detected_frames": 72, "detection_rate": .9},
                "events": [{
                    "event_id": 1,
                    "direction": "RIGHT_FRONT",
                    "clip_start_ms": 100,
                    "clip_end_ms": 900,
                    "motion_features": {"features": {"MF001": {"mean": 3.2}}},
                }],
                "motion_feature_library": {"version": "test"},
                "recovery_speed": {"score": 20, "thresholds": {"fast": .6}},
                "direction_coverage_assessment": {"score": 25},
                "body_stability": {"score": 14, "feature_levels": []},
                "motion_quality": {"score": 22, "aggregate_value": .4},
                "calibration_snapshot": {"config_version": "test"},
            },
        )
        result = self.build("footwork")
        self.assertEqual(result["internal_motion_window"]["events"][0]["direction"], "RIGHT_FRONT")
        self.assertEqual(result["scoring_evidence"]["recovery_speed"]["score"], 20)
        self.assertEqual(result["scoring_evidence"]["calibration_snapshot"]["config_version"], "test")
        self.assertEqual(result["active_side"]["effective_source"], "NOT_APPLICABLE")
        self.assertEqual(result["presentation"]["detail"]["kind"], "EVENTS")
        self.assertEqual(
            result["presentation"]["detail"]["rows"][0]["direction"],
            "RIGHT_FRONT",
        )
        self.assertIn("1 Events", result["presentation"]["overview_rows"][-1]["value"])
        diagnostic = result["presentation"]["score_rows"][-1]
        self.assertEqual(diagnostic["metric"], "direction_coverage")
        self.assertFalse(diagnostic["included_in_overall"])


if __name__ == "__main__":
    unittest.main()
