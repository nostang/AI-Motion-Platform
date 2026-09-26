import pytest

from src.poc_isolation import validate_poc_resource_isolation


def test_local_resources_are_allowed():
    validate_poc_resource_isolation(
        {
            "POC_RESOURCE_ISOLATION": "true",
            "DATABASE_URL": "postgresql://localhost/ai_motion_poc",
            "VIDEO_UPLOAD_BUCKET": "ai-motion-poc-video-temp",
            "KEYFRAME_ASSET_BUCKET": "ai-motion-poc-evidence",
            "AI_MOTION_TASK_QUEUE": "ai-motion-poc-analysis",
        }
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("VIDEO_UPLOAD_BUCKET", "ai-motion-platform-ivesmi-video-temp"),
        ("KEYFRAME_ASSET_BUCKET", "ai-motion-platform-ivesmi-video-temp"),
        (
            "DATABASE_URL",
            "postgresql://user@/ai_motion?host=/cloudsql/"
            "ai-motion-platform-ivesmi:asia-east1:ai-motion-db",
        ),
        ("AI_MOTION_TASK_QUEUE", "ai-motion-analysis"),
    ],
)
def test_product_resource_is_rejected(name, value):
    with pytest.raises(RuntimeError, match="隔離保護"):
        validate_poc_resource_isolation(
            {
                "POC_RESOURCE_ISOLATION": "true",
                "DATABASE_URL": "postgresql://localhost/ai_motion_poc",
                name: value,
            }
        )


def test_isolation_cannot_be_disabled():
    with pytest.raises(RuntimeError, match="不可停用"):
        validate_poc_resource_isolation(
            {
                "POC_RESOURCE_ISOLATION": "false",
                "DATABASE_URL": "postgresql://localhost/ai_motion_poc",
            }
        )
