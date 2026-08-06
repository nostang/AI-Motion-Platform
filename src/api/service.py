"""Application service that executes the existing AI Motion pipelines."""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from src.api.repository import AssessmentRepository
from src.config import MODEL_PATH
from src.motion import MotionContext, get_motion_analyzer


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MotionAssessmentService:
    def __init__(self, repository: AssessmentRepository) -> None:
        self.repository = repository

    def process(self, assessment_id: str) -> None:
        task = self.repository.get(assessment_id)
        if task is None:
            return

        assessment_type = str(task.get("assessment_type", "")).strip().lower()
        output_dir = self.repository.task_dir(assessment_id) / "output"

        task.update(
            status="processing",
            progress=10,
            current_stage="pose_detection",
            updated_at=utc_now(),
        )
        self.repository.save(task)

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

            task.update(
                status="completed",
                progress=100,
                current_stage="completed",
                updated_at=utc_now(),
                completed_at=utc_now(),
                engine_assessment_id=report.get("assessment_id"),
                report_filename=Path(
                    result["artifact_paths"]["analysis_report"]
                ).name,
                failure=None,
            )
        except Exception as exc:
            task.update(
                status="failed",
                progress=100,
                current_stage="analysis",
                updated_at=utc_now(),
                completed_at=utc_now(),
                failure={
                    "code": "ANALYSIS_FAILED",
                    "message": str(exc),
                    "retryable": True,
                },
            )

        self.repository.save(task)
