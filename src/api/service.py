"""Application service that executes the existing AI Motion pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.api.repository import AssessmentRepository
from src.config import MODEL_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MotionAssessmentService:
    def __init__(self, repository: AssessmentRepository) -> None:
        self.repository = repository

    def process(self, assessment_id: str) -> None:
        from src.pose_demo import run_pose_demo
        task = self.repository.get(assessment_id)
        if task is None:
            return
        task.update(status="processing", progress=10, current_stage="pose_detection", updated_at=utc_now())
        self.repository.save(task)
        try:
            result = run_pose_demo(
                video_path=Path(task["video_path"]),
                model_path=MODEL_PATH,
                window_name=f"AI Motion - {assessment_id}",
                display=False,
                output_dir=self.repository.task_dir(assessment_id) / "output",
            )
            report = result["analysis_report"]
            task.update(
                status="completed",
                progress=100,
                current_stage="completed",
                updated_at=utc_now(),
                completed_at=utc_now(),
                engine_assessment_id=report.get("assessment_id"),
                failure=None,
            )
        except Exception as exc:  # API boundary converts internal errors to contract state.
            task.update(
                status="failed",
                progress=100,
                current_stage="analysis",
                updated_at=utc_now(),
                completed_at=utc_now(),
                failure={"code": "ANALYSIS_FAILED", "message": str(exc), "retryable": True},
            )
        self.repository.save(task)
