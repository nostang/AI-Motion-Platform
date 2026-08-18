"""Presentation-safe Footwork Movement Reach Grid response."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from src.api.explainable_pose import LANDMARK_NAMES, _safe_landmarks, _safe_number
from src.visualization.footwork_reach_grid import GRID_CELL_COUNT, GRID_SPECS, VERSION


def footwork_reach_grid_state(*, status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "version": VERSION,
        "motion_type": "footwork",
        "cell_count": GRID_CELL_COUNT,
        "cells": [],
        "reason": reason,
    }


def load_footwork_reach_grid(task_dir: Path) -> dict[str, Any]:
    artifact_path = task_dir / "output" / "footwork_reach_grid.json"
    if not artifact_path.is_file():
        return footwork_reach_grid_state(
            status="NOT_READY",
            reason="REACH_GRID_ARTIFACT_NOT_READY",
        )
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return footwork_reach_grid_state(
            status="NOT_READY",
            reason="REACH_GRID_ARTIFACT_INVALID",
        )
    return sanitize_footwork_reach_grid(artifact)


def sanitize_footwork_reach_grid(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, Mapping) or artifact.get("status") not in {
        "READY",
        "PARTIAL",
    }:
        return footwork_reach_grid_state(
            status="NOT_READY",
            reason="REACH_GRID_ARTIFACT_NOT_READY",
        )
    raw_cells = artifact.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) != GRID_CELL_COUNT:
        return footwork_reach_grid_state(
            status="NOT_READY",
            reason="REACH_GRID_CELLS_NOT_READY",
        )
    by_key = {
        cell.get("key"): cell
        for cell in raw_cells
        if isinstance(cell, Mapping)
    }
    cells: list[dict[str, Any]] = []
    for key, label, row, column, kind in GRID_SPECS:
        source = by_key.get(key)
        if not isinstance(source, Mapping):
            return footwork_reach_grid_state(
                status="NOT_READY",
                reason="REACH_GRID_CELLS_NOT_READY",
            )
        cell = {
            "key": key,
            "label": label,
            "row": row,
            "column": column,
            "kind": kind,
            "status": "NOT_READY",
        }
        if source.get("status") == "READY":
            timestamp = _safe_number(source.get("timestamp_ms"))
            landmarks = _safe_landmarks(source.get("landmarks"))
            if (
                timestamp is None
                or timestamp < 0
                or len(landmarks) != len(LANDMARK_NAMES)
            ):
                cell["reason"] = "CELL_POSE_NOT_READY"
            else:
                cell.update(
                    {
                        "status": "READY",
                        "timestamp_ms": (
                            int(timestamp) if timestamp.is_integer() else timestamp
                        ),
                        "landmarks": landmarks,
                    }
                )
        else:
            cell["reason"] = str(source.get("reason") or "CELL_NOT_READY")
        cells.append(cell)

    ready_count = sum(cell["status"] == "READY" for cell in cells)
    return {
        "status": (
            "READY"
            if ready_count == GRID_CELL_COUNT
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        ),
        "version": VERSION,
        "motion_type": "footwork",
        "cell_count": GRID_CELL_COUNT,
        "ready_cell_count": ready_count,
        "cells": cells,
    }


def add_footwork_reach_grid_references(
    grid: dict[str, Any],
    assessment_id: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if grid.get("status") not in {"READY", "PARTIAL"}:
        return grid
    raw_entries = manifest.get("cells") if isinstance(manifest, Mapping) else []
    entries = raw_entries if isinstance(raw_entries, list) else []
    by_key = {
        entry.get("key"): entry
        for entry in entries
        if isinstance(entry, Mapping)
    }
    safe_assessment_id = quote(str(assessment_id), safe="")
    for cell in grid.get("cells", []):
        if cell.get("status") != "READY":
            continue
        key = cell.get("key")
        entry = by_key.get(key)
        width = entry.get("width") if isinstance(entry, Mapping) else None
        height = entry.get("height") if isinstance(entry, Mapping) else None
        ready = (
            isinstance(entry, Mapping)
            and entry.get("status") == "READY"
            and entry.get("storage_status") == "READY"
            and isinstance(width, int)
            and not isinstance(width, bool)
            and width > 0
            and isinstance(height, int)
            and not isinstance(height, bool)
            and height > 0
        )
        cell["image"] = (
            {
                "status": "READY",
                "url": (
                    f"/api/v1/motion-assessments/{safe_assessment_id}/"
                    f"visualization/reach-grid/{quote(str(key), safe='')}"
                ),
                "width": width,
                "height": height,
            }
            if ready
            else {"status": "NOT_READY"}
        )
    return grid
