"""Fail-soft representative frame extraction for Explainable Pose V1."""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import cv2
import numpy as np


VERSION = "clear-keyframes-v1.0"
STAGES = ("preparation", "swing", "finish")
DEFAULT_MAX_LONG_EDGE = 960
DEFAULT_MIN_LONG_EDGE = 720
DEFAULT_JPEG_QUALITY = 85


def _empty_manifest(reason: str) -> dict[str, Any]:
    return {
        "status": "NOT_READY",
        "version": VERSION,
        "motion_type": "clear",
        "image_format": "image/jpeg",
        "keyframes": [],
        "reason": reason,
        "performance_ms": {
            "extraction_total": 0.0,
            "image_encode_total": 0.0,
        },
    }


def _safe_timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    timestamp = float(value)
    if not isfinite(timestamp) or timestamp < 0:
        return None
    return timestamp


def _stage_snapshots(
    visualization: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    snapshots = visualization.get("snapshots")
    if not isinstance(snapshots, list):
        return {}
    return {
        snapshot.get("stage"): snapshot
        for snapshot in snapshots
        if isinstance(snapshot, Mapping)
        and snapshot.get("stage") in STAGES
    }


def _safe_frame_index(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    frame_index = int(value)
    if frame_index < 0 or float(frame_index) != float(value):
        return None
    return frame_index


def _sequential_source_frames(
    capture: cv2.VideoCapture,
    target_indices: set[int],
) -> tuple[dict[int, np.ndarray], dict[int, float]]:
    frames: dict[int, np.ndarray] = {}
    timestamps: dict[int, float] = {}
    if not target_indices:
        return frames, timestamps

    maximum_index = max(target_indices)
    frame_index = 0
    while frame_index <= maximum_index:
        ok, frame = capture.read()
        if not ok:
            break
        if frame is not None and frame.size and frame_index in target_indices:
            frames[frame_index] = frame.copy()
            decoder_timestamp = float(
                capture.get(cv2.CAP_PROP_POS_MSEC)
            )
            if isfinite(decoder_timestamp) and decoder_timestamp >= 0:
                timestamps[frame_index] = decoder_timestamp
        frame_index += 1
    return frames, timestamps


def _presentation_frame(
    frame: np.ndarray,
    min_long_edge: int,
    max_long_edge: int,
) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(width, height)
    if min_long_edge <= longest <= max_long_edge:
        return frame
    target = max_long_edge if longest > max_long_edge else min_long_edge
    scale = target / longest
    return cv2.resize(
        frame,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=(cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR),
    )


def save_clear_keyframe_manifest(
    manifest: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_clear_keyframes(
    video_path: Path,
    visualization: Mapping[str, Any],
    output_dir: Path,
    *,
    min_long_edge: int = DEFAULT_MIN_LONG_EDGE,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    """Sequentially decode the exact source frames used for Pose inference."""

    started = perf_counter()
    if visualization.get("status") != "READY":
        return _empty_manifest("VISUALIZATION_NOT_READY")

    snapshots = _stage_snapshots(visualization)
    if any(stage not in snapshots for stage in STAGES):
        return _empty_manifest("SNAPSHOTS_NOT_READY")

    video_path = Path(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return _empty_manifest("VIDEO_DECODE_FAILED")

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        capture.release()
        return _empty_manifest("VIDEO_METADATA_NOT_READY")

    if min_long_edge <= 0 or max_long_edge < min_long_edge:
        return _empty_manifest("INVALID_IMAGE_SIZE")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    keyframes: list[dict[str, Any]] = []
    encode_total_ms = 0.0

    requests: dict[str, tuple[float, int, int] | None] = {}
    for stage in STAGES:
        snapshot = snapshots[stage]
        requested_timestamp = _safe_timestamp(snapshot.get("timestamp_ms"))
        analysis_frame_index = _safe_frame_index(
            snapshot.get("analysis_frame_index")
        )
        source_frame_index = _safe_frame_index(
            snapshot.get("source_frame_index")
        )
        requests[stage] = (
            requested_timestamp,
            analysis_frame_index,
            source_frame_index,
        ) if (
            requested_timestamp is not None
            and analysis_frame_index is not None
            and source_frame_index is not None
        ) else None

    target_indices = {
        request[2]
        for request in requests.values()
        if request is not None and request[2] < frame_count
    }
    decode_started = perf_counter()
    frames, decoder_timestamps = _sequential_source_frames(
        capture,
        target_indices,
    )
    sequential_decode_ms = (perf_counter() - decode_started) * 1000.0

    try:
        for stage in STAGES:
            request = requests[stage]
            if request is None:
                keyframes.append(
                    {
                        "stage": stage,
                        "status": "NOT_READY",
                        "reason": "SOURCE_FRAME_MAPPING_NOT_READY",
                    }
                )
                continue
            requested_timestamp, analysis_frame_index, source_frame_index = request
            frame = frames.get(source_frame_index)
            if frame is None:
                keyframes.append(
                    {
                        "stage": stage,
                        "status": "NOT_READY",
                        "requested_timestamp_ms": requested_timestamp,
                        "analysis_frame_index": analysis_frame_index,
                        "source_frame_index": source_frame_index,
                        "reason": "FRAME_DECODE_FAILED",
                    }
                )
                continue

            frame = _presentation_frame(
                frame,
                min_long_edge,
                max_long_edge,
            )
            encode_started = perf_counter()
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
            )
            encode_ms = (perf_counter() - encode_started) * 1000.0
            encode_total_ms += encode_ms
            if not ok or encoded is None or not encoded.size:
                keyframes.append(
                    {
                        "stage": stage,
                        "status": "NOT_READY",
                        "requested_timestamp_ms": requested_timestamp,
                        "analysis_frame_index": analysis_frame_index,
                        "source_frame_index": source_frame_index,
                        "reason": "IMAGE_ENCODE_FAILED",
                    }
                )
                continue

            filename = f"{stage}.jpg"
            destination = output_dir / filename
            destination.write_bytes(encoded.tobytes())
            height, width = frame.shape[:2]
            actual_timestamp = decoder_timestamps.get(source_frame_index)
            keyframes.append(
                {
                    "stage": stage,
                    "status": "READY",
                    "filename": filename,
                    "requested_timestamp_ms": (
                        int(requested_timestamp)
                        if requested_timestamp.is_integer()
                        else requested_timestamp
                    ),
                    "analysis_frame_index": analysis_frame_index,
                    "source_frame_index": source_frame_index,
                    "actual_source_frame_index": source_frame_index,
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
            )
    finally:
        capture.release()

    ready_count = sum(item.get("status") == "READY" for item in keyframes)
    manifest = {
        "status": (
            "READY"
            if ready_count == len(STAGES)
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        ),
        "version": VERSION,
        "motion_type": "clear",
        "image_format": "image/jpeg",
        "min_long_edge": min_long_edge,
        "max_long_edge": max_long_edge,
        "jpeg_quality": jpeg_quality,
        "keyframes": keyframes,
        "performance_ms": {
            "extraction_total": round((perf_counter() - started) * 1000.0, 3),
            "sequential_decode_total": round(sequential_decode_ms, 3),
            "image_encode_total": round(encode_total_ms, 3),
        },
    }
    save_clear_keyframe_manifest(
        manifest,
        output_dir / "manifest.json",
    )
    return manifest
