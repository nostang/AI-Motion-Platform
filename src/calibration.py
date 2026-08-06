"""Center and motion-feature calibration utilities.

This module keeps the existing center-position calibrator and adds a reusable
feature-calibration engine. Feature calibration converts a descriptive motion
feature value into a qualitative level. It does not assign assessment scores;
that remains the responsibility of the Assessment layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Mapping

from src.measurement import (
    calculate_center_offset,
    calculate_center_reference,
    is_inside_center_region,
)


CALIBRATION_LEVELS = ("EXCELLENT", "GOOD", "FAIR", "POOR")


@dataclass
class CenterCalibrationResult:
    """單一影格的中心校正結果。"""

    calibrated: bool
    calibrated_this_frame: bool
    center_reference: tuple[float, float] | None
    center_offset: float | None
    inside_center_region: bool | None
    progress: float


@dataclass
class CenterCalibrator:
    """管理影片開始階段的中心位置校正。"""

    calibration_frame_count: int
    center_region_radius: float
    calibration_points: list[tuple[float, float]] = field(default_factory=list)
    center_reference: tuple[float, float] | None = None
    calibrated: bool = False

    def update(
        self,
        hip_center: tuple[float, float],
    ) -> CenterCalibrationResult:
        """接收目前骨盆中心，更新校正狀態並回傳結果。"""

        calibrated_this_frame = False

        if not self.calibrated:
            self.calibration_points.append(hip_center)

            if len(self.calibration_points) >= self.calibration_frame_count:
                self.center_reference = calculate_center_reference(
                    self.calibration_points
                )
                self.calibrated = self.center_reference is not None
                calibrated_this_frame = self.calibrated

        progress = min(
            1.0,
            len(self.calibration_points) / self.calibration_frame_count,
        )

        center_offset = None
        inside_center_region = None

        if self.calibrated and self.center_reference is not None:
            center_offset = calculate_center_offset(
                hip_center,
                self.center_reference,
            )
            inside_center_region = is_inside_center_region(
                center_offset,
                self.center_region_radius,
            )

        return CenterCalibrationResult(
            calibrated=self.calibrated,
            calibrated_this_frame=calibrated_this_frame,
            center_reference=self.center_reference,
            center_offset=center_offset,
            inside_center_region=inside_center_region,
            progress=progress,
        )


@dataclass(frozen=True)
class FeatureCalibrationResult:
    """Qualitative calibration output for one descriptive feature value."""

    feature_id: str
    value: float
    unit: str
    level: str
    input_statistic: str
    direction: str
    calibration_version: str
    provisional: bool
    thresholds: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MotionFeatureCalibrationEngine:
    """Evaluate motion-feature values against versioned calibration settings.

    V1 supports ``lower_is_better`` rules. It intentionally returns only a
    qualitative level. Assessment modules may later map that level to a score.
    """

    def __init__(self, calibration: Mapping[str, Any]) -> None:
        self._config = dict(calibration)
        self.schema_version = str(self._config.get("schema_version", "1.0"))
        self.config_version = str(
            self._config.get("config_version", "motion-feature-calibration-unknown")
        )
        self.status = str(self._config.get("status", "PROVISIONAL")).upper()
        self.features = self._config.get("features", {})

        if not isinstance(self.features, Mapping) or not self.features:
            raise ValueError("feature_calibration.features 不可為空。")

        self._validate_features()

    @property
    def provisional(self) -> bool:
        return self.status != "VALIDATED"

    def evaluate(self, *, feature_id: str, value: float) -> FeatureCalibrationResult:
        """Return EXCELLENT, GOOD, FAIR, or POOR for one finite feature value."""

        if feature_id not in self.features:
            raise KeyError(f"找不到 Feature Calibration：{feature_id}")

        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("Feature Calibration value 必須是有限數值。")

        rule = self.features[feature_id]
        direction = str(rule.get("direction", "lower_is_better"))
        if direction != "lower_is_better":
            raise ValueError(f"目前不支援的 Calibration direction：{direction}")

        thresholds = {
            level: float(rule["thresholds"][level])
            for level in ("EXCELLENT", "GOOD", "FAIR")
        }

        absolute_value = abs(numeric_value)
        if absolute_value <= thresholds["EXCELLENT"]:
            level = "EXCELLENT"
        elif absolute_value <= thresholds["GOOD"]:
            level = "GOOD"
        elif absolute_value <= thresholds["FAIR"]:
            level = "FAIR"
        else:
            level = "POOR"

        return FeatureCalibrationResult(
            feature_id=feature_id,
            value=round(numeric_value, 4),
            unit=str(rule.get("unit", "unknown")),
            level=level,
            input_statistic=str(rule.get("input_statistic", "value")),
            direction=direction,
            calibration_version=self.config_version,
            provisional=self.provisional,
            thresholds=thresholds,
        )

    def get_rule(self, feature_id: str) -> dict[str, Any]:
        """Return a defensive copy of one feature calibration rule."""

        if feature_id not in self.features:
            raise KeyError(f"找不到 Feature Calibration：{feature_id}")
        rule = self.features[feature_id]
        return {
            key: dict(value) if isinstance(value, Mapping) else value
            for key, value in rule.items()
        }

    def snapshot(self) -> dict[str, Any]:
        """Return the serializable calibration configuration snapshot."""

        return {
            "schema_version": self.schema_version,
            "config_version": self.config_version,
            "status": self.status,
            "features": {
                feature_id: self.get_rule(feature_id)
                for feature_id in self.features
            },
        }

    def _validate_features(self) -> None:
        for feature_id, rule in self.features.items():
            if not isinstance(rule, Mapping):
                raise ValueError(f"{feature_id} Calibration rule 必須是物件。")

            direction = str(rule.get("direction", ""))
            if direction != "lower_is_better":
                raise ValueError(
                    f"{feature_id} direction 必須為 lower_is_better。"
                )

            thresholds = rule.get("thresholds")
            if not isinstance(thresholds, Mapping):
                raise ValueError(f"{feature_id} 缺少 thresholds。")

            missing = [
                level
                for level in ("EXCELLENT", "GOOD", "FAIR")
                if level not in thresholds
            ]
            if missing:
                raise ValueError(
                    f"{feature_id} thresholds 缺少：{', '.join(missing)}"
                )

            excellent = float(thresholds["EXCELLENT"])
            good = float(thresholds["GOOD"])
            fair = float(thresholds["FAIR"])

            if not all(math.isfinite(v) and v >= 0 for v in (excellent, good, fair)):
                raise ValueError(f"{feature_id} thresholds 必須是非負有限數值。")
            if not excellent < good < fair:
                raise ValueError(
                    f"{feature_id} thresholds 必須符合 EXCELLENT < GOOD < FAIR。"
                )
