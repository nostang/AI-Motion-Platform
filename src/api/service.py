"""Application service for AI Motion pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.config import MODEL_PATH
from src.motion import MotionContext, get_motion_analyzer


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MotionAssessmentService:
    def __init__(self, repository) -> None:
        self.repository = repository

    def process(self, assessment_id: str) -> None:
        task = self.repository.get_analysis(assessment_id)
        if task is None:
            return

        assessment_type = str(task["assessment_type"]).strip().lower()
        output_dir = self.repository.task_dir(assessment_id) / "output"

        self.repository.update_status(
            assessment_id,
            processing_status="processing",
            progress=10,
            current_stage="pose_detection",
            updated_at=utc_now(),
        )

        try:
            analyzer = get_motion_analyzer(assessment_type)
            context = MotionContext(
                video_id=f"API_{assessment_type.upper()}_{assessment_id}",
                video_path=Path(task["video_path"]),
                model_path=MODEL_PATH,
                window_name=f"AI Motion - {assessment_type.title()} - {assessment_id}",
                display=False,
                output_dir=output_dir,
            )

            result = analyzer.run(context)
            report = result["analysis_report"]

            self.repository.save_report(
                assessment_id,
                report,
            )

            self.repository.update_status(
                assessment_id,
                processing_status="completed",
                progress=100,
                current_stage="completed",
                updated_at=utc_now(),
                completed_at=utc_now(),
                error_message=None,
            )
        except Exception as exc:
            self.repository.update_status(
                assessment_id,
                processing_status="failed",
                progress=100,
                current_stage="analysis",
                updated_at=utc_now(),
                completed_at=utc_now(),
                error_message=str(exc),
            )
