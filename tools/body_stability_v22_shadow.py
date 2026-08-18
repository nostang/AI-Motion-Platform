#!/usr/bin/env python3
"""
Body Stability Robustness V2.2 — Shadow Comparison

SIMULATION / SHADOW ONLY

This tool reads existing Footwork report JSON files and compares:
- production V1 Body Stability result
- illustrative V2 continuous shadow score

It does NOT modify:
- production scoring
- calibration
- reports
- database
- API
- tests

Default input files:
  /tmp/footwork_original.json
  /tmp/footwork_normalized.json
  /tmp/footwork_720p_originalfps.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


FEATURES = {
    "MF001_shoulder_tilt": {
        "weight": 0.35,
        "thresholds": {
            "EXCELLENT": 3.0,
            "GOOD": 6.0,
            "FAIR": 12.0,
        },
    },
    "MF002_hip_tilt": {
        "weight": 0.35,
        "thresholds": {
            "EXCELLENT": 3.0,
            "GOOD": 6.0,
            "FAIR": 10.0,
        },
    },
    "MF003_torso_lean": {
        "weight": 0.30,
        "thresholds": {
            "EXCELLENT": 5.0,
            "GOOD": 10.0,
            "FAIR": 18.0,
        },
    },
}

DEFAULT_REPORTS = {
    "original": Path("/tmp/footwork_original.json"),
    "720p30": Path("/tmp/footwork_normalized.json"),
    "720p_preserve": Path("/tmp/footwork_720p_originalfps.json"),
}


def overall_level(weighted_points: float) -> str:
    if weighted_points >= 3.5:
        return "EXCELLENT"
    if weighted_points >= 2.75:
        return "GOOD"
    if weighted_points >= 2.0:
        return "FAIR"
    return "POOR"


def continuous_feature_points(
    value: float,
    thresholds: dict[str, float],
) -> float:
    value = abs(float(value))
    excellent = float(thresholds["EXCELLENT"])
    good = float(thresholds["GOOD"])
    fair = float(thresholds["FAIR"])

    if value <= excellent:
        return 4.0
    if value <= good:
        return 4.0 - ((value - excellent) / (good - excellent))
    if value <= fair:
        return 3.0 - ((value - good) / (fair - good))

    poor_span = fair - good
    return max(1.0, 2.0 - ((value - fair) / poor_span))


def continuous_body_score(weighted_points: float) -> float:
    points = max(1.0, min(4.0, float(weighted_points)))

    if points <= 2.0:
        return 12.0 + (points - 1.0) * 6.0
    if points <= 3.0:
        return 18.0 + (points - 2.0) * 4.0
    return 22.0 + (points - 3.0) * 3.0


def load_report(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("data", raw)


def extract_case(name: str, path: Path) -> dict:
    data = load_report(path)

    summary = data.get("summary") or {}
    observation = data.get("observation") or {}
    body = observation.get("body_stable") or {}

    feature_values: dict[str, float] = {}
    production_levels: dict[str, str] = {}

    for item in body.get("feature_levels", []):
        feature_id = item.get("feature_id")
        if feature_id not in FEATURES:
            continue
        feature_values[feature_id] = float(item["aggregate_value"])
        production_levels[feature_id] = str(item.get("level"))

    missing = [
        feature_id
        for feature_id in FEATURES
        if feature_id not in feature_values
    ]
    if missing:
        raise ValueError(
            f"{name}: missing Body Stability features: {missing}"
        )

    feature_points: dict[str, float] = {}
    weighted_points = 0.0

    for feature_id, spec in FEATURES.items():
        points = continuous_feature_points(
            feature_values[feature_id],
            spec["thresholds"],
        )
        feature_points[feature_id] = points
        weighted_points += points * spec["weight"]

    return {
        "name": name,
        "path": str(path),
        "assessment_id": data.get("assessment_id"),
        "overall_score": summary.get("overall_score"),
        "coach_status": summary.get("coach_status"),
        "system_confidence": summary.get("system_confidence"),
        "v1_body_score": body.get("score"),
        "v1_body_level": body.get("level"),
        "feature_values": feature_values,
        "production_levels": production_levels,
        "v2_feature_points": feature_points,
        "v2_weighted_points": weighted_points,
        "v2_display_level": overall_level(weighted_points),
        "v2_shadow_score": continuous_body_score(weighted_points),
    }


def case_delta(case: dict, original: dict) -> dict:
    return {
        "v1_body_delta": (
            float(case["v1_body_score"])
            - float(original["v1_body_score"])
        ),
        "v2_shadow_delta": (
            float(case["v2_shadow_score"])
            - float(original["v2_shadow_score"])
        ),
        "overall_delta": (
            float(case["overall_score"])
            - float(original["overall_score"])
        ),
    }


def print_case(case: dict, original: dict | None = None) -> None:
    print("-" * 84)
    print(case["name"])
    print("-" * 84)
    print(
        f"assessment_id      : {case['assessment_id']}\n"
        f"overall_score      : {case['overall_score']}\n"
        f"coach_status       : {case['coach_status']}\n"
        f"V1 Body Stability  : {case['v1_body_score']} "
        f"({case['v1_body_level']})\n"
        f"V2 shadow score    : {case['v2_shadow_score']:.3f} "
        f"({case['v2_display_level']})\n"
        f"V2 weighted points : {case['v2_weighted_points']:.4f}"
    )

    print("\nfeatures:")
    for feature_id in FEATURES:
        print(
            f"  {feature_id:26s} "
            f"value={case['feature_values'][feature_id]:8.4f} "
            f"V1={case['production_levels'][feature_id]:9s} "
            f"V2_points={case['v2_feature_points'][feature_id]:.4f}"
        )

    if original is not None:
        delta = case_delta(case, original)
        print("\nvs original:")
        print(
            f"  V1 Body delta : {delta['v1_body_delta']:+.3f}\n"
            f"  V2 shadow delta: {delta['v2_shadow_delta']:+.3f}\n"
            f"  Overall delta : {delta['overall_delta']:+.3f}"
        )


def robustness_verdict(cases: list[dict]) -> tuple[str, dict]:
    v1_scores = [float(case["v1_body_score"]) for case in cases]
    v2_scores = [float(case["v2_shadow_score"]) for case in cases]

    v1_range = max(v1_scores) - min(v1_scores)
    v2_range = max(v2_scores) - min(v2_scores)

    original = next(case for case in cases if case["name"] == "original")

    normalization_cases = [
        case for case in cases if case["name"] != "original"
    ]
    v1_abs_deltas = [
        abs(case_delta(case, original)["v1_body_delta"])
        for case in normalization_cases
    ]
    v2_abs_deltas = [
        abs(case_delta(case, original)["v2_shadow_delta"])
        for case in normalization_cases
    ]

    # Shadow candidate should reduce range and average normalization sensitivity.
    range_improved = v2_range < v1_range
    sensitivity_improved = (
        mean(v2_abs_deltas) < mean(v1_abs_deltas)
    )

    verdict = (
        "PASS"
        if range_improved and sensitivity_improved
        else "REVIEW"
    )

    return verdict, {
        "v1_range": v1_range,
        "v2_range": v2_range,
        "v1_mean_abs_delta": mean(v1_abs_deltas),
        "v2_mean_abs_delta": mean(v2_abs_deltas),
        "range_improved": range_improved,
        "sensitivity_improved": sensitivity_improved,
    }


def write_csv(cases: list[dict], output_path: Path) -> None:
    fields = [
        "name",
        "assessment_id",
        "overall_score",
        "coach_status",
        "v1_body_score",
        "v1_body_level",
        "v2_shadow_score",
        "v2_display_level",
        "v2_weighted_points",
        "MF001_shoulder_tilt",
        "MF002_hip_tilt",
        "MF003_torso_lean",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for case in cases:
            writer.writerow({
                "name": case["name"],
                "assessment_id": case["assessment_id"],
                "overall_score": case["overall_score"],
                "coach_status": case["coach_status"],
                "v1_body_score": case["v1_body_score"],
                "v1_body_level": case["v1_body_level"],
                "v2_shadow_score": round(
                    case["v2_shadow_score"], 6
                ),
                "v2_display_level": case["v2_display_level"],
                "v2_weighted_points": round(
                    case["v2_weighted_points"], 6
                ),
                "MF001_shoulder_tilt":
                    case["feature_values"]["MF001_shoulder_tilt"],
                "MF002_hip_tilt":
                    case["feature_values"]["MF002_hip_tilt"],
                "MF003_torso_lean":
                    case["feature_values"]["MF003_torso_lean"],
            })


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--original",
        type=Path,
        default=DEFAULT_REPORTS["original"],
    )
    parser.add_argument(
        "--720p30",
        dest="p720_30",
        type=Path,
        default=DEFAULT_REPORTS["720p30"],
    )
    parser.add_argument(
        "--720p-preserve",
        dest="p720_preserve",
        type=Path,
        default=DEFAULT_REPORTS["720p_preserve"],
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("/tmp/body_stability_v22_shadow.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    paths = {
        "original": args.original,
        "720p30": args.p720_30,
        "720p_preserve": args.p720_preserve,
    }

    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(
                f"{name}: report not found: {path}"
            )

    cases = [
        extract_case(name, path)
        for name, path in paths.items()
    ]
    original = next(
        case for case in cases
        if case["name"] == "original"
    )

    print("=" * 84)
    print("BODY STABILITY V2.2 — SHADOW COMPARISON")
    print("=" * 84)

    for case in cases:
        print_case(
            case,
            None if case["name"] == "original" else original,
        )

    verdict, stats = robustness_verdict(cases)

    print()
    print("=" * 84)
    print("ROBUSTNESS SUMMARY")
    print("=" * 84)
    print(
        f"V1 Body Stability range       : "
        f"{stats['v1_range']:.3f}"
    )
    print(
        f"V2 shadow score range         : "
        f"{stats['v2_range']:.3f}"
    )
    print(
        f"V1 mean |delta vs original|   : "
        f"{stats['v1_mean_abs_delta']:.3f}"
    )
    print(
        f"V2 mean |delta vs original|   : "
        f"{stats['v2_mean_abs_delta']:.3f}"
    )
    print(
        f"Range improved                : "
        f"{'PASS' if stats['range_improved'] else 'FAIL'}"
    )
    print(
        f"Sensitivity improved          : "
        f"{'PASS' if stats['sensitivity_improved'] else 'FAIL'}"
    )
    print()
    print(f"V2.2 SHADOW VERDICT           : {verdict}")

    write_csv(cases, args.csv)
    print(f"CSV                         : {args.csv}")
    print()
    print(
        "NOTE: This is shadow analysis only. "
        "V1 remains the production score."
    )


if __name__ == "__main__":
    main()
