"""FastAPI adapter for AI Motion API Contract v1.9."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import cv2
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.dashboard_service import build_user_dashboard
from src.api.postgres_repository import PostgresVideoAnalysisRepository
from src.api.service import MotionAssessmentService
from src.coach.ai_coach_engine import AICoachEngine
from src.training.training_planner import AITrainingPlanner
from src.progress.progress_engine import ProgressEngine
from src.competency.competency_engine import CompetencyEngine
from src.competency.competency_profile import build_competency_profile
from src.report.competency_profile_report import (
    build_competency_profile_report,
)
from src.report.user_result_builder import build_user_result
from src.report.summary_result_builder import build_summary_result
from src.report.summary_progress_builder import build_summary_progress
from src.report.ai_summary_builder import build_ai_summary
from src.config import PROJECT_ROOT
from src.motion import registered_motion_types


load_dotenv(PROJECT_ROOT / ".env")


API_PREFIX = "/api/v1"
SUPPORTED_ASSESSMENT_TYPES = frozenset(registered_motion_types())
SUPPORTED_EXTENSIONS = {".mp4", ".mov"}
MAX_VIDEO_BYTES = 100 * 1024 * 1024
MIN_VIDEO_SECONDS = 3.0
MAX_VIDEO_SECONDS = 30.0

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL 未設定。"
        "例如：postgresql://ivesmi@localhost:5432/ai_motion"
    )

repository = PostgresVideoAnalysisRepository(
    DATABASE_URL,
    PROJECT_ROOT / "api_data" / "motion_assessments",
)
service = MotionAssessmentService(repository)

competency_engine = CompetencyEngine.from_file(
    PROJECT_ROOT / "src/config_data/competency_engine_rules.json"
)

ai_coach_engine = AICoachEngine.from_file(
    PROJECT_ROOT / "src/config_data/ai_coach_rules.json"
)

training_planner = AITrainingPlanner.from_file(
    PROJECT_ROOT / "src/config_data/training_plan_rules.json"
)

progress_engine = ProgressEngine()

app = FastAPI(
    title="AI Motion API",
    version="2.6.0",
)

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
        return failure(
            400,
            "VIDEO_REQUIRED",
            "未提供影片檔案。",
        )

    return failure(
        400,
        "INVALID_REQUEST",
        "Request 欄位不完整或格式錯誤。",
        {"fields": sorted(missing_fields)},
    )


def envelope(data=None, error=None, success=True):
    return {
        "success": success,
        "data": data,
        "error": error,
    }


def failure(
    status: int,
    code: str,
    message: str,
    details=None,
):
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
    task = repository.get_analysis(assessment_id)

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

    report = repository.get_report(
        assessment_id,
        analysis_type=actual_type,
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


@app.post(
    f"{API_PREFIX}/motion-assessments",
    status_code=202,
)
async def create_motion_assessment(
    background_tasks: BackgroundTasks,
    assessment_type: str = Form(...),
    user_id: int = Form(...),
    video: UploadFile = File(...),
    client_recorded_at: str | None = Form(None),
    notes: str | None = Form(None),
):
    normalized_type = assessment_type.strip().lower()

    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    if normalized_type not in SUPPORTED_ASSESSMENT_TYPES:
        return failure(
            400,
            "INVALID_ASSESSMENT_TYPE",
            "不支援指定的 assessment_type。",
            {
                "received": assessment_type,
                "supported": sorted(
                    SUPPORTED_ASSESSMENT_TYPES
                ),
            },
        )

    suffix = Path(
        video.filename or ""
    ).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        return failure(
            400,
            "INVALID_VIDEO_FORMAT",
            "僅支援 .mp4 與 .mov 影片。",
        )

    assessment_id = f"ma_{uuid4().hex[:16]}"
    directory = repository.task_dir(
        assessment_id
    )
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    video_path = directory / f"source{suffix}"
    size = 0

    with video_path.open("wb") as target:
        while chunk := await video.read(
            1024 * 1024
        ):
            size += len(chunk)

            if size > MAX_VIDEO_BYTES:
                target.close()
                video_path.unlink(
                    missing_ok=True
                )

                return failure(
                    413,
                    "VIDEO_TOO_LARGE",
                    "影片檔案不可超過 100 MB。",
                )

            target.write(chunk)

    await video.close()

    duration = _video_duration_seconds(
        video_path
    )

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
            {
                "duration_seconds": round(
                    duration,
                    3,
                )
            },
        )

    if duration < MIN_VIDEO_SECONDS:
        video_path.unlink(missing_ok=True)

        return failure(
            422,
            "VIDEO_DURATION_INVALID",
            "影片長度至少需要 3 秒。",
            {
                "duration_seconds": round(
                    duration,
                    3,
                )
            },
        )

    now = utc_now()

    repository.create_analysis(
        user_id=user_id,
        external_analysis_id=assessment_id,
        video_url=str(video_path),
        analysis_type=normalized_type,
        processing_status="uploaded",
        progress=0,
        current_stage="uploaded",
        created_at=now,
        updated_at=now,
    )

    background_tasks.add_task(
        service.process,
        assessment_id,
    )

    return envelope(
        {
            "assessment_id": assessment_id,
            "assessment_type": normalized_type,
            "status": "uploaded",
            "created_at": now,
            "status_url": (
                f"{API_PREFIX}/motion-assessments/"
                f"{assessment_id}"
            ),
            "report_url": (
                f"{API_PREFIX}/motion-assessments/"
                f"{assessment_id}/report"
            ),
        }
    )


@app.get(
    f"{API_PREFIX}/motion-assessments/"
    "{assessment_id}"
)
def get_motion_assessment(
    assessment_id: str,
):
    task = repository.get_analysis(
        assessment_id
    )

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
            f"{API_PREFIX}/motion-assessments/"
            f"{assessment_id}/report"
        )

    return envelope(data)


@app.get(
    f"{API_PREFIX}/motion-assessments/"
    "{assessment_id}/report"
)
def get_motion_assessment_report(
    assessment_id: str,
):
    task = repository.get_analysis(
        assessment_id
    )

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

    report = repository.get_report(
        assessment_id,
        analysis_type=task.get(
            "assessment_type"
        ),
    )

    if report is None:
        return failure(
            500,
            "ANALYSIS_FAILED",
            "分析完成但找不到 Report JSON。",
            {
                "assessment_id": assessment_id,
                "assessment_type": task.get(
                    "assessment_type"
                ),
            },
        )

    report = dict(report)
    report.setdefault(
        "meta",
        {},
    )["engine_assessment_id"] = (
        report.get("assessment_id")
    )
    report["assessment_id"] = (
        assessment_id
    )

    return envelope(report)


@app.get(
    f"{API_PREFIX}/motion-assessments/"
    "{assessment_id}/result"
)
def get_motion_assessment_result(
    assessment_id: str,
):
    task = repository.get_analysis(
        assessment_id
    )

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
            "RESULT_NOT_READY",
            "分析尚未完成，暫時無法取得結果。",
            {
                "assessment_id": assessment_id,
                "status": task["status"],
            },
        )

    report = repository.get_report(
        assessment_id,
        analysis_type=task.get(
            "assessment_type"
        ),
    )

    if report is None:
        return failure(
            500,
            "ANALYSIS_FAILED",
            "分析完成但找不到 Report JSON。",
            {
                "assessment_id": assessment_id,
                "assessment_type": task.get(
                    "assessment_type"
                ),
            },
        )

    result = build_user_result(report)

    # Public/Web API always uses the external ma_ assessment ID.
    result["assessment_id"] = assessment_id

    return envelope(result)


@app.get(
    f"{API_PREFIX}/users/{{user_id}}/"
    "motion-assessments"
)
def list_user_motion_assessments(
    user_id: int,
    limit: int = 20,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    analyses = repository.list_by_user(
        user_id,
        limit=limit,
    )

    return envelope(
        {
            "user_id": user_id,
            "count": len(analyses),
            "items": analyses,
        }
    )


@app.get(
    f"{API_PREFIX}/users/{{user_id}}/summary"
)
def get_user_summary(
    user_id: int,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    latest = repository.get_latest_required_motions(
        user_id
    )

    histories = {
        motion_type: repository.get_motion_history(
            user_id,
            motion_type,
        )
        for motion_type in (
            "footwork",
            "serve",
            "clear",
        )
    }

    progress = build_summary_progress(
        histories,
        progress_engine,
    )

    summary = build_summary_result(
        latest,
        progress=progress,
    )

    context, missing = _build_latest_competency_context(
        user_id
    )

    if context is not None:
        coach = ai_coach_engine.generate(
            context["profile"],
            context["interpretation"],
        )
        summary["ai_summary"] = build_ai_summary(
            summary,
            coach,
        )
    else:
        summary["ai_summary"] = {
            "status": "NOT_READY",
            "reason": "MISSING_REQUIRED_MOTIONS",
            "missing_motions": missing,
        }

    return envelope(summary)


@app.get(
    f"{API_PREFIX}/users/{{user_id}}/"
    "dashboard"
)
def get_user_dashboard(
    user_id: int,
    limit: int = 20,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    analyses = repository.list_by_user(
        user_id,
        limit=limit,
    )

    dashboard = build_user_dashboard(
        user_id=user_id,
        analyses=analyses,
    )

    return envelope(dashboard)


def _build_profile_from_request(
    request: CompetencyProfileRequest,
):
    footwork_report, error = _public_report(
        request.footwork_assessment_id,
        "footwork",
    )
    if error is not None:
        return None, error

    serve_report, error = _public_report(
        request.serve_assessment_id,
        "serve",
    )
    if error is not None:
        return None, error

    clear_report, error = _public_report(
        request.clear_assessment_id,
        "clear",
    )
    if error is not None:
        return None, error

    profile = build_competency_profile(
        player_id=request.player_id,
        footwork_report=footwork_report,
        serve_report=serve_report,
        clear_report=clear_report,
    )

    return profile, None


@app.post(
    f"{API_PREFIX}/competency-profiles"
)
def create_competency_profile(
    request: CompetencyProfileRequest,
):
    profile, error = (
        _build_profile_from_request(request)
    )

    if error is not None:
        return error

    return envelope(profile)


@app.post(
    f"{API_PREFIX}/competency-profile-reports"
)
def create_competency_profile_report(
    request: CompetencyProfileRequest,
):
    profile, error = (
        _build_profile_from_request(request)
    )

    if error is not None:
        return error

    report = build_competency_profile_report(
        profile
    )

    return envelope(report)


def _build_latest_competency_context(
    user_id: int,
):
    latest = repository.get_latest_required_motions(
        user_id
    )

    required = {
        "footwork",
        "serve",
        "clear",
    }

    missing = sorted(
        required - set(latest)
    )

    if missing:
        return None, missing

    reports = {}

    for motion_type in required:
        item = latest[motion_type]
        report = dict(item["report"])

        report.setdefault(
            "meta",
            {},
        )["engine_assessment_id"] = (
            report.get("assessment_id")
        )

        report["assessment_id"] = (
            item["assessment_id"]
        )

        reports[motion_type] = report

    profile = build_competency_profile(
        player_id=str(user_id),
        footwork_report=reports["footwork"],
        serve_report=reports["serve"],
        clear_report=reports["clear"],
    )

    interpretation = competency_engine.evaluate(
        profile
    )

    return {
        "latest": latest,
        "reports": reports,
        "profile": profile,
        "interpretation": interpretation,
    }, []


@app.post(
    f"{API_PREFIX}/users/{{user_id}}/"
    "competency"
)
def create_user_competency(
    user_id: int,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    context, missing = _build_latest_competency_context(
        user_id
    )

    if context is None:
        return failure(
            409,
            "COMPETENCY_NOT_READY",
            "尚未完成建立能力檔案所需的全部測驗。",
            {
                "user_id": user_id,
                "missing_motions": missing,
            },
        )

    return envelope(
        {
            "profile": context["profile"],
            "interpretation": context["interpretation"],
        }
    )


@app.post(
    f"{API_PREFIX}/users/{{user_id}}/coach"
)
def create_user_coach(
    user_id: int,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    context, missing = _build_latest_competency_context(
        user_id
    )

    if context is None:
        return failure(
            409,
            "COACH_NOT_READY",
            "尚未完成產生 AI Coach 建議所需的全部測驗。",
            {
                "user_id": user_id,
                "missing_motions": missing,
            },
        )

    coach = ai_coach_engine.generate(
        context["profile"],
        context["interpretation"],
    )

    return envelope(coach)


@app.post(
    f"{API_PREFIX}/users/{{user_id}}/training-plan"
)
def create_user_training_plan(
    user_id: int,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    context, missing = _build_latest_competency_context(
        user_id
    )

    if context is None:
        return failure(
            409,
            "TRAINING_PLAN_NOT_READY",
            "尚未完成產生訓練計畫所需的全部測驗。",
            {
                "user_id": user_id,
                "missing_motions": missing,
            },
        )

    coach = ai_coach_engine.generate(
        context["profile"],
        context["interpretation"],
    )

    plan = training_planner.build(
        coach
    )

    return envelope(plan)


@app.get(
    f"{API_PREFIX}/users/{{user_id}}/progress/{{motion_type}}"
)
def get_user_progress(
    user_id: int,
    motion_type: str,
    mode: str = "PREVIOUS",
    reference_assessment_id: str | None = None,
):
    if not repository.user_exists(user_id):
        return failure(
            404,
            "USER_NOT_FOUND",
            "找不到指定的使用者。",
            {"user_id": user_id},
        )

    normalized_type = motion_type.strip().lower()

    if normalized_type not in SUPPORTED_ASSESSMENT_TYPES:
        return failure(
            400,
            "INVALID_ASSESSMENT_TYPE",
            "不支援的動作類型。",
            {
                "motion_type": normalized_type,
                "supported_types": sorted(
                    SUPPORTED_ASSESSMENT_TYPES
                ),
            },
        )

    history = repository.get_motion_history(
        user_id,
        normalized_type,
    )

    try:
        result = progress_engine.compare(
            history,
            mode=mode,
            reference_assessment_id=reference_assessment_id,
        )
    except ValueError as exc:
        return failure(
            400,
            "INVALID_PROGRESS_REQUEST",
            str(exc),
            {
                "mode": mode,
                "reference_assessment_id": (
                    reference_assessment_id
                ),
            },
        )

    if result.get("status") != "READY":
        return failure(
            409,
            "PROGRESS_NOT_READY",
            result.get(
                "reason",
                {},
            ).get(
                "message",
                "目前沒有足夠的歷史資料可比較。",
            ),
            {
                "user_id": user_id,
                "motion_type": normalized_type,
                "comparison_mode": mode.upper(),
                "reason": result.get("reason"),
                "history_count": len(history),
            },
        )

    return envelope(result)

