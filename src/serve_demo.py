"""Serve MVP：影片 → Pose → Features → Assessment → Coach → Report。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp

from src.assessment.serve_assessment import ServeAssessmentBuilder
from src.coach.serve_coach import build_serve_coach, save_serve_coach
from src.event.serve_event import ServeEvent
from src.features.serve_features import ServeFeatureTracker
from src.pose_demo import create_pose_landmarker
from src.overlay import draw_pose_landmarks, draw_status_panel
from src.report.serve_report import build_serve_report, save_serve_report
from src.validator.serve_validator import validate_serve_pipeline, save_serve_validation
from src.validator.motion_input_validation import (
    MotionInputValidator,
    require_motion_input_ready,
    save_motion_input_validation,
)
from src.visualization.clear_motion_sequence import (
    build_serve_motion_sequence,
    save_clear_motion_sequence,
)


def _load_calibration() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "config_data" / "serve_calibration.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_serve_demo(
    *, video_id: str, video_path: Path, model_path: Path,
    window_name: str = "AI Motion - Serve Demo", display: bool = True,
    output_dir: Path | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    racket_side: str | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    assessment_path = output_dir / "serve_assessment.json"
    coach_path = output_dir / "serve_coach_evaluation.json"
    report_path = output_dir / "serve_analysis_report.json"
    validation_path = output_dir / "serve_pipeline_validation.json"
    motion_sequence_path = output_dir / "serve_motion_sequence.json"
    input_validation_path = output_dir / "motion_input_validation.json"

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV 無法開啟影片：{video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    analysis_start_ms = max(0, int(start_ms or 0))
    analysis_end_ms = (
        int(end_ms)
        if end_ms is not None
        else None
    )

    if (
        analysis_end_ms is not None
        and analysis_end_ms <= analysis_start_ms
    ):
        cap.release()
        raise ValueError(
            "人工標注的 end_ms 必須大於 start_ms。"
        )

    source_start_frame = int(
        analysis_start_ms * fps / 1000
    )
    source_end_frame = (
        int(analysis_end_ms * fps / 1000)
        if analysis_end_ms is not None
        else None
    )

    for skipped_source_frame in range(source_start_frame):
        ok, _ = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(
                "OpenCV 無法循序讀取至人工標注的 start frame："
                f"{skipped_source_frame}"
            )

    frame_index = 0
    source_frame_index = source_start_frame
    detected_frames = 0
    first_detected_frame: int | None = None
    last_detected_frame: int | None = None
    tracker = ServeFeatureTracker(
        racket_side=racket_side,
    )
    input_validator = MotionInputValidator("serve")

    try:
        with create_pose_landmarker(model_path) as landmarker:
            while True:
                if (
                    source_end_frame is not None
                    and source_frame_index
                    > source_end_frame
                ):
                    break

                ok, frame = cap.read()
                if not ok:
                    break
                timestamp_ms = int(frame_index * 1000 / fps)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms
                )
                pose_detected = bool(result.pose_landmarks)
                landmarks = (
                    result.pose_landmarks[0]
                    if pose_detected
                    else None
                )
                input_validator.observe(landmarks)
                overlay_lines: list[str] = []
                if pose_detected:
                    detected_frames += 1
                    if first_detected_frame is None:
                        first_detected_frame = frame_index
                    last_detected_frame = frame_index
                    tracker.observe(
                        landmarks,
                        timestamp_ms,
                        analysis_frame_index=frame_index,
                        source_frame_index=source_frame_index,
                    )
                    draw_pose_landmarks(frame, landmarks)
                    overlay_lines.append(f"Samples: {len(tracker.samples)}")
                overlay_lines.append(f"Frame: {frame_index}")
                overlay_lines.append(f"Time: {timestamp_ms / 1000.0:.2f}s")
                draw_status_panel(
                    frame,
                    title=f"SERVE | {video_id}",
                    lines=overlay_lines,
                    detected=pose_detected,
                )
                if display:
                    cv2.imshow(window_name, frame)
                    if cv2.waitKey(max(1, int(1000 / fps))) & 0xFF in (ord("q"), 27):
                        break
                frame_index += 1
                source_frame_index += 1
    finally:
        cap.release()
        if display:
            cv2.destroyAllWindows()

    input_validation = input_validator.build()
    save_motion_input_validation(
        input_validation,
        input_validation_path,
    )
    require_motion_input_ready(input_validation)

    start_frame = first_detected_frame or 0
    end_frame = last_detected_frame if last_detected_frame is not None else max(0, frame_index - 1)
    event = ServeEvent(
        event_id=1,
        start_frame=start_frame,
        end_frame=end_frame,
        start_ms=int(start_frame * 1000 / fps),
        end_ms=int(end_frame * 1000 / fps),
        completed=detected_frames >= 12,
    )
    event_dict = {
        "event_id": event.event_id, "start_frame": event.start_frame,
        "end_frame": event.end_frame, "start_ms": event.start_ms,
        "end_ms": event.end_ms, "duration_seconds": round(event.duration_seconds, 3),
        "completed": event.completed,
    }
    features = tracker.build()
    motion_sequence = build_serve_motion_sequence(
        tracker.samples,
        racket_side=features.get(
            "active_side_estimate",
            tracker.racket_side or "unknown",
        ),
        analysis_window=features.get("analysis_window") or {},
    )
    save_clear_motion_sequence(
        motion_sequence,
        motion_sequence_path,
    )
    assessment = ServeAssessmentBuilder(_load_calibration()).build(
        video_id=video_id, source_video=str(video_path), total_frames=frame_index,
        detected_frames=detected_frames, event=event_dict, features=features,
    )
    ServeAssessmentBuilder.save(assessment, assessment_path)
    coach = build_serve_coach(assessment)
    save_serve_coach(coach, coach_path)
    report = build_serve_report(assessment, coach)
    save_serve_report(report, report_path)
    validation = validate_serve_pipeline(assessment, coach, report)
    save_serve_validation(validation, validation_path)

    print("\n=== AI Motion Serve MVP 完成 ===")
    print(f"總處理幀數：{frame_index}")
    print(f"成功偵測幀數：{detected_frames}")
    print(f"Assessment JSON：{assessment_path}")
    print(f"Serve Overall Score：{assessment.get('overall_score')}")
    print(f"Coach Status：{coach.get('overall_status')}")
    print(f"Analysis Report：{report_path}")
    print(f"Pipeline Validator：{validation['status']} | Errors {validation['summary']['error_count']} | Warnings {validation['summary']['warning_count']}")
    print(f"Calibration Config：{assessment['config_version']}")

    return {
        "assessment": assessment, "coach_evaluation": coach,
        "analysis_report": report, "pipeline_validation": validation,
        "artifact_paths": {
            "motion_input_validation": str(input_validation_path),
            "motion_sequence": str(motion_sequence_path),
            "assessment": str(assessment_path), "coach_evaluation": str(coach_path),
            "analysis_report": str(report_path), "pipeline_validation": str(validation_path),
        },
    }
