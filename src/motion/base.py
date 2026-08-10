"""共用 Motion Analyzer 契約。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MotionContext:
    """所有動作分析器共用的執行資訊。"""

    video_id: str
    video_path: Path
    model_path: Path
    window_name: str
    display: bool = True
    output_dir: Path | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    annotation_source: str | None = None


class BaseMotionAnalyzer(ABC):
    """動作分析器最小介面。

    各動作可以保留自己的 Event、Feature、Assessment、Coach 與 Report，
    但入口統一由 ``run`` 接收 MotionContext。
    """

    motion_type: str

    @abstractmethod
    def run(self, context: MotionContext) -> dict[str, Any]:
        """執行完整分析流程並回傳結構化結果。"""
