from pathlib import Path

import cv2
import numpy as np

import src.visualization.footwork_reach_grid_keyframes as extractor_module
from src.visualization.footwork_reach_grid import GRID_SPECS
from src.visualization.footwork_reach_grid_keyframes import (
    extract_footwork_reach_grid_keyframes,
)


def _video(path: Path, frame_count: int = 20):
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        25.0,
        (160, 96),
    )
    assert writer.isOpened()
    for index in range(frame_count):
        frame = np.full((96, 160, 3), index * 10, dtype=np.uint8)
        cv2.putText(frame, str(index), (10, 50), 0, 1, (255, 0, 0), 2)
        writer.write(frame)
    writer.release()


def _artifact():
    cells = []
    for index, (key, label, row, column, kind) in enumerate(GRID_SPECS):
        if key in {"LEFT", "RIGHT"}:
            cells.append({
                "key": key,
                "label": label,
                "row": row,
                "column": column,
                "kind": kind,
                "status": "NOT_READY",
                "reason": "DIRECTION_NOT_COMPLETED",
            })
            continue
        cells.append({
            "key": key,
            "label": label,
            "row": row,
            "column": column,
            "kind": kind,
            "status": "READY",
            "timestamp_ms": index * 40,
            "analysis_frame_index": index,
            "source_frame_index": index * 2,
        })
    return {"status": "PARTIAL", "cells": cells}


def test_extracts_ready_cells_by_exact_source_index_in_one_forward_pass(tmp_path):
    video = tmp_path / "source.avi"
    output = tmp_path / "grid"
    _video(video)

    manifest = extract_footwork_reach_grid_keyframes(
        video,
        _artifact(),
        output,
        min_long_edge=96,
        max_long_edge=160,
        jpeg_quality=90,
    )

    assert manifest["status"] == "PARTIAL"
    assert len(manifest["cells"]) == 9
    ready = [cell for cell in manifest["cells"] if cell["status"] == "READY"]
    assert len(ready) == 7
    assert all(
        cell["actual_source_frame_index"] == cell["source_frame_index"]
        for cell in ready
    )
    assert all((output / cell["filename"]).is_file() for cell in ready)
    assert [
        cell["key"] for cell in manifest["cells"] if cell["status"] != "READY"
    ] == ["LEFT", "RIGHT"]


def test_extractor_does_not_use_random_seek_or_average_fps():
    source = Path(extractor_module.__file__).read_text(encoding="utf-8")
    assert "CAP_PROP_POS_FRAMES" not in source
    assert "CAP_PROP_FPS" not in source
    assert ".set(" not in source
