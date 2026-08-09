"""載入並驗證可版本化的 Footwork Calibration 設定。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from src.calibration import MotionFeatureCalibrationEngine


@dataclass(frozen=True)
class FootworkCalibrationSettings:
    schema_version: str
    config_version: str
    raw: dict[str, Any]

    @property
    def center(self) -> dict[str, Any]:
        return self.raw["center"]

    @property
    def event(self) -> dict[str, Any]:
        return self.raw["event"]

    @property
    def direction(self) -> dict[str, Any]:
        return self.raw["direction"]

    @property
    def review(self) -> dict[str, Any]:
        return self.raw["review"]

    @property
    def feature_calibration(self) -> dict[str, Any]:
        return self.raw["feature_calibration"]

    def create_feature_calibration_engine(self) -> MotionFeatureCalibrationEngine:
        return MotionFeatureCalibrationEngine(self.feature_calibration)


def load_footwork_calibration(path: Path) -> FootworkCalibrationSettings:
    if not path.exists():
        raise FileNotFoundError(f"找不到 Footwork Calibration 設定：{path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    required_sections = (
        "center",
        "event",
        "direction",
        "review",
        "feature_calibration",
    )
    missing = [name for name in required_sections if name not in data]
    if missing:
        raise ValueError(f"Calibration 設定缺少區段：{', '.join(missing)}")

    move_threshold = float(
        data["event"]["move_offset_threshold"]
    )
    return_threshold = float(
        data["event"]["return_offset_threshold"]
    )
    base_zone_threshold = float(
        data["event"].get(
            "base_zone_offset_threshold",
            move_threshold,
        )
    )
    base_transition_frames = int(
        data["event"].get(
            "base_transition_confirm_frames",
            2,
        )
    )

    if return_threshold >= move_threshold:
        raise ValueError(
            "return_offset_threshold 必須小於 move_offset_threshold。"
        )

    if not (
        return_threshold
        < base_zone_threshold
        <= move_threshold
    ):
        raise ValueError(
            "base_zone_offset_threshold 必須大於 "
            "return_offset_threshold，且不可大於 "
            "move_offset_threshold。"
        )

    if base_transition_frames < 1:
        raise ValueError(
            "base_transition_confirm_frames 必須至少為 1。"
        )

    # Construction performs complete feature-calibration validation.
    MotionFeatureCalibrationEngine(data["feature_calibration"])

    return FootworkCalibrationSettings(
        schema_version=str(data.get("schema_version", "1.0")),
        config_version=str(data.get("config_version", "unknown")),
        raw=data,
    )
