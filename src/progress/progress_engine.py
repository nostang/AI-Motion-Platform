"""Progress Engine V1."""

from __future__ import annotations
from typing import Any, Iterable, Mapping


class ProgressEngine:
    SUPPORTED_MODES = {"PREVIOUS", "FIRST", "BEST", "CUSTOM"}

    def compare(
        self,
        history: Iterable[Mapping[str, Any]],
        *,
        mode: str = "PREVIOUS",
        reference_assessment_id: str | None = None,
    ) -> dict[str, Any]:
        items = [dict(x) for x in history if isinstance(x, Mapping)]
        if not items:
            return self._not_ready("NO_HISTORY", "沒有可比較的歷史 Assessment。")

        mode = mode.strip().upper()
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(f"Unsupported comparison mode: {mode}")

        items = sorted(
            items,
            key=lambda x: (x.get("created_at") or "", x.get("assessment_id") or ""),
        )
        current = items[-1]

        if current.get("overall_score") is None:
            return self._not_ready(
                "CURRENT_SCORE_MISSING",
                "目前 Assessment 沒有 overall_score。",
                motion_type=current.get("motion_type") or current.get("assessment_type"),
            )

        reference = self._select_reference(
            items,
            mode=mode,
            reference_assessment_id=reference_assessment_id,
        )

        if reference is None:
            return self._not_ready(
                "REFERENCE_NOT_FOUND",
                "找不到可用的比較基準。",
                motion_type=current.get("motion_type") or current.get("assessment_type"),
            )

        current_score = float(current["overall_score"])
        reference_score = float(reference["overall_score"])
        change = round(current_score - reference_score, 2)

        version_mismatch = self._version_mismatch(current, reference)

        if version_mismatch:
            comparison_status = "COMPARISON_VERSION_MISMATCH"
            direction = "NOT_INTERPRETED"
        else:
            comparison_status = "COMPARABLE"
            if change > 0:
                direction = "IMPROVED"
            elif change < 0:
                direction = "DECLINED"
            else:
                direction = "UNCHANGED"

        dimensions = self._compare_dimensions(
            current,
            reference,
            version_mismatch=version_mismatch,
        )

        highlights = self._build_highlights(
            dimensions
        )

        return {
            "schema_version": "1.0",
            "progress_version": "progress-engine-v2.0",
            "status": "READY",
            "comparison_status": comparison_status,
            "comparison_mode": mode,
            "motion_type": current.get("motion_type") or current.get("assessment_type"),
            "current": self._snapshot(current),
            "reference": self._snapshot(reference),
            "change": change,
            "direction": direction,
            "dimensions": dimensions,
            "highlights": highlights,
            "version_mismatch": {
                "detected": version_mismatch,
                "current_model_version": current.get("model_version"),
                "reference_model_version": reference.get("model_version"),
                "current_rule_version": current.get("rule_version"),
                "reference_rule_version": reference.get("rule_version"),
            },
            "limitations": [
                "Progress compares observed historical assessment results only.",
                "Progress does not predict future performance.",
                "When model_version or rule_version differs, the numeric difference is shown but is not interpreted as improvement or decline.",
            ],
        }

    @staticmethod
    def _build_highlights(
        dimensions: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Summarize the largest comparable dimension changes.

        Highlights describe observed score changes only. Dimensions
        that are not comparable, unchanged, or version-mismatched
        are intentionally excluded from interpretation.
        """

        improvements: list[dict[str, Any]] = []
        declines: list[dict[str, Any]] = []

        for dimension_id, comparison in dimensions.items():
            if not isinstance(comparison, Mapping):
                continue

            if comparison.get("comparison_status") != "COMPARABLE":
                continue

            direction = comparison.get("direction")
            change = comparison.get("change")

            if (
                not isinstance(change, (int, float))
                or isinstance(change, bool)
            ):
                continue

            current = comparison.get("current")
            reference = comparison.get("reference")

            if not isinstance(current, Mapping):
                continue
            if not isinstance(reference, Mapping):
                continue

            item = {
                "dimension_id": str(dimension_id),
                "change": float(change),
                "direction": direction,
                "reference_score": reference.get("score"),
                "current_score": current.get("score"),
                "reference_level": reference.get("level"),
                "current_level": current.get("level"),
            }

            if direction == "IMPROVED" and change > 0:
                improvements.append(item)
            elif direction == "DECLINED" and change < 0:
                declines.append(item)

        largest_improvement = (
            max(
                improvements,
                key=lambda item: item["change"],
            )
            if improvements
            else None
        )

        largest_decline = (
            min(
                declines,
                key=lambda item: item["change"],
            )
            if declines
            else None
        )

        return {
            "largest_improvement": largest_improvement,
            "largest_decline": largest_decline,
        }

    @classmethod
    def _compare_dimensions(
        cls,
        current: Mapping[str, Any],
        reference: Mapping[str, Any],
        *,
        version_mismatch: bool,
    ) -> dict[str, Any]:
        current_dimensions = cls._extract_dimensions(
            current.get("report")
        )
        reference_dimensions = cls._extract_dimensions(
            reference.get("report")
        )

        dimension_ids = (
            set(current_dimensions)
            | set(reference_dimensions)
        )

        result: dict[str, Any] = {}

        for dimension_id in sorted(dimension_ids):
            current_item = current_dimensions.get(
                dimension_id
            )
            reference_item = reference_dimensions.get(
                dimension_id
            )

            current_score = (
                current_item.get("score")
                if current_item
                else None
            )
            reference_score = (
                reference_item.get("score")
                if reference_item
                else None
            )

            comparable = (
                current_score is not None
                and reference_score is not None
            )

            current_config_version = (
                current_item.get("config_version")
                if current_item
                else None
            )
            reference_config_version = (
                reference_item.get("config_version")
                if reference_item
                else None
            )

            dimension_version_mismatch = (
                current_config_version is not None
                and reference_config_version is not None
                and current_config_version
                != reference_config_version
            )

            if not comparable:
                change = None
                comparison_status = "NOT_COMPARABLE"
                direction = "NOT_INTERPRETED"
            else:
                change = round(
                    float(current_score)
                    - float(reference_score),
                    3,
                )

                if (
                    version_mismatch
                    or dimension_version_mismatch
                ):
                    comparison_status = (
                        "COMPARISON_VERSION_MISMATCH"
                    )
                    direction = "NOT_INTERPRETED"
                else:
                    comparison_status = "COMPARABLE"

                    if change > 0:
                        direction = "IMPROVED"
                    elif change < 0:
                        direction = "DECLINED"
                    else:
                        direction = "UNCHANGED"

            result[dimension_id] = {
                "current": current_item,
                "reference": reference_item,
                "change": change,
                "comparison_status": comparison_status,
                "direction": direction,
            }

        return result

    @staticmethod
    def _extract_dimensions(
        report: Any,
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(report, Mapping):
            return {}

        dimensions: dict[str, dict[str, Any]] = {}

        observation = report.get("observation")
        observation = (
            observation
            if isinstance(observation, Mapping)
            else {}
        )

        dimension_versions = {
            "body_stability": (
                observation.get("body_stable") or {}
            ).get("config_version")
            if isinstance(
                observation.get("body_stable"),
                Mapping,
            )
            else None,
            "recovery_speed": (
                observation.get("recovery_time") or {}
            ).get("config_version")
            if isinstance(
                observation.get("recovery_time"),
                Mapping,
            )
            else None,
            "motion_quality": (
                observation.get("motion_quality") or {}
            ).get("config_version")
            if isinstance(
                observation.get("motion_quality"),
                Mapping,
            )
            else None,
        }

        for section_name in (
            "skill_score",
            "assessment_metrics",
            "score_breakdown",
        ):
            section = report.get(section_name)

            if not isinstance(section, Mapping):
                continue

            for dimension_id, raw_item in section.items():
                if not isinstance(raw_item, Mapping):
                    continue

                raw_score = raw_item.get("score")

                score = (
                    float(raw_score)
                    if isinstance(raw_score, (int, float))
                    and not isinstance(raw_score, bool)
                    else None
                )

                raw_max_score = raw_item.get("max_score")

                max_score = (
                    float(raw_max_score)
                    if isinstance(raw_max_score, (int, float))
                    and not isinstance(raw_max_score, bool)
                    else None
                )

                level = raw_item.get("level")

                normalized_id = str(dimension_id)

                # Earlier sections have higher precedence.
                #
                # Footwork's normalized skill_score /
                # assessment_metrics must not be silently
                # overwritten by a later generic
                # score_breakdown compatibility section.
                if normalized_id in dimensions:
                    continue

                dimension = {
                    "score": score,
                    "max_score": max_score,
                    "level": (
                        str(level)
                        if level is not None
                        else None
                    ),
                }

                config_version = (
                    dimension_versions.get(
                        normalized_id
                    )
                )

                if config_version is not None:
                    dimension["config_version"] = str(
                        config_version
                    )

                dimensions[normalized_id] = dimension

        return dimensions

    def _select_reference(
        self,
        items: list[dict[str, Any]],
        *,
        mode: str,
        reference_assessment_id: str | None,
    ) -> dict[str, Any] | None:
        current = items[-1]
        candidates = [
            item for item in items[:-1] if item.get("overall_score") is not None
        ]

        if mode == "PREVIOUS":
            return candidates[-1] if candidates else None
        if mode == "FIRST":
            return candidates[0] if candidates else None
        if mode == "BEST":
            return max(candidates, key=lambda x: float(x["overall_score"])) if candidates else None
        if mode == "CUSTOM":
            if not reference_assessment_id:
                raise ValueError("CUSTOM mode requires reference_assessment_id.")
            if current.get("assessment_id") == reference_assessment_id:
                raise ValueError("CUSTOM reference cannot be the current assessment.")
            for item in candidates:
                if item.get("assessment_id") == reference_assessment_id:
                    return item
            return None
        return None

    @staticmethod
    def _version_mismatch(
        current: Mapping[str, Any],
        reference: Mapping[str, Any],
    ) -> bool:
        return (
            current.get("model_version") != reference.get("model_version")
            or current.get("rule_version") != reference.get("rule_version")
        )

    @staticmethod
    def _snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "assessment_id": item.get("assessment_id"),
            "score": float(item["overall_score"]) if item.get("overall_score") is not None else None,
            "created_at": item.get("created_at"),
            "model_version": item.get("model_version"),
            "rule_version": item.get("rule_version"),
        }

    @staticmethod
    def _not_ready(
        code: str,
        message: str,
        *,
        motion_type: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "progress_version": "progress-engine-v2.0",
            "status": "NOT_READY",
            "reason": {"code": code, "message": message},
            "motion_type": motion_type,
        }
