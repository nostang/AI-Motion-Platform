from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.api.app as api_module


class FakeRepository:
    def __init__(self, root: Path):
        self.root = root
        self.created = []

    def user_exists(self, user_id: int) -> bool:
        return user_id == 1

    def allocate_analysis_id(self) -> int:
        return 101

    def task_dir(self, assessment_id: int) -> Path:
        return self.root / str(assessment_id)

    def create_analysis(self, **kwargs):
        self.created.append(kwargs)

    def expire_stale_analyses(self, user_id, *, max_age_minutes=30):
        return []

    def get_active_analysis(self, user_id):
        return None

    def update_status(self, assessment_id, **kwargs):
        return None


class FakeStorageUploadService:
    def get_video_object(self, object_name):
        return SimpleNamespace(
            object_name=object_name,
            size=85_320_352,
            content_type="video/mp4",
            suffix=".mp4",
        )


def test_create_assessment_from_storage(
    monkeypatch,
    tmp_path,
):
    fake_repository = FakeRepository(tmp_path)
    background_calls = []

    monkeypatch.setattr(
        api_module,
        "repository",
        fake_repository,
    )
    monkeypatch.setattr(
        api_module,
        "StorageUploadService",
        FakeStorageUploadService,
    )
    monkeypatch.setattr(
        api_module,
        "_process_storage_assessment",
        lambda *args: background_calls.append(args),
    )
    monkeypatch.setattr(
        api_module,
        "task_queue",
        SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(api_module, "APP_ENV", "development")

    client = TestClient(api_module.app)
    response = client.post(
        "/api/v1/motion-assessments/from-storage",
        json={
            "object_name": "uploads/test/source.mp4",
            "assessment_type": "footwork",
            "user_id": 1,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    data = payload.get("data", payload)

    assert data["upload_source"] == "cloud_storage"
    assert data["assessment_type"] == "footwork"
    assert data["assessment_id"] == 101
    assert len(fake_repository.created) == 1
    assert len(background_calls) == 1
    assert fake_repository.created[0]["video_url"].endswith(
        "source.mp4"
    )
    assert fake_repository.created[0]["analysis_id"] == 101
    assert fake_repository.created[0]["processing_status"] == "uploaded"


def test_rejects_second_active_assessment(
    monkeypatch,
    tmp_path,
):
    fake_repository = FakeRepository(tmp_path)
    fake_repository.get_active_analysis = lambda user_id: {
        "assessment_id": 88,
        "assessment_type": "footwork",
        "status": "processing",
        "progress": 10,
        "current_stage": "pose_detection",
        "created_at": "2026-08-23T06:50:00+00:00",
    }
    monkeypatch.setattr(api_module, "repository", fake_repository)

    client = TestClient(api_module.app)
    response = client.post(
        "/api/v1/motion-assessments/from-storage",
        json={
            "object_name": "uploads/test/source.mp4",
            "assessment_type": "footwork",
            "user_id": 1,
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["code"] == "ACTIVE_ASSESSMENT_EXISTS"
    assert payload["error"]["details"]["assessment_id"] == 88
    assert fake_repository.created == []


def test_production_enqueues_durable_cloud_task(
    monkeypatch,
    tmp_path,
):
    fake_repository = FakeRepository(tmp_path)
    queued = []

    class FakeQueue:
        enabled = True

        def enqueue(self, **kwargs):
            queued.append(kwargs)
            return "queues/test/tasks/assessment-101-storage"

    monkeypatch.setattr(api_module, "repository", fake_repository)
    monkeypatch.setattr(
        api_module,
        "StorageUploadService",
        FakeStorageUploadService,
    )
    monkeypatch.setattr(api_module, "task_queue", FakeQueue())
    monkeypatch.setattr(api_module, "APP_ENV", "production")

    client = TestClient(api_module.app)
    response = client.post(
        "/api/v1/motion-assessments/from-storage",
        json={
            "object_name": "uploads/test/source.mp4",
            "assessment_type": "footwork",
            "user_id": 1,
        },
    )

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "uploaded"
    assert queued == [
        {
            "assessment_id": 101,
            "job_type": "storage",
            "object_name": "uploads/test/source.mp4",
        }
    ]
