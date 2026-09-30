"""Fail-closed protection against reusing Badminton Plus One production resources."""

from __future__ import annotations

from collections.abc import Mapping


PRODUCTION_RESOURCE_MARKERS = (
    "ai-motion-platform-ivesmi-video-temp",
    "ai-motion-platform-ivesmi:asia-east1:ai-motion-db",
    "/cloudsql/ai-motion-platform-ivesmi:asia-east1:ai-motion-db",
)
PRODUCTION_QUEUE_NAME = "ai-motion-analysis"


def validate_poc_resource_isolation(environ: Mapping[str, str]) -> None:
    """Reject configuration that points this PoC at the product's resources."""

    enabled = environ.get("POC_RESOURCE_ISOLATION", "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        raise RuntimeError(
            "POC_RESOURCE_ISOLATION 不可停用；AI_Motion_PoC 必須保持獨立。"
        )

    billing_mode = environ.get(
        "AI_MOTION_BILLING_MODE",
        "free",
    ).strip().lower()
    if billing_mode != "free":
        raise RuntimeError(
            "AI_MOTION_BILLING_MODE 必須為 free；"
            "獨立 AI_Motion_PoC 不可使用羽球＋1 Goo 點數。"
        )

    collisions: list[str] = []
    guarded_values = {
        "DATABASE_URL": environ.get("DATABASE_URL", ""),
        "INSTANCE_CONNECTION_NAME": environ.get("INSTANCE_CONNECTION_NAME", ""),
        "VIDEO_UPLOAD_BUCKET": environ.get("VIDEO_UPLOAD_BUCKET", ""),
        "KEYFRAME_ASSET_BUCKET": environ.get("KEYFRAME_ASSET_BUCKET", ""),
    }
    for name, value in guarded_values.items():
        if any(marker in value for marker in PRODUCTION_RESOURCE_MARKERS):
            collisions.append(name)

    if environ.get("AI_MOTION_TASK_QUEUE", "").strip() == PRODUCTION_QUEUE_NAME:
        collisions.append("AI_MOTION_TASK_QUEUE")

    if collisions:
        names = ", ".join(sorted(set(collisions)))
        raise RuntimeError(
            "AI_Motion_PoC 隔離保護已阻擋羽球＋1正式資源："
            f"{names}。請建立 PoC 專用資料庫、bucket 與 queue。"
        )
