from copy import deepcopy
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient

import src.api.app as api_module


class FakeKeyframeStorage:
    def __init__(
        self,
        manifest=None,
        images=None,
        sequence_manifest=None,
        sequence_images=None,
        reach_grid_manifest=None,
        reach_grid_images=None,
    ):
        self.manifest = manifest
        self.images = images or {}
        self.sequence_manifest = sequence_manifest
        self.sequence_images = sequence_images or {}
        self.reach_grid_manifest = reach_grid_manifest
        self.reach_grid_images = reach_grid_images or {}

    def load_manifest(self, assessment_id: str):
        return deepcopy(self.manifest)

    def download_keyframe(self, assessment_id: str, stage: str):
        if stage not in self.images:
            raise FileNotFoundError(stage)
        return self.images[stage]

    def load_sequence_manifest(self, assessment_id: str):
        return deepcopy(self.sequence_manifest)

    def download_sequence_frame(self, assessment_id: str, index: int):
        if index not in self.sequence_images:
            raise FileNotFoundError(index)
        return self.sequence_images[index]

    def load_reach_grid_manifest(self, assessment_id: str):
        return deepcopy(self.reach_grid_manifest)

    def download_reach_grid_frame(self, assessment_id: str, key: str):
        if key not in self.reach_grid_images:
            raise FileNotFoundError(key)
        return self.reach_grid_images[key]

    @staticmethod
    def _reach_grid_key(value: str):
        key = str(value).upper()
        if key not in {
            "LEFT_FRONT", "FRONT", "RIGHT_FRONT", "LEFT", "CENTER",
            "RIGHT", "LEFT_BACK", "BACK", "RIGHT_BACK",
        }:
            raise ValueError(key)
        return key


class FakeRepository:
    def __init__(self, root: Path):
        self.root = root
        self.tasks = {
            "ready-clear": {
                "assessment_id": "ready-clear",
                "assessment_type": "clear",
                "status": "completed",
            },
            "missing-clear": {
                "assessment_id": "missing-clear",
                "assessment_type": "clear",
                "status": "completed",
            },
            "pending-clear": {
                "assessment_id": "pending-clear",
                "assessment_type": "clear",
                "status": "processing",
            },
            "serve": {
                "assessment_id": "serve",
                "assessment_type": "serve",
                "status": "completed",
            },
            "footwork": {
                "assessment_id": "footwork",
                "assessment_type": "footwork",
                "status": "completed",
            },
        }
        self.report = {
            "assessment_id": "engine-clear-001",
            "motion_type": "clear",
            "summary": {"overall_score": 82},
        }

    def get_analysis(self, assessment_id: str):
        return self.tasks.get(assessment_id)

    def get_report(self, assessment_id: str, *, analysis_type=None):
        if assessment_id == "ready-clear" and analysis_type == "clear":
            return deepcopy(self.report)
        return None

    def task_dir(self, assessment_id: str) -> Path:
        return self.root / assessment_id


def _artifact() -> dict:
    names = (
        "nose",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    )
    snapshots = []
    for index, (stage, label, focus) in enumerate(
        (
            ("preparation", "準備姿勢", "sideways_preparation"),
            ("swing", "揮拍階段", "swing_smoothness"),
            ("finish", "動作完成", "weight_transfer"),
        )
    ):
        snapshots.append(
            {
                "stage": stage,
                "label": label,
                "focus": focus,
                "timestamp_ms": index * 500,
                "landmarks": {
                    name: {"x": 0.25 + index * 0.1, "y": 0.4}
                    for name in names
                },
            }
        )
    return {
        "status": "READY",
        "version": "clear-explainable-pose-v0.1",
        "motion_type": "clear",
        "racket_side": "right",
        "sample_count": 99,
        "source_video": "/private/source.mp4",
        "snapshots": snapshots,
        "limitations": ["Internal analysis limitation."],
    }


def _sequence_artifact(motion_type: str = "clear") -> dict:
    names = (
        "nose",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    )
    return {
        "status": "READY",
        "version": f"{motion_type}-motion-sequence-v1.1",
        "motion_type": motion_type,
        "racket_side": "right",
        "frames": [
            {
                "index": index,
                "timestamp_ms": index * 400,
                "analysis_frame_index": index * 10,
                "source_frame_index": index * 10 + 100,
                "landmarks": {
                    name: {"x": 0.2 + index * 0.02, "y": 0.4}
                    for name in names
                },
            }
            for index in range(1, 7)
        ],
    }


