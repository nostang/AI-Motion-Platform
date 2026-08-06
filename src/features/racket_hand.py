"""高遠球影片持拍手推估（Experimental v0.2）。

此模組只輸出影片層級的 racket_hand，不參與既有評分。
主要依據：
1. 峰值速度
2. 高速爆發區段
3. 準備階段手腕相對位置
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Sequence


EPSILON = 1e-9
MIN_SAMPLES = 12


def _distance(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
) -> float:
    dx = point_a[0] - point_b[0]
    dy = point_a[1] - point_b[1]
    return (dx * dx + dy * dy) ** 0.5


def _side_vote(left_value: float, right_value: float) -> str:
    if abs(left_value - right_value) <= EPSILON:
        return "tie"
    return "right" if right_value > left_value else "left"


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * ratio) - 1))
    return ordered[index]


def estimate_racket_hand(
    samples: Sequence[dict[str, float]],
) -> dict[str, Any]:
    """從完整高遠球動作推估本支影片的持拍手。"""

    if len(samples) < MIN_SAMPLES:
        return {
            "status": "NOT_EVALUATED",
            "feature_version": "racket-hand-v0.2",
            "estimated": "unknown",
            "confidence": 0.0,
            "reason": "INSUFFICIENT_POSE_SAMPLES",
        }

    sample_count = len(samples)
    prep_count = max(3, int(sample_count * 0.25))
    preparation = samples[:prep_count]
    finish = samples[-prep_count:]

    prep_hip_x = mean(sample["hip_center_x"] for sample in preparation)
    finish_hip_x = mean(sample["hip_center_x"] for sample in finish)
    forward_delta_x = finish_hip_x - prep_hip_x

    left_speeds: list[float] = []
    right_speeds: list[float] = []

    for previous, current in zip(samples, samples[1:]):
        delta_time = (
            current["timestamp_ms"] - previous["timestamp_ms"]
        ) / 1000.0

        if delta_time <= 0:
            continue

        left_speeds.append(
            _distance(
                (
                    previous["left_wrist_x"],
                    previous["left_wrist_y"],
                ),
                (
                    current["left_wrist_x"],
                    current["left_wrist_y"],
                ),
            )
            / delta_time
        )

        right_speeds.append(
            _distance(
                (
                    previous["right_wrist_x"],
                    previous["right_wrist_y"],
                ),
                (
                    current["right_wrist_x"],
                    current["right_wrist_y"],
                ),
            )
            / delta_time
        )

    if not left_speeds or not right_speeds:
        return {
            "status": "NOT_EVALUATED",
            "feature_version": "racket-hand-v0.2",
            "estimated": "unknown",
            "confidence": 0.0,
            "reason": "INSUFFICIENT_MOTION_SAMPLES",
        }

    left_peak_speed = max(left_speeds)
    right_peak_speed = max(right_speeds)
    left_p95_speed = _percentile(left_speeds, 0.95)
    right_p95_speed = _percentile(right_speeds, 0.95)

    peak_speed_vote = _side_vote(
        left_peak_speed,
        right_peak_speed,
    )
    burst_speed_vote = _side_vote(
        left_p95_speed,
        right_p95_speed,
    )

    left_wrist_x = mean(
        sample["left_wrist_x"]
        for sample in preparation
    )
    right_wrist_x = mean(
        sample["right_wrist_x"]
        for sample in preparation
    )

    if abs(forward_delta_x) <= EPSILON:
        preparation_position_vote = "tie"
    elif forward_delta_x > 0:
        preparation_position_vote = (
            "left"
            if left_wrist_x < right_wrist_x
            else "right"
        )
    else:
        preparation_position_vote = (
            "left"
            if left_wrist_x > right_wrist_x
            else "right"
        )

    weights = {
        "peak_speed": 0.50,
        "burst_speed": 0.35,
        "preparation_position": 0.15,
    }

    evidence = {
        "peak_speed": peak_speed_vote,
        "burst_speed": burst_speed_vote,
        "preparation_position": preparation_position_vote,
    }

    left_score = sum(
        weights[key]
        for key, vote in evidence.items()
        if vote == "left"
    )
    right_score = sum(
        weights[key]
        for key, vote in evidence.items()
        if vote == "right"
    )

    winning_score = max(left_score, right_score)
    margin = abs(right_score - left_score)

    if margin < 0.20:
        estimated = "unknown"
        status = "UNCERTAIN"
    else:
        estimated = "right" if right_score > left_score else "left"
        status = "ESTIMATED" if winning_score >= 0.70 else "UNCERTAIN"

    confidence = round(winning_score, 4)

    if status != "ESTIMATED":
        estimated = "unknown"

    return {
        "status": status,
        "feature_version": "racket-hand-v0.2",
        "estimated": estimated,
        "confidence": confidence,
        "evidence": evidence,
        "weighted_scores": {
            "left": round(left_score, 4),
            "right": round(right_score, 4),
        },
        "measurements": {
            "forward_hip_shift_x": round(forward_delta_x, 6),
            "left_peak_speed": round(left_peak_speed, 6),
            "right_peak_speed": round(right_peak_speed, 6),
            "left_p95_speed": round(left_p95_speed, 6),
            "right_p95_speed": round(right_p95_speed, 6),
            "left_preparation_wrist_x": round(left_wrist_x, 6),
            "right_preparation_wrist_x": round(right_wrist_x, 6),
        },
        "limitations": [
            "Experimental high-clear racket-hand estimation.",
            "Uses one-camera 2D MediaPipe landmarks and does not detect the racket.",
            "Assumes the video contains a visible preparation and swing.",
            "Mirrored video or incomplete movement may reduce reliability.",
            "This result does not modify the L3 assessment racket-side configuration.",
        ],
    }
