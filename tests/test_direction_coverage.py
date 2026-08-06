from src.assessment.direction_coverage import evaluate_direction_coverage
from src.coach.coach_rules import evaluate_direction_coverage as coach_rule


def test_incomplete_direction_coverage_is_scored_but_needs_review():
    coverage = {
        "RIGHT_FRONT": True,
        "LEFT_FRONT": True,
        "RIGHT_BACK": True,
        "LEFT_BACK": False,
        "RIGHT": False,
        "LEFT": True,
        "FRONT": True,
        "BACK": True,
    }
    metric = evaluate_direction_coverage(
        direction_coverage=coverage,
        missing_directions=["LEFT_BACK", "RIGHT"],
        duplicate_directions={"RIGHT_FRONT": 2, "LEFT_FRONT": 2},
        unknown_direction_count=0,
    )
    assert metric["metric_id"] == "AR003"
    assert metric["score"] == 18.75
    assert metric["result"] == "NEEDS_REVIEW"

    rule = coach_rule({
        "direction_coverage_assessment": metric,
        "direction_coverage_complete": False,
        "direction_coverage": coverage,
        "missing_directions": ["LEFT_BACK", "RIGHT"],
        "duplicate_directions": {"RIGHT_FRONT": 2, "LEFT_FRONT": 2},
        "unknown_direction_count": 0,
        "system_confidence": 0.8341,
    })
    assert rule["rule_id"] == "CR003"
    assert rule["evidence"]["score"] == 18.75
    assert rule["result"] == "NEEDS_REVIEW"


def test_complete_direction_coverage_passes():
    coverage = {name: True for name in (
        "RIGHT_FRONT", "LEFT_FRONT", "RIGHT_BACK", "LEFT_BACK",
        "RIGHT", "LEFT", "FRONT", "BACK",
    )}
    metric = evaluate_direction_coverage(
        direction_coverage=coverage,
        missing_directions=[],
        duplicate_directions={},
        unknown_direction_count=0,
    )
    assert metric["score"] == 25
    assert metric["result"] == "PASS"
