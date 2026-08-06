"""AR004 Body Stability Assessment.

This module consumes calibrated Motion Feature levels only. It does not read
MediaPipe landmarks or recalculate raw angles. V1 evaluates image-plane body
stability from MF001 shoulder tilt, MF002 hip tilt, and MF003 torso lean.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Iterable, Mapping

from src.calibration import MotionFeatureCalibrationEngine


METRIC_ID = "AR004"
CONFIG_VERSION = "body-stability-v1"
REQUIRED_EVENT_COUNT = 6

FEATURE_IDS = (
    "MF001_shoulder_tilt",
    "MF002_hip_tilt",
    "MF003_torso_lean",
)

FEATURE_WEIGHTS = {
    "MF001_shoulder_tilt": 0.35,
    "MF002_hip_tilt": 0.35,
    "MF003_torso_lean": 0.30,
}

LEVEL_POINTS = {
    "EXCELLENT": 4.0,
    "GOOD": 3.0,
    "FAIR": 2.0,
    "POOR": 1.0,
}

LEVEL_SCORES = {
    "EXCELLENT": 25,
    "GOOD": 22,
    "FAIR": 18,
    "POOR": 12,
}


@dataclass(frozen=True)
class FeatureLevel:
    """Assessment-facing, calibrated representation of one Motion Feature."""

    feature_id: str
    input_statistic: str
    aggregate_value: float
    unit: str
    level: str
    valid_event_count: int
    calibration_version: str
    provisional: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _collect_feature_values(
    events: Iterable[Mapping[str, Any]],
    *,
    feature_id: str,
    input_statistic: str,
) -> list[float]:
    values: list[float] = []
    for event in events:
        motion_features = event.get("motion_features") or {}
        if motion_features.get("status") != "EXTRACTED":
            continue
        features = motion_features.get("features") or {}
        feature = features.get(feature_id) or {}
        value = _numeric(feature.get(input_statistic))
        if value is not None:
            values.append(value)
    return values


def _overall_level(weighted_level_points: float) -> str:
    if weighted_level_points >= 3.5:
        return "EXCELLENT"
    if weighted_level_points >= 2.75:
        return "GOOD"
    if weighted_level_points >= 2.0:
        return "FAIR"
    return "POOR"


def evaluate_body_stability(
    *,
    events: Iterable[Mapping[str, Any]],
    calibration_engine: MotionFeatureCalibrationEngine,
    required_event_count: int = REQUIRED_EVENT_COUNT,
) -> dict[str, Any]:
    """Evaluate body stability from calibrated aggregate Feature Levels.

    Each feature uses the median of its event-level input statistic. Median is
    used to reduce the effect of one short or noisy event. Calibration converts
    the aggregate value to a qualitative level; AR004 then combines only those
    levels and maps the result to a provisional 25-point assessment score.
    """

    event_list = list(events)
    feature_levels: list[FeatureLevel] = []
    missing_features: list[str] = []

    for feature_id in FEATURE_IDS:
        rule = calibration_engine.get_rule(feature_id)
        input_statistic = str(rule.get("input_statistic", "mean_absolute_degrees"))
        values = _collect_feature_values(
            event_list,
            feature_id=feature_id,
            input_statistic=input_statistic,
        )

        if len(values) < required_event_count:
            missing_features.append(feature_id)
            continue

        aggregate_value = float(median(values))
        calibrated = calibration_engine.evaluate(
            feature_id=feature_id,
            value=aggregate_value,
        )
        feature_levels.append(
            FeatureLevel(
                feature_id=feature_id,
                input_statistic=input_statistic,
                aggregate_value=round(aggregate_value, 4),
                unit=calibrated.unit,
                level=calibrated.level,
                valid_event_count=len(values),
                calibration_version=calibrated.calibration_version,
                provisional=calibrated.provisional,
            )
        )

    if missing_features:
        return {
            "metric_id": METRIC_ID,
            "name": "BODY_STABILITY",
            "display_name": "身體穩定度",
            "status": "NOT_EVALUATED",
            "result": "NOT_EVALUATED",
            "level": None,
            "score": None,
            "max_score": 25,
            "required_event_count": required_event_count,
            "feature_levels": [item.to_dict() for item in feature_levels],
            "missing_features": missing_features,
            "config_version": CONFIG_VERSION,
            "calibration_version": calibration_engine.config_version,
            "explanation": "Motion Feature 有效樣本不足，暫不評估身體穩定度。",
            "limitations": [
                "Body Stability V1 需要三項 Feature 各至少六個有效 Event。",
                "未評估不代表動作不穩定。",
            ],
        }

    weighted_points = sum(
        LEVEL_POINTS[item.level] * FEATURE_WEIGHTS[item.feature_id]
        for item in feature_levels
    )
    level = _overall_level(weighted_points)
    score = LEVEL_SCORES[level]

    result = "PASS" if level in {"EXCELLENT", "GOOD"} else "NEEDS_REVIEW"
    explanations = {
        "EXCELLENT": "三項軀幹 Feature 均呈現高度穩定。",
        "GOOD": "移動過程中的肩、髖與軀幹傾斜整體穩定。",
        "FAIR": "移動過程出現部分軀幹傾斜，建議持續觀察。",
        "POOR": "移動過程的軀幹傾斜較明顯，建議人工複核。",
    }

    return {
        "metric_id": METRIC_ID,
        "name": "BODY_STABILITY",
        "display_name": "身體穩定度",
        "status": "EVALUATED",
        "result": result,
        "level": level,
        "score": score,
        "max_score": 25,
        "required_event_count": required_event_count,
        "evaluated_feature_count": len(feature_levels),
        "weighted_level_points": round(weighted_points, 4),
        "feature_levels": [item.to_dict() for item in feature_levels],
        "missing_features": [],
        "config_version": CONFIG_VERSION,
        "calibration_version": calibration_engine.config_version,
        "calibration_status": calibration_engine.status,
        "explanation": explanations[level],
        "limitations": [
            "Body Stability V1 使用暫定 Calibration，尚未經羽球教練樣本驗證。",
            "評估僅使用 2D 影像平面的肩線、髖線與軀幹傾斜 Feature。",
            "拍攝角度、透視與衣物遮擋可能影響結果。",
            "NEEDS_REVIEW 不等同於使用者動作錯誤。",
        ],
    }
