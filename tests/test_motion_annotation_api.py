from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost/test",
)

import src.api.app as api_module


class FakeRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tasks: dict[str, dict] = {}
        self.status_updates: list[tuple[str, dict]] = []
        self.created_analyses: list[dict] = []

    def task_dir(self, assessment_id: str) -> Path:
        return self.root / assessment_id

    def get_analysis(
        self,
        assessment_id: str,
    ) -> dict | None:
        return self.tasks.get(assessment_id)

    def user_exists(self, user_id: int) -> bool:
        return user_id == 1

    def create_analysis(self, **kwargs) -> None:
        self.created_analyses.append(kwargs)
        assessment_id = kwargs[
            "external_analysis_id"
        ]
        self.tasks[assessment_id] = {
            "assessment_id": assessment_id,
            "assessment_type": kwargs[
                "analysis_type"
            ],
            "status": kwargs[
                "processing_status"
            ],
            "processing_status": kwargs[
                "processing_status"
            ],
            "video_path": kwargs["video_url"],
        }

    def update_status(
        self,
        assessment_id: str,
        **kwargs,
    ) -> None:
        self.status_updates.append(
            (assessment_id, kwargs)
        )
        task = self.tasks.setdefault(
            assessment_id,
            {},
        )
        task.update(kwargs)

        if "processing_status" in kwargs:
            task["status"] = kwargs[
                "processing_status"
            ]


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def process(
        self,
        assessment_id: str,
        use_annotation: bool = False,
    ) -> None:
        self.calls.append(
            (assessment_id, use_annotation)
        )


class MotionAnnotationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.repository = FakeRepository(
            Path(self.temporary.name)
        )
        self.service = FakeService()

        self.repository_patch = patch.object(
            api_module,
            "repository",
            self.repository,
        )
        self.service_patch = patch.object(
            api_module,
            "service",
            self.service,
        )
        self.duration_patch = patch.object(
            api_module,
            "_video_duration_seconds",
            return_value=60.0,
        )

        self.repository_patch.start()
        self.service_patch.start()
        self.mock_duration = (
            self.duration_patch.start()
        )

        self.client = TestClient(api_module.app)

    def tearDown(self) -> None:
        self.client.close()
        self.duration_patch.stop()
        self.service_patch.stop()
        self.repository_patch.stop()
        self.temporary.cleanup()

    def create_task(
        self,
        assessment_id: str = "ma_test",
        *,
        status: str = "uploaded",
    ) -> Path:
        directory = self.repository.task_dir(
            assessment_id
        )
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        video_path = directory / "source.mp4"
        video_path.write_bytes(b"test-video")

        self.repository.tasks[assessment_id] = {
            "assessment_id": assessment_id,
            "assessment_type": "serve",
            "status": status,
            "processing_status": status,
            "video_path": str(video_path),
        }

        return video_path

    def put_annotation(
        self,
        assessment_id: str = "ma_test",
        *,
        start_ms: int = 1000,
        end_ms: int = 5000,
    ):
        return self.client.put(
            (
                "/api/v1/motion-assessments/"
                f"{assessment_id}/annotation"
            ),
            json={
                "start_ms": start_ms,
                "end_ms": end_ms,
                "status": "COMPLETE",
                "motion_type": "serve",
                "action_type": "FOREHAND_SERVE",
                "racket_side": "right",
                "calibration_eligibility": (
                    "ELIGIBLE"
                ),
                "notes": "完整正手發球",
            },
        )

    def test_saves_and_reads_annotation(self) -> None:
        self.create_task()

        response = self.put_annotation()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(
            body["data"]["window"],
            {
                "start_ms": 1000,
                "end_ms": 5000,
                "duration_ms": 4000,
                "source": "HUMAN",
                "status": "COMPLETE",
            },
        )

        annotation_path = (
            self.repository.task_dir("ma_test")
            / "human_annotation.json"
        )
        self.assertTrue(annotation_path.is_file())

        saved = json.loads(
            annotation_path.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            saved["action_type"],
            "FOREHAND_SERVE",
        )

        get_response = self.client.get(
            (
                "/api/v1/motion-assessments/"
                "ma_test/annotation"
            )
        )
        self.assertEqual(
            get_response.status_code,
            200,
        )
        self.assertEqual(
            get_response.json()["data"]["window"],
            body["data"]["window"],
        )

    def test_rejects_reversed_window(self) -> None:
        self.create_task()

        response = self.put_annotation(
            start_ms=5000,
            end_ms=1000,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "INVALID_ANNOTATION_WINDOW",
        )

    def test_rejects_window_over_30_seconds(
        self,
    ) -> None:
        self.create_task()

        response = self.put_annotation(
            start_ms=0,
            end_ms=30001,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "ANNOTATION_WINDOW_TOO_LONG",
        )

    def test_rejects_window_beyond_video(
        self,
    ) -> None:
        self.create_task()
        self.mock_duration.return_value = 5.0

        response = self.put_annotation(
            start_ms=1000,
            end_ms=6000,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "ANNOTATION_OUT_OF_RANGE",
        )

    def test_analysis_requires_annotation(
        self,
    ) -> None:
        self.create_task()

        response = self.client.post(
            (
                "/api/v1/motion-assessments/"
                "ma_test/analyze-annotation"
            )
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "ANNOTATION_REQUIRED",
        )
        self.assertEqual(self.service.calls, [])

    def test_queues_annotation_analysis(
        self,
    ) -> None:
        self.create_task()
        save_response = self.put_annotation()
        self.assertEqual(
            save_response.status_code,
            200,
        )

        response = self.client.post(
            (
                "/api/v1/motion-assessments/"
                "ma_test/analyze-annotation"
            )
        )

        self.assertEqual(response.status_code, 202)
        self.assertTrue(
            response.json()["data"][
                "annotation_applied"
            ]
        )
        self.assertEqual(
            self.service.calls,
            [("ma_test", True)],
        )
        self.assertTrue(
            any(
                update.get("current_stage")
                == "annotation_queued"
                for _, update
                in self.repository.status_updates
            )
        )

    def test_deferred_upload_accepts_90_seconds(
        self,
    ) -> None:
        self.mock_duration.return_value = 90.0

        response = self.client.post(
            "/api/v1/motion-assessments",
            data={
                "user_id": "1",
                "assessment_type": "serve",
                "defer_analysis": "true",
            },
            files={
                "video": (
                    "serve.mp4",
                    b"test-video",
                    "video/mp4",
                )
            },
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(
            body["data"]["analysis_deferred"]
        )
        self.assertEqual(self.service.calls, [])
        self.assertEqual(
            len(self.repository.created_analyses),
            1,
        )

    def test_direct_upload_rejects_90_seconds(
        self,
    ) -> None:
        self.mock_duration.return_value = 90.0

        response = self.client.post(
            "/api/v1/motion-assessments",
            data={
                "user_id": "1",
                "assessment_type": "serve",
                "defer_analysis": "false",
            },
            files={
                "video": (
                    "serve.mp4",
                    b"test-video",
                    "video/mp4",
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "VIDEO_TOO_LONG",
        )


if __name__ == "__main__":
    unittest.main()
