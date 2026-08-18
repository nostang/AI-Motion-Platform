"""Private durable storage for assessment-scoped Explainable Pose keyframes."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Mapping

from google.api_core.exceptions import NotFound
from google.cloud import storage

from src.api.storage_upload import DEFAULT_BUCKET, VIDEO_UPLOAD_BUCKET_ENV
from src.visualization.footwork_reach_grid import CELL_SLUGS, GRID_CELL_COUNT


STAGES = frozenset({"preparation", "swing", "finish"})
ASSESSMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
KEYFRAME_ASSET_BUCKET_ENV = "KEYFRAME_ASSET_BUCKET"
KEYFRAME_OBJECT_PREFIX = "motion-assessments"
MOTION_SEQUENCE_OBJECT_PREFIX = "motion-sequence"
MOTION_SEQUENCE_FRAME_COUNT = 6
REACH_GRID_OBJECT_PREFIX = "reach-grid"


class KeyframeStorageService:
    """Persist private JPEGs without exposing bucket object names to clients."""

    def __init__(
        self,
        bucket_name: str | None = None,
        *,
        client: Any | None = None,
    ) -> None:
        self.bucket_name = (
            bucket_name
            or os.environ.get(KEYFRAME_ASSET_BUCKET_ENV)
            or os.environ.get(VIDEO_UPLOAD_BUCKET_ENV)
            or DEFAULT_BUCKET
        )
        self._storage_client = client

    @staticmethod
    def _assessment_id(value: str) -> str:
        assessment_id = str(value or "").strip()
        if not ASSESSMENT_PATTERN.fullmatch(assessment_id):
            raise ValueError("INVALID_ASSESSMENT_ID")
        return assessment_id

    @staticmethod
    def _stage(value: str) -> str:
        stage = str(value or "").strip().lower()
        if stage not in STAGES:
            raise ValueError("INVALID_KEYFRAME_STAGE")
        return stage

    @staticmethod
    def _sequence_index(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("INVALID_SEQUENCE_INDEX")
        if not 1 <= value <= MOTION_SEQUENCE_FRAME_COUNT:
            raise ValueError("INVALID_SEQUENCE_INDEX")
        return value

    @staticmethod
    def _reach_grid_key(value: Any) -> str:
        key = str(value or "").strip().upper()
        if key not in CELL_SLUGS:
            raise ValueError("INVALID_REACH_GRID_KEY")
        return key

    def _client(self):
        if self._storage_client is None:
            self._storage_client = storage.Client()
        return self._storage_client

    def _object_name(self, assessment_id: str, filename: str) -> str:
        return (
            f"{KEYFRAME_OBJECT_PREFIX}/{self._assessment_id(assessment_id)}/"
            f"keyframes/{filename}"
        )

    def _sequence_object_name(self, assessment_id: str, filename: str) -> str:
        return (
            f"{KEYFRAME_OBJECT_PREFIX}/{self._assessment_id(assessment_id)}/"
            f"{MOTION_SEQUENCE_OBJECT_PREFIX}/{filename}"
        )

    def _reach_grid_object_name(self, assessment_id: str, filename: str) -> str:
        return (
            f"{KEYFRAME_OBJECT_PREFIX}/{self._assessment_id(assessment_id)}/"
            f"{REACH_GRID_OBJECT_PREFIX}/{filename}"
        )

    def _blob(self, object_name: str):
        client = self._client()
        return client.bucket(self.bucket_name).blob(object_name)

    def persist(
        self,
        assessment_id: str,
        source_dir: Path,
        manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Upload available images and a durable manifest; failures stay per-stage."""

        started = perf_counter()
        source_dir = Path(source_dir)
        durable = deepcopy(dict(manifest))
        raw_keyframes = durable.get("keyframes")
        keyframes = raw_keyframes if isinstance(raw_keyframes, list) else []
        upload_total_ms = 0.0

        for entry in keyframes:
            if not isinstance(entry, dict) or entry.get("status") != "READY":
                continue
            stage = self._stage(entry.get("stage"))
            filename = f"{stage}.jpg"
            source_path = source_dir / filename
            if not source_path.is_file():
                entry.update(
                    {
                        "status": "NOT_READY",
                        "reason": "LOCAL_KEYFRAME_NOT_READY",
                    }
                )
                entry.pop("filename", None)
                continue

            object_name = self._object_name(assessment_id, filename)
            upload_started = perf_counter()
            try:
                blob = self._blob(object_name)
                blob.cache_control = "private, max-age=300"
                blob.metadata = {
                    "assessment_id": self._assessment_id(assessment_id),
                    "stage": stage,
                    "requested_timestamp_ms": str(
                        entry.get("requested_timestamp_ms", "")
                    ),
                    "actual_frame_timestamp_ms": str(
                        entry.get("actual_frame_timestamp_ms", "")
                    ),
                    "analysis_frame_index": str(
                        entry.get("analysis_frame_index", "")
                    ),
                    "source_frame_index": str(
                        entry.get("source_frame_index", "")
                    ),
                }
                blob.upload_from_filename(
                    str(source_path),
                    content_type="image/jpeg",
                )
                elapsed_ms = (perf_counter() - upload_started) * 1000.0
                upload_total_ms += elapsed_ms
                entry["object_name"] = object_name
                entry["storage_status"] = "READY"
                entry["upload_duration_ms"] = round(elapsed_ms, 3)
            except Exception:
                entry.update(
                    {
                        "status": "NOT_READY",
                        "storage_status": "NOT_READY",
                        "reason": "KEYFRAME_UPLOAD_FAILED",
                    }
                )
                entry.pop("filename", None)
                entry.pop("object_name", None)

        ready_count = sum(
            isinstance(item, Mapping) and item.get("status") == "READY"
            for item in keyframes
        )
        durable["status"] = (
            "READY"
            if ready_count == len(STAGES)
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        )
        performance = durable.setdefault("performance_ms", {})
        if isinstance(performance, dict):
            performance["storage_upload_total"] = round(upload_total_ms, 3)
            performance["persistence_total"] = round(
                (perf_counter() - started) * 1000.0,
                3,
            )

        manifest_name = self._object_name(assessment_id, "manifest.json")
        manifest_blob = self._blob(manifest_name)
        manifest_blob.cache_control = "private, no-store"
        manifest_blob.upload_from_string(
            json.dumps(durable, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )
        return durable

    def load_manifest(self, assessment_id: str) -> dict[str, Any] | None:
        object_name = self._object_name(assessment_id, "manifest.json")
        try:
            payload = self._blob(object_name).download_as_bytes()
            manifest = json.loads(payload.decode("utf-8"))
        except (NotFound, UnicodeError, json.JSONDecodeError):
            return None
        return manifest if isinstance(manifest, dict) else None

    def download_keyframe(
        self,
        assessment_id: str,
        stage: str,
    ) -> bytes:
        stage = self._stage(stage)
        object_name = self._object_name(assessment_id, f"{stage}.jpg")
        try:
            return self._blob(object_name).download_as_bytes()
        except NotFound as exc:
            raise FileNotFoundError(object_name) from exc

    def persist_sequence(
        self,
        assessment_id: str,
        source_dir: Path,
        manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Upload six assessment-scoped sequence frames and their manifest."""

        started = perf_counter()
        source_dir = Path(source_dir)
        durable = deepcopy(dict(manifest))
        raw_frames = durable.get("frames")
        frames = raw_frames if isinstance(raw_frames, list) else []
        upload_total_ms = 0.0

        for entry in frames:
            if not isinstance(entry, dict) or entry.get("status") != "READY":
                continue
            index = self._sequence_index(entry.get("index"))
            filename = f"{index:02d}.jpg"
            source_path = source_dir / filename
            if not source_path.is_file():
                entry.update(
                    {
                        "status": "NOT_READY",
                        "reason": "LOCAL_SEQUENCE_FRAME_NOT_READY",
                    }
                )
                entry.pop("filename", None)
                continue

            object_name = self._sequence_object_name(assessment_id, filename)
            upload_started = perf_counter()
            try:
                blob = self._blob(object_name)
                blob.cache_control = "private, max-age=300"
                blob.metadata = {
                    "assessment_id": self._assessment_id(assessment_id),
                    "sequence_index": str(index),
                    "requested_timestamp_ms": str(
                        entry.get("requested_timestamp_ms", "")
                    ),
                    "analysis_frame_index": str(
                        entry.get("analysis_frame_index", "")
                    ),
                    "source_frame_index": str(
                        entry.get("source_frame_index", "")
                    ),
                }
                blob.upload_from_filename(
                    str(source_path),
                    content_type="image/jpeg",
                )
                elapsed_ms = (perf_counter() - upload_started) * 1000.0
                upload_total_ms += elapsed_ms
                entry["object_name"] = object_name
                entry["storage_status"] = "READY"
                entry["upload_duration_ms"] = round(elapsed_ms, 3)
            except Exception:
                entry.update(
                    {
                        "status": "NOT_READY",
                        "storage_status": "NOT_READY",
                        "reason": "SEQUENCE_FRAME_UPLOAD_FAILED",
                    }
                )
                entry.pop("filename", None)
                entry.pop("object_name", None)

        ready_count = sum(
            isinstance(item, Mapping) and item.get("status") == "READY"
            for item in frames
        )
        durable["status"] = (
            "READY"
            if ready_count == MOTION_SEQUENCE_FRAME_COUNT
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        )
        performance = durable.setdefault("performance_ms", {})
        if isinstance(performance, dict):
            performance["storage_upload_total"] = round(upload_total_ms, 3)
            performance["persistence_total"] = round(
                (perf_counter() - started) * 1000.0,
                3,
            )

        manifest_name = self._sequence_object_name(
            assessment_id,
            "manifest.json",
        )
        manifest_blob = self._blob(manifest_name)
        manifest_blob.cache_control = "private, no-store"
        manifest_blob.upload_from_string(
            json.dumps(durable, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )
        return durable

    def load_sequence_manifest(
        self,
        assessment_id: str,
    ) -> dict[str, Any] | None:
        object_name = self._sequence_object_name(assessment_id, "manifest.json")
        try:
            payload = self._blob(object_name).download_as_bytes()
            manifest = json.loads(payload.decode("utf-8"))
        except (NotFound, UnicodeError, json.JSONDecodeError):
            return None
        return manifest if isinstance(manifest, dict) else None

    def download_sequence_frame(
        self,
        assessment_id: str,
        index: int,
    ) -> bytes:
        index = self._sequence_index(index)
        object_name = self._sequence_object_name(
            assessment_id,
            f"{index:02d}.jpg",
        )
        try:
            return self._blob(object_name).download_as_bytes()
        except NotFound as exc:
            raise FileNotFoundError(object_name) from exc

    def persist_reach_grid(
        self,
        assessment_id: str,
        source_dir: Path,
        manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Upload available Footwork grid cells and a private manifest."""

        started = perf_counter()
        source_dir = Path(source_dir)
        durable = deepcopy(dict(manifest))
        raw_cells = durable.get("cells")
        cells = raw_cells if isinstance(raw_cells, list) else []
        upload_total_ms = 0.0

        for entry in cells:
            if not isinstance(entry, dict) or entry.get("status") != "READY":
                continue
            key = self._reach_grid_key(entry.get("key"))
            filename = f"{CELL_SLUGS[key]}.jpg"
            source_path = source_dir / filename
            if not source_path.is_file():
                entry.update(
                    {
                        "status": "NOT_READY",
                        "reason": "LOCAL_REACH_GRID_FRAME_NOT_READY",
                    }
                )
                entry.pop("filename", None)
                continue

            object_name = self._reach_grid_object_name(assessment_id, filename)
            upload_started = perf_counter()
            try:
                blob = self._blob(object_name)
                blob.cache_control = "private, max-age=300"
                blob.metadata = {
                    "assessment_id": self._assessment_id(assessment_id),
                    "reach_grid_key": key,
                    "requested_timestamp_ms": str(
                        entry.get("requested_timestamp_ms", "")
                    ),
                    "analysis_frame_index": str(
                        entry.get("analysis_frame_index", "")
                    ),
                    "source_frame_index": str(
                        entry.get("source_frame_index", "")
                    ),
                }
                blob.upload_from_filename(
                    str(source_path),
                    content_type="image/jpeg",
                )
                elapsed_ms = (perf_counter() - upload_started) * 1000.0
                upload_total_ms += elapsed_ms
                entry["object_name"] = object_name
                entry["storage_status"] = "READY"
                entry["upload_duration_ms"] = round(elapsed_ms, 3)
            except Exception:
                entry.update(
                    {
                        "status": "NOT_READY",
                        "storage_status": "NOT_READY",
                        "reason": "REACH_GRID_FRAME_UPLOAD_FAILED",
                    }
                )
                entry.pop("filename", None)
                entry.pop("object_name", None)

        ready_count = sum(
            isinstance(item, Mapping) and item.get("status") == "READY"
            for item in cells
        )
        durable["status"] = (
            "READY"
            if ready_count == GRID_CELL_COUNT
            else "PARTIAL"
            if ready_count
            else "NOT_READY"
        )
        performance = durable.setdefault("performance_ms", {})
        if isinstance(performance, dict):
            performance["storage_upload_total"] = round(upload_total_ms, 3)
            performance["persistence_total"] = round(
                (perf_counter() - started) * 1000.0,
                3,
            )

        manifest_name = self._reach_grid_object_name(
            assessment_id,
            "manifest.json",
        )
        manifest_blob = self._blob(manifest_name)
        manifest_blob.cache_control = "private, no-store"
        manifest_blob.upload_from_string(
            json.dumps(durable, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )
        return durable

    def load_reach_grid_manifest(
        self,
        assessment_id: str,
    ) -> dict[str, Any] | None:
        object_name = self._reach_grid_object_name(
            assessment_id,
            "manifest.json",
        )
        try:
            payload = self._blob(object_name).download_as_bytes()
            manifest = json.loads(payload.decode("utf-8"))
        except (NotFound, UnicodeError, json.JSONDecodeError):
            return None
        return manifest if isinstance(manifest, dict) else None

    def download_reach_grid_frame(
        self,
        assessment_id: str,
        key: str,
    ) -> bytes:
        key = self._reach_grid_key(key)
        object_name = self._reach_grid_object_name(
            assessment_id,
            f"{CELL_SLUGS[key]}.jpg",
        )
        try:
            return self._blob(object_name).download_as_bytes()
        except NotFound as exc:
            raise FileNotFoundError(object_name) from exc
