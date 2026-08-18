from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

import src.visualization.clear_motion_sequence_keyframes as sequence_module
from src.visualization.clear_motion_sequence_keyframes import (
    extract_clear_motion_sequence_keyframes,
    extract_serve_motion_sequence_keyframes,
)


def _video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10.0,
        (640, 360),
    )
    assert writer.isOpened()
    for index in range(24):
        frame = np.full((360, 640, 3), index * 8, dtype=np.uint8)
        cv2.circle(frame, (80 + index * 10, 180), 35, (20, 180, 240), -1)
        writer.write(frame)
    writer.release()


def _sequence() -> dict:
    indices = (2, 5, 8, 11, 14, 17)
    return {
        "status": "READY",
        "frames": [
            {
                "index": index,
                "timestamp_ms": 90_000 - index,
                "analysis_frame_index": source_index - 2,
                "source_frame_index": source_index,
            }
            for index, source_index in enumerate(indices, start=1)
        ],
    }


def test_extracts_six_exact_sequential_source_frames(tmp_path):
    video_path = tmp_path / "source.avi"
    output_dir = tmp_path / "motion_sequence"
    _video(video_path)

    result = extract_clear_motion_sequence_keyframes(
        video_path,
        _sequence(),
        output_dir,
    )

    assert result["status"] == "READY"
    assert [frame["index"] for frame in result["frames"]] == list(range(1, 7))
    assert [frame["source_frame_index"] for frame in result["frames"]] == [
        2,
        5,
        8,
        11,
        14,
        17,
    ]

    capture = cv2.VideoCapture(str(video_path))
    expected_sources = {}
    source_index = 0
    while source_index <= 17:
        ok, frame = capture.read()
        assert ok
        if source_index in {2, 5, 8, 11, 14, 17}:
            expected_sources[source_index] = frame
        source_index += 1
    capture.release()

    for entry in result["frames"]:
        source = cv2.resize(
            expected_sources[entry["source_frame_index"]],
            (720, 405),
            interpolation=cv2.INTER_LINEAR,
        )
        ok, expected = cv2.imencode(
            ".jpg",
            source,
            [cv2.IMWRITE_JPEG_QUALITY, 85],
        )
        assert ok
        actual_path = output_dir / f"{entry['index']:02d}.jpg"
        assert actual_path.read_bytes() == expected.tobytes()


def test_timestamp_values_never_choose_source_frames(tmp_path):
    video_path = tmp_path / "source.avi"
    _video(video_path)

    result = extract_clear_motion_sequence_keyframes(
        video_path,
        _sequence(),
        tmp_path / "motion_sequence",
    )

    assert [frame["source_frame_index"] for frame in result["frames"]] == [
        2,
        5,
        8,
        11,
        14,
        17,
    ]


def test_incomplete_or_unordered_mapping_fails_softly(tmp_path):
    video_path = tmp_path / "source.avi"
    _video(video_path)
    sequence = _sequence()
    sequence["frames"][3]["source_frame_index"] = 5

    result = extract_clear_motion_sequence_keyframes(
        video_path,
        sequence,
        tmp_path / "motion_sequence",
    )

    assert result["status"] == "NOT_READY"
    assert result["reason"] == "SEQUENCE_ORDER_NOT_READY"


def test_sequence_extractor_has_no_random_seek_or_fps_mapping():
    source = Path(sequence_module.__file__).read_text(encoding="utf-8")

    assert "CAP_PROP_POS_FRAMES" not in source
    assert "CAP_PROP_FPS" not in source
    assert "source_timestamp" not in source


def test_serve_uses_the_same_forward_only_exact_frame_extractor(tmp_path):
    video_path = tmp_path / "source.avi"
    _video(video_path)
    sequence = _sequence()
    sequence["motion_type"] = "serve"

    result = extract_serve_motion_sequence_keyframes(
        video_path,
        sequence,
        tmp_path / "serve_motion_sequence",
    )

    assert result["status"] == "READY"
    assert result["version"] == "serve-motion-sequence-keyframes-v1.1"
    assert result["motion_type"] == "serve"
    assert [frame["actual_source_frame_index"] for frame in result["frames"]] == [
        2,
        5,
        8,
        11,
        14,
        17,
    ]
