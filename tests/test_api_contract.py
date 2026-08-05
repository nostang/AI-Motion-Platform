import tempfile
import cv2
import numpy as np
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import src.api.app as api_module
from src.api.repository import AssessmentRepository


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_repository = api_module.repository
        self.original_service_repository = api_module.service.repository
        repo = AssessmentRepository(Path(self.tmp.name))
        api_module.repository = repo
        api_module.service.repository = repo
        self.client = TestClient(api_module.app)

    def tearDown(self):
        self.client.close()
        api_module.repository = self.original_repository
        api_module.service.repository = self.original_service_repository
        self.tmp.cleanup()


    def test_create_assessment_returns_202(self):
        video_path = Path(self.tmp.name) / "sample.mp4"
        writer = cv2.VideoWriter(
            str(video_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            10.0,
            (32, 32),
        )
        for _ in range(40):
            writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
        writer.release()

        original_process = api_module.service.process
        api_module.service.process = lambda assessment_id: None
        try:
            with video_path.open("rb") as handle:
                response = self.client.post(
                    "/api/v1/motion-assessments",
                    data={"assessment_type": "footwork"},
                    files={"video": ("sample.mp4", handle, "video/mp4")},
                )
        finally:
            api_module.service.process = original_process

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "uploaded")
        self.assertTrue(body["data"]["assessment_id"].startswith("ma_"))

    def test_missing_video_uses_contract_error(self):
        response = self.client.post(
            "/api/v1/motion-assessments",
            data={"assessment_type": "footwork"},
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "VIDEO_REQUIRED")

    def test_unknown_assessment_returns_404_envelope(self):
        response = self.client.get("/api/v1/motion-assessments/ma_missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "ASSESSMENT_NOT_FOUND")

    def test_report_not_ready_returns_409(self):
        api_module.repository.save({
            "assessment_id": "ma_pending",
            "assessment_type": "footwork",
            "status": "processing",
            "progress": 50,
            "current_stage": "event_detection",
            "created_at": "2026-08-05T00:00:00+00:00",
            "updated_at": "2026-08-05T00:00:01+00:00",
            "completed_at": None,
            "failure": None,
        })
        response = self.client.get("/api/v1/motion-assessments/ma_pending/report")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "REPORT_NOT_READY")


if __name__ == "__main__":
    unittest.main()
