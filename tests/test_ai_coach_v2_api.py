from fastapi.testclient import TestClient

import src.api.app as api_module


def _report():
    return {
        "assessment_id": "sa_internal",
        "assessment_type": "serve",
        "summary": {
            "completed": True,
            "evaluation_status": "EVALUATED",
            "overall_score": 79,
            "system_confidence": 0.92,
        },
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
            "strengths": ["preparation_stability", "swing_completeness"],
            "improvement_priorities": ["body_coordination"],
        },
        "coach": {
            "feedback": [
                {"metric": "body_coordination", "level": "FAIR"}
            ]
        },
    }


class FakeRepository:
    def __init__(self, status="completed"):
        self.status = status

    def get_analysis(self, assessment_id):
        if assessment_id == "missing":
            return None
        return {
            "assessment_id": assessment_id,
            "assessment_type": "serve",
            "status": self.status,
            "user_id": 1,
        }

    def get_report(self, assessment_id, analysis_type=None):
        return _report()

    def get_motion_history(self, user_id, motion_type):
        scores = (70, 74, 79)
        return [
            {
                "assessment_id": f"ma_{index}",
                "motion_type": motion_type,
                "overall_score": score,
                "report": {
                    "summary": {
                        "completed": True,
                        "evaluation_status": "EVALUATED",
                        "overall_score": score,
                    }
                },
                "created_at": f"2026-08-0{index}T00:00:00+00:00",
                "completed_at": None,
            }
            for index, score in enumerate(scores, start=1)
        ]


def test_coach_v2_endpoint_is_additive_and_uses_user_history(monkeypatch):
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)

    response = client.get("/api/v1/motion-assessments/ma_serve/coach-v2")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["assessment_id"] == "ma_serve"
    assert data["user_id"] == 1
    assert data["motion_type"] == "serve"
    assert data["recent_trend"]["status"] == "UPWARD"
    assert data["priorities"][0]["metric"] == "body_coordination"

    report_response = client.get(
        "/api/v1/motion-assessments/ma_serve/report"
    )
    assert report_response.status_code == 200
    assert "ai_coach_v2" not in report_response.json()["data"]


def test_coach_v2_endpoint_preserves_not_found_and_not_ready(monkeypatch):
    monkeypatch.setattr(api_module, "repository", FakeRepository())
    client = TestClient(api_module.app)
    missing = client.get("/api/v1/motion-assessments/missing/coach-v2")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ASSESSMENT_NOT_FOUND"

    monkeypatch.setattr(api_module, "repository", FakeRepository("processing"))
    pending = client.get("/api/v1/motion-assessments/ma_serve/coach-v2")
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "COACH_V2_NOT_READY"
