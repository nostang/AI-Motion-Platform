"""Application service for AI Motion pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from src.config import MODEL_PATH
from src.api.explainable_pose import (
    sanitize_explainable_pose,
    sanitize_motion_sequence,
)
from src.api.footwork_reach_grid import sanitize_footwork_reach_grid
from src.api.keyframe_storage import KeyframeStorageService
from src.motion import MotionContext, get_motion_analyzer
from src.visualization.clear_keyframes import extract_clear_keyframes
from src.visualization.clear_motion_sequence_keyframes import (
    extract_clear_motion_sequence_keyframes,
    extract_serve_motion_sequence_keyframes,
)
from src.visualization.footwork_reach_grid_keyframes import (
    extract_footwork_reach_grid_keyframes,
)
from src.validator.motion_input_validation import (
    MotionInputValidationRejected,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist_clear_keyframes(
    assessment_id: str,
    video_path: Path,
    output_dir: Path,
) -> dict | None:
    visualization_path = output_dir / "clear_pose_visualization.json"
    sequence_path = output_dir / "clear_motion_sequence.json"
    if not visualization_path.is_file() and not sequence_path.is_file():
        return None

    storage = KeyframeStorageService()
    durable: dict[str, dict] = {}

    if visualization_path.is_file():
        try:
            visualization = json.loads(
                visualization_path.read_text(encoding="utf-8")
            )
            keyframe_dir = output_dir / "keyframes"
            manifest = extract_clear_keyframes(
                video_path,
                visualization,
                keyframe_dir,
            )
            manifest["visualization"] = sanitize_explainable_pose(
                visualization,
                "clear",
            )
            durable["keyframes"] = storage.persist(
                assessment_id,
                keyframe_dir,
                manifest,
            )
            print(
                "[KEYFRAME_V1]",
                assessment_id,
                durable["keyframes"].get("status"),
                durable["keyframes"].get("performance_ms") or {},
            )
        except Exception as exc:
            print("[KEYFRAME_V1_NOT_READY]", assessment_id, type(exc).__name__)

    if sequence_path.is_file():
        try:
            sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
            sequence_dir = output_dir / "motion_sequence"
            manifest = extract_clear_motion_sequence_keyframes(
                video_path,
                sequence,
                sequence_dir,
            )
            manifest["sequence"] = sanitize_motion_sequence(
                sequence,
                "clear",
            )
            durable["sequence"] = storage.persist_sequence(
                assessment_id,
                sequence_dir,
                manifest,
            )
            print(
                "[MOTION_SEQUENCE_V1_1]",
                assessment_id,
                durable["sequence"].get("status"),
                durable["sequence"].get("performance_ms") or {},
            )
        except Exception as exc:
            print(
                "[MOTION_SEQUENCE_V1_1_NOT_READY]",
                assessment_id,
                type(exc).__name__,
            )

    return durable or None


def _persist_serve_motion_sequence(
    assessment_id: str,
    video_path: Path,
    output_dir: Path,
) -> dict | None:
    sequence_path = output_dir / "serve_motion_sequence.json"
    if not sequence_path.is_file():
        return None

    try:
        sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
        sequence_dir = output_dir / "motion_sequence"
        manifest = extract_serve_motion_sequence_keyframes(
            video_path,
            sequence,
            sequence_dir,
        )
        manifest["sequence"] = sanitize_motion_sequence(sequence, "serve")
        durable = KeyframeStorageService().persist_sequence(
            assessment_id,
            sequence_dir,
            manifest,
        )
        print(
            "[SERVE_MOTION_SEQUENCE_V1_1]",
            assessment_id,
            durable.get("status"),
            durable.get("performance_ms") or {},
        )
        return durable
    except Exception as exc:
        print(
            "[SERVE_MOTION_SEQUENCE_V1_1_NOT_READY]",
            assessment_id,
            type(exc).__name__,
        )
        return None


def _persist_footwork_reach_grid(
    assessment_id: str,
    video_path: Path,
    output_dir: Path,
) -> dict | None:
    grid_path = output_dir / "footwork_reach_grid.json"
    if not grid_path.is_file():
        return None

    try:
        grid = json.loads(grid_path.read_text(encoding="utf-8"))
        keyframe_dir = output_dir / "reach_grid"
        manifest = extract_footwork_reach_grid_keyframes(
            video_path,
            grid,
            keyframe_dir,
        )
        manifest["reach_grid"] = sanitize_footwork_reach_grid(grid)
        durable = KeyframeStorageService().persist_reach_grid(
            assessment_id,
            keyframe_dir,
            manifest,
        )
        print(
            "[FOOTWORK_REACH_GRID_V1]",
            assessment_id,
            durable.get("status"),
            durable.get("performance_ms") or {},
        )
        return durable
    except Exception as exc:
        print(
            "[FOOTWORK_REACH_GRID_V1_NOT_READY]",
            assessment_id,
            type(exc).__name__,
        )
        return None


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
            racket_side: str | None = None

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

                raw_racket_side = annotation.get(
                    "racket_side"
                )

                if raw_racket_side:
                    racket_side = str(
                        raw_racket_side
                    ).strip().lower()

                    if racket_side not in {
                        "left",
                        "right",
                    }:
                        raise ValueError(
                            "人工標注的 racket_side "
                            "必須是 left 或 right。"
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
                racket_side=racket_side,
            )

            result = analyzer.run(context)
            report = result["analysis_report"]

            if assessment_type == "clear":
                try:
                    _persist_clear_keyframes(
                        assessment_id,
                        context.video_path,
                        output_dir,
                    )
                except Exception as exc:
                    # Presentation artifacts are fail-soft. A keyframe issue
                    # must never change assessment, scoring, or report status.
                    print(
                        "[KEYFRAME_V1_NOT_READY]",
                        assessment_id,
                        type(exc).__name__,
                    )

            if assessment_type == "serve":
                try:
                    _persist_serve_motion_sequence(
                        assessment_id,
                        context.video_path,
                        output_dir,
                    )
                except Exception as exc:
                    # Serve sequence is presentation-only and fail-soft.
                    print(
                        "[SERVE_MOTION_SEQUENCE_V1_1_NOT_READY]",
                        assessment_id,
                        type(exc).__name__,
                    )

            if assessment_type == "footwork":
                try:
                    _persist_footwork_reach_grid(
                        assessment_id,
                        context.video_path,
                        output_dir,
                    )
                except Exception as exc:
                    # Reach Grid is presentation-only and fail-soft.
                    print(
                        "[FOOTWORK_REACH_GRID_V1_NOT_READY]",
                        assessment_id,
                        type(exc).__name__,
                    )

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

        except MotionInputValidationRejected as exc:
            self.repository.update_status(
                assessment_id,
                processing_status="failed",
                progress=100,
                current_stage="input_validation",
                updated_at=utc_now(),
                completed_at=utc_now(),
                error_message=str(exc),
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
