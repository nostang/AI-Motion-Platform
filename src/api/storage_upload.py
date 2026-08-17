"""Temporary Cloud Storage upload URL service for AI Motion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import timedelta
import os
from pathlib import PurePosixPath
from uuid import uuid4

import google.auth
from google.auth import impersonated_credentials
from google.cloud import storage


DEFAULT_BUCKET = "your-private-video-bucket"
ALLOWED_CONTENT_TYPES = frozenset({
    "video/mp4",
    "video/quicktime",
})
EXTENSION_BY_CONTENT_TYPE = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}


@dataclass(frozen=True)
class StoredVideoObject:
    object_name: str
    size: int
    content_type: str
    suffix: str


@dataclass(frozen=True)
class UploadTicket:
    object_name: str
    upload_url: str
    method: str
    expires_in_seconds: int
    content_type: str


class StorageUploadService:
    def __init__(
        self,
        bucket_name: str | None = None,
        service_account_email: str | None = None,
        expires_in_seconds: int = 15 * 60,
    ):
        self.bucket_name = (
            bucket_name
            or os.environ.get("VIDEO_UPLOAD_BUCKET")
            or DEFAULT_BUCKET
        )
        self.service_account_email = (
            service_account_email
            or os.environ.get("AI_MOTION_SERVICE_ACCOUNT")
        )
        self.expires_in_seconds = expires_in_seconds

    def create_upload_ticket(
        self,
        *,
        filename: str,
        content_type: str,
    ) -> UploadTicket:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("UNSUPPORTED_CONTENT_TYPE")

        suffix = PurePosixPath(filename or "").suffix.lower()
        expected_suffix = EXTENSION_BY_CONTENT_TYPE[content_type]
        if suffix not in {".mp4", ".mov"}:
            suffix = expected_suffix

        object_name = (
            f"uploads/{uuid4().hex}/source{suffix}"
        )

        source_credentials, _ = google.auth.default()
        signing_credentials = source_credentials

        # Cloud Run's attached service-account credentials do not carry a
        # local private key. Impersonation delegates V4 signing to IAM
        # Credentials (signBlob) while keeping the bucket private.
        if self.service_account_email:
            signing_credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=self.service_account_email,
                target_scopes=[
                    "https://www.googleapis.com/auth/devstorage.read_write"
                ],
                lifetime=self.expires_in_seconds,
            )

        client = storage.Client(credentials=source_credentials)
        blob = client.bucket(self.bucket_name).blob(object_name)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=self.expires_in_seconds),
            method="PUT",
            content_type=content_type,
            credentials=signing_credentials,
        )

        return UploadTicket(
            object_name=object_name,
            upload_url=upload_url,
            method="PUT",
            expires_in_seconds=self.expires_in_seconds,
            content_type=content_type,
        )

    @staticmethod
    def _validated_object_name(object_name: str) -> str:
        value = str(object_name or "").strip()
        path = PurePosixPath(value)

        if (
            not value.startswith("uploads/")
            or ".." in path.parts
            or path.suffix.lower() not in {".mp4", ".mov"}
        ):
            raise ValueError("INVALID_STORAGE_OBJECT")

        return value

    def get_video_object(
        self,
        object_name: str,
    ) -> StoredVideoObject:
        object_name = self._validated_object_name(object_name)
        client = storage.Client()
        blob = client.bucket(self.bucket_name).blob(object_name)

        if not blob.exists(client=client):
            raise FileNotFoundError(object_name)

        blob.reload(client=client)
        content_type = str(blob.content_type or "")
        suffix = PurePosixPath(object_name).suffix.lower()

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("UNSUPPORTED_CONTENT_TYPE")

        return StoredVideoObject(
            object_name=object_name,
            size=int(blob.size or 0),
            content_type=content_type,
            suffix=suffix,
        )

    def download_video(
        self,
        object_name: str,
        destination: Path,
    ) -> Path:
        object_name = self._validated_object_name(object_name)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        client = storage.Client()
        blob = client.bucket(self.bucket_name).blob(object_name)
        blob.download_to_filename(str(destination))
        return destination

    def delete_video(
        self,
        object_name: str,
    ) -> None:
        object_name = self._validated_object_name(object_name)
        client = storage.Client()
        blob = client.bucket(self.bucket_name).blob(object_name)
        blob.delete()
