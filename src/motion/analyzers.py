"""目前已支援動作的 Analyzer Adapter。"""

from __future__ import annotations
from typing import Any
from src.motion.base import BaseMotionAnalyzer, MotionContext


class FootworkAnalyzer(BaseMotionAnalyzer):
    motion_type = "footwork"

    def run(self, context: MotionContext) -> dict[str, Any]:
        from src.pose_demo import run_pose_demo
        return run_pose_demo(
            video_path=context.video_path,
            model_path=context.model_path,
            window_name=context.window_name,
            display=context.display,
            output_dir=context.output_dir,
            start_ms=context.start_ms,
            end_ms=context.end_ms,
        )


class ServeAnalyzer(BaseMotionAnalyzer):
    motion_type = "serve"

    def run(self, context: MotionContext) -> dict[str, Any]:
        from src.serve_demo import run_serve_demo
        return run_serve_demo(
            video_id=context.video_id,
            video_path=context.video_path,
            model_path=context.model_path,
            window_name=context.window_name,
            display=context.display,
            output_dir=context.output_dir,
            start_ms=context.start_ms,
            end_ms=context.end_ms,
        )


class ClearAnalyzer(BaseMotionAnalyzer):
    motion_type = "clear"

    def run(self, context: MotionContext) -> dict[str, Any]:
        from src.clear_demo import run_clear_demo
        return run_clear_demo(
            video_id=context.video_id,
            video_path=context.video_path,
            model_path=context.model_path,
            window_name=context.window_name,
            display=context.display,
            output_dir=context.output_dir,
            start_ms=context.start_ms,
            end_ms=context.end_ms,
        )
