import json

import pytest

from src.coach.ai_coach_v2 import (
    MOTION_METRICS,
    UNSUPPORTED_CLAIM_TERMS,
    build_ai_coach_v2,
    build_recent_trend,
)


def _summary(score=80):
    return {
        "completed": True,
        "evaluation_status": "EVALUATED",
        "overall_score": score,
        "system_confidence": 0.9,
    }


def _history(*scores):
    return {
        "status": "READY",
        "points": [
            {"overall_score": score}
            for score in scores
        ],
    }


def _clear_report():
    return {
        "assessment_id": "ma_clear",
        "assessment_type": "clear",
        "summary": _summary(85),
        "score_breakdown": {
            "sideways_preparation": {
                "score": 25, "max_score": 25, "level": "EXCELLENT"
            },
            "weight_transfer": {
                "score": 20, "max_score": 25, "level": "GOOD"
            },
            "non_racket_arm_balance": {
                "score": 20, "max_score": 25, "level": "GOOD"
            },
            "swing_smoothness": {
                "score": 20, "max_score": 25, "level": "FAIR"
            },
        },
        "highlights": {
            "strengths": [
                "sideways_preparation",
                "weight_transfer",
                "non_racket_arm_balance",
                "swing_smoothness",
            ],
            "improvement_priorities": [],
        },
        "coach": {
            "feedback": [
                {"metric": "swing_smoothness", "level": "FAIR"}
            ]
        },
    }


def _serve_report():
    return {
        "assessment_id": "ma_serve",
        "assessment_type": "serve",
        "summary": _summary(79),
        "score_breakdown": {
            "preparation_stability": {
                "score": 25, "max_score": 25, "level": "EXCELLENT"
            },
            "swing_completeness": {
                "score": 20, "max_score": 25, "level": "GOOD"
            },
            "body_coordination": {
                "score": 14, "max_score": 25, "level": "FAIR"
            },
            "motion_smoothness": {
                "score": 20, "max_score": 25, "level": "GOOD"
            },
        },
        "highlights": {
            "strengths": [
                "preparation_stability",
                "swing_completeness",
                "motion_smoothness",
            ],
            "improvement_priorities": ["body_coordination"],
        },
        "coach": {
            "feedback": [
                {"metric": "body_coordination", "level": "FAIR"}
            ]
        },
    }


def _footwork_report():
    return {
        "assessment_id": "ma_footwork",
        "assessment_type": "footwork",
        "summary": _summary(84.6),
        "skill_score": {
            "movement_completion": {"level": "EXCELLENT"},
            "recovery_speed": {"level": "GOOD"},
            "motion_quality": {"level": "GOOD"},
            "body_stability": {"level": "FAIR"},
        },
        "assessment_metrics": {
            "direction_coverage": {"level": "GOOD"}
        },
        "result_summary": {
            "score_breakdown": {
                "movement_completion": {"score": 25, "max_score": 25},
                "recovery_speed": {"score": 18, "max_score": 25},
                "direction_coverage": {"score": 18.75, "max_score": 25},
                "motion_quality": {"score": 22, "max_score": 25},
                "body_stability": {"score": 19.6, "max_score": 25},
            },
            "highlights": {
                "strengths": ["movement_completion"],
                "improvement_priorities": ["recovery_speed"],
                "review_required": [
                    {"rule_id": "CR003", "display_name": "八方向覆蓋"},
                    {"rule_id": "CR006", "display_name": "身體穩定度"},
                ],
            },
        },
        "feedback": [
            {"source_rule_id": "CR006", "message": "既有回饋"}
        ],
    }


@pytest.mark.parametrize(
    ("report_factory", "strengths", "priorities"),
    [
        (
            _clear_report,
            ["sideways_preparation", "weight_transfer"],
            ["swing_smoothness"],
        ),
        (
            _serve_report,
            ["preparation_stability", "swing_completeness"],
            ["body_coordination"],
        ),
        (
            _footwork_report,
            ["movement_completion", "motion_quality"],
            ["recovery_speed", "direction_coverage"],
        ),
    ],
)
def test_ai_coach_v2_selects_supported_motion_evidence(
    report_factory,
    strengths,
    priorities,
):
    result = build_ai_coach_v2(report_factory(), _history(70, 76, 82))

    assert result["status"] == "READY"
    assert [item["metric"] for item in result["strengths"]] == strengths
    assert [item["metric"] for item in result["priorities"]] == priorities
    assert result["next_focus"]["metric"] == priorities[0]
    assert len(result["strengths"]) <= 2
    assert len(result["priorities"]) <= 2


def test_training_plan_only_references_supported_priority_metrics():
    for report in (_clear_report(), _serve_report(), _footwork_report()):
        result = build_ai_coach_v2(report, _history(70, 75, 80))
        priority_metrics = {item["metric"] for item in result["priorities"]}
        for drill in result["training_plan"]:
            assert drill["focus_metric"] in priority_metrics
            assert drill["focus_metric"] in MOTION_METRICS[result["motion_type"]]
            assert drill["tracking_status"] == "SUGGESTED_ONLY"
        assert len(result["training_plan"]) <= 3


@pytest.mark.parametrize(
    ("scores", "status"),
    [
        ((70, 74, 79), "UPWARD"),
        ((82, 78, 76), "DOWNWARD"),
        ((80, 81, 81), "STABLE"),
        ((80, 81), "INSUFFICIENT_DATA"),
    ],
)
def test_recent_trend_conservative_rules(scores, status):
    result = build_recent_trend(_history(*scores))

    assert result["status"] == status
    assert result["window_size"] == min(3, len(scores))


def test_output_contains_no_unsupported_claims():
    for report in (_clear_report(), _serve_report(), _footwork_report()):
        rendered = json.dumps(
            build_ai_coach_v2(report, _history(70, 75, 80)),
            ensure_ascii=False,
        ).lower()
        for term in UNSUPPORTED_CLAIM_TERMS:
            assert term.lower() not in rendered
