from fastapi.testclient import TestClient

import src.api.app as api_module


class FakeRepository:
    def user_exists(self, user_id: int) -> bool:
        return user_id == 1

    def get_motion_history(self, user_id: int, motion_type: str):
        if user_id != 1:
            return []
        return [
            {
                "assessment_id": f"ma_{motion_type}_{index}",
                "motion_type": motion_type,
                "overall_score": 70 + index,
                "report": {
                    "summary": {
                        "completed": True,
                        "evaluation_status": "EVALUATED",
                        "overall_score": 70 + index,
                    }
                },
                "created_at": f"2026-08-0{index}T00:00:00+00:00",
                "completed_at": None,
            }
            for index in (1, 2)
        ]


def test_history_trend_endpoint_is_additive_and_overall_only(monkeypatch):
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)

    response = client.get("/api/v1/users/1/history-trend")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version"] == "history-trend-v1.1"
    assert [item["motion_type"] for item in data["motions"]] == [
        "footwork",
        "serve",
        "clear",
    ]
    assert all(item["status"] == "READY" for item in data["motions"])
    assert all(len(item["points"]) == 2 for item in data["motions"])
    serialized = response.text
    assert "report" not in serialized
    assert "dimension" not in serialized
    assert "metrics_json" not in serialized


def test_history_trend_endpoint_preserves_user_not_found(monkeypatch):
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)

    response = client.get("/api/v1/users/999/history-trend")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
