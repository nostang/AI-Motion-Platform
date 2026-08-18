from __future__ import annotations

from dataclasses import dataclass
from math import sin
from pathlib import Path

import pytest

from src.features.clear_features import ClearFeatureTracker
from src.validator.motion_input_validation import (
    MotionInputValidationRejected,
    MotionInputValidator,
    load_motion_input_validation_config,
    require_motion_input_ready,
    save_motion_input_validation,
)


@dataclass
class Landmark:
    x: float
    y: float
    visibility: float = 1.0
    presence: float = 1.0


BASE_POINTS = {
    0: (0.50, 0.16),
    11: (0.42, 0.30),
    12: (0.58, 0.30),
    13: (0.38, 0.42),
    14: (0.62, 0.42),
    15: (0.35, 0.54),
    16: (0.65, 0.54),
    23: (0.45, 0.55),
    24: (0.55, 0.55),
    25: (0.45, 0.72),
    26: (0.55, 0.72),
    27: (0.45, 0.90),
    28: (0.55, 0.90),
}


def landmarks(
    frame: int = 0,
    *,
    motion_type: str = "clear",
    hidden: set[int] | None = None,
) -> list[Landmark]:
    result = [Landmark(0.5, 0.5) for _ in range(33)]
    movement = sin(frame * 0.8) * 0.045
    hidden = hidden or set()
    for index, (x, y) in BASE_POINTS.items():
        if motion_type in {"clear", "serve"} and index in {15, 16}:
            x += movement
        if motion_type == "footwork" and index in {23, 24, 25, 26, 27, 28}:
            x += movement
        confidence = 0.1 if index in hidden else 1.0
        result[index] = Landmark(x, y, confidence, confidence)
    return result


@pytest.mark.parametrize("motion_type", ["clear", "serve", "footwork"])
def test_valid_motion_profiles_are_ready(motion_type):
    validator = MotionInputValidator(motion_type)
    for frame in range(30):
        validator.observe(landmarks(frame, motion_type=motion_type))

    result = validator.build()

    assert result["status"] == "READY"
    assert result["reasons"] == []
    assert result["metrics"]["pose_detection_ratio"] == 1.0
    assert result["metrics"]["motion_activity"] > 0


def test_no_reliable_pose_is_invalid_and_retryable():
    validator = MotionInputValidator("clear")
    for _ in range(30):
        validator.observe(None)

    result = validator.build()

    assert result["status"] == "INVALID"
    assert result["reasons"] == ["NO_RELIABLE_POSE"]
    assert result["retryable"] is True


def test_static_person_needs_review_instead_of_invalid():
    validator = MotionInputValidator("serve")
    static = landmarks()
    for _ in range(30):
        validator.observe(static)

    result = validator.build()

    assert result["status"] == "NEEDS_REVIEW"
    assert result["reasons"] == ["LOW_MOTION_ACTIVITY"]
    assert result["metrics"]["pose_detection_ratio"] == 1.0


def test_low_detection_is_reviewable_when_pose_exists():
    validator = MotionInputValidator("clear")
    for frame in range(30):
        validator.observe(
            landmarks(frame) if frame % 4 == 0 else None
        )

    result = validator.build()

    assert result["status"] == "NEEDS_REVIEW"
    assert "LOW_POSE_DETECTION" in result["reasons"]


def test_clear_tolerates_missing_distal_lower_body():
    validator = MotionInputValidator("clear")
    for frame in range(30):
        validator.observe(
            landmarks(frame, hidden={25, 26, 27, 28})
        )

    result = validator.build()

    assert result["status"] == "READY"


def test_footwork_requires_lower_body_visibility():
    validator = MotionInputValidator("footwork")
    for frame in range(30):
        validator.observe(
            landmarks(
                frame,
                motion_type="footwork",
                hidden={25, 26, 27, 28},
            )
        )

    result = validator.build()

    assert result["status"] == "NEEDS_REVIEW"
    assert "INSUFFICIENT_LOWER_BODY_VISIBILITY" in result["reasons"]


def test_serve_requires_upper_body_visibility():
    validator = MotionInputValidator("serve")
    for frame in range(30):
        validator.observe(
            landmarks(
                frame,
                motion_type="serve",
                hidden={11, 12, 13, 14, 15, 16},
            )
        )

    result = validator.build()

    assert result["status"] == "NEEDS_REVIEW"
    assert "INSUFFICIENT_UPPER_BODY_VISIBILITY" in result["reasons"]


def test_thresholds_are_versioned_provisional_and_separate():
    config = load_motion_input_validation_config()

    assert config["validation_version"] == "motion-input-validation-v1"
    assert config["status"] == "PROVISIONAL"
    assert set(config["profiles"]) == {"clear", "serve", "footwork"}


def test_non_ready_result_stops_before_formal_scoring(tmp_path):
    validator = MotionInputValidator("clear")
    for _ in range(20):
        validator.observe(None)
    result = validator.build()
    path = tmp_path / "motion_input_validation.json"
    save_motion_input_validation(result, path)

    with pytest.raises(MotionInputValidationRejected) as rejected:
        require_motion_input_ready(result)

    assert rejected.value.code == "INPUT_VALIDATION_FAILED"
    assert rejected.value.retryable is True
    assert path.is_file()


def test_validation_observation_does_not_change_clear_scoring_features():
    baseline = ClearFeatureTracker(expected_racket_side="right")
    observed = ClearFeatureTracker(expected_racket_side="right")
    validator = MotionInputValidator("clear")

    for frame in range(30):
        pose = landmarks(frame)
        baseline.observe(pose, frame * 40)
        validator.observe(pose)
        observed.observe(pose, frame * 40)

    assert observed.build() == baseline.build()


@pytest.mark.parametrize(
    ("filename", "scoring_call"),
    [
        ("clear_demo.py", "assessment = ClearAssessmentBuilder"),
        ("serve_demo.py", "assessment = ServeAssessmentBuilder"),
        ("pose_demo.py", "assessment_result = assessment_builder.build"),
    ],
)
def test_all_motion_pipelines_gate_before_formal_scoring(
    filename,
    scoring_call,
):
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / filename
    ).read_text(encoding="utf-8")

    assert source.index(
        "require_motion_input_ready(input_validation)"
    ) < source.index(scoring_call)
