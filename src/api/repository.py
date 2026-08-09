"""Repository contract for AI Motion video analyses.

This module defines the data-access contract used by the application/service
layer. Concrete implementations (for example PostgreSQL) only need to satisfy
this interface.

Python ``Protocol`` is used intentionally:
- no runtime inheritance requirement
- existing PostgreSQL repository remains unchanged
- easy to replace with an in-memory/mock repository in tests
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol


class VideoAnalysisRepository(Protocol):
    def task_dir(self, external_analysis_id: str) -> Path:
        ...

    def user_exists(self, user_id: int) -> bool:
        ...

    def create_analysis(
        self,
        *,
        user_id: int,
        external_analysis_id: str,
        video_url: str,
        analysis_type: str,
        processing_status: str,
        progress: int,
        current_stage: str | None,
        created_at,
        updated_at,
    ) -> None:
        ...

    def update_status(
        self,
        external_analysis_id: str,
        *,
        processing_status: str,
        progress: int,
        current_stage: str | None,
        updated_at,
        completed_at=None,
        error_message: str | None = None,
    ) -> None:
        ...

    def save_report(
        self,
        external_analysis_id: str,
        report: Mapping[str, Any],
    ) -> None:
        ...

    def clear_video_reference(
        self,
        external_analysis_id: str,
    ) -> None:
        ...

    def get_analysis(
        self,
        external_analysis_id: str,
    ) -> dict[str, Any] | None:
        ...

    def get_report(
        self,
        external_analysis_id: str,
        analysis_type: str | None = None,
    ) -> dict[str, Any] | None:
        ...

    def get_latest_motion(
        self,
        user_id: int,
        motion_type: str,
    ) -> dict[str, Any] | None:
        ...

    def get_previous_motion(
        self,
        user_id: int,
        motion_type: str,
    ) -> dict[str, Any] | None:
        ...

    def get_latest_required_motions(
        self,
        user_id: int,
    ) -> dict[str, dict[str, Any]]:
        ...


    def get_motion_history(
        self,
        user_id: int,
        motion_type: str,
    ) -> list[dict[str, Any]]:
        ...

    def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        ...
