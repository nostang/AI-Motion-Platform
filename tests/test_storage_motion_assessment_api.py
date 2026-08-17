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

    def task_dir(self, assessment_id: str) -> Path:
        return self.root / assessment_id

    def create_analysis(self, **kwargs):
        self.created.append(kwargs)


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
    assert len(fake_repository.created) == 1
    assert len(background_calls) == 1
    assert fake_repository.created[0]["video_url"].endswith(
        "source.mp4"
    )