def _reach_grid_artifact() -> dict:
    specs = (
        ("LEFT_FRONT", "左前", 1, 1, "direction"),
        ("FRONT", "前", 1, 2, "direction"),
        ("RIGHT_FRONT", "右前", 1, 3, "direction"),
        ("LEFT", "左", 2, 1, "direction"),
        ("CENTER", "中心", 2, 2, "center"),
        ("RIGHT", "右", 2, 3, "direction"),
        ("LEFT_BACK", "左後", 3, 1, "direction"),
        ("BACK", "後", 3, 2, "direction"),
        ("RIGHT_BACK", "右後", 3, 3, "direction"),
    )
    names = _artifact()["snapshots"][0]["landmarks"].keys()
    cells = []
    for index, (key, label, row, column, kind) in enumerate(specs):
        if key in {"LEFT", "RIGHT"}:
            cells.append({
                "key": key,
                "label": label,
                "row": row,
                "column": column,
                "kind": kind,
                "status": "NOT_READY",
                "reason": "DIRECTION_NOT_COMPLETED",
            })
        else:
            cells.append({
                "key": key,
                "label": label,
                "row": row,
                "column": column,
                "kind": kind,
                "status": "READY",
                "timestamp_ms": index * 100,
                "source_frame_index": index * 10,
                "event_id": index,
                "landmarks": {
                    name: {"x": 0.25 + index * 0.01, "y": 0.4}
                    for name in names
                },
            })
    return {
        "status": "PARTIAL",
        "version": "footwork-reach-grid-v1.0",
        "motion_type": "footwork",
        "cells": cells,
    }


def _client(monkeypatch, tmp_path, storage=None):
    repository = FakeRepository(tmp_path)
    artifact_path = (
        repository.task_dir("ready-clear")
        / "output"
        / "clear_pose_visualization.json"
    )
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(_artifact()), encoding="utf-8")
    monkeypatch.setattr(api_module, "repository", repository)
    storage = storage or FakeKeyframeStorage()
    monkeypatch.setattr(api_module, "KeyframeStorageService", lambda: storage)
    return TestClient(api_module.app)


