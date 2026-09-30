"""Durable Cloud Tasks dispatcher for AI Motion assessments.

The web request only creates the database row and enqueues work.  The actual
CPU-heavy analysis runs inside a separate HTTP request initiated by Cloud
Tasks, so leaving the browser page cannot suspend the worker.
"""

from __future__ import annotations

import json
import os


class TaskQueueConfigurationError(RuntimeError):
    """Raised when production queue settings are incomplete."""


class MotionTaskQueue:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        location: str | None = None,
        queue_name: str | None = None,
        worker_url: str | None = None,
        internal_api_key: str | None = None,
        service_account_email: str | None = None,
        oidc_audience: str | None = None,
    ) -> None:
        self.project_id = (project_id or "").strip()
        self.location = (location or "").strip()
        self.queue_name = (queue_name or "").strip()
        self.worker_url = (worker_url or "").strip()
        self.internal_api_key = (internal_api_key or "").strip()
        self.service_account_email = (service_account_email or "").strip()
        self.oidc_audience = (oidc_audience or "").strip()

    @classmethod
    def from_environment(cls) -> "MotionTaskQueue":
        return cls(
            project_id=(
                os.environ.get("GOOGLE_CLOUD_PROJECT")
                or os.environ.get("GCP_PROJECT")
            ),
            location=os.environ.get(
                "AI_MOTION_TASK_LOCATION",
                "asia-east1",
            ),
            queue_name=os.environ.get("AI_MOTION_TASK_QUEUE"),
            worker_url=os.environ.get("AI_MOTION_WORKER_URL"),
            internal_api_key=os.environ.get("INTERNAL_API_KEY"),
            service_account_email=os.environ.get("AI_MOTION_SERVICE_ACCOUNT"),
            oidc_audience=os.environ.get("AI_MOTION_TASK_AUDIENCE"),
        )

    @property
    def enabled(self) -> bool:
        return all(
            (
                self.project_id,
                self.location,
                self.queue_name,
                self.worker_url,
                self.internal_api_key,
            )
        )

    def validate(self) -> None:
        if not self.enabled:
            raise TaskQueueConfigurationError(
                "AI Motion Cloud Tasks 設定不完整。"
            )

    def enqueue(
        self,
        *,
        assessment_id: int,
        job_type: str,
        object_name: str | None = None,
    ) -> str:
        self.validate()

        # Imported lazily so local development and API contract tests can run
        # without Google credentials or the Cloud Tasks package.
        from google.api_core.exceptions import AlreadyExists
        from google.cloud import tasks_v2
        from google.protobuf import duration_pb2

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            self.project_id,
            self.location,
            self.queue_name,
        )
        task_name = client.task_path(
            self.project_id,
            self.location,
            self.queue_name,
            f"assessment-{assessment_id}-{job_type}",
        )
        payload = {
            "assessment_id": assessment_id,
            "job_type": job_type,
            "object_name": object_name,
        }
        http_request = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": self.worker_url,
            "headers": {
                "Content-Type": "application/json",
                "X-Internal-Api-Key": self.internal_api_key,
            },
            "body": json.dumps(payload).encode("utf-8"),
        }
        if self.service_account_email:
            http_request["oidc_token"] = {
                "service_account_email": self.service_account_email,
                "audience": self.oidc_audience or self.worker_url,
            }

        task = {
            "name": task_name,
            "http_request": http_request,
            "dispatch_deadline": duration_pb2.Duration(seconds=1800),
        }

        try:
            response = client.create_task(
                request={"parent": parent, "task": task}
            )
        except AlreadyExists:
            # Named tasks make enqueueing idempotent if the browser retries the
            # creation request after losing its response.
            return task_name

        return response.name
