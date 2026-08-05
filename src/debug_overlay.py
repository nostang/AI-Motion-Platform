"""
Footwork Event Debug Overlay V2

用途：
1. 顯示目前 Event 與 State
2. 顯示原始／平滑中心距離與骨盆速度
3. 顯示方向反轉確認進度與 Reach Event
4. 顯示最近幾次 State Transition
"""

from collections import deque
from dataclasses import dataclass

import cv2


@dataclass
class StateTransition:
    """一次 Footwork State 切換紀錄。"""

    previous_state: str
    current_state: str
    timestamp_ms: int
    frame_index: int


class FootworkDebugOverlay:
    """管理 Footwork Event 的除錯資訊與畫面呈現。"""

    def __init__(self, history_size: int = 6) -> None:
        self.history: deque[StateTransition] = deque(
            maxlen=history_size
        )

    def record_transition(
        self,
        *,
        previous_state: str,
        current_state: str,
        timestamp_ms: int,
        frame_index: int,
    ) -> None:
        """紀錄一次 State Transition。"""

        self.history.append(
            StateTransition(
                previous_state=previous_state,
                current_state=current_state,
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
            )
        )

    def draw(
        self,
        frame,
        *,
        event_id: int,
        current_state: str,
        frame_index: int,
        timestamp_ms: int,
        center_offset: float | None,
        smoothed_center_offset: float | None,
        pelvis_speed: float | None,
        maximum_center_offset: float,
        reversal_candidate_frames: int,
        reach_frame: int | None,
        reach_timestamp_ms: int | None,
        direction: str | None,
        direction_angle_degrees: float | None,
    ) -> None:
        """在影片右側繪製 Footwork Event V2 除錯面板。"""

        height, width = frame.shape[:2]
        panel_width = min(460, max(340, width // 4))
        panel_x = width - panel_width

        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (panel_x, 0),
            (width, height),
            (0, 0, 0),
            -1,
        )
        cv2.addWeighted(
            overlay,
            0.58,
            frame,
            0.42,
            0,
            frame,
        )

        state_color = self._get_state_color(current_state)
        x = panel_x + 18
        y = 42

        self._put_text(frame, "FOOTWORK DEBUG V2", x, y, scale=0.75)
        y += 40
        self._put_text(frame, f"Event ID: {event_id}", x, y)
        y += 34

        cv2.putText(
            frame,
            f"STATE: {current_state}",
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.78,
            state_color,
            2,
            cv2.LINE_AA,
        )
        y += 38

        self._put_text(frame, f"Frame: {frame_index}", x, y)
        y += 30
        self._put_text(
            frame,
            f"Time: {timestamp_ms / 1000:.2f} sec",
            x,
            y,
        )
        y += 34

        raw_offset_text = (
            "--" if center_offset is None else f"{center_offset:.4f}"
        )
        smooth_offset_text = (
            "--"
            if smoothed_center_offset is None
            else f"{smoothed_center_offset:.4f}"
        )
        speed_text = (
            "--" if pelvis_speed is None else f"{pelvis_speed:.4f}"
        )

        self._put_text(frame, f"Raw Offset: {raw_offset_text}", x, y)
        y += 30
        self._put_text(
            frame,
            f"Smooth Offset: {smooth_offset_text}",
            x,
            y,
        )
        y += 30
        self._put_text(frame, f"Pelvis Speed: {speed_text}", x, y)
        y += 30
        self._put_text(
            frame,
            f"Max Offset: {maximum_center_offset:.4f}",
            x,
            y,
        )
        y += 30
        self._put_text(
            frame,
            f"Reversal Confirm: {reversal_candidate_frames}",
            x,
            y,
        )
        y += 36

        if reach_frame is None or reach_timestamp_ms is None:
            reach_text = "Reach Event: --"
        else:
            reach_text = (
                f"Reach Event: F{reach_frame} / "
                f"{reach_timestamp_ms / 1000:.2f}s"
            )

        self._put_text(frame, reach_text, x, y, scale=0.56)
        y += 30

        direction_text = direction or "--"
        self._put_text(
            frame,
            f"Direction: {direction_text}",
            x,
            y,
            scale=0.58,
        )
        y += 28

        angle_text = (
            "--"
            if direction_angle_degrees is None
            else f"{direction_angle_degrees:.1f} deg"
        )
        self._put_text(
            frame,
            f"Direction Angle: {angle_text}",
            x,
            y,
            scale=0.54,
        )

        y += 38
        self._put_text(frame, "STATE HISTORY", x, y, scale=0.68)
        y += 31

        if not self.history:
            self._put_text(
                frame,
                "No transition yet",
                x,
                y,
                scale=0.52,
            )
            return

        for transition in reversed(self.history):
            history_text = (
                f"{transition.previous_state} -> "
                f"{transition.current_state}  "
                f"{transition.timestamp_ms / 1000:.2f}s"
            )
            self._put_text(
                frame,
                history_text,
                x,
                y,
                scale=0.49,
            )
            y += 27

    @staticmethod
    def _put_text(
        frame,
        text: str,
        x: int,
        y: int,
        *,
        scale: float = 0.62,
    ) -> None:
        cv2.putText(
            frame,
            text,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    @staticmethod
    def _get_state_color(state: str) -> tuple[int, int, int]:
        state_colors = {
            "CALIBRATING": (0, 255, 255),
            "READY": (0, 255, 0),
            "MOVE": (255, 255, 0),
            "RECOVER": (255, 0, 255),
        }
        return state_colors.get(state, (255, 255, 255))
