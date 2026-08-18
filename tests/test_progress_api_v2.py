from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost/test",
)

import src.api.app as api_module


def footwork_report(
    *,
    recovery: float | None = 18.0,
    recovery_level: str | None = "FAIR",
    body: float | None = 18.0,
    body_level: str | None = "FAIR",
) -> dict:
    skill_score = {}

    if recovery is not None:
        skill_score["recovery_speed"] = {
            "score": recovery,
            "max_score": 25,
            "level": recovery_level,
        }

    if body is not None:
        skill_score["body_stability"] = {
            "score": body,
            "max_score": 25,
            "level": body_level,
        }

    return {
        "assessment_type": "footwork",
        "skill_score": skill_score,
    }


def history_item(
    assessment_id: str,
    *,
    overall_score: float,
    report: dict,
    created_at: str,
    model_version: str = "footwork-engine-v1",
    rule_version: str = "footwork-calibration-v1.3",
) -> dict:
    return {
        "assessment_id": assessment_id,
        "assessment_type": "footwork",
        "motion_type": "footwork",
        "overall_score": overall_score,
        "report": report,
        "model_version": model_version,
        "rule_version": rule_version,
        "created_at": created_at,
    }


class FakeRepository:
    def __init__(
        self,
        history: list[dict],
    ) -> None:
        self.history = history

    def user_exists(
        self,
        user_id: int,
    ) -> bool:
        return user_id == 1

    def get_motion_history(
        self,
        user_id: int,
        motion_type: str,
    ) -> list[dict]:
        if user_id != 1:
            return []

        if motion_type != "footwork":
            return []

        return list(self.history)


def test_progress_api_returns_v2_dimensions_and_highlights(
    monkeypatch,
):
    history = [
        history_item(
            "ma_old",
            overall_score=80.0,
            report=footwork_report(
                recovery=18.0,
                recovery_level="FAIR",
                body=18.4,
                body_level="FAIR",
            ),
            created_at="2026-08-01T00:00:00+00:00",
        ),
        history_item(
            "ma_new",
            overall_score=84.5,
            report=footwork_report(
                recovery=21.0,
                recovery_level="GOOD",
                body=19.756,
                body_level="FAIR",
            ),
            created_at="2026-08-18T00:00:00+00:00",
        ),
    ]

    monkeypatch.setattr(
        api_module,
        "repository",
        FakeRepository(history),
    )

    client = TestClient(api_module.app)

    response = client.get(
        "/api/v1/users/1/progress/footwork"
    )

    assert response.status_code == 200

    payload = response.json()
    data = payload.get("data", payload)

    assert data["status"] == "READY"
    assert (
        data["progress_version"]
        == "progress-engine-v2.0"
    )

    body = data["dimensions"]["body_stability"]

    assert body["reference"]["score"] == 18.4
    assert body["current"]["score"] == 19.756
    assert body["current"]["level"] == "FAIR"
    assert body["change"] == 1.356
    assert body["direction"] == "IMPROVED"

    recovery = data["dimensions"]["recovery_speed"]

    assert recovery["reference"]["score"] == 18.0
    assert recovery["current"]["score"] == 21.0
    assert recovery["change"] == 3.0
    assert recovery["direction"] == "IMPROVED"

    highlight = data["highlights"][
        "largest_improvement"
    ]

    assert highlight["dimension_id"] == "recovery_speed"
    assert highlight["change"] == 3.0
    assert highlight["reference_score"] == 18.0
    assert highlight["current_score"] == 21.0

    client.close()


def test_progress_api_does_not_interpret_version_mismatch(
    monkeypatch,
):
    history = [
        history_item(
            "ma_old",
            overall_score=80.0,
            report=footwork_report(
                recovery=None,
                body=12.0,
                body_level="POOR",
            ),
            created_at="2026-08-01T00:00:00+00:00",
            rule_version="footwork-calibration-v1.2",
        ),
        history_item(
            "ma_new",
            overall_score=84.0,
            report=footwork_report(
                recovery=None,
                body=19.756,
                body_level="FAIR",
            ),
            created_at="2026-08-18T00:00:00+00:00",
            rule_version="footwork-calibration-v1.3",
        ),
    ]

    monkeypatch.setattr(
        api_module,
        "repository",
        FakeRepository(history),
    )

    client = TestClient(api_module.app)

    response = client.get(
        "/api/v1/users/1/progress/footwork"
    )

    assert response.status_code == 200

    payload = response.json()
    data = payload.get("data", payload)

    assert (
        data["comparison_status"]
        == "COMPARISON_VERSION_MISMATCH"
    )
    assert data["direction"] == "NOT_INTERPRETED"

    body = data["dimensions"]["body_stability"]

    assert body["current"]["score"] == 19.756
    assert body["reference"]["score"] == 12.0
    assert body["direction"] == "NOT_INTERPRETED"

    assert (
        data["highlights"]["largest_improvement"]
        is None
    )
    assert (
        data["highlights"]["largest_decline"]
        is None
    )

    client.close()


def test_progress_api_returns_409_when_history_is_insufficient(
    monkeypatch,
):
    history = [
        history_item(
            "ma_only",
            overall_score=84.0,
            report=footwork_report(
                body=19.756,
            ),
            created_at="2026-08-18T00:00:00+00:00",
        ),
    ]

    monkeypatch.setattr(
        api_module,
        "repository",
        FakeRepository(history),
    )

    client = TestClient(api_module.app)

    response = client.get(
        "/api/v1/users/1/progress/footwork"
    )

    assert response.status_code == 409

    payload = response.json()

    assert payload["success"] is False
    assert payload["error"]["code"] == "PROGRESS_NOT_READY"

    details = payload["error"].get("details") or {}

    assert details["history_count"] == 1
    assert details["motion_type"] == "footwork"

    client.close()
