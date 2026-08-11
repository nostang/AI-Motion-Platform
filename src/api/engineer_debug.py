"""Internal Engineer Mode evidence assembler.

This module only joins evidence already emitted by the analysis pipeline.  It
does not calculate features, levels, sub-scores, or overall scores.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ASSESSMENT_FILES = {
    "footwork": "footwork_assessment.json",
    "serve": "serve_assessment.json",
    "clear": "clear_assessment.json",
}

REPORT_FILES = {
    "footwork": "footwork_analysis_report.json",
    "serve": "serve_analysis_report.json",
    "clear": "clear_analysis_report.json",
}

METRIC_LABELS = {
    "preparation_stability": "準備穩定度",
    "swing_completeness": "揮拍完整性",
    "body_coordination": "身體協調",
    "motion_smoothness": "動作流暢度",
    "sideways_preparation": "側身準備",
    "weight_transfer": "重心轉移",
    "non_racket_arm_balance": "非持拍手平衡",
    "swing_smoothness": "揮拍流暢度",
    "movement_completion": "移動完成度",
    "recovery_speed": "回位速度",
    "motion_quality": "動作品質",
    "body_stability": "身體穩定度",
    "direction_coverage": "方向覆蓋（診斷）",
}

METRIC_FEATURES = {
    "serve": {
        "preparation_stability": ("preparation_stability_index",),
        "swing_completeness": ("swing_path_length", "wrist_extension_range"),
        "body_coordination": ("torso_change_degrees",),
        "motion_smoothness": ("wrist_speed_variation",),
    },
    "clear": {
        "sideways_preparation": (
            "minimum_shoulder_hip_ratio", "shoulder_angle_range_degrees",
        ),
        "weight_transfer": ("hip_center_shift",),
        "non_racket_arm_balance": (
            "maximum_arm_elevation", "elevated_sample_ratio",
        ),
        "swing_smoothness": ("wrist_path_length", "wrist_speed_variation"),
    },
}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _source_video(task_dir: Path) -> Path | None:
    for suffix in (".mp4", ".mov"):
        path = task_dir / f"source{suffix}"
        if path.is_file():
            return path
    return None


def _video_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "MISSING", "evidence_gap": "SOURCE_VIDEO_NOT_FOUND"}

    try:
        import cv2
    except ImportError:
        return {
            "status": "DEPENDENCY_MISSING",
            "file_name": path.name,
            "evidence_gap": "OPENCV_NOT_AVAILABLE_FOR_CONTAINER_METADATA",
        }

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return {"status": "UNREADABLE", "file_name": path.name}
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration_ms = round(total_frames * 1000 / fps) if fps > 0 else None
        return {
            "status": "READY",
            "file_name": path.name,
            "duration_ms": duration_ms,
            "fps": round(fps, 4) if fps else None,
            "resolution": {"width": width, "height": height},
            "container_total_frames": total_frames,
        }
    finally:
        capture.release()


def _thresholds(
    motion_type: str,
    config_root: Path,
) -> dict[str, Any] | None:
    path = config_root / f"{motion_type}_calibration.json"
    config = _read_json(path)
    if config is None:
        return None
    return {
        "config_version": config.get("config_version"),
        "rubric_version": config.get("rubric_version"),
        "calibration_status": config.get("status"),
        "level_scores": config.get("level_scores"),
        "thresholds": config.get("thresholds"),
    }


def _annotation_evidence(annotation: Mapping[str, Any] | None) -> dict[str, Any]:
    if annotation is None:
        return {"status": "MISSING", "window": None}
    return {
        "status": "PRESENT",
        "window": annotation.get("window"),
        "action_type": annotation.get("action_type"),
        "racket_side": annotation.get("racket_side"),
        "calibration_eligibility": annotation.get("calibration_eligibility"),
        "notes": annotation.get("notes"),
        "updated_at": annotation.get("updated_at"),
    }


def _analysis_window(
    annotation: Mapping[str, Any] | None,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    window = annotation.get("window") if annotation else None
    if isinstance(window, Mapping):
        return {
            "status": "APPLIED",
            "source": "HUMAN_ANNOTATION",
            "start_ms": window.get("start_ms"),
            "end_ms": window.get("end_ms"),
            "duration_ms": window.get("duration_ms"),
            "pipeline_event": assessment.get("event"),
        }
    return {
        "status": "FULL_SOURCE_OR_PIPELINE_DEFAULT",
        "source": "PIPELINE",
        "start_ms": None,
        "end_ms": None,
        "duration_ms": None,
        "pipeline_event": assessment.get("event"),
        "evidence_gap": "NO_HUMAN_ANALYSIS_WINDOW_RECORDED",
    }


def _internal_window(
    motion_type: str,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    features = assessment.get("features") or {}
    if motion_type == "serve":
        return {
            "kind": "SWING_WINDOW",
            "window": features.get("analysis_window"),
            "source": "features.analysis_window",
        }
    if motion_type == "clear":
        return {
            "kind": "CLEAR_EVENT_WINDOW",
            "window": assessment.get("event"),
            "source": "event",
            "evidence_gap": "CLEAR_DOES_NOT_EMIT_A_NESTED_FEATURE_WINDOW",
        }
    return {
        "kind": "FOOTWORK_EVENTS",
        "events": assessment.get("events") or [],
        "source": "events",
    }


def _active_side(
    motion_type: str,
    annotation: Mapping[str, Any] | None,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    features = assessment.get("features") or {}
    manual = annotation.get("racket_side") if annotation else None
    if motion_type == "serve":
        hand = features.get("dominant_hand") or {}
        automatic = hand.get("automatic_estimate") or hand
        effective = features.get("active_side_estimate") or hand.get("estimated")
        return {
            "manual_annotation": manual,
            "automatic_estimate": automatic,
            "effective_side": effective,
            "effective_source": "MANUAL" if manual else "AUTO",
            "effective_evidence": hand,
        }
    if motion_type == "clear":
        hand = features.get("racket_hand") or {}
        automatic = hand.get("estimated") or features.get("racket_side_estimate")
        return {
            "manual_annotation": manual,
            "automatic_estimate": hand,
            "effective_side": manual or automatic,
            "effective_source": "MANUAL" if manual else "AUTO",
            "effective_evidence": hand,
        }
    return {
        "manual_annotation": manual,
        "automatic_estimate": None,
        "effective_side": None,
        "effective_source": "NOT_APPLICABLE",
    }


def _feature_evidence(
    motion_type: str,
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    if motion_type in {"serve", "clear"}:
        features = dict(assessment.get("features") or {})
        for metadata_key in (
            "status", "feature_version", "sample_count", "limitations",
            "dominant_hand", "racket_hand", "analysis_window",
            "active_side_estimate", "racket_side_estimate",
            "non_racket_side_estimate",
        ):
            features.pop(metadata_key, None)
        return {
            "feature_version": (assessment.get("features") or {}).get("feature_version"),
            "raw": features,
            "normalized": None,
            "normalized_evidence_gap": "NO_NORMALIZED_FEATURE_VALUES_EMITTED",
        }
    return {
        "feature_library": assessment.get("motion_feature_library"),
        "events": [
            {
                "event_id": event.get("event_id"),
                "direction": event.get("direction"),
                "motion_features": event.get("motion_features"),
            }
            for event in assessment.get("events") or []
        ],
    }


def _scoring_evidence(
    motion_type: str,
    assessment: Mapping[str, Any],
    report: Mapping[str, Any] | None,
    config_root: Path,
) -> dict[str, Any]:
    if motion_type in {"serve", "clear"}:
        return {
            "metrics": assessment.get("metrics"),
            "calibration": _thresholds(motion_type, config_root),
            "overall_score": assessment.get("overall_score"),
            "public_report_summary": report.get("summary") if report else None,
            "public_report_breakdown": report.get("score_breakdown") if report else None,
            "note": (
                "Metrics and levels are stored Backend decisions. Thresholds are "
                "the matching calibration configuration; Engineer Mode does not rescore."
            ),
        }
    return {
        "recovery_speed": assessment.get("recovery_speed"),
        "direction_coverage": assessment.get("direction_coverage_assessment"),
        "body_stability": assessment.get("body_stability"),
        "motion_quality": assessment.get("motion_quality"),
        "technique_score": assessment.get("technique_score"),
        "public_report_summary": report.get("summary") if report else None,
        "public_report_skill_score": report.get("skill_score") if report else None,
        "public_report_result_summary": report.get("result_summary") if report else None,
        "calibration_snapshot": assessment.get("calibration_snapshot"),
        "note": "All values are copied from the stored footwork assessment.",
    }


def _feature_value(
    motion_type: str,
    metric_key: str,
    feature_key: str,
    features: Mapping[str, Any],
) -> Any:
    if motion_type == "serve":
        return features.get(feature_key)
    metric_features = features.get(metric_key) or {}
    return metric_features.get(feature_key)


def _metric_threshold(
    motion_type: str,
    metric_key: str,
    feature_key: str,
    thresholds: Mapping[str, Any],
) -> Any:
    if motion_type == "serve":
        return thresholds.get(feature_key)
    return (thresholds.get(metric_key) or {}).get(feature_key)


def _serve_clear_score_rows(
    motion_type: str,
    assessment: Mapping[str, Any],
    config_root: Path,
) -> list[dict[str, Any]]:
    features = assessment.get("features") or {}
    metrics = assessment.get("metrics") or {}
    calibration = _thresholds(motion_type, config_root) or {}
    thresholds = calibration.get("thresholds") or {}
    rows = []
    for metric_key, metric in metrics.items():
        measurements = []
        measurement_levels = metric.get("measurement_levels") or {}
        for feature_key in METRIC_FEATURES[motion_type].get(metric_key, ()):
            measurements.append({
                "feature": feature_key,
                "value": _feature_value(
                    motion_type, metric_key, feature_key, features,
                ),
                "threshold": _metric_threshold(
                    motion_type, metric_key, feature_key, thresholds,
                ),
                "level": measurement_levels.get(feature_key),
            })
        rows.append({
            "metric": metric_key,
            "label": METRIC_LABELS.get(metric_key, metric_key),
            "measurements": measurements,
            "level": metric.get("level"),
            "score": metric.get("score"),
            "max_score": metric.get("max_score"),
            "included_in_overall": True,
        })
    return rows


def _footwork_score_rows(
    assessment: Mapping[str, Any],
    report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    skill = report.get("skill_score") if report else {}
    skill = skill or {}
    calibration_features = (
        ((assessment.get("calibration_snapshot") or {})
         .get("feature_calibration") or {}).get("features") or {}
    )

    def row(
        key: str,
        measurements: list[dict[str, Any]],
        stored: Mapping[str, Any] | None,
        *,
        included: bool = True,
    ) -> dict[str, Any]:
        stored = stored or {}
        return {
            "metric": key,
            "label": METRIC_LABELS[key],
            "measurements": measurements,
            "level": stored.get("level") or stored.get("result"),
            "score": stored.get("score"),
            "max_score": stored.get("max_score"),
            "included_in_overall": included,
            "source_rule_id": stored.get("source_rule_id"),
        }

    completion = skill.get("movement_completion") or {}
    recovery = assessment.get("recovery_speed") or {}
    quality = assessment.get("motion_quality") or {}
    stability = assessment.get("body_stability") or {}
    coverage = assessment.get("direction_coverage_assessment") or {}
    stability_measurements = []
    for item in stability.get("feature_levels") or []:
        feature_key = item.get("feature_id")
        calibration = calibration_features.get(feature_key) or {}
        stability_measurements.append({
            "feature": feature_key,
            "value": item.get("aggregate_value"),
            "unit": item.get("unit"),
            "threshold": {
                "direction": calibration.get("direction"),
                **(calibration.get("thresholds") or {}),
            },
            "level": item.get("level"),
        })
    quality_calibration = calibration_features.get(quality.get("feature_id")) or {}
    return [
        row("movement_completion", [{
            "feature": "completed_events",
            "value": {
                "actual": assessment.get("event_count"),
                "expected": assessment.get("expected_event_count"),
                "all_completed": assessment.get("all_events_completed"),
            },
            "threshold": None,
            "level": completion.get("level"),
        }], completion),
        row("recovery_speed", [{
            "feature": "average_seconds",
            "value": recovery.get("average_seconds"),
            "unit": "seconds",
            "threshold": recovery.get("thresholds"),
            "level": (skill.get("recovery_speed") or {}).get("level"),
        }], skill.get("recovery_speed") or recovery),
        row("motion_quality", [{
            "feature": quality.get("feature_id"),
            "value": quality.get("aggregate_value"),
            "unit": quality.get("unit"),
            "threshold": {
                "direction": quality_calibration.get("direction"),
                **(quality_calibration.get("thresholds") or {}),
            },
            "level": quality.get("level"),
        }], skill.get("motion_quality") or quality),
        row("body_stability", stability_measurements, skill.get("body_stability") or stability),
        row("direction_coverage", [{
            "feature": "coverage_ratio",
            "value": coverage.get("coverage_ratio"),
            "threshold": {
                "expected_direction_count": coverage.get("expected_direction_count"),
            },
            "level": coverage.get("result"),
        }], coverage, included=False),
    ]


def _overview_rows(
    motion_type: str,
    assessment: Mapping[str, Any],
    video: Mapping[str, Any],
    analysis_window: Mapping[str, Any],
    internal_window: Mapping[str, Any],
    active_side: Mapping[str, Any],
    report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    pose = assessment.get("pose_detection") or {}
    internal = internal_window.get("window")
    summary = report.get("summary") if report else {}

    def seconds(value: Any) -> str:
        if not isinstance(value, (int, float)):
            return "--"
        return f"{value / 1000:.3f}"

    def range_seconds(value: Mapping[str, Any] | None) -> str:
        value = value or {}
        start = value.get("start_ms")
        end = value.get("end_ms")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            return "--"
        return f"{start / 1000:.3f}–{end / 1000:.3f} 秒"

    motion_labels = {
        "footwork": "步法",
        "serve": "正手發球",
        "clear": "高遠球",
    }
    resolution = video.get("resolution") or {}
    video_parts = [f"{seconds(video.get('duration_ms'))} 秒"]
    if resolution.get("width") and resolution.get("height"):
        video_parts.append(f"{resolution['width']}×{resolution['height']}")
    if isinstance(video.get("fps"), (int, float)):
        video_parts.append(f"{video['fps']:.1f} FPS")

    detected = pose.get("detected_frames")
    processed = pose.get("total_frames")
    ratio = pose.get("detection_rate")
    pose_text = f"{detected if detected is not None else '--'} / {processed if processed is not None else '--'}"
    if isinstance(ratio, (int, float)):
        pose_text += f" · {ratio * 100:.1f}%"

    source = active_side.get("effective_source")
    side = active_side.get("effective_side")
    side_label = {"right": "右手", "left": "左手"}.get(str(side).lower(), side)
    if source == "NOT_APPLICABLE":
        side_text = "不適用"
    elif source == "MANUAL":
        side_text = f"{side_label or '--'} · 人工"
    else:
        automatic = active_side.get("automatic_estimate")
        confidence = automatic.get("confidence") if isinstance(automatic, Mapping) else None
        side_text = f"{side_label or '--'} · AUTO"
        if isinstance(confidence, (int, float)):
            side_text += f" {confidence * 100:.0f}%"

    if analysis_window.get("source") == "HUMAN_ANNOTATION":
        window_text = f"人工 {range_seconds(analysis_window)}"
    else:
        window_text = "全片（Pipeline）"
    if motion_type == "footwork":
        window_text += f" · {len(internal_window.get('events') or [])} Events"
    elif internal:
        inner_name = "內層" if motion_type == "serve" else "Event"
        window_text += f" · {inner_name} {range_seconds(internal)}"

    overall = (summary or {}).get("overall_score")
    if overall is None:
        overall = assessment.get("overall_score")
    return [
        {"label": "分析動作", "value": motion_labels.get(motion_type, motion_type)},
        {"label": "總分", "value": f"{overall} / 100" if overall is not None else "--"},
        {"label": "持拍側", "value": side_text},
        {"label": "影片資訊", "value": " · ".join(video_parts)},
        {"label": "Pose", "value": pose_text},
        {"label": "分析區間", "value": window_text},
    ]


def _detail_rows(
    motion_type: str,
    assessment: Mapping[str, Any],
    annotation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if motion_type == "footwork":
        return {
            "kind": "EVENTS",
            "rows": [{
                "event": event.get("event_id"),
                "direction": event.get("direction"),
                "move_s": event.get("move_time_seconds"),
                "recovery_s": event.get("recovery_time_seconds"),
                "total_s": event.get("total_time_seconds"),
                "completion": event.get("completion_reason"),
                "return": event.get("returned_to_center"),
                "confidence": event.get("classification_confidence"),
            } for event in assessment.get("events") or []],
        }
    annotation_window = annotation.get("window") if annotation else None
    return {
        "kind": "WINDOWS",
        "rows": [
            {"name": "人工選取區間", "source": "human_annotation.window", **(annotation_window or {})},
            {"name": "Pipeline Event", "source": "assessment.event", **(assessment.get("event") or {})},
            ({"name": "Feature Motion Window", "source": "features.analysis_window",
              **((assessment.get("features") or {}).get("analysis_window") or {})}
             if motion_type == "serve" else
             {"name": "Feature Motion Window", "source": "--", "status": "NOT_EMITTED"}),
        ],
    }


def build_engineer_debug(
    *,
    assessment_id: str,
    motion_type: str,
    task: Mapping[str, Any],
    task_dir: Path,
    config_root: Path,
) -> dict[str, Any]:
    """Build one internal debug payload without changing public report data."""
    assessment_path = task_dir / "output" / ASSESSMENT_FILES[motion_type]
    assessment = _read_json(assessment_path)
    if assessment is None:
        raise FileNotFoundError(str(assessment_path))
    annotation = _read_json(task_dir / "human_annotation.json")
    report = _read_json(task_dir / "output" / REPORT_FILES[motion_type])
    pose = dict(assessment.get("pose_detection") or {})
    pose["processed_frames"] = pose.get("total_frames")
    video = {
        **_video_evidence(_source_video(task_dir)),
        "processed_frames": pose.get("total_frames"),
    }
    analysis_window = _analysis_window(annotation, assessment)
    internal_window = _internal_window(motion_type, assessment)
    active_side = _active_side(motion_type, annotation, assessment)
    scoring = _scoring_evidence(
        motion_type, assessment, report, config_root,
    )
    score_rows = (
        _serve_clear_score_rows(motion_type, assessment, config_root)
        if motion_type in {"serve", "clear"}
        else _footwork_score_rows(assessment, report)
    )
    payload = {
        "schema_version": "engineer-debug-v1",
        "visibility": "INTERNAL",
        "assessment": {
            "assessment_id": assessment_id,
            "motion_type": motion_type,
            "status": task.get("status"),
            "engine_version": assessment.get("engine_version"),
            "feature_version": (assessment.get("features") or {}).get("feature_version"),
            "config_version": assessment.get("config_version"),
            "calibration_status": assessment.get("calibration_status"),
        },
        "video": video,
        "annotation": _annotation_evidence(annotation),
        "analysis_window": analysis_window,
        "internal_motion_window": internal_window,
        "active_side": active_side,
        "pose_quality": pose,
        "features": _feature_evidence(motion_type, assessment),
        "scoring_evidence": scoring,
    }
    payload["presentation"] = {
        "overview_rows": _overview_rows(
            motion_type, assessment, video, analysis_window,
            internal_window, active_side, report,
        ),
        "score_rows": score_rows,
        "detail": _detail_rows(motion_type, assessment, annotation),
    }
    return payload
