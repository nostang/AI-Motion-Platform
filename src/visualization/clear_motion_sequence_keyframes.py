"""Sequential JPEG extraction for racket Motion Sequence V1.1."""

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
from src.visualization.clear_motion_sequence import SEQUENCE_FRAME_COUNT


VERSION = "clear-motion-sequence-keyframes-v1.1"
SERVE_VERSION = "serve-motion-sequence-keyframes-v1.1"


def _empty_manifest(
    reason: str,
    *,
    motion_type: str = "clear",
) -> dict[str, Any]:
    return {
        "status": "NOT_READY",
        "version": SERVE_VERSION if motion_type == "serve" else VERSION,
        "motion_type": motion_type,
        "image_format": "image/jpeg",
        "frames": [],
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


def _extract_motion_sequence_keyframes(
    video_path: Path,
    sequence: Mapping[str, Any],
    output_dir: Path,
    *,
    motion_type: str,
    min_long_edge: int = DEFAULT_MIN_LONG_EDGE,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    """Decode exact source frames in one forward-only pass."""

    started = perf_counter()
    if sequence.get("status") != "READY":
        return _empty_manifest("SEQUENCE_NOT_READY", motion_type=motion_type)
    raw_frames = sequence.get("frames")
    if not isinstance(raw_frames, list) or len(raw_frames) != SEQUENCE_FRAME_COUNT:
        return _empty_manifest(
            "SEQUENCE_FRAMES_NOT_READY",
            motion_type=motion_type,
        )
    if min_long_edge <= 0 or max_long_edge < min_long_edge:
        return _empty_manifest("INVALID_IMAGE_SIZE", motion_type=motion_type)

    requests: list[tuple[int, float, int, int]] = []
    for expected_index, frame in enumerate(raw_frames, start=1):
        if not isinstance(frame, Mapping) or frame.get("index") != expected_index:
            return _empty_manifest(
                "SEQUENCE_FRAME_MAPPING_NOT_READY",
                motion_type=motion_type,
            )
        timestamp = _safe_timestamp(frame.get("timestamp_ms"))
        analysis_index = _safe_frame_index(frame.get("analysis_frame_index"))
        source_index = _safe_frame_index(frame.get("source_frame_index"))
        if timestamp is None or analysis_index is None or source_index is None:
            return _empty_manifest(
                "SEQUENCE_FRAME_MAPPING_NOT_READY",
                motion_type=motion_type,
            )
        requests.append((expected_index, timestamp, analysis_index, source_index))

    source_indices = [request[3] for request in requests]
    if source_indices != sorted(set(source_indices)):
        return _empty_manifest(
            "SEQUENCE_ORDER_NOT_READY",
            motion_type=motion_type,
        )

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return _empty_manifest("VIDEO_DECODE_FAILED", motion_type=motion_type)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0 or source_indices[-1] >= frame_count:
        capture.release()
        return _empty_manifest(
            "VIDEO_METADATA_NOT_READY",
            motion_type=motion_type,
        )

    decode_started = perf_counter()
    decoded, decoder_timestamps = _sequential_source_frames(
        capture,
        set(source_indices),
    )
    sequential_decode_ms = (perf_counter() - decode_started) * 1000.0
    capture.release()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    encode_total_ms = 0.0

    for index, timestamp, analysis_index, source_index in requests:
        source = decoded.get(source_index)
        if source is None:
            results.append(
                {
                    "index": index,
                    "status": "NOT_READY",
                    "analysis_frame_index": analysis_index,
                    "source_frame_index": source_index,
                    "reason": "FRAME_DECODE_FAILED",
                }
            )
            continue

        presentation = _presentation_frame(source, min_long_edge, max_long_edge)
        encode_started = perf_counter()
        ok, encoded = cv2.imencode(
            ".jpg",
            presentation,
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
        )
        encode_ms = (perf_counter() - encode_started) * 1000.0
        encode_total_ms += encode_ms
        if not ok or encoded is None or not encoded.size:
            results.append(
                {
                    "index": index,
                    "status": "NOT_READY",
                    "analysis_frame_index": analysis_index,
                    "source_frame_index": source_index,
                    "reason": "IMAGE_ENCODE_FAILED",
                }
            )
            continue

        filename = f"{index:02d}.jpg"
        (output_dir / filename).write_bytes(encoded.tobytes())
        height, width = presentation.shape[:2]
        actual_timestamp = decoder_timestamps.get(source_index)
        results.append(
            {
                "index": index,
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
        )

    ready_count = sum(frame.get("status") == "READY" for frame in results)
    manifest = {
        "status": (
            "READY"
            if ready_count == SEQUENCE_FRAME_COUNT
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        ),
        "version": SERVE_VERSION if motion_type == "serve" else VERSION,
        "motion_type": motion_type,
        "image_format": "image/jpeg",
        "min_long_edge": min_long_edge,
        "max_long_edge": max_long_edge,
        "jpeg_quality": jpeg_quality,
        "frames": results,
        "performance_ms": {
            "extraction_total": round((perf_counter() - started) * 1000.0, 3),
            "sequential_decode_total": round(sequential_decode_ms, 3),
            "image_encode_total": round(encode_total_ms, 3),
        },
    }
    _save_manifest(manifest, output_dir / "manifest.json")
    return manifest


def extract_clear_motion_sequence_keyframes(
    video_path: Path,
    sequence: Mapping[str, Any],
    output_dir: Path,
    *,
    min_long_edge: int = DEFAULT_MIN_LONG_EDGE,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    return _extract_motion_sequence_keyframes(
        video_path,
        sequence,
        output_dir,
        motion_type="clear",
        min_long_edge=min_long_edge,
        max_long_edge=max_long_edge,
        jpeg_quality=jpeg_quality,
    )


def extract_serve_motion_sequence_keyframes(
    video_path: Path,
    sequence: Mapping[str, Any],
    output_dir: Path,
    *,
    min_long_edge: int = DEFAULT_MIN_LONG_EDGE,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    return _extract_motion_sequence_keyframes(
        video_path,
        sequence,
        output_dir,
        motion_type="serve",
        min_long_edge=min_long_edge,
        max_long_edge=max_long_edge,
        jpeg_quality=jpeg_quality,
    )
