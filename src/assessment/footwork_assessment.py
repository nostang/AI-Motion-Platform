"""Footwork Assessment JSON V1.7。

輸出客觀分析結果、可重現的設定版本，以及提供專家審查使用的片段範圍。
本模組不產生教練技術分數。
"""

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.assessment.body_stability import evaluate_body_stability
from src.assessment.direction_coverage import evaluate_direction_coverage
from src.assessment.recovery_speed import evaluate_recovery_speed
from src.assessment.motion_quality import evaluate_motion_quality
from src.calibration import MotionFeatureCalibrationEngine


EXPECTED_DIRECTIONS = (
    "RIGHT_FRONT",
    "LEFT_FRONT",
    "RIGHT_BACK",
    "LEFT_BACK",
    "RIGHT",
    "LEFT",
    "FRONT",
    "BACK",
)


@dataclass(frozen=True)
class FootworkEventRecord:
    event_id: int
    direction: str
    classification_confidence: float | None
    direction_angle_degrees: float | None
    direction_vector_length: float | None
    boundary_ambiguous: bool
    completion_reason: str
    move_started_at_ms: int | None
    reach_at_ms: int | None
    returned_at_ms: int | None
    completed_at_ms: int | None
    clip_start_ms: int | None
    clip_end_ms: int | None
    move_time_seconds: float | None
    recovery_time_seconds: float | None
    total_time_seconds: float | None
    maximum_center_offset: float
    move_started_frame: int | None
    reach_frame: int | None
    returned_frame: int | None
    completed_frame: int | None
    completed: bool
    returned_to_center: bool
    motion_features: dict[str, Any] | None


