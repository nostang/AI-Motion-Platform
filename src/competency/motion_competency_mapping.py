"""Motion Competency Mapping V1.

Maps existing Footwork, Serve, and Clear report dimensions into five
cross-motion presentation axes. It does not modify source assessments
or calculate an overall player level.
"""

from __future__ import annotations

from typing import Any, Mapping


MAPPING_VERSION = "motion-competency-mapping-v1"

AXIS_MAPPING = (
    {
        "key": "mobility",
        "label": "移動能力",
        "sources": (
            ("footwork", "skill_score", "movement_completion"),
            ("footwork", "skill_score", "recovery_speed"),
            ("footwork", "assessment_metrics", "direction_coverage"),
            ("footwork", "skill_score", "motion_quality"),
        ),
    },
    {
        "key": "preparation_quality",
        "label": "準備品質",
        "sources": (
            ("serve", "score_breakdown", "preparation_stability"),
            ("clear", "score_breakdown", "sideways_preparation"),
        ),
    },
    {
        "key": "swing_mechanics",
        "label": "揮拍機制",
        "sources": (
            ("serve", "score_breakdown", "swing_completeness"),
            ("clear", "score_breakdown", "swing_smoothness"),
        ),
    },
    {
        "key": "body_coordination",
        "label": "身體協調",
        "sources": (
            ("serve", "score_breakdown", "body_coordination"),
            ("clear", "score_breakdown", "weight_transfer"),
            ("clear", "score_breakdown", "non_racket_arm_balance"),
        ),
    },
    {
        "key": "movement_stability",
        "label": "動作穩定",
        "sources": (
            ("footwork", "skill_score", "body_stability"),
            ("serve", "score_breakdown", "motion_smoothness"),
        ),
    },
)


def _metric(
    reports: Mapping[str, Mapping[str, Any]],
    motion_type: str,
    section: str,
    metric_key: str,
) -> Mapping[str, Any] | None:
    report = reports.get(motion_type)
    if not isinstance(report, Mapping):
        return None

    container = report.get(section)
    if not isinstance(container, Mapping):
        return None

    metric = container.get(metric_key)
    return metric if isinstance(metric, Mapping) else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def build_motion_competency_axes(
    reports: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    axes: list[dict[str, Any]] = []

    for axis_config in AXIS_MAPPING:
        evidence: list[dict[str, Any]] = []
        missing_sources: list[str] = []

        for motion_type, section, metric_key in axis_config["sources"]:
            metric = _metric(
                reports,
                motion_type,
                section,
                metric_key,
            )

            score = _number(metric.get("score")) if metric else None
            max_score = (
                _number(metric.get("max_score"))
                if metric
                else None
            )

            source_id = f"{motion_type}.{section}.{metric_key}"

            if (
                score is None
                or max_score is None
                or max_score <= 0
            ):
                missing_sources.append(source_id)
                continue

            normalized_score = round(
                score / max_score * 100.0,
                1,
            )

            evidence.append(
                {
                    "motion_type": motion_type,
                    "metric_key": metric_key,
                    "score": score,
                    "max_score": max_score,
                    "normalized_score": normalized_score,
                    "source": source_id,
                }
            )

        ready = not missing_sources
        axis_score = (
            round(
                sum(item["normalized_score"] for item in evidence)
                / len(evidence),
                1,
            )
            if ready and evidence
            else None
        )

        axes.append(
            {
                "key": axis_config["key"],
                "label": axis_config["label"],
                "status": "READY" if ready else "INCOMPLETE",
                "score": axis_score,
                "max_score": 100.0,
                "evidence": evidence,
                "missing_sources": missing_sources,
            }
        )

    ready_count = sum(
        axis["status"] == "READY"
        for axis in axes
    )

    return {
        "status": (
            "READY"
            if ready_count == len(axes)
            else "INCOMPLETE"
        ),
        "mapping_version": MAPPING_VERSION,
        "axes": axes,
        "radar_chart": {
            "labels": [axis["label"] for axis in axes],
            "scores": [axis["score"] for axis in axes],
            "max_score": 100.0,
        },
        "overall_score": None,
        "limitations": [
            "Axes are provisional cross-motion presentation mappings.",
            "No cross-axis overall score or formal playing level is calculated.",
            "Each axis uses equal weighting across its declared evidence sources.",
        ],
    }


def build_motion_competency_comparison(
    current_reports: Mapping[str, Mapping[str, Any]],
    previous_reports: Mapping[str, Mapping[str, Any]],
    progress: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build comparable current and previous five-axis profiles."""

    current = build_motion_competency_axes(current_reports)
    previous = build_motion_competency_axes(previous_reports)

    if (
        current["status"] != "READY"
        or previous["status"] != "READY"
    ):
        return {
            "mapping_version": MAPPING_VERSION,
            "comparison_status": "NOT_READY",
            "current": current,
            "previous": previous,
            "changes": [],
        }

    motion_statuses = [
        progress.get(motion_type, {})
        for motion_type in ("footwork", "serve", "clear")
    ]

    if any(
        item.get("status") != "READY"
        for item in motion_statuses
    ):
        comparison_status = "NOT_READY"
    elif any(
        item.get("comparison_status") != "COMPARABLE"
        for item in motion_statuses
    ):
        comparison_status = "COMPARISON_VERSION_MISMATCH"
    else:
        comparison_status = "COMPARABLE"

    changes: list[dict[str, Any]] = []

    if comparison_status == "COMPARABLE":
        previous_by_key = {
            axis["key"]: axis
            for axis in previous["axes"]
        }

        for current_axis in current["axes"]:
            previous_axis = previous_by_key[current_axis["key"]]
            change = round(
                float(current_axis["score"])
                - float(previous_axis["score"]),
                1,
            )

            if change > 0:
                direction = "IMPROVED"
            elif change < 0:
                direction = "DECLINED"
            else:
                direction = "UNCHANGED"

            changes.append(
                {
                    "key": current_axis["key"],
                    "label": current_axis["label"],
                    "current_score": current_axis["score"],
                    "previous_score": previous_axis["score"],
                    "change": change,
                    "direction": direction,
                }
            )

    return {
        "mapping_version": MAPPING_VERSION,
        "comparison_status": comparison_status,
        "current": current,
        "previous": previous,
        "changes": changes,
    }
