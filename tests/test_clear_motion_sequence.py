from __future__ import annotations

from src.visualization.clear_motion_sequence import (
    LANDMARK_NAMES,
    SEQUENCE_FRAME_COUNT,
    build_clear_motion_sequence,
    build_serve_motion_sequence,
)


def _sample(index: int, *, source_offset: int = 100) -> dict[str, float]:
    sample: dict[str, float] = {
        "timestamp_ms": float(index * 40),
        "analysis_frame_index": index,
        "source_frame_index": index + source_offset,
    }
    for landmark_index, name in enumerate(LANDMARK_NAMES):
        sample[f"{name}_x"] = 0.2 + landmark_index * 0.01
        sample[f"{name}_y"] = 0.1 + index * 0.001
    return sample


def test_selects_six_strictly_increasing_source_frames_with_padding():
    result = build_clear_motion_sequence(
        [_sample(index) for index in range(100)],
        racket_side="right",
    )

    assert result["status"] == "READY"
    assert len(result["frames"]) == SEQUENCE_FRAME_COUNT
    indices = [frame["source_frame_index"] for frame in result["frames"]]
    assert indices == [107, 124, 141, 158, 175, 192]
    assert indices == sorted(set(indices))
    assert result["valid_pose_window"] == {
        "first_source_frame_index": 100,
        "last_source_frame_index": 199,
    }
    assert result["usable_pose_window"] == {
        "first_source_frame_index": 107,
        "last_source_frame_index": 192,
    }


def test_short_six_sample_window_safely_uses_all_valid_samples():
    result = build_clear_motion_sequence(
        [_sample(index, source_offset=0) for index in range(6)],
        racket_side="left",
    )

    assert result["status"] == "READY"
    assert [frame["source_frame_index"] for frame in result["frames"]] == list(
        range(6)
    )


def test_fewer_than_six_valid_samples_are_not_ready():
    result = build_clear_motion_sequence(
        [_sample(index) for index in range(5)],
        racket_side="right",
    )

    assert result["status"] == "NOT_READY"
    assert result["reason"] == "INSUFFICIENT_VALID_POSE_SAMPLES"
    assert result["frames"] == []


def test_invalid_pose_sample_is_skipped_and_each_frame_keeps_own_landmarks():
    samples = [_sample(index, source_offset=0) for index in range(20)]
    samples[10]["right_wrist_x"] = 2.0

    result = build_clear_motion_sequence(samples, racket_side="right")

    assert result["status"] == "READY"
    by_source = {int(sample["source_frame_index"]): sample for sample in samples}
    for frame in result["frames"]:
        source = frame["source_frame_index"]
        assert source != 10
        assert frame["landmarks"]["nose"] == {
            "x": by_source[source]["nose_x"],
            "y": by_source[source]["nose_y"],
        }
        assert frame["analysis_frame_index"] == by_source[source][
            "analysis_frame_index"
        ]


def test_duplicate_source_frames_are_removed_before_selection():
    samples = [_sample(index, source_offset=0) for index in range(8)]
    duplicate = dict(samples[3])
    duplicate["analysis_frame_index"] = 99
    samples.insert(4, duplicate)

    result = build_clear_motion_sequence(samples, racket_side="right")

    indices = [frame["source_frame_index"] for frame in result["frames"]]
    assert result["status"] == "READY"
    assert len(indices) == len(set(indices)) == SEQUENCE_FRAME_COUNT


def test_serve_selects_only_from_analysis_window_with_same_strategy():
    samples = [_sample(index, source_offset=0) for index in range(120)]

    result = build_serve_motion_sequence(
        samples,
        racket_side="right",
        analysis_window={"start_sample": 10, "end_sample": 109},
    )

    assert result["status"] == "READY"
    assert result["version"] == "serve-motion-sequence-v1.1"
    assert result["motion_type"] == "serve"
    assert result["analysis_window"] == {
        "start_sample": 10,
        "end_sample": 109,
    }
    indices = [frame["source_frame_index"] for frame in result["frames"]]
    assert indices == [17, 34, 51, 68, 85, 102]
    assert indices == sorted(set(indices))


def test_serve_requires_a_valid_analysis_window():
    result = build_serve_motion_sequence(
        [_sample(index) for index in range(20)],
        racket_side="right",
        analysis_window={"start_sample": 10, "end_sample": 99},
    )

    assert result["status"] == "NOT_READY"
    assert result["motion_type"] == "serve"
    assert result["reason"] == "ANALYSIS_WINDOW_NOT_READY"
