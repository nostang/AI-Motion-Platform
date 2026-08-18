#!/usr/bin/env python3
"""
Body Stability Robustness V2.1 — Sensitivity Sweep / Curve Validation

DESIGN / SIMULATION ONLY

This file is deliberately isolated from the production scoring pipeline.

It does NOT modify:
- src/assessment/body_stability.py
- src/config_data/footwork_calibration.json
- production tests
- API contracts
- coach logic

Purpose:
1. Keep the real Original vs 720p case.
2. Sweep each Body Stability feature across its useful range.
3. Verify monotonicity.
4. Measure boundary jump size around current thresholds.
5. Verify extreme discrimination.
6. Compare V1 hard-boundary behavior with one continuous V2 candidate.

The continuous formula remains illustrative only and is NOT approved calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise


FEATURES = {
    "MF001_shoulder_tilt": {
        "display_name": "Shoulder Tilt",
        "weight": 0.35,
        "thresholds": {
            "EXCELLENT": 3.0,
            "GOOD": 6.0,
            "FAIR": 12.0,
        },
        "sweep_max": 22.0,
    },
    "MF002_hip_tilt": {
        "display_name": "Hip Tilt",
        "weight": 0.35,
        "thresholds": {
            "EXCELLENT": 3.0,
            "GOOD": 6.0,
            "FAIR": 10.0,
        },
        "sweep_max": 18.0,
    },
    "MF003_torso_lean": {
        "display_name": "Torso Lean",
        "weight": 0.30,
        "thresholds": {
            "EXCELLENT": 5.0,
            "GOOD": 10.0,
            "FAIR": 18.0,
        },
        "sweep_max": 28.0,
    },
}

LEVEL_POINTS = {
    "EXCELLENT": 4.0,
    "GOOD": 3.0,
    "FAIR": 2.0,
    "POOR": 1.0,
}

LEVEL_SCORES = {
    "EXCELLENT": 25.0,
    "GOOD": 22.0,
    "FAIR": 18.0,
    "POOR": 12.0,
}

CASES = {
    "original": {
        "MF001_shoulder_tilt": 15.5245,
        "MF002_hip_tilt": 10.5511,
        "MF003_torso_lean": 3.3624,
    },
    "normalized_720p_preserve_timing": {
        "MF001_shoulder_tilt": 13.3181,
        "MF002_hip_tilt": 9.4668,
        "MF003_torso_lean": 3.2920,
    },
}

# Neutral baseline used when sweeping one feature at a time.
BASELINE = {
    "MF001_shoulder_tilt": 6.0,
    "MF002_hip_tilt": 6.0,
    "MF003_torso_lean": 10.0,
}


@dataclass(frozen=True)
class V1Result:
    feature_levels: dict[str, str]
    weighted_points: float
    level: str
    score: float


@dataclass(frozen=True)
class V2Result:
    feature_points: dict[str, float]
    weighted_points: float
    display_level: str
    continuous_score: float


def hard_feature_level(value: float, thresholds: dict[str, float]) -> str:
    value = abs(float(value))
    if value <= thresholds["EXCELLENT"]:
        return "EXCELLENT"
    if value <= thresholds["GOOD"]:
        return "GOOD"
    if value <= thresholds["FAIR"]:
        return "FAIR"
    return "POOR"


def overall_level(weighted_points: float) -> str:
    if weighted_points >= 3.5:
        return "EXCELLENT"
    if weighted_points >= 2.75:
        return "GOOD"
    if weighted_points >= 2.0:
        return "FAIR"
    return "POOR"


def v1_score(values: dict[str, float]) -> V1Result:
    levels: dict[str, str] = {}
    weighted = 0.0

    for feature_id, spec in FEATURES.items():
        level = hard_feature_level(
            values[feature_id],
            spec["thresholds"],
        )
        levels[feature_id] = level
        weighted += LEVEL_POINTS[level] * spec["weight"]

    level = overall_level(weighted)
    return V1Result(
        feature_levels=levels,
        weighted_points=weighted,
        level=level,
        score=LEVEL_SCORES[level],
    )


def continuous_feature_points(
    value: float,
    thresholds: dict[str, float],
) -> float:
    """
    Illustrative continuous candidate using current threshold locations.

    lower_is_better:
    <= excellent: 4.0
    excellent..good: 4 -> 3
    good..fair: 3 -> 2
    above fair: 2 -> 1 across one additional (fair-good) span
    then floor at 1.0
    """
    value = abs(float(value))
    excellent = float(thresholds["EXCELLENT"])
    good = float(thresholds["GOOD"])
    fair = float(thresholds["FAIR"])

    if value <= excellent:
        return 4.0

    if value <= good:
        span = good - excellent
        return 4.0 - ((value - excellent) / span)

    if value <= fair:
        span = fair - good
        return 3.0 - ((value - good) / span)

    poor_span = fair - good
    return max(1.0, 2.0 - ((value - fair) / poor_span))


def continuous_body_score(weighted_points: float) -> float:
    """
    Piecewise-linear interpolation through V1 score anchors:
    1.0 -> 12
    2.0 -> 18
    3.0 -> 22
    4.0 -> 25
    """
    points = max(1.0, min(4.0, float(weighted_points)))

    if points <= 2.0:
        return 12.0 + (points - 1.0) * 6.0
    if points <= 3.0:
        return 18.0 + (points - 2.0) * 4.0
    return 22.0 + (points - 3.0) * 3.0


def v2_candidate(values: dict[str, float]) -> V2Result:
    feature_points: dict[str, float] = {}
    weighted = 0.0

    for feature_id, spec in FEATURES.items():
        points = continuous_feature_points(
            values[feature_id],
            spec["thresholds"],
        )
        feature_points[feature_id] = points
        weighted += points * spec["weight"]

    return V2Result(
        feature_points=feature_points,
        weighted_points=weighted,
        display_level=overall_level(weighted),
        continuous_score=continuous_body_score(weighted),
    )


def print_real_case_comparison() -> None:
    print("=" * 80)
    print("REAL CASE: ORIGINAL VS 720P PRESERVE TIMING")
    print("=" * 80)

    results = {}
    for name, values in CASES.items():
        v1 = v1_score(values)
        v2 = v2_candidate(values)
        results[name] = (v1, v2)

        print(name)
        for feature_id in FEATURES:
            print(
                f"  {feature_id:26s} "
                f"value={values[feature_id]:8.4f} "
                f"V1={v1.feature_levels[feature_id]:9s} "
                f"V2_points={v2.feature_points[feature_id]:.4f}"
            )
        print(
            f"  V1: weighted={v1.weighted_points:.4f} "
            f"level={v1.level} score={v1.score:.1f}"
        )
        print(
            f"  V2: weighted={v2.weighted_points:.4f} "
            f"display_level={v2.display_level} "
            f"continuous_score={v2.continuous_score:.3f}"
        )
        print()

    original_v1, original_v2 = results["original"]
    norm_v1, norm_v2 = results["normalized_720p_preserve_timing"]

    print(
        f"V1 delta: {norm_v1.score - original_v1.score:+.1f} "
        f"({original_v1.score:.1f} -> {norm_v1.score:.1f})"
    )
    print(
        f"V2 delta: {norm_v2.continuous_score - original_v2.continuous_score:+.3f} "
        f"({original_v2.continuous_score:.3f} -> "
        f"{norm_v2.continuous_score:.3f})"
    )
    print()


def sweep_values(max_value: float, step: float = 0.25) -> list[float]:
    count = int(round(max_value / step))
    return [round(i * step, 6) for i in range(count + 1)]


def score_when_sweeping(
    feature_id: str,
    value: float,
) -> tuple[float, float]:
    values = dict(BASELINE)
    values[feature_id] = value
    return (
        v1_score(values).score,
        v2_candidate(values).continuous_score,
    )


def monotonicity_check() -> tuple[bool, list[str]]:
    """
    lower_is_better => as tilt increases, score must never increase.
    """
    errors: list[str] = []

    for feature_id, spec in FEATURES.items():
        values = sweep_values(spec["sweep_max"])
        v2_scores = [
            score_when_sweeping(feature_id, value)[1]
            for value in values
        ]

        for (left_v, left_s), (right_v, right_s) in pairwise(
            zip(values, v2_scores)
        ):
            if right_s > left_s + 1e-9:
                errors.append(
                    f"{feature_id}: score increased "
                    f"{left_s:.4f}->{right_s:.4f} "
                    f"when value worsened "
                    f"{left_v:.2f}->{right_v:.2f}"
                )

    return (not errors, errors)


def boundary_jump_check(
    epsilon: float = 0.01,
) -> tuple[bool, dict[str, dict[str, tuple[float, float]]]]:
    """
    Measure score discontinuity immediately across current thresholds.
    For V2 we require <= 0.10 Body Stability points for a 0.02° crossing.
    """
    details: dict[str, dict[str, tuple[float, float]]] = {}
    passed = True

    for feature_id, spec in FEATURES.items():
        details[feature_id] = {}

        for level_name, threshold in spec["thresholds"].items():
            below = max(0.0, float(threshold) - epsilon)
            above = float(threshold) + epsilon

            v1_below, v2_below = score_when_sweeping(
                feature_id,
                below,
            )
            v1_above, v2_above = score_when_sweeping(
                feature_id,
                above,
            )

            v1_jump = abs(v1_above - v1_below)
            v2_jump = abs(v2_above - v2_below)

            details[feature_id][level_name] = (
                v1_jump,
                v2_jump,
            )

            if v2_jump > 0.10:
                passed = False

    return passed, details


def discrimination_check() -> tuple[bool, list[str]]:
    """
    Extreme clearly-better vs clearly-worse measurements must remain separated.

    Requirement:
    - V2 body score difference >= 3 points when one feature moves from
      an excellent-side value to a clearly poor-side value while others
      stay at neutral baseline.
    """
    errors: list[str] = []

    for feature_id, spec in FEATURES.items():
        thresholds = spec["thresholds"]

        excellent_value = max(
            0.0,
            float(thresholds["EXCELLENT"]) * 0.5,
        )
        poor_span = (
            float(thresholds["FAIR"])
            - float(thresholds["GOOD"])
        )
        poor_value = float(thresholds["FAIR"]) + poor_span

        _, excellent_score = score_when_sweeping(
            feature_id,
            excellent_value,
        )
        _, poor_score = score_when_sweeping(
            feature_id,
            poor_value,
        )

        delta = excellent_score - poor_score
        if delta < 3.0:
            errors.append(
                f"{feature_id}: discrimination delta "
                f"{delta:.3f} < 3.0 "
                f"({excellent_value:.2f}° vs {poor_value:.2f}°)"
            )

    return (not errors, errors)


def print_sweep_preview() -> None:
    print("=" * 80)
    print("SWEEP PREVIEW")
    print("=" * 80)

    for feature_id, spec in FEATURES.items():
        thresholds = spec["thresholds"]
        checkpoints = sorted(
            {
                0.0,
                thresholds["EXCELLENT"] - 0.1,
                thresholds["EXCELLENT"],
                thresholds["EXCELLENT"] + 0.1,
                thresholds["GOOD"] - 0.1,
                thresholds["GOOD"],
                thresholds["GOOD"] + 0.1,
                thresholds["FAIR"] - 0.1,
                thresholds["FAIR"],
                thresholds["FAIR"] + 0.1,
                spec["sweep_max"],
            }
        )

        print(f"{feature_id} ({spec['display_name']})")
        print("  value     V1_score   V2_score")
        for value in checkpoints:
            value = max(0.0, float(value))
            v1, v2 = score_when_sweeping(feature_id, value)
            print(
                f"  {value:6.2f}°   {v1:8.2f}   {v2:8.3f}"
            )
        print()


def main() -> None:
    print_real_case_comparison()
    print_sweep_preview()

    mono_pass, mono_errors = monotonicity_check()
    boundary_pass, boundary_details = boundary_jump_check()
    discrim_pass, discrim_errors = discrimination_check()

    print("=" * 80)
    print("AUTOMATED VALIDATION")
    print("=" * 80)

    print(
        f"MONOTONICITY        : "
        f"{'PASS' if mono_pass else 'FAIL'}"
    )
    if mono_errors:
        for error in mono_errors[:10]:
            print(f"  - {error}")

    print(
        f"BOUNDARY ROBUSTNESS : "
        f"{'PASS' if boundary_pass else 'FAIL'}"
    )
    for feature_id, levels in boundary_details.items():
        print(f"  {feature_id}")
        for level_name, (v1_jump, v2_jump) in levels.items():
            print(
                f"    {level_name:9s} "
                f"V1_jump={v1_jump:5.2f} "
                f"V2_jump={v2_jump:.4f}"
            )

    print(
        f"DISCRIMINATION      : "
        f"{'PASS' if discrim_pass else 'FAIL'}"
    )
    if discrim_errors:
        for error in discrim_errors:
            print(f"  - {error}")

    verdict = (
        "PASS"
        if mono_pass and boundary_pass and discrim_pass
        else "REVIEW"
    )

    print()
    print(f"V2.1 VERDICT        : {verdict}")
    print()
    print(
        "NOTE: PASS means the illustrative candidate passed these "
        "mathematical robustness checks only. It does NOT approve "
        "production calibration or scoring changes."
    )


if __name__ == "__main__":
    main()
