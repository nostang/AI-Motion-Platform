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

        return {
            "schema_version": "1.0",
            "progress_version": "progress-engine-v1.0",
            "status": "READY",
            "comparison_status": comparison_status,
            "comparison_mode": mode,
            "motion_type": current.get("motion_type") or current.get("assessment_type"),
            "current": self._snapshot(current),
            "reference": self._snapshot(reference),
            "change": change,
            "direction": direction,
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
            "progress_version": "progress-engine-v1.0",
            "status": "NOT_READY",
            "reason": {"code": code, "message": message},
            "motion_type": motion_type,
        }
