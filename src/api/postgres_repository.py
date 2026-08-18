"""PostgreSQL repository for AI Motion VIDEO_ANALYSES.

Repository V2 uses explicit operations instead of a generic save().
It follows the team ERD and keeps SQL out of API / Service layers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PostgresVideoAnalysisRepository:
    def __init__(
        self,
        database_url: str,
        storage_root: Path,
    ) -> None:
        self.database_url = database_url
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
        )

    def task_dir(self, external_analysis_id: str) -> Path:
        return self.storage_root / external_analysis_id

    def user_exists(self, user_id: int) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE user_id = %s",
                (user_id,),
            )
            return cur.fetchone() is not None

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
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO video_analyses (
                    user_id,
                    external_analysis_id,
                    video_url,
                    analysis_type,
                    processing_status,
                    progress,
                    current_stage,
                    created_at,
                    updated_at
                )
                VALUES (
                    %(user_id)s,
                    %(external_analysis_id)s,
                    %(video_url)s,
                    %(analysis_type)s,
                    %(processing_status)s,
                    %(progress)s,
                    %(current_stage)s,
                    %(created_at)s,
                    %(updated_at)s
                )
                """,
                {
                    "user_id": user_id,
                    "external_analysis_id": external_analysis_id,
                    "video_url": video_url,
                    "analysis_type": analysis_type,
                    "processing_status": processing_status,
                    "progress": progress,
                    "current_stage": current_stage,
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )

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
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    processing_status = %(processing_status)s,
                    progress = %(progress)s,
                    current_stage = %(current_stage)s,
                    error_message = %(error_message)s,
                    updated_at = %(updated_at)s,
                    completed_at = %(completed_at)s
                WHERE external_analysis_id = %(external_analysis_id)s
                """,
                {
                    "external_analysis_id": external_analysis_id,
                    "processing_status": processing_status,
                    "progress": progress,
                    "current_stage": current_stage,
                    "error_message": error_message,
                    "updated_at": updated_at,
                    "completed_at": completed_at,
                },
            )
            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{external_analysis_id}"
                )

    @staticmethod
    def _overall_score(report: Mapping[str, Any]) -> float | None:
        summary = report.get("summary")
        if isinstance(summary, Mapping):
            value = summary.get("overall_score")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)

        result_summary = report.get("result_summary")
        if isinstance(result_summary, Mapping):
            overall = result_summary.get("overall")
            if isinstance(overall, Mapping):
                value = overall.get("score")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)

        return None

    @staticmethod
    def _feedback(report: Mapping[str, Any]) -> str | None:
        coach = report.get("coach")
        if isinstance(coach, Mapping):
            value = coach.get("overall_message")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def save_report(
        self,
        external_analysis_id: str,
        report: Mapping[str, Any],
    ) -> None:
        meta = report.get("meta")
        meta = meta if isinstance(meta, Mapping) else {}

        model_version = (
            meta.get("engine_version")
            or report.get("engine_version")
        )
        rule_version = (
            meta.get("config_version")
            or report.get("config_version")
        )

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    overall_score = %(overall_score)s,
                    metrics_json = %(metrics_json)s,
                    feedback = %(feedback)s,
                    model_version = %(model_version)s,
                    rule_version = %(rule_version)s,
                    updated_at = NOW()
                WHERE external_analysis_id = %(external_analysis_id)s
                """,
                {
                    "external_analysis_id": external_analysis_id,
                    "overall_score": self._overall_score(report),
                    "metrics_json": Jsonb(dict(report)),
                    "feedback": self._feedback(report),
                    "model_version": model_version,
                    "rule_version": rule_version,
                },
            )
            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{external_analysis_id}"
                )

    def update_video_reference(
        self,
        external_analysis_id: str,
        video_path: str,
    ) -> None:
        """Update the analysis source path after video normalization."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    video_url = %s,
                    updated_at = NOW()
                WHERE external_analysis_id = %s
                """,
                (video_path, external_analysis_id),
            )

            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{external_analysis_id}"
                )

    def clear_video_reference(
        self,
        external_analysis_id: str,
    ) -> None:
        """清除已完成分析的暫存影片路徑。"""

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    video_url = NULL,
                    updated_at = NOW()
                WHERE external_analysis_id = %s
                """,
                (external_analysis_id,),
            )

            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{external_analysis_id}"
                )

    def get_analysis(
        self,
        external_analysis_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    analysis_id,
                    user_id,
                    external_analysis_id,
                    video_url,
                    analysis_type,
                    processing_status,
                    progress,
                    current_stage,
                    overall_score,
                    error_message,
                    created_at,
                    updated_at,
                    completed_at
                FROM video_analyses
                WHERE external_analysis_id = %s
                """,
                (external_analysis_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "analysis_id": row["analysis_id"],
            "assessment_id": row["external_analysis_id"],
            "user_id": row["user_id"],
            "assessment_type": row["analysis_type"],
            "status": row["processing_status"],
            "progress": row["progress"],
            "current_stage": row["current_stage"],
            "overall_score": (
                float(row["overall_score"])
                if row["overall_score"] is not None
                else None
            ),
            "video_path": row["video_url"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "completed_at": (
                row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None
            ),
            "failure": (
                {
                    "code": (
                        "INPUT_VALIDATION_FAILED"
                        if row["current_stage"] == "input_validation"
                        else "ANALYSIS_FAILED"
                    ),
                    "message": row["error_message"],
                    "retryable": True,
                }
                if row["error_message"]
                else None
            ),
        }

    def get_report(
        self,
        external_analysis_id: str,
        analysis_type: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            if analysis_type is None:
                cur.execute(
                    """
                    SELECT metrics_json
                    FROM video_analyses
                    WHERE external_analysis_id = %s
                    """,
                    (external_analysis_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT metrics_json
                    FROM video_analyses
                    WHERE external_analysis_id = %s
                      AND analysis_type = %s
                    """,
                    (external_analysis_id, analysis_type),
                )
            row = cur.fetchone()

        if row is None or row["metrics_json"] is None:
            return None
        return dict(row["metrics_json"])

    def get_latest_motion(
        self,
        user_id: int,
        motion_type: str,
    ) -> dict[str, Any] | None:
        """取得使用者某一 Motion 最新的已完成分析。"""

        normalized_type = motion_type.strip().lower()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    external_analysis_id,
                    analysis_type,
                    processing_status,
                    overall_score,
                    metrics_json,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND processing_status = 'completed'
                  AND metrics_json IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, normalized_type),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "assessment_id": row["external_analysis_id"],
            "assessment_type": row["analysis_type"],
            "status": row["processing_status"],
            "overall_score": (
                float(row["overall_score"])
                if row["overall_score"] is not None
                else None
            ),
            "report": dict(row["metrics_json"]),
            "created_at": row["created_at"].isoformat(),
            "completed_at": (
                row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None
            ),
        }

    def get_previous_motion(
        self,
        user_id: int,
        motion_type: str,
    ) -> dict[str, Any] | None:
        """取得某一 Motion 前一次已完成且具有完整 Report 的結果。"""

        normalized_type = motion_type.strip().lower()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    external_analysis_id,
                    analysis_type,
                    processing_status,
                    overall_score,
                    metrics_json,
                    model_version,
                    rule_version,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND processing_status = 'completed'
                  AND metrics_json IS NOT NULL
                ORDER BY created_at DESC, analysis_id DESC
                LIMIT 1 OFFSET 1
                """,
                (user_id, normalized_type),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "assessment_id": row["external_analysis_id"],
            "assessment_type": row["analysis_type"],
            "status": row["processing_status"],
            "overall_score": (
                float(row["overall_score"])
                if row["overall_score"] is not None
                else None
            ),
            "report": dict(row["metrics_json"]),
            "model_version": row["model_version"],
            "rule_version": row["rule_version"],
            "created_at": row["created_at"].isoformat(),
            "completed_at": (
                row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None
            ),
        }

    def get_latest_required_motions(
        self,
        user_id: int,
    ) -> dict[str, dict[str, Any]]:
        """取得 Competency Profile 所需三種 Motion 的最新完成結果。"""

        required = ("footwork", "serve", "clear")
        result: dict[str, dict[str, Any]] = {}

        for motion_type in required:
            item = self.get_latest_motion(
                user_id,
                motion_type,
            )
            if item is not None:
                result[motion_type] = item

        return result


    def get_motion_history(
        self,
        user_id: int,
        motion_type: str,
    ) -> list[dict[str, Any]]:
        """取得同一使用者、同一 Motion 的完整已完成 Assessment History。

        Progress Engine V2 需要永久保存的總分、版本資訊，
        以及 Report JSON 中的 dimension score evidence。
        不需要讀取 AI Coach 文字。
        """

        normalized_type = motion_type.strip().lower()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    external_analysis_id,
                    analysis_type,
                    overall_score,
                    metrics_json,
                    model_version,
                    rule_version,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND processing_status = 'completed'
                  AND overall_score IS NOT NULL
                  AND metrics_json IS NOT NULL
                ORDER BY created_at ASC, analysis_id ASC
                """,
                (user_id, normalized_type),
            )
            rows = cur.fetchall()

        return [
            {
                "assessment_id": row["external_analysis_id"],
                "motion_type": row["analysis_type"],
                "assessment_type": row["analysis_type"],
                "overall_score": float(row["overall_score"]),
                "report": dict(row["metrics_json"]),
                "model_version": row["model_version"],
                "rule_version": row["rule_version"],
                "created_at": row["created_at"].isoformat(),
                "completed_at": (
                    row["completed_at"].isoformat()
                    if row["completed_at"] is not None
                    else None
                ),
            }
            for row in rows
        ]

    def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    external_analysis_id,
                    analysis_type,
                    processing_status,
                    overall_score,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, safe_limit),
            )
            rows = cur.fetchall()

        return [
            {
                "assessment_id": row["external_analysis_id"],
                "assessment_type": row["analysis_type"],
                "status": row["processing_status"],
                "overall_score": (
                    float(row["overall_score"])
                    if row["overall_score"] is not None
                    else None
                ),
                "created_at": row["created_at"].isoformat(),
                "completed_at": (
                    row["completed_at"].isoformat()
                    if row["completed_at"] is not None
                    else None
                ),
            }
            for row in rows
        ]
