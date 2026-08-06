"""FastAPI adapter for AI Motion API Contract v1.2."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.repository import AssessmentRepository
from src.api.service import MotionAssessmentService
from src.competency.competency_profile import build_competency_profile
from src.config import PROJECT_ROOT
from src.motion import registered_motion_types


API_PREFIX = "/api/v1"
SUPPORTED_ASSESSMENT_TYPES = frozenset(registered_motion_types())
SUPPORTED_EXTENSIONS = {".mp4", ".mov"}
MAX_VIDEO_BYTES = 100 * 1024 * 1024
MIN_VIDEO_SECONDS = 3.0
MAX_VIDEO_SECONDS = 30.0

repository = AssessmentRepository(
    PROJECT_ROOT / "api_data" / "motion_assessments"
)
service = MotionAssessmentService(repository)
app = FastAPI(title="AI Motion API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompetencyProfileRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=100)
    footwork_assessment_id: str = Field(min_length=1)
    serve_assessment_id: str = Field(min_length=1)
    clear_assessment_id: str = Field(min_length=1)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    missing_fields = {
        str(error.get("loc", [""])[-1])
        for error in exc.errors()
        if error.get("type") == "missing"
    }

    if "video" in missing_fields:
        return failure(400, "VIDEO_REQUIRED", "未提供影片檔案。")

    return failure(
        400,
        "INVALID_REQUEST",
        "Request 欄位不完整或格式錯誤。",
        {"fields": sorted(missing_fields)},
    )


def envelope(data=None, error=None, success=True):
    return {"success": success, "data": data, "error": error}


def failure(status: int, code: str, message: str, details=None):
    return JSONResponse(
        status_code=status,
        content=envelope(
            None,
            {
                "code": code,
                "message": message,
                "details": details or {},
            },
            False,
        ),
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _video_duration_seconds(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return 0.0
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        return frames / fps if fps > 0 else 0.0
    finally:
        cap.release()


def _public_report(
    assessment_id: str,
    expected_type: str,
) -> tuple[dict | None, JSONResponse | None]:
    task = repository.get(assessment_id)

    if task is None:
        return None, failure(
            404,
            "ASSESSMENT_NOT_FOUND",
            "找不到指定的分析任務。",
            {
                "assessment_id": assessment_id,
                "expected_type": expected_type,
            },
        )

    actual_type = task.get("assessment_type")
    if actual_type != expected_type:
        return None, failure(
            409,
            "ASSESSMENT_TYPE_MISMATCH",
            "分析任務類型與 Competency Profile 欄位不符。",
            {
                "assessment_id": assessment_id,
                "expected_type": expected_type,
                "actual_type": actual_type,
            },
        )

    if task.get("status") != "completed":
        return None, failure(
            409,
            "ASSESSMENT_NOT_READY",
            "分析任務尚未完成，無法建立 Competency Profile。",
            {
                "assessment_id": assessment_id,
                "assessment_type": actual_type,
                "status": task.get("status"),
            },
        )

    report = repository.report(
        assessment_id,
        assessment_type=actual_type,
    )
    if report is None:
        return None, failure(
            500,
            "REPORT_NOT_FOUND",
            "分析任務已完成，但找不到對應 Report JSON。",
            {
                "assessment_id": assessment_id,
                "assessment_type": actual_type,
            },
        )

    public_report = dict(report)
    public_report.setdefault("meta", {})[
        "engine_assessment_id"
    ] = public_report.get("assessment_id")
    public_report["assessment_id"] = assessment_id
    return public_report, None


@app.post(f"{API_PREFIX}/motion-assessments", status_code=202)
async def create_motion_assessment(
    background_tasks: BackgroundTasks,
    assessment_type: str = Form(...),
    video: UploadFile = File(...),
    client_recorded_at: str | None = Form(None),
    notes: str | None = Form(None),
):
    normalized_type = assessment_type.strip().lower()

    if normalized_type not in SUPPORTED_ASSESSMENT_TYPES:
        return failure(
            400,
            "INVALID_ASSESSMENT_TYPE",
            "不支援指定的 assessment_type。",
            {
                "received": assessment_type,
                "supported": sorted(SUPPORTED_ASSESSMENT_TYPES),
            },
        )

    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return failure(
            400,
            "INVALID_VIDEO_FORMAT",
            "僅支援 .mp4 與 .mov 影片。",
        )

    assessment_id = f"ma_{uuid4().hex[:16]}"
    directory = repository.task_dir(assessment_id)
    directory.mkdir(parents=True, exist_ok=True)

    video_path = directory / f"source{suffix}"
    size = 0

    with video_path.open("wb") as target:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_BYTES:
                target.close()
                video_path.unlink(missing_ok=True)
                return failure(
                    413,
                    "VIDEO_TOO_LARGE",
                    "影片檔案不可超過 100 MB。",
                )
            target.write(chunk)

    await video.close()
    duration = _video_duration_seconds(video_path)

    if duration <= 0:
        video_path.unlink(missing_ok=True)
        return failure(
            400,
            "INVALID_VIDEO_FORMAT",
            "影片無法讀取或檔案已損壞。",
        )

    if duration > MAX_VIDEO_SECONDS:
        video_path.unlink(missing_ok=True)
        return failure(
            400,
            "VIDEO_TOO_LONG",
            "影片不可超過 30 秒。",
            {"duration_seconds": round(duration, 3)},
        )

    if duration < MIN_VIDEO_SECONDS:
        video_path.unlink(missing_ok=True)
        return failure(
            422,
            "VIDEO_DURATION_INVALID",
            "影片長度至少需要 3 秒。",
            {"duration_seconds": round(duration, 3)},
        )

    now = utc_now()
    task = {
        "assessment_id": assessment_id,
        "assessment_type": normalized_type,
        "status": "uploaded",
        "progress": 0,
        "current_stage": "uploaded",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "client_recorded_at": client_recorded_at,
        "notes": notes,
        "original_filename": video.filename,
        "video_path": str(video_path),
        "video_duration_seconds": round(duration, 3),
        "failure": None,
    }

    repository.save(task)
    background_tasks.add_task(service.process, assessment_id)

    return envelope(
        {
            "assessment_id": assessment_id,
            "assessment_type": normalized_type,
            "status": "uploaded",
            "created_at": now,
            "status_url": f"{API_PREFIX}/motion-assessments/{assessment_id}",
            "report_url": (
                f"{API_PREFIX}/motion-assessments/{assessment_id}/report"
            ),
        }
    )


@app.get(f"{API_PREFIX}/motion-assessments/{{assessment_id}}")
def get_motion_assessment(assessment_id: str):
    task = repository.get(assessment_id)

    if task is None:
        return failure(
            404,
            "ASSESSMENT_NOT_FOUND",
            "找不到指定的分析任務。",
            {"assessment_id": assessment_id},
        )

    data = {
        key: task.get(key)
        for key in (
            "assessment_id",
            "assessment_type",
            "status",
            "progress",
            "current_stage",
            "created_at",
            "updated_at",
            "completed_at",
            "failure",
        )
    }

    if task["status"] == "completed":
        data["report_url"] = (
            f"{API_PREFIX}/motion-assessments/{assessment_id}/report"
        )

    return envelope(data)


@app.get(f"{API_PREFIX}/motion-assessments/{{assessment_id}}/report")
def get_motion_assessment_report(assessment_id: str):
    task = repository.get(assessment_id)

    if task is None:
        return failure(
            404,
            "ASSESSMENT_NOT_FOUND",
            "找不到指定的分析任務。",
            {"assessment_id": assessment_id},
        )

    if task["status"] != "completed":
        return failure(
            409,
            "REPORT_NOT_READY",
            "分析尚未完成，暫時無法取得報告。",
            {
                "assessment_id": assessment_id,
                "status": task["status"],
            },
        )

    report = repository.report(
        assessment_id,
        assessment_type=task.get("assessment_type"),
    )

    if report is None:
        return failure(
            500,
            "ANALYSIS_FAILED",
            "分析完成但找不到 Report JSON。",
            {
                "assessment_id": assessment_id,
                "assessment_type": task.get("assessment_type"),
            },
        )

    report = dict(report)
    report.setdefault("meta", {})["engine_assessment_id"] = report.get(
        "assessment_id"
    )
    report["assessment_id"] = assessment_id
    return envelope(report)


@app.post(f"{API_PREFIX}/competency-profiles")
def create_competency_profile(
    request: CompetencyProfileRequest,
):
    footwork_report, error = _public_report(
        request.footwork_assessment_id,
        "footwork",
    )
    if error is not None:
        return error

    serve_report, error = _public_report(
        request.serve_assessment_id,
        "serve",
    )
    if error is not None:
        return error

    clear_report, error = _public_report(
        request.clear_assessment_id,
        "clear",
    )
    if error is not None:
        return error

    profile = build_competency_profile(
        player_id=request.player_id,
        footwork_report=footwork_report,
        serve_report=serve_report,
        clear_report=clear_report,
    )
    return envelope(profile)
