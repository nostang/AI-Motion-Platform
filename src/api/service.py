"""Application service for AI Motion pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from src.config import MODEL_PATH
from src.motion import MotionContext, get_motion_analyzer


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MotionAssessmentService:
    def __init__(self, repository) -> None:
        self.repository = repository

    def process(
        self,
        assessment_id: str,
        use_annotation: bool = False,
    ) -> None:
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
            start_ms: int | None = None
            end_ms: int | None = None
            annotation_source: str | None = None

            if use_annotation:
                annotation_path = (
                    self.repository.task_dir(assessment_id)
                    / "human_annotation.json"
                )

                if not annotation_path.exists():
                    raise FileNotFoundError(
                        "找不到人工標注資料。"
                    )

                annotation = json.loads(
                    annotation_path.read_text(
                        encoding="utf-8"
                    )
                )
                window = annotation.get("window") or {}

                start_ms = int(window["start_ms"])
                end_ms = int(window["end_ms"])

                if end_ms <= start_ms:
                    raise ValueError(
                        "人工標注的 end_ms 必須大於 start_ms。"
                    )

                annotation_source = str(
                    window.get("source") or "HUMAN"
                )

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
                start_ms=start_ms,
                end_ms=end_ms,
                annotation_source=annotation_source,
            )

            result = analyzer.run(context)
            report = result["analysis_report"]

            if use_annotation:
                report_meta = report.setdefault(
                    "meta",
                    {},
                )
                report_meta["analysis_window"] = {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "duration_ms": end_ms - start_ms,
                    "source": annotation_source,
                }
                report_meta[
                    "human_annotation_applied"
                ] = True

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

            # Video Retention V2
            #
            # 原始影片需暫時保留，供分析完成後進行
            # 人工時間標注與重新分析。
            #
            # 正式環境將由獨立清理程序依保存政策刪除，
            # 不可在分析完成後立即移除。
            print(
                "[VIDEO_RETENTION]",
                assessment_id,
                "source video retained for annotation",
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
