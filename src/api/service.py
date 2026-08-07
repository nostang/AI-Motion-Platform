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
                window_name=(
                    f"AI Motion - {assessment_type.title()} - "
                    f"{assessment_id}"
                ),
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

            # Temporary Video Lifecycle V1
            #
            # Assessment 已經成功保存並標記 completed，
            # 此後才刪除暫存影片。
            #
            # Cleanup 失敗不能把有效 Assessment 改成 failed。
            try:
                video_path = Path(task["video_path"])
                video_path.unlink(missing_ok=True)
                self.repository.clear_video_reference(
                    assessment_id
                )
            except Exception as cleanup_exc:
                print(
                    "[VIDEO_CLEANUP_WARNING]",
                    assessment_id,
                    str(cleanup_exc),
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
