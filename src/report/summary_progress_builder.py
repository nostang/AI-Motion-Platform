"""Build compact per-motion progress data for the Web summary."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

MOTION_ORDER = ("footwork", "serve", "clear")


def build_summary_progress(
    histories: Mapping[str, Iterable[Mapping[str, Any]]],
    progress_engine,
) -> dict[str, dict[str, Any]]:
    """Build PREVIOUS comparison for each motion independently."""

    output: dict[str, dict[str, Any]] = {}

    for motion_type in MOTION_ORDER:
        history = list(histories.get(motion_type, []))

        result = progress_engine.compare(
            history,
            mode="PREVIOUS",
        )

        if result.get("status") != "READY":
            reason = result.get("reason") or {}
            reason_code = reason.get("code")

            if reason_code == "REFERENCE_NOT_FOUND":
                output[motion_type] = {
                    "status": "FIRST_RECORD",
                    "previous_score": None,
                    "change": None,
                    "direction": None,
                }
            else:
                output[motion_type] = {
                    "status": "NOT_READY",
                    "previous_score": None,
                    "change": None,
                    "direction": None,
                    "reason": reason,
                }
            continue

        reference = result.get("reference") or {}

        output[motion_type] = {
            "status": "READY",
            "previous_score": reference.get("score"),
            "change": result.get("change"),
            "direction": result.get("direction"),
            "comparison_status": result.get("comparison_status"),
        }

    return output
