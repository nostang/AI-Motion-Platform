"""AR005 Motion Quality Assessment V1.

V1 uses MF005 Motion Smoothness only. It evaluates generic movement flow and
must not be interpreted as sport-specific badminton technique.
"""

from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping

from src.calibration import MotionFeatureCalibrationEngine


METRIC_ID = "AR005"
FEATURE_ID = "MF005_motion_smoothness"
CONFIG_VERSION = "motion-quality-v1"
REQUIRED_EVENT_COUNT = 6
LEVEL_SCORES = {
    "EXCELLENT": 25,
    "GOOD": 22,
    "FAIR": 18,
    "POOR": 12,
}


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def evaluate_motion_quality(
    *,
    events: Iterable[Mapping[str, Any]],
    calibration_engine: MotionFeatureCalibrationEngine,
    required_event_count: int = REQUIRED_EVENT_COUNT,
) -> dict[str, Any]:
    rule = calibration_engine.get_rule(FEATURE_ID)
    input_statistic = str(rule.get("input_statistic", "combined_smoothness_index"))
    values: list[float] = []

    for event in events:
        motion_features = event.get("motion_features") or {}
        if motion_features.get("status") != "EXTRACTED":
            continue
        feature = (motion_features.get("features") or {}).get(FEATURE_ID) or {}
        value = _numeric(feature.get(input_statistic))
        if value is not None and feature.get("status") == "EXTRACTED":
            values.append(value)

    if len(values) < required_event_count:
        return {
            "metric_id": METRIC_ID,
            "name": "MOTION_QUALITY",
            "display_name": "動作品質",
            "status": "NOT_EVALUATED",
            "result": "NOT_EVALUATED",
            "level": None,
            "score": None,
            "max_score": 25,
            "valid_event_count": len(values),
            "required_event_count": required_event_count,
            "feature_id": FEATURE_ID,
            "input_statistic": input_statistic,
            "aggregate_value": None,
            "config_version": CONFIG_VERSION,
            "calibration_version": calibration_engine.config_version,
            "explanation": "Motion Smoothness 有效 Event 不足，暫不評估動作品質。",
            "limitations": [
                "AR005 V1 至少需要六個有效 Event。",
                "未評估不代表動作不流暢。",
            ],
        }

    aggregate_value = float(median(values))
    calibrated = calibration_engine.evaluate(
        feature_id=FEATURE_ID,
        value=aggregate_value,
    )
    level = calibrated.level
    score = LEVEL_SCORES[level]
    result = "PASS" if level in {"EXCELLENT", "GOOD"} else "NEEDS_REVIEW"
    explanations = {
        "EXCELLENT": "整體位移軌跡與速度變化高度流暢。",
        "GOOD": "整體動作節奏與位移變化大致流暢。",
        "FAIR": "部分 Event 的位移或速度變化較不穩定，建議持續觀察。",
        "POOR": "多個 Event 的位移或速度變化明顯不穩定，建議人工複核。",
    }

    return {
        "metric_id": METRIC_ID,
        "name": "MOTION_QUALITY",
        "display_name": "動作品質",
        "status": "EVALUATED",
        "result": result,
        "level": level,
        "score": score,
        "max_score": 25,
        "valid_event_count": len(values),
        "required_event_count": required_event_count,
        "feature_id": FEATURE_ID,
        "input_statistic": input_statistic,
        "aggregate_value": round(aggregate_value, 4),
        "unit": calibrated.unit,
        "config_version": CONFIG_VERSION,
        "calibration_version": calibrated.calibration_version,
        "calibration_status": calibration_engine.status,
        "provisional": calibrated.provisional,
        "explanation": explanations[level],
        "limitations": [
            "Motion Quality V1 使用暫定 Calibration，尚未經教練樣本驗證。",
            "本評估描述一般動作流暢度，不等同於羽球專項技術正確性。",
            "速度與位移皆為 2D image-normalized measurement。",
            "NEEDS_REVIEW 不等同於使用者動作錯誤。",
        ],
    }
