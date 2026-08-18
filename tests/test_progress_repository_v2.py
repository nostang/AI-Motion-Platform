from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.api.postgres_repository import (
    PostgresVideoAnalysisRepository,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = None
        self.executed_params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self.executed_sql = sql
        self.executed_params = params

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_motion_history_preserves_report_metrics_json(
    monkeypatch,
    tmp_path: Path,
):
    created_at = datetime(
        2026,
        8,
        18,
        2,
        6,
        32,
        tzinfo=timezone.utc,
    )

    completed_at = datetime(
        2026,
        8,
        18,
        2,
        8,
        17,
        tzinfo=timezone.utc,
    )

    report = {
        "assessment_type": "footwork",
        "skill_score": {
            "body_stability": {
                "score": 19.783,
                "max_score": 25,
                "level": "FAIR",
            },
            "recovery_speed": {
                "score": 18.0,
                "max_score": 25,
                "level": "GOOD",
            },
        },
        "assessment_metrics": {
            "direction_coverage": {
                "score": 18.75,
                "max_score": 25,
                "level": "GOOD",
            },
        },
    }

    rows = [
        {
            "external_analysis_id": "ma_test",
            "analysis_type": "footwork",
            "overall_score": 84.783,
            "metrics_json": report,
            "model_version": "0.5.1",
            "rule_version": "footwork-calibration-v1.3",
            "created_at": created_at,
            "completed_at": completed_at,
        }
    ]

    repository = PostgresVideoAnalysisRepository(
        "postgresql://unused",
        tmp_path,
    )

    connection = FakeConnection(rows)

    monkeypatch.setattr(
        repository,
        "_connect",
        lambda: connection,
    )

    history = repository.get_motion_history(
        1,
        " FOOTWORK ",
    )

    assert len(history) == 1

    item = history[0]

    assert item["assessment_id"] == "ma_test"
    assert item["motion_type"] == "footwork"
    assert item["assessment_type"] == "footwork"
    assert item["overall_score"] == 84.783

    assert item["report"] == report

    assert (
        item["report"]["skill_score"]["body_stability"]["score"]
        == 19.783
    )
    assert (
        item["report"]["skill_score"]["body_stability"]["level"]
        == "FAIR"
    )

    assert item["model_version"] == "0.5.1"
    assert (
        item["rule_version"]
        == "footwork-calibration-v1.3"
    )

    assert item["created_at"] == created_at.isoformat()
    assert item["completed_at"] == completed_at.isoformat()

    sql = connection.cursor_instance.executed_sql
    params = connection.cursor_instance.executed_params

    assert "metrics_json" in sql
    assert "metrics_json IS NOT NULL" in sql
    assert params == (1, "footwork")
