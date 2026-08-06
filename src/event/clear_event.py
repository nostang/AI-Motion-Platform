"""高遠球教學動作 MVP Event Contract。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClearPhase:
    phase_id: str
    phase_name: str
    start_frame: int
    end_frame: int
    start_ms: int
    end_ms: int
    completed: bool

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.end_ms - self.start_ms) / 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "phase_name": self.phase_name,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_seconds": round(self.duration_seconds, 3),
            "completed": self.completed,
        }


@dataclass(frozen=True)
class ClearEvent:
    event_id: int
    start_frame: int
    end_frame: int
    start_ms: int
    end_ms: int
    completed: bool
    phases: tuple[ClearPhase, ...] = field(default_factory=tuple)

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.end_ms - self.start_ms) / 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": "high_clear_teaching_motion",
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_seconds": round(self.duration_seconds, 3),
            "completed": self.completed,
            "phases": [phase.to_dict() for phase in self.phases],
        }


def build_clear_event(
    *,
    first_detected_frame: int | None,
    last_detected_frame: int | None,
    total_frames: int,
    detected_frames: int,
    fps: float,
    minimum_detected_frames: int = 12,
) -> ClearEvent:
    safe_fps = fps if fps > 0 else 30.0

    start_frame = (
        first_detected_frame
        if first_detected_frame is not None
        else 0
    )
    end_frame = (
        last_detected_frame
        if last_detected_frame is not None
        else max(0, total_frames - 1)
    )

    completed = (
        detected_frames >= minimum_detected_frames
        and end_frame > start_frame
    )

    return ClearEvent(
        event_id=1,
        start_frame=start_frame,
        end_frame=end_frame,
        start_ms=int(start_frame * 1000 / safe_fps),
        end_ms=int(end_frame * 1000 / safe_fps),
        completed=completed,
        phases=(),
    )
