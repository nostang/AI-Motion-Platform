"""
AI Motion PoC 主程式入口。
"""

from src.config import (
    MODEL_PATH,
    VIDEO_PATH,
    WINDOW_NAME,
)
from src.pose_demo import run_pose_demo


def main() -> None:
    """
    啟動 AI Motion 人體姿態 Demo。
    """

    print("啟動 AI Motion Pose Demo...")
    print(f"影片：{VIDEO_PATH}")
    print(f"模型：{MODEL_PATH}")

    run_pose_demo(
        video_path=VIDEO_PATH,
        model_path=MODEL_PATH,
        window_name=WINDOW_NAME,
    )


if __name__ == "__main__":
    main()