"""Motion Analyzer Registry。"""

from __future__ import annotations

from src.motion.analyzers import FootworkAnalyzer, ServeAnalyzer
from src.motion.base import BaseMotionAnalyzer
from src.motion.analyzers import (
    FootworkAnalyzer,
    ServeAnalyzer,
    ClearAnalyzer,
)


_ANALYZERS: dict[str, BaseMotionAnalyzer] = {
    "footwork": FootworkAnalyzer(),
    "serve": ServeAnalyzer(),
    "clear": ClearAnalyzer(),
}


def get_motion_analyzer(motion_type: str) -> BaseMotionAnalyzer:
    """取得指定動作分析器；未完成模組會清楚拒絕執行。"""

    normalized = motion_type.strip().lower()
    try:
        return _ANALYZERS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(_ANALYZERS))
        raise NotImplementedError(
            f"{normalized} 分析器尚未完成。目前可執行：{supported}。"
        ) from exc


def registered_motion_types() -> tuple[str, ...]:
    return tuple(sorted(_ANALYZERS))
