"""Serve MVP 將單支影片視為一個完整發球事件。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServeEvent:
    event_id: int
    start_frame: int
    end_frame: int
    start_ms: int
    end_ms: int
    completed: bool

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.end_ms - self.start_ms) / 1000.0)
