from __future__ import annotations

import json
from pathlib import Path

from src.api.keyframe_storage import (
    KEYFRAME_ASSET_BUCKET_ENV,
    KEYFRAME_OBJECT_PREFIX,
    KeyframeStorageService,
)
from src.api.storage_upload import (
    UPLOAD_OBJECT_PREFIX,
    VIDEO_UPLOAD_BUCKET_ENV,
    StorageUploadService,
)


class FakeBlob:
    def __init__(self, objects: dict[str, bytes], name: str):
        self.objects = objects
        self.name = name
        self.cache_control = None
        self.metadata = None

    def upload_from_filename(self, filename: str, *, content_type: str):
        assert content_type == "image/jpeg"
        self.objects[self.name] = Path(filename).read_bytes()

    def upload_from_string(self, payload: bytes, *, content_type: str):
        assert content_type == "application/json"
        self.objects[self.name] = payload

    def download_as_bytes(self):
        return self.objects[self.name]


class FakeBucket:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def blob(self, name: str):
        return FakeBlob(self.objects, name)


class FakeClient:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def bucket(self, name: str):
        assert name == "private-test"
        return FakeBucket(self.objects)


def test_persists_and_retrieves_assessment_scoped_private_assets(tmp_path):
    source_dir = tmp_path / "keyframes"
    source_dir.mkdir()
    keyframes = []
    for stage in ("preparation", "swing", "finish"):
        (source_dir / f"{stage}.jpg").write_bytes(b"jpeg-" + stage.encode())
        keyframes.append({
            "stage": stage,
            "status": "READY",
            "filename": f"{stage}.jpg",
            "width": 960,
            "height": 540,
            "requested_timestamp_ms": 100,
        })
    manifest = {
        "status": "READY",
        "keyframes": keyframes,
        "visualization": {"status": "READY", "snapshots": []},
    }
    client = FakeClient()
    service = KeyframeStorageService("private-test", client=client)

    durable = service.persist("assessment_123", source_dir, manifest)

    prefix = "motion-assessments/assessment_123/keyframes/"
    assert set(client.objects) == {
        prefix + "preparation.jpg",
        prefix + "swing.jpg",
        prefix + "finish.jpg",
        prefix + "manifest.json",
    }
    assert durable["status"] == "READY"
    assert all(item["storage_status"] == "READY" for item in durable["keyframes"])
    assert service.download_keyframe("assessment_123", "swing") == b"jpeg-swing"
    loaded = service.load_manifest("assessment_123")
    assert loaded["visualization"]["status"] == "READY"
    assert json.loads(client.objects[prefix + "manifest.json"])["status"] == "READY"


def test_missing_local_image_is_not_ready_but_manifest_survives(tmp_path):
    client = FakeClient()
    service = KeyframeStorageService("private-test", client=client)
    manifest = {
        "status": "READY",
        "keyframes": [{
            "stage": "swing",
            "status": "READY",
            "filename": "swing.jpg",
            "width": 960,
            "height": 540,
        }],
    }

    durable = service.persist("assessment_123", tmp_path, manifest)

    assert durable["status"] == "NOT_READY"
    assert durable["keyframes"][0]["reason"] == "LOCAL_KEYFRAME_NOT_READY"
    assert service.load_manifest("assessment_123")["status"] == "NOT_READY"


def test_keyframe_bucket_configuration_does_not_change_video_bucket(monkeypatch):
    monkeypatch.setenv(VIDEO_UPLOAD_BUCKET_ENV, "video-temp")
    monkeypatch.setenv(KEYFRAME_ASSET_BUCKET_ENV, "assessment-assets")

    assert StorageUploadService().bucket_name == "video-temp"
    assert KeyframeStorageService().bucket_name == "assessment-assets"


def test_keyframe_bucket_can_share_configured_video_bucket(monkeypatch):
    monkeypatch.setenv(VIDEO_UPLOAD_BUCKET_ENV, "video-temp")
    monkeypatch.delenv(KEYFRAME_ASSET_BUCKET_ENV, raising=False)

    assert StorageUploadService().bucket_name == "video-temp"
    assert KeyframeStorageService().bucket_name == "video-temp"


def test_same_bucket_lifecycle_only_matches_video_upload_prefix():
    lifecycle_path = (
        Path(__file__).resolve().parents[1]
        / "infra"
        / "gcs"
        / "video-temp-lifecycle.json"
    )
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))

    assert lifecycle == {
        "rule": [
            {
                "action": {"type": "Delete"},
                "condition": {
                    "age": 1,
                    "matchesPrefix": [f"{UPLOAD_OBJECT_PREFIX}/"],
                },
            }
        ]
    }
    assert KEYFRAME_OBJECT_PREFIX != UPLOAD_OBJECT_PREFIX


def test_persists_six_sequence_images_outside_temporary_upload_prefix(tmp_path):
    source_dir = tmp_path / "motion_sequence"
    source_dir.mkdir()
    frames = []
    for index in range(1, 7):
        filename = f"{index:02d}.jpg"
        (source_dir / filename).write_bytes(f"jpeg-{index}".encode())
        frames.append(
            {
                "index": index,
                "status": "READY",
                "filename": filename,
                "width": 960,
                "height": 523,
                "source_frame_index": index * 10,
            }
        )
    client = FakeClient()
    service = KeyframeStorageService("private-test", client=client)

    durable = service.persist_sequence(
        "assessment_456",
        source_dir,
        {"status": "READY", "frames": frames, "sequence": {"status": "READY"}},
    )

    prefix = "motion-assessments/assessment_456/motion-sequence/"
    assert set(client.objects) == {
        *(prefix + f"{index:02d}.jpg" for index in range(1, 7)),
        prefix + "manifest.json",
    }
    assert all(not name.startswith("uploads/") for name in client.objects)
    assert durable["status"] == "READY"
    assert service.download_sequence_frame("assessment_456", 4) == b"jpeg-4"
    assert service.load_sequence_manifest("assessment_456")["status"] == "READY"


def test_persists_partial_reach_grid_in_assessment_scoped_private_prefix(tmp_path):
    source_dir = tmp_path / "reach_grid"
    source_dir.mkdir()
    cells = []
    slugs = {
        "LEFT_FRONT": "left-front",
        "FRONT": "front",
        "RIGHT_FRONT": "right-front",
        "CENTER": "center",
    }
    for key, slug in slugs.items():
        (source_dir / f"{slug}.jpg").write_bytes(f"jpeg-{key}".encode())
        cells.append({
            "key": key,
            "status": "READY",
            "filename": f"{slug}.jpg",
            "width": 960,
            "height": 523,
            "source_frame_index": 10,
        })
    cells.extend([
        {"key": "LEFT", "status": "NOT_READY"},
        {"key": "RIGHT", "status": "NOT_READY"},
    ])
    client = FakeClient()
    service = KeyframeStorageService("private-test", client=client)

    durable = service.persist_reach_grid(
        "assessment_789",
        source_dir,
        {"status": "PARTIAL", "cells": cells, "reach_grid": {"status": "PARTIAL"}},
    )

    prefix = "motion-assessments/assessment_789/reach-grid/"
    assert set(client.objects) == {
        *(prefix + f"{slug}.jpg" for slug in slugs.values()),
        prefix + "manifest.json",
    }
    assert all(not name.startswith("uploads/") for name in client.objects)
    assert durable["status"] == "PARTIAL"
    assert service.download_reach_grid_frame("assessment_789", "CENTER") == b"jpeg-CENTER"
    assert service.load_reach_grid_manifest("assessment_789")["status"] == "PARTIAL"
