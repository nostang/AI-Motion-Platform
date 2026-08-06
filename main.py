"""AI Motion PoC 主程式入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import (
    DEFAULT_VIDEO_ID,
    MODEL_PATH,
    PROJECT_ROOT,
    WINDOW_NAME,
)
from src.pipeline import run_motion_analysis


VIDEO_PREFIX_TO_DATASET = {
    "FW": "footwork",
    "SV": "serve",
    "CL": "clear",
    "SM": "smash",
}


def parse_args() -> argparse.Namespace:
    """解析命令列參數。"""

    parser = argparse.ArgumentParser(
        description="執行 AI Motion Dataset 影片分析。"
    )
    parser.add_argument(
        "--video",
        default=DEFAULT_VIDEO_ID,
        help=f"Dataset Video ID，預設為 {DEFAULT_VIDEO_ID}",
    )
    return parser.parse_args()


def get_video_path(video_id: str) -> Path:
    """依 Dataset Video ID 取得影片路徑。"""

    normalized_id = video_id.strip().upper()
    parts = normalized_id.split("_", maxsplit=1)

    if len(parts) != 2 or not parts[1]:
        raise ValueError(
            f"影片 ID 格式錯誤：{video_id!r}。"
            "請使用 FW_001、SV_001、CL_001 或 SM_001 這類格式。"
        )

    prefix = parts[0]
    dataset_folder = VIDEO_PREFIX_TO_DATASET.get(prefix)

    if dataset_folder is None:
        supported = ", ".join(VIDEO_PREFIX_TO_DATASET)
        raise ValueError(
            f"不支援的影片前綴：{prefix}。支援前綴：{supported}。"
        )

    video_path = (
        PROJECT_ROOT
        / "dataset"
        / dataset_folder
        / "videos"
        / f"{normalized_id}.mov"
    )

    if not video_path.is_file():
        raise FileNotFoundError(
            f"找不到 Dataset 影片：{video_path}\n"
            f"請確認影片 ID 為 {normalized_id}，並將影片放在：\n"
            f"{PROJECT_ROOT / 'dataset' / dataset_folder / 'videos'}"
        )

    return video_path


def main() -> None:
    """啟動 AI Motion 人體姿態 Demo。"""

    args = parse_args()
    video_path = get_video_path(args.video)

    print("啟動 AI Motion Pose Demo...")
    print(f"影片 ID：{args.video.strip().upper()}")
    print(f"影片：{video_path}")
    print(f"模型：{MODEL_PATH}")

    run_motion_analysis(
        video_id=args.video.strip().upper(),
        video_path=video_path,
        model_path=MODEL_PATH,
        window_name=WINDOW_NAME,
    )


if __name__ == "__main__":
    main()
