from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.visualization.clear_keyframes import extract_clear_keyframes
import src.visualization.clear_keyframes as keyframe_module


def _visualization(status: str = "READY") -> dict:
    return {
        "status": status,
        "motion_type": "clear",
        "racket_side": "right",
        "snapshots": [
            {
                "stage": "preparation",
                "timestamp_ms": 0,
                "analysis_frame_index": 0,
                "source_frame_index": 0,
            },
            {
                "stage": "swing",
                "timestamp_ms": 500,
                "analysis_frame_index": 5,
                "source_frame_index": 5,
            },
            {
                "stage": "finish",
                "timestamp_ms": 1000,
                "analysis_frame_index": 10,
                "source_frame_index": 10,
            },
        ],
    }


def _video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10.0,
        (640, 360),
    )
    assert writer.isOpened()
    for index in range(15):
        frame = np.full((360, 640, 3), index * 12, dtype=np.uint8)
        cv2.rectangle(frame, (80, 60), (240, 300), (30, 180, 240), -1)
        writer.write(frame)
    writer.release()


def test_extracts_three_mapped_resized_jpegs(tmp_path):
    video_path = tmp_path / "source.avi"
    output_dir = tmp_path / "keyframes"
    _video(video_path)

    result = extract_clear_keyframes(
        video_path,
        _visualization(),
        output_dir,
    )

    assert result["status"] == "READY"
    assert [item["stage"] for item in result["keyframes"]] == [
        "preparation",
        "swing",
        "finish",
    ]
    assert [item["requested_timestamp_ms"] for item in result["keyframes"]] == [
        0,
        500,
        1000,
    ]
    assert [item["source_frame_index"] for item in result["keyframes"]] == [
        0,
        5,
        10,
    ]
    assert all(max(item["width"], item["height"]) == 720 for item in result["keyframes"])
    assert all((output_dir / f"{item['stage']}.jpg").is_file() for item in result["keyframes"])
    capture = cv2.VideoCapture(str(video_path))
    sequential_frames = {}
    frame_index = 0
    while frame_index <= 10:
        ok, frame = capture.read()
        assert ok
        if frame_index in {0, 5, 10}:
            sequential_frames[frame_index] = frame
        frame_index += 1
    capture.release()
    for item in result["keyframes"]:
        image_path = output_dir / f"{item['stage']}.jpg"
        decoded = cv2.imread(str(image_path))
        assert decoded is not None
        assert decoded.shape[:2] == (item["height"], item["width"])
        assert item["width"] > item["height"]
        assert float(decoded.std()) > 1.0
        assert 1_000 < image_path.stat().st_size < 1_000_000
        source = sequential_frames[item["source_frame_index"]]
        source = cv2.resize(source, (720, 405), interpolation=cv2.INTER_LINEAR)
        encoded_ok, expected = cv2.imencode(
            ".jpg",
            source,
            [cv2.IMWRITE_JPEG_QUALITY, 85],
        )
        assert encoded_ok
        assert image_path.read_bytes() == expected.tobytes()
    assert json.loads((output_dir / "manifest.json").read_text())["status"] == "READY"


def test_explicit_source_frame_mapping_selects_trimmed_source_frame(tmp_path):
    video_path = tmp_path / "source.avi"
    _video(video_path)
    visualization = _visualization()
    for snapshot in visualization["snapshots"]:
        snapshot["source_frame_index"] += 2

    result = extract_clear_keyframes(
        video_path,
        visualization,
        tmp_path / "keyframes",
    )

    assert [item["analysis_frame_index"] for item in result["keyframes"]] == [
        0,
        5,
        10,
    ]
    assert [item["source_frame_index"] for item in result["keyframes"]] == [
        2,
        7,
        12,
    ]
    assert result["keyframes"][0]["actual_frame_timestamp_ms"] == 200.0
    assert result["keyframes"][1]["actual_frame_timestamp_ms"] == 700.0


def test_timestamps_are_not_used_to_derive_frame_indices(tmp_path):
    video_path = tmp_path / "source.avi"
    _video(video_path)
    visualization = _visualization()
    for index, snapshot in enumerate(visualization["snapshots"]):
        snapshot["timestamp_ms"] = 90_000 - index

    result = extract_clear_keyframes(
        video_path,
        visualization,
        tmp_path / "keyframes",
    )

    assert result["status"] == "READY"
    assert [item["source_frame_index"] for item in result["keyframes"]] == [
        0,
        5,
        10,
    ]


def test_missing_source_frame_mapping_falls_back_safely(tmp_path):
    video_path = tmp_path / "source.avi"
    _video(video_path)
    visualization = _visualization()
    visualization["snapshots"][1].pop("source_frame_index")

    result = extract_clear_keyframes(
        video_path,
        visualization,
        tmp_path / "keyframes",
    )

    assert result["status"] == "PARTIAL"
    assert result["keyframes"][1]["status"] == "NOT_READY"
    assert result["keyframes"][1]["reason"] == "SOURCE_FRAME_MAPPING_NOT_READY"


def test_not_ready_visualization_fails_softly(tmp_path):
    result = extract_clear_keyframes(
        tmp_path / "missing.mov",
        _visualization("NOT_READY"),
        tmp_path / "keyframes",
    )

    assert result["status"] == "NOT_READY"
    assert result["reason"] == "VISUALIZATION_NOT_READY"
    assert result["keyframes"] == []


def test_production_extractor_has_no_random_frame_seek():
    source = Path(keyframe_module.__file__).read_text(encoding="utf-8")

    assert "CAP_PROP_POS_FRAMES" not in source
    assert "source_timestamp" not in source
