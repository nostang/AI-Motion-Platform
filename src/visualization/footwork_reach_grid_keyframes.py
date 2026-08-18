"""Forward-only JPEG extraction for Footwork Movement Reach Grid."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import cv2

from src.visualization.clear_keyframes import (
    DEFAULT_JPEG_QUALITY,
    DEFAULT_MAX_LONG_EDGE,
    DEFAULT_MIN_LONG_EDGE,
    _presentation_frame,
    _safe_frame_index,
    _safe_timestamp,
    _sequential_source_frames,
)
from src.visualization.footwork_reach_grid import (
    CELL_SLUGS,
    GRID_CELL_COUNT,
    GRID_SPECS,
)


VERSION = "footwork-reach-grid-keyframes-v1.0"


def _manifest_state(reason: str) -> dict[str, Any]:
    return {
        "status": "NOT_READY",
        "version": VERSION,
        "motion_type": "footwork",
        "image_format": "image/jpeg",
        "cells": [],
        "reason": reason,
        "performance_ms": {
            "extraction_total": 0.0,
            "sequential_decode_total": 0.0,
            "image_encode_total": 0.0,
        },
    }


def _save_manifest(manifest: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_footwork_reach_grid_keyframes(
    video_path: Path,
    artifact: Mapping[str, Any],
    output_dir: Path,
    *,
    min_long_edge: int = DEFAULT_MIN_LONG_EDGE,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    """Decode every ready grid cell by exact source index in one pass."""

    started = perf_counter()
    if artifact.get("status") not in {"READY", "PARTIAL"}:
        return _manifest_state("GRID_NOT_READY")
    raw_cells = artifact.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) != GRID_CELL_COUNT:
        return _manifest_state("GRID_CELLS_NOT_READY")
    if min_long_edge <= 0 or max_long_edge < min_long_edge:
        return _manifest_state("INVALID_IMAGE_SIZE")

    by_key = {
        cell.get("key"): cell
        for cell in raw_cells
        if isinstance(cell, Mapping)
    }
    requests: list[tuple[str, float, int, int]] = []
    results: list[dict[str, Any]] = []
    for key, label, _, _, _ in GRID_SPECS:
        cell = by_key.get(key)
        if not isinstance(cell, Mapping):
            return _manifest_state("GRID_CELL_MAPPING_NOT_READY")
        if cell.get("status") != "READY":
            results.append(
                {
                    "key": key,
                    "label": label,
                    "status": "NOT_READY",
                    "reason": str(cell.get("reason") or "CELL_NOT_READY"),
                }
            )
            continue
        timestamp = _safe_timestamp(cell.get("timestamp_ms"))
        analysis_index = _safe_frame_index(cell.get("analysis_frame_index"))
        source_index = _safe_frame_index(cell.get("source_frame_index"))
        if timestamp is None or analysis_index is None or source_index is None:
            return _manifest_state("GRID_CELL_MAPPING_NOT_READY")
        requests.append((key, timestamp, analysis_index, source_index))

    if not requests:
        return _manifest_state("GRID_HAS_NO_READY_CELLS")
    source_indices = {request[3] for request in requests}
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return _manifest_state("VIDEO_DECODE_FAILED")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0 or max(source_indices) >= frame_count:
        capture.release()
        return _manifest_state("VIDEO_METADATA_NOT_READY")

    decode_started = perf_counter()
    decoded, decoder_timestamps = _sequential_source_frames(
        capture,
        source_indices,
    )
    sequential_decode_ms = (perf_counter() - decode_started) * 1000.0
    capture.release()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    encoded_by_key: dict[str, dict[str, Any]] = {}
    encode_total_ms = 0.0
    for key, timestamp, analysis_index, source_index in requests:
        source = decoded.get(source_index)
        if source is None:
            encoded_by_key[key] = {
                "key": key,
                "status": "NOT_READY",
                "reason": "FRAME_DECODE_FAILED",
            }
            continue
        presentation = _presentation_frame(
            source,
            min_long_edge,
            max_long_edge,
        )
        encode_started = perf_counter()
        ok, encoded = cv2.imencode(
            ".jpg",
            presentation,
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
        )
        encode_ms = (perf_counter() - encode_started) * 1000.0
        encode_total_ms += encode_ms
        if not ok or encoded is None or not encoded.size:
            encoded_by_key[key] = {
                "key": key,
                "status": "NOT_READY",
                "reason": "IMAGE_ENCODE_FAILED",
            }
            continue

        filename = f"{CELL_SLUGS[key]}.jpg"
        (output_dir / filename).write_bytes(encoded.tobytes())
        height, width = presentation.shape[:2]
        actual_timestamp = decoder_timestamps.get(source_index)
        encoded_by_key[key] = {
            "key": key,
            "status": "READY",
            "filename": filename,
            "requested_timestamp_ms": (
                int(timestamp) if timestamp.is_integer() else timestamp
            ),
            "analysis_frame_index": analysis_index,
            "source_frame_index": source_index,
            "actual_source_frame_index": source_index,
            "actual_frame_timestamp_ms": (
                round(actual_timestamp, 3)
                if actual_timestamp is not None
                else None
            ),
            "width": width,
            "height": height,
            "size_bytes": int(encoded.size),
            "encode_duration_ms": round(encode_ms, 3),
        }

    results = [encoded_by_key.get(item["key"], item) for item in results]
    existing_keys = {item["key"] for item in results}
    for key, _, _, _, _ in GRID_SPECS:
        if key not in existing_keys:
            results.append(encoded_by_key[key])
    order = {spec[0]: index for index, spec in enumerate(GRID_SPECS)}
    results.sort(key=lambda item: order[item["key"]])

    ready_count = sum(item.get("status") == "READY" for item in results)
    manifest = {
        "status": (
            "READY"
            if ready_count == GRID_CELL_COUNT
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        ),
        "version": VERSION,
        "motion_type": "footwork",
        "image_format": "image/jpeg",
        "min_long_edge": min_long_edge,
        "max_long_edge": max_long_edge,
        "jpeg_quality": jpeg_quality,
        "cells": results,
        "performance_ms": {
            "extraction_total": round((perf_counter() - started) * 1000.0, 3),
            "sequential_decode_total": round(sequential_decode_ms, 3),
            "image_encode_total": round(encode_total_ms, 3),
        },
    }
    _save_manifest(manifest, output_dir / "manifest.json")
    return manifest