def test_ready_clear_visualization_is_sanitized(monkeypatch, tmp_path):
    response = _client(monkeypatch, tmp_path).get(
        "/api/v1/motion-assessments/ready-clear/visualization"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "READY"
    assert data["racket_side"] == "right"
    assert [item["stage"] for item in data["snapshots"]] == [
        "preparation",
        "swing",
        "finish",
    ]
    assert all(len(item["landmarks"]) == 13 for item in data["snapshots"])
    assert all(item["keyframe"]["status"] == "NOT_READY" for item in data["snapshots"])
    serialized = response.text.lower()
    assert "source_video" not in serialized
    assert "/private/" not in serialized
    assert "sample_count" not in serialized
    assert "limitations" not in serialized
    assert "source_frame_index" not in serialized
    assert "analysis_frame_index" not in serialized
    for forbidden in ("contact", "impact", "擊球瞬間"):
        assert forbidden not in serialized


def test_visualization_states_are_safe(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    cases = (
        ("missing-clear", 200, "NOT_READY"),
        ("pending-clear", 200, "NOT_READY"),
        ("serve", 200, "NOT_AVAILABLE"),
        ("unknown", 404, None),
    )
    for assessment_id, status_code, state in cases:
        response = client.get(
            f"/api/v1/motion-assessments/{assessment_id}/visualization"
        )
        assert response.status_code == status_code
        if state is not None:
            assert response.json()["data"]["status"] == state
        else:
            assert response.json()["error"]["code"] == "ASSESSMENT_NOT_FOUND"


def test_existing_report_contract_is_unchanged(monkeypatch, tmp_path):
    response = _client(monkeypatch, tmp_path).get(
        "/api/v1/motion-assessments/ready-clear/report"
    )

    assert response.status_code == 200
    report = response.json()["data"]
    assert report["assessment_id"] == "ready-clear"
    assert report["summary"] == {"overall_score": 82}
    assert report["meta"]["engine_assessment_id"] == "engine-clear-001"
    assert "visualization" not in report
    assert "snapshots" not in report


def test_visualization_adds_controlled_keyframe_urls_and_serves_jpeg(monkeypatch, tmp_path):
    entries = [
        {
            "stage": stage,
            "status": "READY",
            "storage_status": "READY",
            "width": 960,
            "height": 540,
            "object_name": f"private/{stage}.jpg",
        }
        for stage in ("preparation", "swing", "finish")
    ]
    storage = FakeKeyframeStorage(
        {"status": "READY", "keyframes": entries},
        {stage: b"jpeg-" + stage.encode() for stage in ("preparation", "swing", "finish")},
    )
    client = _client(monkeypatch, tmp_path, storage)

    response = client.get("/api/v1/motion-assessments/ready-clear/visualization")
    assert response.status_code == 200
    snapshots = response.json()["data"]["snapshots"]
    assert all(item["keyframe"]["status"] == "READY" for item in snapshots)
    assert all(item["keyframe"]["url"].startswith("/api/v1/") for item in snapshots)
    assert "object_name" not in response.text
    assert "private/" not in response.text

    image = client.get(snapshots[1]["keyframe"]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "private, max-age=300"
    assert image.content == b"jpeg-swing"


def test_visualization_falls_back_to_durable_pose_when_task_files_are_gone(monkeypatch, tmp_path):
    artifact = _artifact()
    storage = FakeKeyframeStorage({
        "status": "READY",
        "visualization": artifact,
        "keyframes": [],
    })
    client = _client(monkeypatch, tmp_path, storage)
    artifact_path = (
        api_module.repository.task_dir("ready-clear")
        / "output"
        / "clear_pose_visualization.json"
    )
    shutil.rmtree(api_module.repository.task_dir("ready-clear"))

    response = client.get("/api/v1/motion-assessments/ready-clear/visualization")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "READY"
    assert len(response.json()["data"]["snapshots"]) == 3


def test_keyframe_failures_are_safe_404(monkeypatch, tmp_path):
    storage = FakeKeyframeStorage({"status": "NOT_READY", "keyframes": []})
    client = _client(monkeypatch, tmp_path, storage)

    response = client.get(
        "/api/v1/motion-assessments/ready-clear/visualization/keyframes/swing"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "KEYFRAME_NOT_READY"


def test_sequence_is_additive_private_and_controlled(monkeypatch, tmp_path):
    entries = [
        {
            "index": index,
            "status": "READY",
            "storage_status": "READY",
            "width": 960,
            "height": 523,
            "object_name": f"private/motion-sequence/{index:02d}.jpg",
        }
        for index in range(1, 7)
    ]
    storage = FakeKeyframeStorage(
        sequence_manifest={"status": "READY", "frames": entries},
        sequence_images={index: f"sequence-{index}".encode() for index in range(1, 7)},
    )
    client = _client(monkeypatch, tmp_path, storage)
    sequence_path = (
        api_module.repository.task_dir("ready-clear")
        / "output"
        / "clear_motion_sequence.json"
    )
    sequence_path.write_text(json.dumps(_sequence_artifact()), encoding="utf-8")

    response = client.get("/api/v1/motion-assessments/ready-clear/visualization")

    assert response.status_code == 200
    sequence = response.json()["data"]["sequence"]
    assert sequence["status"] == "READY"
    assert [frame["index"] for frame in sequence["frames"]] == list(range(1, 7))
    assert all(frame["image"]["status"] == "READY" for frame in sequence["frames"])
    serialized = response.text
    assert "object_name" not in serialized
    assert "motion-sequence/01.jpg" not in serialized
    assert "source_frame_index" not in serialized
    assert "analysis_frame_index" not in serialized

    image = client.get(sequence["frames"][3]["image"]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "private, max-age=300"
    assert image.content == b"sequence-4"


def test_sequence_durable_fallback_survives_local_task_removal(monkeypatch, tmp_path):
    sequence_artifact = _sequence_artifact()
    storage = FakeKeyframeStorage(
        sequence_manifest={
            "status": "READY",
            "sequence": sequence_artifact,
            "frames": [],
        }
    )
    client = _client(monkeypatch, tmp_path, storage)
    shutil.rmtree(api_module.repository.task_dir("ready-clear"))

    response = client.get("/api/v1/motion-assessments/ready-clear/visualization")

    assert response.status_code == 200
    sequence = response.json()["data"]["sequence"]
    assert sequence["status"] == "READY"
    assert len(sequence["frames"]) == 6


def test_serve_sequence_is_additive_and_uses_controlled_images(monkeypatch, tmp_path):
    entries = [
        {
            "index": index,
            "status": "READY",
            "storage_status": "READY",
            "width": 960,
            "height": 523,
            "object_name": f"private/motion-sequence/{index:02d}.jpg",
        }
        for index in range(1, 7)
    ]
    storage = FakeKeyframeStorage(
        sequence_manifest={"status": "READY", "frames": entries},
        sequence_images={index: f"serve-{index}".encode() for index in range(1, 7)},
    )
    client = _client(monkeypatch, tmp_path, storage)
    sequence_path = (
        api_module.repository.task_dir("serve")
        / "output"
        / "serve_motion_sequence.json"
    )
    sequence_path.parent.mkdir(parents=True)
    sequence_path.write_text(
        json.dumps(_sequence_artifact("serve")),
        encoding="utf-8",
    )

    response = client.get("/api/v1/motion-assessments/serve/visualization")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "NOT_AVAILABLE"
    assert data["snapshots"] == []
    assert data["sequence"]["status"] == "READY"
    assert data["sequence"]["motion_type"] == "serve"
    assert data["sequence"]["version"] == "serve-motion-sequence-v1.1"
    assert all(
        frame["image"]["url"].startswith("/api/v1/")
        for frame in data["sequence"]["frames"]
    )
    assert "object_name" not in response.text
    assert "private/" not in response.text
    assert "source_frame_index" not in response.text

    image = client.get(data["sequence"]["frames"][0]["image"]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == b"serve-1"


def test_serve_sequence_durable_fallback_does_not_need_local_task_files(
    monkeypatch,
    tmp_path,
):
    storage = FakeKeyframeStorage(
        sequence_manifest={
            "status": "READY",
            "sequence": _sequence_artifact("serve"),
            "frames": [],
        }
    )
    client = _client(monkeypatch, tmp_path, storage)

    response = client.get("/api/v1/motion-assessments/serve/visualization")

    assert response.status_code == 200
    sequence = response.json()["data"]["sequence"]
    assert sequence["status"] == "READY"
    assert sequence["motion_type"] == "serve"
    assert len(sequence["frames"]) == 6


def test_footwork_reach_grid_is_partial_private_and_controlled(monkeypatch, tmp_path):
    artifact = _reach_grid_artifact()
    entries = [
        {
            "key": cell["key"],
            "status": "READY",
            "storage_status": "READY",
            "width": 960,
            "height": 523,
            "object_name": f"private/reach-grid/{cell['key']}.jpg",
        }
        for cell in artifact["cells"]
        if cell["status"] == "READY"
    ]
    storage = FakeKeyframeStorage(
        reach_grid_manifest={"status": "PARTIAL", "cells": entries},
        reach_grid_images={
            entry["key"]: f"grid-{entry['key']}".encode()
            for entry in entries
        },
    )
    client = _client(monkeypatch, tmp_path, storage)
    grid_path = (
        api_module.repository.task_dir("footwork")
        / "output"
        / "footwork_reach_grid.json"
    )
    grid_path.parent.mkdir(parents=True)
    grid_path.write_text(json.dumps(artifact), encoding="utf-8")

    response = client.get("/api/v1/motion-assessments/footwork/visualization")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "NOT_AVAILABLE"
    grid = data["reach_grid"]
    assert grid["status"] == "PARTIAL"
    assert len(grid["cells"]) == 9
    assert [cell["key"] for cell in grid["cells"] if cell["status"] != "READY"] == [
        "LEFT",
        "RIGHT",
    ]
    assert all(
        len(cell["landmarks"]) == 13
        for cell in grid["cells"]
        if cell["status"] == "READY"
    )
    assert "object_name" not in response.text
    assert "source_frame_index" not in response.text
    assert "event_id" not in response.text

    center = next(cell for cell in grid["cells"] if cell["key"] == "CENTER")
    image = client.get(center["image"]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "private, max-age=300"
    assert image.content == b"grid-CENTER"


def test_footwork_reach_grid_uses_durable_copy_after_local_task_disappears(
    monkeypatch,
    tmp_path,
):
    artifact = _reach_grid_artifact()
    storage = FakeKeyframeStorage(
        reach_grid_manifest={
            "status": "PARTIAL",
            "reach_grid": artifact,
            "cells": [],
        }
    )
    client = _client(monkeypatch, tmp_path, storage)

    response = client.get("/api/v1/motion-assessments/footwork/visualization")

    assert response.status_code == 200
    assert response.json()["data"]["reach_grid"]["status"] == "PARTIAL"
    assert len(response.json()["data"]["reach_grid"]["cells"]) == 9
