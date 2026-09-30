from __future__ import annotations

from types import SimpleNamespace

from google.cloud import tasks_v2

from src.api.task_queue import MotionTaskQueue


class FakeCloudTasksClient:
    def __init__(self):
        self.request = None

    @staticmethod
    def queue_path(project_id, location, queue_name):
        return f"projects/{project_id}/locations/{location}/queues/{queue_name}"

    @staticmethod
    def task_path(project_id, location, queue_name, task_name):
        return (
            f"projects/{project_id}/locations/{location}/queues/"
            f"{queue_name}/tasks/{task_name}"
        )

    def create_task(self, *, request):
        self.request = request
        return SimpleNamespace(name=request["task"]["name"])


def test_queue_attaches_oidc_identity_for_private_cloud_run(monkeypatch):
    fake = FakeCloudTasksClient()
    monkeypatch.setattr(tasks_v2, "CloudTasksClient", lambda: fake)
    queue = MotionTaskQueue(
        project_id="ai-motion-lab-ivesmi",
        location="asia-east1",
        queue_name="ai-motion-poc-analysis",
        worker_url=(
            "https://preview---ai-motion-poc.example.run.app/"
            "api/v1/internal/motion-assessments/process"
        ),
        internal_api_key="test-internal-key",
        service_account_email=(
            "ai-motion-poc-runtime@ai-motion-lab-ivesmi.iam.gserviceaccount.com"
        ),
        oidc_audience="https://ai-motion-poc.example.run.app",
    )

    queue.enqueue(assessment_id=42, job_type="storage", object_name="uploads/x.mp4")

    http_request = fake.request["task"]["http_request"]
    assert http_request["oidc_token"] == {
        "service_account_email": (
            "ai-motion-poc-runtime@ai-motion-lab-ivesmi.iam.gserviceaccount.com"
        ),
        "audience": "https://ai-motion-poc.example.run.app",
    }
    assert http_request["headers"]["X-Internal-Api-Key"] == "test-internal-key"


def test_queue_keeps_local_compatibility_without_oidc_identity(monkeypatch):
    fake = FakeCloudTasksClient()
    monkeypatch.setattr(tasks_v2, "CloudTasksClient", lambda: fake)
    queue = MotionTaskQueue(
        project_id="local-test",
        location="asia-east1",
        queue_name="local-analysis",
        worker_url="http://127.0.0.1:8000/api/v1/internal/motion-assessments/process",
        internal_api_key="test-internal-key",
    )

    queue.enqueue(assessment_id=7, job_type="annotation")

    assert "oidc_token" not in fake.request["task"]["http_request"]
