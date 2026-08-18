from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.api.service import MotionAssessmentService
from src.validator.motion_input_validation import (
    MotionInputValidationRejected,
)


class FakeRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.status_updates = []
        self.saved_report = None

    def task_dir(self, assessment_id: str) -> Path:
        path = self.root / assessment_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_analysis(self, assessment_id: str):
        return {
            "assessment_id": assessment_id,
            "assessment_type": "serve",
            "video_path": str(
                self.task_dir(assessment_id)
                / "source.mov"
            ),
        }

    def update_status(
        self,
        assessment_id: str,
        **values,
    ) -> None:
        self.status_updates.append(
            (assessment_id, values)
        )

    def save_report(
        self,
        assessment_id: str,
        report,
    ) -> None:
        self.saved_report = report


class CapturingAnalyzer:
    def __init__(self) -> None:
        self.context = None

    def run(self, context):
        self.context = context
        return {
            "analysis_report": {
                "meta": {},
            }
        }


class MotionAnnotationServiceTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = FakeRepository(
            self.root
        )
        self.service = MotionAssessmentService(
            self.repository
        )
        self.analyzer = CapturingAnalyzer()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def save_annotation(
        self,
        *,
        racket_side: str,
    ) -> None:
        path = (
            self.repository.task_dir("ma_test")
            / "human_annotation.json"
        )
        path.write_text(
            json.dumps({
                "window": {
                    "start_ms": 1000,
                    "end_ms": 4000,
                    "source": "HUMAN",
                },
                "racket_side": racket_side,
            }),
            encoding="utf-8",
        )

    def test_passes_human_racket_side_to_analyzer(
        self,
    ) -> None:
        self.save_annotation(
            racket_side="RIGHT",
        )

        with patch(
            "src.api.service.get_motion_analyzer",
            return_value=self.analyzer,
        ):
            self.service.process(
                "ma_test",
                use_annotation=True,
            )

        context = self.analyzer.context

        self.assertIsNotNone(context)
        self.assertEqual(
            context.racket_side,
            "right",
        )
        self.assertEqual(context.start_ms, 1000)
        self.assertEqual(context.end_ms, 4000)
        self.assertEqual(
            context.annotation_source,
            "HUMAN",
        )
        self.assertTrue(
            self.repository.saved_report[
                "meta"
            ]["human_annotation_applied"]
        )
        self.assertEqual(
            self.repository.status_updates[-1][1][
                "processing_status"
            ],
            "completed",
        )

    def test_rejects_invalid_human_racket_side(
        self,
    ) -> None:
        self.save_annotation(
            racket_side="middle",
        )

        with patch(
            "src.api.service.get_motion_analyzer",
            return_value=self.analyzer,
        ):
            self.service.process(
                "ma_test",
                use_annotation=True,
            )

        self.assertIsNone(self.analyzer.context)

        final_status = (
            self.repository.status_updates[-1][1]
        )
        self.assertEqual(
            final_status["processing_status"],
            "failed",
        )
        self.assertIn(
            "left 或 right",
            final_status["error_message"],
        )

    def test_clear_keyframe_failure_does_not_fail_assessment(self) -> None:
        video_path = self.repository.task_dir("ma_test") / "source.mov"
        self.repository.get_analysis = lambda assessment_id: {
            "assessment_id": assessment_id,
            "assessment_type": "clear",
            "video_path": str(video_path),
        }

        with (
            patch(
                "src.api.service.get_motion_analyzer",
                return_value=self.analyzer,
            ),
            patch(
                "src.api.service._persist_clear_keyframes",
                side_effect=RuntimeError("presentation only"),
            ),
        ):
            self.service.process("ma_test")

        self.assertIsNotNone(self.repository.saved_report)
        self.assertEqual(
            self.repository.status_updates[-1][1]["processing_status"],
            "completed",
        )

    def test_serve_sequence_failure_does_not_fail_assessment(self) -> None:
        with (
            patch(
                "src.api.service.get_motion_analyzer",
                return_value=self.analyzer,
            ),
            patch(
                "src.api.service._persist_serve_motion_sequence",
                side_effect=RuntimeError("presentation only"),
            ),
        ):
            self.service.process("ma_test")

        self.assertIsNotNone(self.repository.saved_report)
        self.assertEqual(
            self.repository.status_updates[-1][1]["processing_status"],
            "completed",
        )

    def test_footwork_does_not_create_racket_motion_assets(self) -> None:
        self.repository.get_analysis = lambda assessment_id: {
            "assessment_id": assessment_id,
            "assessment_type": "footwork",
            "video_path": str(self.root / "source.mov"),
        }

        with (
            patch(
                "src.api.service.get_motion_analyzer",
                return_value=self.analyzer,
            ),
            patch("src.api.service._persist_clear_keyframes") as clear_persist,
            patch(
                "src.api.service._persist_serve_motion_sequence"
            ) as serve_persist,
            patch(
                "src.api.service._persist_footwork_reach_grid"
            ) as reach_grid_persist,
        ):
            self.service.process("ma_test")

        clear_persist.assert_not_called()
        serve_persist.assert_not_called()
        reach_grid_persist.assert_called_once()

    def test_footwork_reach_grid_failure_does_not_fail_assessment(self) -> None:
        self.repository.get_analysis = lambda assessment_id: {
            "assessment_id": assessment_id,
            "assessment_type": "footwork",
            "video_path": str(self.root / "source.mov"),
        }

        with (
            patch(
                "src.api.service.get_motion_analyzer",
                return_value=self.analyzer,
            ),
            patch(
                "src.api.service._persist_footwork_reach_grid",
                side_effect=RuntimeError("presentation only"),
            ),
        ):
            self.service.process("ma_test")

        self.assertIsNotNone(self.repository.saved_report)
        self.assertEqual(
            self.repository.status_updates[-1][1]["processing_status"],
            "completed",
        )

    def test_input_validation_rejection_is_retryable_and_saves_no_report(
        self,
    ) -> None:
        result = {
            "status": "NEEDS_REVIEW",
            "message": (
                "目前沒有偵測到足夠明顯的可分析動作，請確認影片內容。"
            ),
            "retryable": True,
        }
        rejecting_analyzer = CapturingAnalyzer()
        rejecting_analyzer.run = lambda context: (_ for _ in ()).throw(
            MotionInputValidationRejected(result)
        )

        with patch(
            "src.api.service.get_motion_analyzer",
            return_value=rejecting_analyzer,
        ):
            self.service.process("ma_test")

        final = self.repository.status_updates[-1][1]
        self.assertIsNone(self.repository.saved_report)
        self.assertEqual(final["processing_status"], "failed")
        self.assertEqual(final["current_stage"], "input_validation")
        self.assertIn("足夠明顯", final["error_message"])


if __name__ == "__main__":
    unittest.main()
