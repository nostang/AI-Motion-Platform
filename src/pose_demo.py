"""
AI Motion Pose Demo

功能：
1. 使用 OpenCV 逐幀讀取影片
2. 使用 MediaPipe Pose Landmarker 擷取人體 33 個關鍵點
3. 執行 Center Calibration
4. 執行基礎 Measurement
5. 執行 Footwork Event V2
6. 顯示分析與除錯結果
"""

from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from src.assessment.footwork_assessment import FootworkAssessmentBuilder
from src.coach import CoachEngine
from src.report import ReportBuilder
from src.validator import PipelineValidator
from src.validator.motion_input_validation import (
    MotionInputValidator,
    require_motion_input_ready,
    save_motion_input_validation,
)
from src.review.expert_review import (
    build_expert_review_package,
    save_expert_review_package,
)
from src.calibration import CenterCalibrator
from src.classification.motion_classifier import MotionClassifier
from src.config import (
    CALIBRATION_CONFIG_SNAPSHOT,
    CALIBRATION_CONFIG_VERSION,
    CENTER_CALIBRATION_SECONDS,
    CENTER_REGION_RADIUS,
    ANALYSIS_REPORT_OUTPUT_PATH,
    PIPELINE_VALIDATION_OUTPUT_PATH,
    ASSESSMENT_OUTPUT_PATH,
    COACH_EVALUATION_OUTPUT_PATH,
    REVIEW_PACKAGE_OUTPUT_PATH,
    REVIEW_CLIP_POST_ROLL_MS,
    REVIEW_CLIP_PRE_ROLL_MS,
    REVIEW_CONSENSUS_VOTES_REQUIRED,
    REVIEW_MINIMUM_REVIEWERS,
    DIRECTION_MIN_CONFIDENCE,
    DIRECTION_MIN_VECTOR_LENGTH,
    DIRECTION_LEFT_BACK_BOUNDARY_DEGREES,
    DIRECTION_MIRROR_X,
    DIRECTION_X_SCALE,
    DIRECTION_Y_SCALE,
    FOOTWORK_MOVE_OFFSET_THRESHOLD,
    FOOTWORK_BASE_ZONE_OFFSET_THRESHOLD,
    FOOTWORK_READY_CONFIRM_FRAMES,
    FOOTWORK_RETURN_OFFSET_THRESHOLD,
    FOOTWORK_REVERSAL_CONFIRM_FRAMES,
    FOOTWORK_REVERSAL_MIN_DROP,
    FOOTWORK_BASE_TRANSITION_CONFIRM_FRAMES,
    EXPECTED_FOOTWORK_EVENT_COUNT,
    FOOTWORK_SMOOTHING_WINDOW,
    TRAJECTORY_MAX_POINTS,
)
from src.debug_overlay import FootworkDebugOverlay
from src.drawing import (
    draw_center_region,
    draw_center_status,
    draw_foot_distance,
    draw_footwork_state,
    draw_frame_info,
    draw_hip_center,
    draw_knee_angles,
    draw_pelvis_motion,
    draw_pose_landmarks,
    draw_trajectory,
    get_hip_center_pixel,
)
from src.event.footwork_event import FootworkEvent, FootworkState
from src.features.motion_features import MotionFeatureTracker
from src.measurement import (
    calculate_displacement,
    calculate_hip_center,
    calculate_velocity,
)
from src.visualization.footwork_reach_grid import (
    build_footwork_reach_grid,
    capture_footwork_pose_sample,
    save_footwork_reach_grid,
)


def create_pose_landmarker(
    model_path: Path,
) -> vision.PoseLandmarker:
    """建立 MediaPipe Pose Landmarker。"""

    if not model_path.exists():
        raise FileNotFoundError(
            f"找不到 MediaPipe 模型：{model_path}\n"
            "請確認 models/pose_landmarker_lite.task 已下載。"
        )

    base_options = python.BaseOptions(
        model_asset_path=str(model_path)
    )

    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    return vision.PoseLandmarker.create_from_options(options)


