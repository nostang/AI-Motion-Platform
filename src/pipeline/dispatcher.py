"""依 Dataset 影片 ID 分派至對應 Motion Analyzer。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from src.motion import MotionContext, get_motion_analyzer


class MotionType(str, Enum):
    FOOTWORK = "footwork"
    SERVE = "serve"
    CLEAR = "clear"
    SMASH = "smash"


_PREFIX_TO_MOTION = {
    "FW": MotionType.FOOTWORK,
    "SV": MotionType.SERVE,
    "CL": MotionType.CLEAR,
    "SM": MotionType.SMASH,
}


def detect_motion_type(video_id: str) -> MotionType:
    """由 Dataset ID 前綴判斷動作種類。"""

    prefix = video_id.strip().upper().split("_", maxsplit=1)[0]
    try:
        return _PREFIX_TO_MOTION[prefix]
    except KeyError as exc:
        supported = ", ".join(sorted(_PREFIX_TO_MOTION))
        raise ValueError(
            f"不支援的影片前綴：{prefix!r}。支援前綴：{supported}。"
        ) from exc


def run_motion_analysis(
    *,
    video_id: str,
    video_path: Path,
    model_path: Path,
    window_name: str,
    display: bool = True,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """透過 Registry 執行對應動作分析。"""

    normalized_video_id = video_id.strip().upper()
    motion_type = detect_motion_type(normalized_video_id)
    analyzer = get_motion_analyzer(motion_type.value)

    context = MotionContext(
        video_id=normalized_video_id,
        video_path=Path(video_path),
        model_path=Path(model_path),
        window_name=(
            window_name
            if motion_type is MotionType.FOOTWORK
            else f"AI Motion - {motion_type.value.title()} Demo"
        ),
        display=display,
        output_dir=output_dir,
    )
    return analyzer.run(context)
