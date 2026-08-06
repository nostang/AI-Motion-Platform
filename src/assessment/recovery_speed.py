"""Recovery Speed Assessment V1.

This module evaluates existing ``recovery_time_seconds`` values from the
Footwork Assessment event records. It does not recompute pose landmarks or
motion events.

The thresholds are calibration parameters, not validated badminton coaching
standards. They must remain explicit and versioned so domain review can adjust
them without changing the scoring algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RecoverySpeedConfig:
    """Transparent V1 calibration parameters for recovery scoring."""

    version: str = "recovery-speed-v1"
    fast_reference_seconds: float = 0.60
    slow_reference_seconds: float = 1.50
    maximum_score: int = 25
    minimum_score: int = 5
    minimum_valid_events: int = 6
    pass_score: int = 18

    def __post_init__(self) -> None:
        if self.fast_reference_seconds <= 0:
            raise ValueError("fast_reference_seconds 必須大於 0。")
        if self.slow_reference_seconds <= self.fast_reference_seconds:
            raise ValueError(
                "slow_reference_seconds 必須大於 fast_reference_seconds。"
            )
        if self.maximum_score <= self.minimum_score:
            raise ValueError("maximum_score 必須大於 minimum_score。")
        if self.minimum_valid_events <= 0:
            raise ValueError("minimum_valid_events 必須大於 0。")


DEFAULT_RECOVERY_SPEED_CONFIG = RecoverySpeedConfig()


def _valid_recovery_times(events: Iterable[Mapping[str, Any]]) -> list[float]:
    values: list[float] = []

    for event in events:
        value = event.get("recovery_time_seconds")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value <= 0:
            continue
        values.append(float(value))

    return values


def _score_average_seconds(
    average_seconds: float,
    config: RecoverySpeedConfig,
) -> int:
    """Map average recovery time to a bounded score using linear interpolation."""

    if average_seconds <= config.fast_reference_seconds:
        return config.maximum_score

    if average_seconds >= config.slow_reference_seconds:
        return config.minimum_score

    time_ratio = (
        average_seconds - config.fast_reference_seconds
    ) / (
        config.slow_reference_seconds - config.fast_reference_seconds
    )
    score_range = config.maximum_score - config.minimum_score
    score = config.maximum_score - (time_ratio * score_range)
    return int(round(score))


def evaluate_recovery_speed(
    assessment: Mapping[str, Any],
    config: RecoverySpeedConfig = DEFAULT_RECOVERY_SPEED_CONFIG,
) -> dict[str, Any]:
    """Evaluate recovery speed from Assessment event timing data."""

    events = assessment.get("events") or []
    if not isinstance(events, list):
        raise ValueError("assessment events 必須是 list。")

    recovery_times = _valid_recovery_times(events)
    valid_event_count = len(recovery_times)

    base_result: dict[str, Any] = {
        "metric_id": "AR002",
        "name": "RECOVERY_SPEED",
        "display_name": "回位速度",
        "config_version": config.version,
        "valid_event_count": valid_event_count,
        "required_event_count": config.minimum_valid_events,
        "average_seconds": None,
        "median_seconds": None,
        "fastest_seconds": None,
        "slowest_seconds": None,
        "score": None,
        "max_score": config.maximum_score,
        "status": "NOT_EVALUATED",
        "result": "NOT_EVALUATED",
        "thresholds": {
            "fast_reference_seconds": config.fast_reference_seconds,
            "slow_reference_seconds": config.slow_reference_seconds,
            "pass_score": config.pass_score,
        },
        "explanation": "有效回位時間資料不足，暫不評分。",
        "limitations": [
            "Recovery Speed V1 使用暫定 Calibration 門檻，尚未經教練樣本驗證。",
            "此分數只描述目前影片中的回位時間，不代表完整步法技術能力。",
            "不同方向、拍攝角度與場地尺度可能影響回位時間。",
        ],
    }

    if valid_event_count < config.minimum_valid_events:
        return base_result

    average_seconds = round(mean(recovery_times), 4)
    median_seconds = round(median(recovery_times), 4)
    score = _score_average_seconds(average_seconds, config)
    passed = score >= config.pass_score

    base_result.update(
        {
            "average_seconds": average_seconds,
            "median_seconds": median_seconds,
            "fastest_seconds": round(min(recovery_times), 4),
            "slowest_seconds": round(max(recovery_times), 4),
            "score": score,
            "status": "EVALUATED",
            "result": "PASS" if passed else "NEEDS_REVIEW",
            "explanation": (
                f"平均回位時間為 {average_seconds:.2f} 秒，"
                f"Recovery Speed 得分 {score}/{config.maximum_score}。"
            ),
        }
    )

    return base_result
