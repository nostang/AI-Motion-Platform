"""Direction Coverage Assessment AR003.

This metric describes system-observed coverage of the expected footwork
 directions. It does not claim that a missing direction is a user technique
 error because direction classification still requires calibration and expert
 review.
"""

from __future__ import annotations

from typing import Any, Mapping


METRIC_ID = "AR003"
CONFIG_VERSION = "direction-coverage-v1"
MAX_SCORE = 25


def evaluate_direction_coverage(
    *,
    direction_coverage: Mapping[str, Any],
    missing_directions: list[str],
    duplicate_directions: Mapping[str, Any],
    unknown_direction_count: int,
    expected_direction_count: int = 8,
) -> dict[str, Any]:
    observed_count = sum(bool(value) for value in direction_coverage.values())
    expected_count = max(1, int(expected_direction_count))
    coverage_ratio = min(1.0, observed_count / expected_count)
    score = round(MAX_SCORE * coverage_ratio, 2)
    complete = observed_count == expected_count and unknown_direction_count == 0

    return {
        "metric_id": METRIC_ID,
        "name": "DIRECTION_COVERAGE",
        "display_name": "方向覆蓋",
        "status": "EVALUATED",
        "result": "PASS" if complete else "NEEDS_REVIEW",
        "score": score,
        "max_score": MAX_SCORE,
        "observed_direction_count": observed_count,
        "expected_direction_count": expected_count,
        "coverage_ratio": round(coverage_ratio, 4),
        "direction_coverage": dict(direction_coverage),
        "missing_directions": list(missing_directions),
        "duplicate_directions": dict(duplicate_directions),
        "unknown_direction_count": int(unknown_direction_count),
        "config_version": CONFIG_VERSION,
        "explanation": (
            "系統辨識到八個預期方向。"
            if complete
            else f"系統辨識到 {observed_count}/{expected_count} 個預期方向，需人工確認缺少方向。"
        ),
        "limitations": [
            "此分數描述系統辨識到的方向覆蓋，不等同於完整步法技術分數。",
            "缺少方向可能來自動作、拍攝角度或方向分類誤差。",
            "方向分類仍需 Expert Review 與 Calibration 驗證。",
        ],
    }
