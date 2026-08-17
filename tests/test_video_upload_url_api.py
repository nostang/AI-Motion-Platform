from types import SimpleNamespace

from fastapi.testclient import TestClient

import src.api.app as api_module


class FakeStorageUploadService:
    def create_upload_ticket(self, *, filename, content_type):
        return SimpleNamespace(
            object_name="uploads/test/source.mp4",
            upload_url="https://storage.example/upload",
            method="PUT",
            expires_in_seconds=900,
            content_type=content_type,
        )


def test_create_video_upload_url(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "StorageUploadService",
        FakeStorageUploadService,
    )
    client = TestClient(api_module.app)
    response = client.post(
        "/api/v1/video-upload-urls",
        json={
            "filename": "footwork.mp4",
            "content_type": "video/mp4",
        },
    )
    assert response.status_code == 200
    assert response.json()["method"] == "PUT"
    assert response.json()["object_name"].startswith("uploads/")
    assert response.json()["expires_in_seconds"] == 900