def run_pose_demo(
    video_path: Path,
    model_path: Path,
    window_name: str = "AI Motion Demo",
    *,
    display: bool = True,
    output_dir: Path | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> dict:
    """
    執行完整 Pose Demo。

    主流程：
        讀影片
        → Pose Landmarker
        → Center Calibration
        → Measurement
        → Footwork Event V2
        → Drawing / Debug Overlay
    """

    video_path = Path(video_path)
    model_path = Path(model_path)
    output_dir = Path(output_dir) if output_dir is not None else ASSESSMENT_OUTPUT_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    assessment_output_path = output_dir / "footwork_assessment.json"
    coach_output_path = output_dir / "coach_evaluation.json"
    report_output_path = output_dir / "footwork_analysis_report.json"
    review_output_path = output_dir / "footwork_review_package.json"
    validation_output_path = output_dir / "pipeline_validation.json"
    input_validation_output_path = output_dir / "motion_input_validation.json"
    reach_grid_output_path = output_dir / "footwork_reach_grid.json"

    if not video_path.exists():
        raise FileNotFoundError(f"找不到影片：{video_path}")

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(
            f"OpenCV 無法開啟影片：{video_path}\n"
            "請確認影片沒有損壞，或改成 MP4 格式再測試。"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

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
        success, _ = cap.read()
        if not success:
            cap.release()
            raise RuntimeError(
                "OpenCV 無法循序讀取至人工標注的 start frame："
                f"{skipped_source_frame}"
            )

    frame_index = 0
    source_frame_index = source_start_frame
    detected_frame_count = 0
    pose_samples: list[dict] = []
    initial_ready_frame_index: int | None = None

    previous_hip_center_normalized = None
    previous_timestamp_ms = None

    calibration_frame_count = max(
        1,
        int(fps * CENTER_CALIBRATION_SECONDS),
    )

    center_calibrator = CenterCalibrator(
        calibration_frame_count=calibration_frame_count,
        center_region_radius=CENTER_REGION_RADIUS,
    )

    footwork_event = FootworkEvent(
        move_offset_threshold=FOOTWORK_MOVE_OFFSET_THRESHOLD,
        return_offset_threshold=FOOTWORK_RETURN_OFFSET_THRESHOLD,
        base_zone_offset_threshold=(
            FOOTWORK_BASE_ZONE_OFFSET_THRESHOLD
        ),
        smoothing_window=FOOTWORK_SMOOTHING_WINDOW,
        reversal_confirm_frames=FOOTWORK_REVERSAL_CONFIRM_FRAMES,
        reversal_min_drop=FOOTWORK_REVERSAL_MIN_DROP,
        ready_confirm_frames=FOOTWORK_READY_CONFIRM_FRAMES,
        base_transition_confirm_frames=(
            FOOTWORK_BASE_TRANSITION_CONFIRM_FRAMES
        ),
    )

    motion_feature_tracker = MotionFeatureTracker()
    input_validator = MotionInputValidator("footwork")

    motion_classifier = MotionClassifier(
        mirror_x=DIRECTION_MIRROR_X,
        x_scale=DIRECTION_X_SCALE,
        y_scale=DIRECTION_Y_SCALE,
        min_vector_length=DIRECTION_MIN_VECTOR_LENGTH,
        min_confidence=DIRECTION_MIN_CONFIDENCE,
        left_back_boundary_degrees=(
            DIRECTION_LEFT_BACK_BOUNDARY_DEGREES
        ),
    )

    assessment_builder = FootworkAssessmentBuilder(
        expected_event_count=EXPECTED_FOOTWORK_EVENT_COUNT,
        config_version=CALIBRATION_CONFIG_VERSION,
        calibration_snapshot=CALIBRATION_CONFIG_SNAPSHOT,
        clip_pre_roll_ms=REVIEW_CLIP_PRE_ROLL_MS,
        clip_post_roll_ms=REVIEW_CLIP_POST_ROLL_MS,
    )

    debug_overlay = FootworkDebugOverlay(history_size=6)
    hip_trajectory = deque(maxlen=TRAJECTORY_MAX_POINTS)

    try:
        with create_pose_landmarker(model_path) as landmarker:
            while True:
                if (
                    source_end_frame is not None
                    and source_frame_index
                    > source_end_frame
                ):
                    break

                success, frame = cap.read()
                if not success:
                    break

                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB,
                )

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame,
                )

                timestamp_ms = int(frame_index * 1000 / fps)

                result = landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms,
                )

                landmarks = (
                    result.pose_landmarks[0]
                    if result.pose_landmarks
                    else None
                )
                input_validator.observe(landmarks)

                if result.pose_landmarks:
                    detected_frame_count += 1
                    pose_sample = capture_footwork_pose_sample(
                        landmarks,
                        timestamp_ms,
                        analysis_frame_index=frame_index,
                        source_frame_index=source_frame_index,
                    )
                    if pose_sample is not None:
                        pose_samples.append(pose_sample)

                    draw_pose_landmarks(frame, landmarks)
                    draw_knee_angles(frame, landmarks)
                    draw_foot_distance(frame, landmarks)

                    hip_center_normalized = calculate_hip_center(
                        landmarks[23],
                        landmarks[24],
                    )

                    calibration_result = center_calibrator.update(
                        hip_center_normalized
                    )

                    if calibration_result.calibrated_this_frame:
                        previous_hip_center_normalized = None
                        previous_timestamp_ms = None
                        hip_trajectory.clear()

                    if (
                        calibration_result.calibrated
                        and calibration_result.center_reference is not None
                    ):
                        draw_center_region(
                            frame,
                            calibration_result.center_reference,
                            CENTER_REGION_RADIUS,
                        )

                    draw_center_status(
                        frame,
                        calibrated=calibration_result.calibrated,
                        inside_center=(
                            calibration_result.inside_center_region
                        ),
                        calibration_progress=calibration_result.progress,
                    )

                    if not calibration_result.calibrated:
                        current_state = footwork_event.update(
                            center_calibrated=False,
                            center_offset=None,
                            current_position=None,
                            timestamp_ms=timestamp_ms,
                            frame_index=frame_index,
                        )

                        draw_footwork_state(
                            frame,
                            state_text=current_state.value,
                            event_id=footwork_event.event_id,
                            move_time_seconds=None,
                            recovery_time_seconds=None,
                            total_time_seconds=None,
                        )

                        debug_overlay.draw(
                            frame,
                            event_id=footwork_event.event_id,
                            current_state=current_state.value,
                            frame_index=frame_index,
                            timestamp_ms=timestamp_ms,
                            center_offset=None,
                            smoothed_center_offset=None,
                            pelvis_speed=None,
                            maximum_center_offset=(
                                footwork_event.maximum_center_offset
                            ),
                            reversal_candidate_frames=(
                                footwork_event.reversal_candidate_frames
                            ),
                            reach_frame=footwork_event.reach_frame,
                            reach_timestamp_ms=footwork_event.reach_at_ms,
                            direction=footwork_event.direction,
                            direction_angle_degrees=(
                                footwork_event.direction_angle_degrees
                            ),
                        )

                    else:
                        pelvis_displacement = calculate_displacement(
                            previous_hip_center_normalized,
                            hip_center_normalized,
                        )

                        if previous_timestamp_ms is None:
                            delta_time_seconds = 0.0
                        else:
                            delta_time_seconds = (
                                timestamp_ms - previous_timestamp_ms
                            ) / 1000.0

                        pelvis_velocity = calculate_velocity(
                            pelvis_displacement,
                            delta_time_seconds,
                        )

                        current_state = footwork_event.update(
                            center_calibrated=True,
                            center_offset=calibration_result.center_offset,
                            current_position=hip_center_normalized,
                            timestamp_ms=timestamp_ms,
                            frame_index=frame_index,
                        )

                        if (
                            footwork_event.event_id == 0
                            and current_state == FootworkState.READY
                        ):
                            initial_ready_frame_index = frame_index

                        motion_feature_tracker.observe(
                            event_id=footwork_event.event_id,
                            previous_state=footwork_event.previous_state.value,
                            current_state=footwork_event.state.value,
                            landmarks=landmarks,
                            timestamp_ms=timestamp_ms,
                            smoothed_center_offset=(
                                footwork_event.smoothed_center_offset
                            ),
                            pelvis_speed=(
                                pelvis_velocity["speed"]
                                if pelvis_velocity["valid"]
                                else None
                            ),
                        )

                        draw_footwork_state(
                            frame,
                            state_text=current_state.value,
                            event_id=footwork_event.event_id,
                            move_time_seconds=(
                                footwork_event.get_move_time_seconds()
                            ),
                            recovery_time_seconds=(
                                footwork_event.get_recovery_time_seconds()
                            ),
                            total_time_seconds=(
                                footwork_event.get_total_time_seconds()
                            ),
                        )

                        if footwork_event.state_changed():
                            previous_state = (
                                footwork_event.previous_state.value
                            )
                            current_state_text = footwork_event.state.value

                            print(
                                "[Footwork State] "
                                f"{previous_state} -> {current_state_text} "
                                f"at {timestamp_ms} ms | Frame {frame_index}"
                            )

                            debug_overlay.record_transition(
                                previous_state=previous_state,
                                current_state=current_state_text,
                                timestamp_ms=timestamp_ms,
                                frame_index=frame_index,
                            )

                        if (
                            footwork_event.reach_detected_this_frame
                            and calibration_result.center_reference is not None
                            and footwork_event.reach_position is not None
                        ):
                            direction_result = motion_classifier.classify(
                                center_reference=(
                                    calibration_result.center_reference
                                ),
                                reach_point=footwork_event.reach_position,
                            )

                            footwork_event.set_direction(
                                direction=direction_result.direction.value,
                                angle_degrees=direction_result.angle_degrees,
                                confidence=direction_result.confidence,
                                vector_length=direction_result.vector_length,
                                boundary_ambiguous=(
                                    direction_result.boundary_ambiguous
                                ),
                            )

                            angle_text = (
                                "--"
                                if direction_result.angle_degrees is None
                                else f"{direction_result.angle_degrees:.1f} deg"
                            )

                            print(
                                "[Motion Classification] "
                                f"Event {footwork_event.event_id} | "
                                f"{direction_result.direction.value} | "
                                f"Angle {angle_text} | "
                                f"Vector {direction_result.vector_length:.4f} | "
                                f"Confidence {direction_result.confidence:.2f} | "
                                "Boundary "
                                f"{direction_result.boundary_ambiguous}"
                            )

                        if footwork_event.reach_detected_this_frame:
                            print(
                                "[Reach Event] "
                                f"Event {footwork_event.event_id} | "
                                f"Frame {footwork_event.reach_frame} | "
                                f"{footwork_event.reach_at_ms} ms | "
                                "Max Offset "
                                f"{footwork_event.maximum_center_offset:.4f}"
                            )

                        if footwork_event.completed_this_frame:
                            motion_features = (
                                motion_feature_tracker.finalize_event(
                                    footwork_event.event_id
                                )
                            )
                            assessment_builder.add_completed_event(
                                footwork_event,
                                motion_features=motion_features,
                            )

                            move_seconds = (
                                footwork_event.get_move_time_seconds()
                            )
                            recovery_seconds = (
                                footwork_event.get_recovery_time_seconds()
                            )
                            total_seconds = (
                                footwork_event.get_total_time_seconds()
                            )

                            move_text = (
                                f"{move_seconds:.2f}s"
                                if move_seconds is not None
                                else "--"
                            )
                            recovery_text = (
                                f"{recovery_seconds:.2f}s"
                                if recovery_seconds is not None
                                else "--"
                            )
                            total_text = (
                                f"{total_seconds:.2f}s"
                                if total_seconds is not None
                                else "--"
                            )

                            print(
                                "[Footwork Complete] "
                                f"Event {footwork_event.event_id} | "
                                f"Direction "
                                f"{footwork_event.direction or 'UNKNOWN'} | "
                                f"Reason "
                                f"{footwork_event.completion_reason or 'UNKNOWN'} | "
                                f"Move {move_text} | "
                                f"Recovery {recovery_text} | "
                                f"Total {total_text}"
                            )

                        draw_pelvis_motion(
                            frame,
                            pelvis_displacement,
                            pelvis_velocity,
                        )

                        previous_hip_center_normalized = (
                            hip_center_normalized
                        )
                        previous_timestamp_ms = timestamp_ms

                        hip_center_point = get_hip_center_pixel(
                            frame,
                            hip_center_normalized,
                        )
                        hip_trajectory.append(hip_center_point)

                        draw_trajectory(frame, hip_trajectory)
                        draw_hip_center(frame, hip_center_point)

                        debug_overlay.draw(
                            frame,
                            event_id=footwork_event.event_id,
                            current_state=footwork_event.state.value,
                            frame_index=frame_index,
                            timestamp_ms=timestamp_ms,
                            center_offset=calibration_result.center_offset,
                            smoothed_center_offset=(
                                footwork_event.smoothed_center_offset
                            ),
                            pelvis_speed=(
                                pelvis_velocity["speed"]
                                if pelvis_velocity["valid"]
                                else None
                            ),
                            maximum_center_offset=(
                                footwork_event.maximum_center_offset
                            ),
                            reversal_candidate_frames=(
                                footwork_event.reversal_candidate_frames
                            ),
                            reach_frame=footwork_event.reach_frame,
                            reach_timestamp_ms=footwork_event.reach_at_ms,
                            direction=footwork_event.direction,
                            direction_angle_degrees=(
                                footwork_event.direction_angle_degrees
                            ),
                        )

                    status_text = "Pose detected"
                else:
                    status_text = "Pose not detected"

                draw_frame_info(
                    frame,
                    status_text,
                    frame_index,
                )

                if display:
                    cv2.imshow(window_name, frame)
                    delay_ms = max(1, int(1000 / fps))
                    key = cv2.waitKey(delay_ms) & 0xFF
                    if key in (ord("q"), 27):
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
        input_validation_output_path,
    )
    require_motion_input_ready(input_validation)

    assessment_result = assessment_builder.build(
        total_frame_count=frame_index,
        detected_frame_count=detected_frame_count,
        source_video=str(video_path),
    )
    reach_grid = build_footwork_reach_grid(
        pose_samples,
        assessment_result.get("events") or [],
        ready_frame_index=initial_ready_frame_index,
    )
    save_footwork_reach_grid(
        reach_grid,
        reach_grid_output_path,
    )
    assessment_builder.save(
        assessment_result,
        assessment_output_path,
    )

    coach_engine = CoachEngine(version="1.0")
    coach_evaluation = coach_engine.evaluate(assessment_result)
    coach_engine.save(
        coach_evaluation,
        coach_output_path,
    )

    report_builder = ReportBuilder(version="1.0")
    analysis_report = report_builder.build(
        assessment_result,
        coach_evaluation,
    )
    report_builder.save(
        analysis_report,
        report_output_path,
    )

    review_package = build_expert_review_package(
        assessment_result,
        minimum_reviewers=REVIEW_MINIMUM_REVIEWERS,
        consensus_votes_required=(
            REVIEW_CONSENSUS_VOTES_REQUIRED
        ),
    )
    save_expert_review_package(
        review_package,
        review_output_path,
    )

    pipeline_validator = PipelineValidator(version="1.0")
    validation_report = pipeline_validator.validate(
        assessment_result,
        coach_evaluation,
        analysis_report,
        review_package,
        artifact_paths={
            "assessment": assessment_output_path,
            "coach_evaluation": coach_output_path,
            "analysis_report": report_output_path,
            "review_package": review_output_path,
        },
        raise_on_error=True,
    )
    pipeline_validator.save(
        validation_report,
        validation_output_path,
    )

    print("\n=== AI Motion Demo 完成 ===")
    print(f"總處理幀數：{frame_index}")
    print(f"成功偵測幀數：{detected_frame_count}")

    if frame_index > 0:
        detection_rate = (
            detected_frame_count / frame_index * 100
        )
        print(f"人體偵測率：{detection_rate:.1f}%")

    print(
        "Assessment JSON："
        f"{assessment_output_path}"
    )
    print(
        "測驗流程完成："
        f"{assessment_result['test_completed']}"
        " | Event "
        f"{assessment_result['event_count']}"
        "/"
        f"{assessment_result['expected_event_count']}"
    )
    print(
        "方向覆蓋完整："
        f"{assessment_result['direction_coverage_complete']}"
        " | System Confidence "
        f"{assessment_result['system_confidence']}"
    )

    print(
        "Coach Evaluation："
        f"{coach_output_path}"
    )
    checklist_summary = coach_evaluation["checklist_summary"]

    evaluated_rule_count = (
        checklist_summary["pass_count"]
        + checklist_summary["fail_count"]
        + checklist_summary["needs_review_count"]
    )

    print(
        "Coach Engine："
        f"{coach_evaluation['overall_status']}"
        " | PASS "
        f"{checklist_summary['pass_count']}"
        f"/{evaluated_rule_count}"
    )
    print(
        "Analysis Report："
        f"{report_output_path}"
    )
    print(
        "Report Overall Score："
        f"{analysis_report['summary']['overall_score']}"
        " | Coach Status "
        f"{analysis_report['summary']['coach_status']}"
    )
    print(
        "Expert Review Package："
        f"{review_output_path}"
    )
    print(
        "Pipeline Validation："
        f"{validation_output_path}"
    )
    print(
        "Pipeline Validator："
        f"{validation_report['status']}"
        " | Errors "
        f"{validation_report['summary']['error_count']}"
        " | Warnings "
        f"{validation_report['summary']['warning_count']}"
    )
    print(
        "Calibration Config："
        f"{CALIBRATION_CONFIG_VERSION}"
    )

    return {
        "assessment": assessment_result,
        "coach_evaluation": coach_evaluation,
        "analysis_report": analysis_report,
        "review_package": review_package,
        "pipeline_validation": validation_report,
        "artifact_paths": {
            "motion_input_validation": str(input_validation_output_path),
            "reach_grid": str(reach_grid_output_path),
            "assessment": str(assessment_output_path),
            "coach_evaluation": str(coach_output_path),
            "analysis_report": str(report_output_path),
            "review_package": str(review_output_path),
            "pipeline_validation": str(validation_output_path),
        },
    }


if __name__ == "__main__":
    print("請從專案根目錄執行：python main.py")
