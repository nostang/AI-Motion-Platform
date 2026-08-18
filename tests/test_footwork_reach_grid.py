from types import SimpleNamespace

from src.visualization.clear_pose_visualization import LANDMARK_NAMES
from src.visualization.footwork_reach_grid import (
    GRID_SPECS,
    build_footwork_reach_grid,
    capture_footwork_pose_sample,
)


def _sample(analysis_index: int, source_index: int):
    sample = {
        "timestamp_ms": analysis_index * 40,
        "analysis_frame_index": analysis_index,
        "source_frame_index": source_index,
    }
    for point_index, name in enumerate(LANDMARK_NAMES):
        sample[f"{name}_x"] = 0.2 + point_index * 0.01
        sample[f"{name}_y"] = 0.3 + analysis_index * 0.0001
    return sample


def _event(event_id, direction, reach_frame, offset):
    return {
        "event_id": event_id,
        "direction": direction,
        "completed": True,
        "reach_frame": reach_frame,
        "maximum_center_offset": offset,
    }


def test_grid_uses_ready_frame_and_existing_reach_evidence():
    directions = [spec[0] for spec in GRID_SPECS if spec[4] == "direction"]
    events = [
        _event(index, direction, index * 10, index / 10)
        for index, direction in enumerate(directions, start=1)
    ]
    samples = [_sample(5, 105)] + [
        _sample(event["reach_frame"], event["reach_frame"] + 100)
        for event in events
    ]

    grid = build_footwork_reach_grid(samples, events, ready_frame_index=5)

    assert grid["status"] == "READY"
    assert [cell["key"] for cell in grid["cells"]] == [
        spec[0] for spec in GRID_SPECS
    ]
    center = next(cell for cell in grid["cells"] if cell["key"] == "CENTER")
    assert center["analysis_frame_index"] == 5
    assert center["source_frame_index"] == 105
    for event in events:
        cell = next(
            item for item in grid["cells"] if item["key"] == event["direction"]
        )
        assert cell["analysis_frame_index"] == event["reach_frame"]
        assert cell["source_frame_index"] == event["reach_frame"] + 100
        assert cell["event_id"] == event["event_id"]
        assert len(cell["landmarks"]) == 13


def test_duplicate_direction_uses_largest_existing_maximum_offset():
    events = [
        _event(1, "FRONT", 10, 0.2),
        _event(2, "FRONT", 20, 0.4),
    ]
    samples = [_sample(2, 102), _sample(10, 110), _sample(20, 120)]

    grid = build_footwork_reach_grid(samples, events, ready_frame_index=2)

    front = next(cell for cell in grid["cells"] if cell["key"] == "FRONT")
    assert front["event_id"] == 2
    assert front["analysis_frame_index"] == 20
    assert front["source_frame_index"] == 120


def test_incomplete_directions_remain_empty_without_fabricated_frames():
    grid = build_footwork_reach_grid(
        [_sample(3, 103), _sample(12, 112)],
        [_event(1, "RIGHT_FRONT", 12, 0.3)],
        ready_frame_index=3,
    )

    assert grid["status"] == "PARTIAL"
    assert grid["ready_cell_count"] == 2
    left = next(cell for cell in grid["cells"] if cell["key"] == "LEFT")
    assert left == {
        "key": "LEFT",
        "label": "左",
        "row": 2,
        "column": 1,
        "kind": "direction",
        "status": "NOT_READY",
        "reason": "DIRECTION_NOT_COMPLETED",
    }


def test_pose_capture_is_visualization_only_and_has_13_points():
    landmarks = [SimpleNamespace(x=0.25, y=0.5) for _ in range(33)]

    sample = capture_footwork_pose_sample(
        landmarks,
        400,
        analysis_frame_index=10,
        source_frame_index=18,
    )

    assert sample["analysis_frame_index"] == 10
    assert sample["source_frame_index"] == 18
    assert {name for name in LANDMARK_NAMES if f"{name}_x" in sample} == set(
        LANDMARK_NAMES
    )