class FootworkAssessmentBuilder:
    def __init__(
        self,
        *,
        expected_event_count: int = 8,
        engine_version: str = "0.5.1",
        config_version: str,
        calibration_snapshot: dict[str, Any],
        clip_pre_roll_ms: int = 350,
        clip_post_roll_ms: int = 350,
    ) -> None:
        self.expected_event_count = expected_event_count
        self.engine_version = engine_version
        self.config_version = config_version
        self.calibration_snapshot = calibration_snapshot
        self.clip_pre_roll_ms = max(0, clip_pre_roll_ms)
        self.clip_post_roll_ms = max(0, clip_post_roll_ms)
        self.assessment_id = f"fa_{uuid4().hex[:16]}"
        self.events: list[FootworkEventRecord] = []

    def add_completed_event(
        self,
        event: Any,
        *,
        motion_features: dict[str, Any] | None = None,
    ) -> None:
        clip_start = (
            max(0, event.move_started_at_ms - self.clip_pre_roll_ms)
            if event.move_started_at_ms is not None
            else None
        )
        clip_end = (
            event.completed_at_ms + self.clip_post_roll_ms
            if event.completed_at_ms is not None
            else None
        )

        self.events.append(
            FootworkEventRecord(
                event_id=event.event_id,
                direction=event.direction or "UNKNOWN",
                classification_confidence=event.direction_confidence,
                direction_angle_degrees=event.direction_angle_degrees,
                direction_vector_length=event.direction_vector_length,
                boundary_ambiguous=(
                    event.direction_boundary_ambiguous
                ),
                completion_reason=(
                    event.completion_reason or "UNKNOWN"
                ),
                move_started_at_ms=event.move_started_at_ms,
                reach_at_ms=event.reach_at_ms,
                returned_at_ms=event.returned_at_ms,
                completed_at_ms=event.completed_at_ms,
                clip_start_ms=clip_start,
                clip_end_ms=clip_end,
                move_time_seconds=event.get_move_time_seconds(),
                recovery_time_seconds=event.get_recovery_time_seconds(),
                total_time_seconds=event.get_total_time_seconds(),
                maximum_center_offset=round(event.maximum_center_offset, 6),
                move_started_frame=event.move_started_frame,
                reach_frame=event.reach_frame,
                returned_frame=event.returned_frame,
                completed_frame=event.completed_frame,
                completed=True,
                returned_to_center=(
                    event.completion_reason
                    == "STRICT_CENTER"
                ),
                motion_features=motion_features,
            )
        )

    def build(
        self,
        *,
        total_frame_count: int,
        detected_frame_count: int,
        source_video: str,
    ) -> dict[str, Any]:
        counts = Counter(event.direction for event in self.events)
        coverage = {
            direction: counts.get(direction, 0) > 0
            for direction in EXPECTED_DIRECTIONS
        }
        missing = [d for d, present in coverage.items() if not present]
        duplicates = {
            direction: count
            for direction, count in counts.items()
            if direction != "UNKNOWN" and count > 1
        }
        unknown_count = counts.get("UNKNOWN", 0)

        event_count_valid = (
            len(self.events)
            == self.expected_event_count
        )
        all_events_completed = all(
            event.completed
            for event in self.events
        )
        all_events_returned = all(
            event.returned_to_center
            for event in self.events
        )
        base_zone_completion_count = sum(
            event.completion_reason == "BASE_ZONE"
            for event in self.events
        )
        direction_coverage_complete = all(
            coverage.values()
        )

        # 測驗完成與精準回中心分開記錄。
        test_completed = (
            event_count_valid
            and all_events_completed
        )

        confidences = [
            e.classification_confidence
            for e in self.events
            if e.classification_confidence is not None
        ]
        system_confidence = (
            round(sum(confidences) / len(confidences), 4)
            if confidences
            else None
        )

        failure_reasons: list[str] = []
        if not event_count_valid:
            failure_reasons.append(
                "EVENT_COUNT_NOT_EQUAL_TO_8"
            )
        if not all_events_completed:
            failure_reasons.append(
                "EVENT_NOT_COMPLETED"
            )

        quality_notes: list[str] = []
        if base_zone_completion_count:
            quality_notes.append(
                "BASE_ZONE_RETURN_DETECTED"
            )
        if missing:
            quality_notes.append("DIRECTION_COVERAGE_INCOMPLETE")
        if duplicates:
            quality_notes.append("DUPLICATE_DIRECTION_DETECTED")
        if unknown_count:
            quality_notes.append("UNKNOWN_DIRECTION_DETECTED")

        detection_rate = (
            round(detected_frame_count / total_frame_count, 4)
            if total_frame_count > 0
            else 0.0
        )

        recovery_speed = evaluate_recovery_speed(
            {"events": [asdict(event) for event in self.events]}
        )
        direction_coverage_assessment = evaluate_direction_coverage(
            direction_coverage=coverage,
            missing_directions=missing,
            duplicate_directions=duplicates,
            unknown_direction_count=unknown_count,
            expected_direction_count=len(EXPECTED_DIRECTIONS),
        )
        feature_calibration = self.calibration_snapshot.get(
            "feature_calibration", {}
        )
        calibration_engine = MotionFeatureCalibrationEngine(feature_calibration)
        body_stability = evaluate_body_stability(
            events=[asdict(event) for event in self.events],
            calibration_engine=calibration_engine,
        )
        motion_quality = evaluate_motion_quality(
            events=[asdict(event) for event in self.events],
            calibration_engine=calibration_engine,
        )

        return {
            "schema_version": "1.7",
            "assessment_id": self.assessment_id,
            "engine_version": self.engine_version,
            "config_version": self.config_version,
            "calibration_snapshot": self.calibration_snapshot,
            "assessment_type": "footwork",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_video": source_video,
            "analysis_status": "completed",
            "test_completed": test_completed,
            "event_count": len(self.events),
            "expected_event_count": self.expected_event_count,
            "event_count_valid": event_count_valid,
            "all_events_completed": all_events_completed,
            "all_events_returned_to_center": all_events_returned,
            "base_zone_completion_count": (
                base_zone_completion_count
            ),
            "direction_coverage_complete": direction_coverage_complete,
            "direction_coverage": coverage,
            "missing_directions": missing,
            "duplicate_directions": duplicates,
            "unknown_direction_count": unknown_count,
            "system_confidence": system_confidence,
            "failure_reasons": failure_reasons,
            "quality_notes": quality_notes,
            "pose_detection": {
                "total_frames": total_frame_count,
                "detected_frames": detected_frame_count,
                "detection_rate": detection_rate,
            },
            "timing_used_for_score": True,
            "recovery_speed": recovery_speed,
            "direction_coverage_assessment": direction_coverage_assessment,
            "body_stability": body_stability,
            "motion_quality": motion_quality,
            "motion_feature_library": {
                "version": "motion-feature-v1.2",
                "status": "EXTRACTED",
                "scoring_enabled": True,
                "consumed_by": [
                    "AR004_BODY_STABILITY",
                    "AR005_MOTION_QUALITY",
                ],
                "feature_ids": [
                    "MF001_shoulder_tilt",
                    "MF002_hip_tilt",
                    "MF003_torso_lean",
                    "MF005_motion_smoothness",
                ],
                "limitations": [
                    "Features are based on 2D image-normalized landmarks.",
                    "Feature values are descriptive and are not body-stability scores.",
                ],
            },
            "technique_score": None,
            "not_evaluated": [
                "lead_foot",
                "dominant_hand_rule",
                "extra_steps",
                "split_step",
                "coach_similarity_score",
            ],
            "events": [asdict(event) for event in self.events],
            "expert_review_ready": len(self.events) > 0,
            "gemini_input_ready": True,
        }

    @staticmethod
    def save(result: dict[str, Any], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
