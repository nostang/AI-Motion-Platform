from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

import src.api.app as api_module


class FakeRepository:
    def get_analysis(self, assessment_id):
        if assessment_id == 42:
            return {
                "assessment_id": 42,
                "user_id": 1,
                "assessment_type": "footwork",
                "status": "processing",
                "progress": 10,
                "current_stage": "pose_detection",
            }
        return None


def token(user_id: int, secret: str, *, expired: bool = False) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iss": "badminton-event-poc",
            "iat": now,
            "exp": now + timedelta(minutes=-1 if expired else 5),
        },
        secret,
        algorithm="HS256",
    )


def test_public_motion_routes_require_valid_auth_in_production(monkeypatch):
    secret = "motion-test-secret"
    monkeypatch.setenv("APP_JWT_SECRET", secret)
    monkeypatch.setattr(api_module, "REQUIRE_PUBLIC_AUTH", True)
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)

    missing = client.get("/api/v1/users/1/history-trend")
    expired = client.get(
        "/api/v1/users/1/history-trend",
        headers={"Authorization": f"Bearer {token(1, secret, expired=True)}"},
    )

    assert missing.status_code == 401
    assert expired.status_code == 401


def test_user_and_assessment_paths_reject_cross_account_idor(monkeypatch):
    secret = "motion-test-secret"
    headers = {"Authorization": f"Bearer {token(2, secret)}"}
    monkeypatch.setenv("APP_JWT_SECRET", secret)
    monkeypatch.setattr(api_module, "REQUIRE_PUBLIC_AUTH", True)
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)

    user_response = client.get("/api/v1/users/1/history-trend", headers=headers)
    assessment_response = client.get("/api/v1/motion-assessments/42", headers=headers)

    assert user_response.status_code == 403
    assert assessment_response.status_code == 403


def test_engineer_debug_requires_internal_key(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "internal-secret")
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)

    missing = client.get("/api/v1/internal/motion-assessments/42/engineer-debug")
    assert missing.status_code == 401
