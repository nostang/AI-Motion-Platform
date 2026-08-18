from src.api.history_trend import build_history_trend


def _report(score, *, completed=True, evaluation_status="EVALUATED"):
    return {
        "summary": {
            "completed": completed,
            "evaluation_status": evaluation_status,
            "overall_score": score,
        },
        "dimensions": {"must_not_leak": 99},
    }


def _item(
    assessment_id,
    motion_type,
    score,
    created_at,
    *,
    completed_at=None,
    report=None,
    status=None,
):
    item = {
        "assessment_id": assessment_id,
        "motion_type": motion_type,
        "overall_score": score,
        "created_at": created_at,
        "completed_at": completed_at,
        "report": report if report is not None else _report(score),
    }
    if status is not None:
        item["status"] = status
    return item


def test_history_trend_filters_invalid_results_and_sorts_full_history():
    histories = {
        "footwork": [
            _item(
                "ma_new",
                "footwork",
                84.5,
                "2026-08-03T00:00:00+00:00",
                completed_at="2026-08-03T00:05:00+00:00",
            ),
            _item(
                "ma_old",
                "footwork",
                78,
                "2026-08-01T00:00:00+00:00",
                completed_at="2026-08-01T00:05:00+00:00",
            ),
            _item(
                "ma_middle",
                "footwork",
                81,
                "2026-08-02T00:00:00+00:00",
            ),
            _item(
                "ma_failed",
                "footwork",
                99,
                "2026-08-04T00:00:00+00:00",
                status="failed",
            ),
            _item(
                "ma_not_evaluated",
                "footwork",
                90,
                "2026-08-05T00:00:00+00:00",
                report=_report(90, evaluation_status="NOT_EVALUATED"),
            ),
            _item(
                "ma_incomplete",
                "footwork",
                88,
                "2026-08-06T00:00:00+00:00",
                report=_report(88, completed=False),
            ),
            _item(
                "ma_no_score",
                "footwork",
                None,
                "2026-08-07T00:00:00+00:00",
            ),
        ],
        "serve": [
            _item(
                "ma_serve",
                "serve",
                79,
                "2026-08-01T00:00:00+00:00",
            )
        ],
        "clear": [],
    }

    result = build_history_trend(1, histories)

    footwork = result["motions"][0]
    assert footwork["status"] == "READY"
    assert [point["assessment_id"] for point in footwork["points"]] == [
        "ma_old",
        "ma_middle",
        "ma_new",
    ]
    assert [point["overall_score"] for point in footwork["points"]] == [
        78.0,
        81.0,
        84.5,
    ]
    assert all("report" not in point for point in footwork["points"])
    assert all("dimensions" not in point for point in footwork["points"])

    serve, clear = result["motions"][1:]
    assert serve["status"] == "INSUFFICIENT_DATA"
    assert serve["point_count"] == 1
    assert clear["status"] == "INSUFFICIENT_DATA"
    assert clear["point_count"] == 0


def test_history_trend_supports_result_summary_score_shape():
    report = {
        "result_summary": {
            "overall": {"score": 86, "status": "EVALUATED"}
        }
    }
    histories = {
        "clear": [
            _item(
                "ma_clear",
                "clear",
                86,
                "2026-08-18T00:00:00Z",
                report=report,
            )
        ]
    }

    result = build_history_trend(7, histories)

    clear = result["motions"][2]
    assert clear["points"][0]["overall_score"] == 86.0
    assert clear["points"][0]["motion_type"] == "clear"
