"""High Clear MVP：影片 → Pose → Event → Features → Assessment → Coach → Report → Validator。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp

from src.assessment.clear_assessment import ClearAssessmentBuilder
from src.coach.clear_coach import build_clear_coach, save_clear_coach
from src.event.clear_event import build_clear_event
from src.features.clear_features import ClearFeatureTracker
from src.overlay import draw_pose_landmarks, draw_status_panel
from src.pose_demo import create_pose_landmarker
from src.report.clear_report import build_clear_report, save_clear_report
from src.validator.clear_validator import (
    save_clear_validation,
    validate_clear_pipeline,
)


def _load_calibration() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parent
        / "config_data"
        / "clear_calibration.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def run_clear_demo(
    *,
    video_id: str,
    video_path: Path,
    model_path: Path,
    window_name: str = "AI Motion - Clear Demo",
    display: bool = True,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = (
        Path(output_dir)
        if output_dir
        else Path(__file__).resolve().parent.parent / "output"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    assessment_path = output_dir / "clear_assessment.json"
    coach_path = output_dir / "clear_coach_evaluation.json"
    report_path = output_dir / "clear_analysis_report.json"
    validation_path = output_dir / "clear_pipeline_validation.json"

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV 無法開啟影片：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_index = 0
    detected_frames = 0
    first_detected_frame: int | None = None
    last_detected_frame: int | None = None

    tracker = ClearFeatureTracker(expected_racket_side="right")

    try:
        with create_pose_landmarker(model_path) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                timestamp_ms = int(frame_index * 1000 / fps)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                result = landmarker.detect_for_video(
                    mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=rgb,
                    ),
                    timestamp_ms,
                )

                pose_detected = bool(result.pose_landmarks)
                overlay_lines: list[str] = []

                if pose_detected:
                    detected_frames += 1

                    if first_detected_frame is None:
                        first_detected_frame = frame_index

                    last_detected_frame = frame_index
                    landmarks = result.pose_landmarks[0]

                    tracker.observe(landmarks, timestamp_ms)
                    draw_pose_landmarks(frame, landmarks)

                    overlay_lines.append(
                        f"Samples: {len(tracker.samples)}"
                    )

                overlay_lines.append(f"Frame: {frame_index}")
                overlay_lines.append(
                    f"Time: {timestamp_ms / 1000.0:.2f}s"
                )

                draw_status_panel(
                    frame,
                    title=f"CLEAR | {video_id}",
                    lines=overlay_lines,
                    detected=pose_detected,
                )

                if display:
                    cv2.imshow(window_name, frame)

                    key = cv2.waitKey(
                        max(1, int(1000 / fps))
                    ) & 0xFF

                    if key in (ord("q"), 27):
                        break

                frame_index += 1
    finally:
        cap.release()

        if display:
            cv2.destroyAllWindows()

    event = build_clear_event(
        first_detected_frame=first_detected_frame,
        last_detected_frame=last_detected_frame,
        total_frames=frame_index,
        detected_frames=detected_frames,
        fps=fps,
    )

    features = tracker.build()

    assessment = ClearAssessmentBuilder(
        _load_calibration()
    ).build(
        video_id=video_id,
        source_video=str(video_path),
        total_frames=frame_index,
        detected_frames=detected_frames,
        event=event.to_dict(),
        features=features,
    )

    ClearAssessmentBuilder.save(
        assessment,
        assessment_path,
    )

    coach = build_clear_coach(assessment)
    save_clear_coach(
        coach,
        coach_path,
    )

    report = build_clear_report(
        assessment,
        coach,
    )
    save_clear_report(
        report,
        report_path,
    )

    validation = validate_clear_pipeline(
        assessment,
        coach,
        report,
    )
    save_clear_validation(
        validation,
        validation_path,
    )

    print("\n=== AI Motion High Clear MVP 完成 ===")
    print(f"總處理幀數：{frame_index}")
    print(f"成功偵測幀數：{detected_frames}")
    print(f"Assessment JSON：{assessment_path}")
    print(f"Coach JSON：{coach_path}")
    print(f"Analysis Report：{report_path}")
    print(
        "Pipeline Validator："
        f"{validation['status']} | "
        f"Errors {validation['summary']['error_count']} | "
        f"Warnings {validation['summary']['warning_count']}"
    )
    print(f"Clear Overall Score：{assessment.get('overall_score')}")
    print(f"Coach Status：{coach.get('overall_status')}")
    print(
        "Evaluation Status："
        f"{assessment.get('evaluation_status')}"
    )
    print(
        "Calibration Config："
        f"{assessment.get('config_version')}"
    )

    return {
        "assessment": assessment,
        "coach_evaluation": coach,
        "analysis_report": report,
        "pipeline_validation": validation,
        "artifact_paths": {
            "assessment": str(assessment_path),
            "coach_evaluation": str(coach_path),
            "analysis_report": str(report_path),
            "pipeline_validation": str(validation_path),
        },
    }
