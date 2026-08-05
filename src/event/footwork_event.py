"""
Footwork Event State Machine V2

專業概念簡化版：

1. Center Offset 訊號平滑
2. Hysteresis 遲滯區間
3. Direction Reversal 方向反轉偵測
4. READY Debounce 防抖
5. Reach 作為瞬間 Event，而不是 State

狀態流程：

CALIBRATING
→ READY
→ MOVE
→ RECOVER
→ READY
"""

from collections import deque
from enum import Enum


class FootworkState(str, Enum):
    """米字步主要狀態。"""

    CALIBRATING = "CALIBRATING"
    READY = "READY"
    MOVE = "MOVE"
    RECOVER = "RECOVER"


class FootworkEvent:
    """
    管理一次米字步事件。

    REACH 不再是 State。

    系統在 MOVE 期間持續記錄最遠 Center Offset，
    當距離連續縮短時，將最遠位置記錄為 Reach Event，
    並由 MOVE 切換為 RECOVER。
    """

    def __init__(
        self,
        *,
        move_offset_threshold: float,
        return_offset_threshold: float,
        smoothing_window: int,
        reversal_confirm_frames: int,
        reversal_min_drop: float,
        ready_confirm_frames: int,
    ) -> None:
        """
        建立 Footwork Event V2。

        Parameters
        ----------
        move_offset_threshold:
            離開中心多少距離後開始 MOVE。

        return_offset_threshold:
            回到多少距離內才視為返回中心。

        smoothing_window:
            Center Offset 移動平均視窗大小。

        reversal_confirm_frames:
            距離需連續縮短多少幀才確認方向反轉。

        reversal_min_drop:
            距離相較最遠點至少縮短多少才算有效反轉。

        ready_confirm_frames:
            回到中心後需穩定多少幀才恢復 READY。
        """

        if return_offset_threshold >= move_offset_threshold:
            raise ValueError(
                "return_offset_threshold 必須小於 "
                "move_offset_threshold，才能形成 Hysteresis。"
            )

        self.move_offset_threshold = (
            move_offset_threshold
        )

        self.return_offset_threshold = (
            return_offset_threshold
        )

        self.smoothing_window = max(
            1,
            smoothing_window,
        )

        self.reversal_confirm_frames = max(
            1,
            reversal_confirm_frames,
        )

        self.reversal_min_drop = max(
            0.0,
            reversal_min_drop,
        )

        self.ready_confirm_frames = max(
            1,
            ready_confirm_frames,
        )

        self.offset_history: deque[float] = deque(
            maxlen=self.smoothing_window
        )

        self.state = FootworkState.CALIBRATING
        self.previous_state = (
            FootworkState.CALIBRATING
        )

        self.event_id = 0

        # Event 時間
        self.move_started_at_ms: int | None = None
        self.reach_at_ms: int | None = None
        self.recover_started_at_ms: int | None = None
        self.returned_at_ms: int | None = None

        # Event Frame
        self.move_started_frame: int | None = None
        self.reach_frame: int | None = None
        self.recover_started_frame: int | None = None
        self.returned_frame: int | None = None

        # Offset 資料
        self.smoothed_center_offset: float | None = None
        self.previous_smoothed_offset: float | None = None
        self.maximum_center_offset = 0.0

        self.maximum_offset_frame: int | None = None
        self.maximum_offset_timestamp_ms: int | None = None
        self.maximum_offset_position: tuple[float, float] | None = None

        # Reach Event 與方向分類結果
        self.reach_position: tuple[float, float] | None = None
        self.direction: str | None = None
        self.direction_angle_degrees: float | None = None
        self.direction_confidence: float | None = None
        self.direction_vector_length: float | None = None

        # 防抖與趨勢確認
        self.reversal_candidate_frames = 0
        self.ready_stable_frames = 0
        self.can_start_next_event = False

        # Debug 用
        self.reach_detected_this_frame = False
        self.completed_this_frame = False

    def update(
        self,
        *,
        center_calibrated: bool,
        center_offset: float | None,
        current_position: tuple[float, float] | None,
        timestamp_ms: int,
        frame_index: int,
    ) -> FootworkState:
        """
        根據目前 Center Offset 與骨盆位置更新狀態。

        每一幀呼叫一次。
        current_position 使用 MediaPipe 正規化骨盆中心座標。
        """

        self.previous_state = self.state
        self.reach_detected_this_frame = False
        self.completed_this_frame = False

        if not center_calibrated:
            self._reset_calibrating_state()
            return self.state

        if center_offset is None or current_position is None:
            return self.state

        self._update_smoothed_offset(
            center_offset
        )

        if self.smoothed_center_offset is None:
            return self.state

        if self.state == FootworkState.CALIBRATING:
            self._update_from_calibrating()

        elif self.state == FootworkState.READY:
            self._update_from_ready(
                current_position=current_position,
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
            )

        elif self.state == FootworkState.MOVE:
            self._update_from_move(
                current_position=current_position,
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
            )

        elif self.state == FootworkState.RECOVER:
            self._update_from_recover(
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
            )

        self.previous_smoothed_offset = (
            self.smoothed_center_offset
        )

        return self.state

    def _update_smoothed_offset(
        self,
        center_offset: float,
    ) -> None:
        """
        對 Center Offset 使用簡單移動平均。

        用來降低 MediaPipe Landmark 每幀抖動。
        """

        self.offset_history.append(
            center_offset
        )

        self.smoothed_center_offset = (
            sum(self.offset_history)
            / len(self.offset_history)
        )

    def _reset_calibrating_state(self) -> None:
        """
        中心尚未校正時維持 CALIBRATING。
        """

        self.state = FootworkState.CALIBRATING

        self.offset_history.clear()

        self.smoothed_center_offset = None
        self.previous_smoothed_offset = None

        self.ready_stable_frames = 0
        self.can_start_next_event = False

    def _update_from_calibrating(
        self,
    ) -> None:
        """
        CALIBRATING → READY

        校正完成後，需先在中心區穩定數幀。
        """

        if (
            self.smoothed_center_offset
            <= self.return_offset_threshold
        ):
            self.ready_stable_frames += 1
        else:
            self.ready_stable_frames = 0

        if (
            self.ready_stable_frames
            >= self.ready_confirm_frames
        ):
            self.state = FootworkState.READY
            self.can_start_next_event = True

    def _update_from_ready(
        self,
        *,
        current_position: tuple[float, float],
        timestamp_ms: int,
        frame_index: int,
    ) -> None:
        """
        READY → MOVE

        只有中心已穩定，且距離超過離開門檻，
        才允許建立新 Event。
        """

        if (
            self.smoothed_center_offset
            <= self.return_offset_threshold
        ):
            self.ready_stable_frames = min(
                self.ready_confirm_frames,
                self.ready_stable_frames + 1,
            )

            if (
                self.ready_stable_frames
                >= self.ready_confirm_frames
            ):
                self.can_start_next_event = True

            return

        if (
            self.can_start_next_event
            and self.smoothed_center_offset
            >= self.move_offset_threshold
        ):
            self._start_new_event(
                current_position=current_position,
                timestamp_ms=timestamp_ms,
                frame_index=frame_index,
            )

            self.state = FootworkState.MOVE

    def _update_from_move(
        self,
        *,
        current_position: tuple[float, float],
        timestamp_ms: int,
        frame_index: int,
    ) -> None:
        """
        MOVE → RECOVER

        MOVE 期間：

        1. 持續保存最遠 Center Offset。
        2. 若距離開始連續縮短，確認方向反轉。
        3. 最遠點被記錄為 Reach Event。
        4. 直接切換為 RECOVER。
        """

        current_offset = (
            self.smoothed_center_offset
        )

        if (
            current_offset
            > self.maximum_center_offset
        ):
            self.maximum_center_offset = (
                current_offset
            )

            self.maximum_offset_frame = (
                frame_index
            )

            self.maximum_offset_timestamp_ms = (
                timestamp_ms
            )

            self.maximum_offset_position = (
                current_position
            )

        distance_from_maximum = (
            self.maximum_center_offset
            - current_offset
        )

        offset_is_decreasing = False

        if self.previous_smoothed_offset is not None:
            offset_is_decreasing = (
                current_offset
                < self.previous_smoothed_offset
            )

        valid_reversal_drop = (
            distance_from_maximum
            >= self.reversal_min_drop
        )

        if (
            offset_is_decreasing
            and valid_reversal_drop
        ):
            self.reversal_candidate_frames += 1
        else:
            self.reversal_candidate_frames = 0

        if (
            self.reversal_candidate_frames
            >= self.reversal_confirm_frames
        ):
            self._record_reach_event()

            self.recover_started_at_ms = (
                timestamp_ms
            )

            self.recover_started_frame = (
                frame_index
            )

            self.state = FootworkState.RECOVER

    def _update_from_recover(
        self,
        *,
        timestamp_ms: int,
        frame_index: int,
    ) -> None:
        """
        RECOVER → READY

        進入回中心門檻後，需連續穩定數幀，
        才正式完成 Event。
        """

        if (
            self.smoothed_center_offset
            <= self.return_offset_threshold
        ):
            self.ready_stable_frames += 1
        else:
            self.ready_stable_frames = 0

        if (
            self.ready_stable_frames
            >= self.ready_confirm_frames
        ):
            self.returned_at_ms = timestamp_ms
            self.returned_frame = frame_index

            self.state = FootworkState.READY
            self.completed_this_frame = True

            # 必須重新在 READY 累積穩定度，
            # 才能開始下一個 Event。
            self.ready_stable_frames = 0
            self.can_start_next_event = False

    def _start_new_event(
        self,
        *,
        current_position: tuple[float, float],
        timestamp_ms: int,
        frame_index: int,
    ) -> None:
        """
        初始化一個新的 Footwork Event。
        """

        self.event_id += 1

        self.move_started_at_ms = timestamp_ms
        self.move_started_frame = frame_index

        self.reach_at_ms = None
        self.reach_frame = None
        self.reach_position = None
        self.direction = None
        self.direction_angle_degrees = None
        self.direction_confidence = None
        self.direction_vector_length = None

        self.recover_started_at_ms = None
        self.recover_started_frame = None

        self.returned_at_ms = None
        self.returned_frame = None

        self.maximum_center_offset = (
            self.smoothed_center_offset
            if self.smoothed_center_offset is not None
            else 0.0
        )

        self.maximum_offset_frame = frame_index
        self.maximum_offset_timestamp_ms = (
            timestamp_ms
        )
        self.maximum_offset_position = current_position

        self.reversal_candidate_frames = 0
        self.ready_stable_frames = 0
        self.can_start_next_event = False

    def _record_reach_event(
        self,
    ) -> None:
        """
        將 MOVE 期間記錄到的最遠點，
        保存為 Reach Event。
        """

        self.reach_at_ms = (
            self.maximum_offset_timestamp_ms
        )

        self.reach_frame = (
            self.maximum_offset_frame
        )

        self.reach_position = (
            self.maximum_offset_position
        )

        self.reach_detected_this_frame = True
        self.reversal_candidate_frames = 0


    def set_direction(
        self,
        *,
        direction: str,
        angle_degrees: float | None,
        confidence: float,
        vector_length: float,
    ) -> None:
        """保存 Motion Classification 的方向與信心結果。"""

        self.direction = direction
        self.direction_angle_degrees = angle_degrees
        self.direction_confidence = confidence
        self.direction_vector_length = vector_length

    def state_changed(self) -> bool:
        """判斷目前影格是否發生 State 切換。"""

        return self.state != self.previous_state

    def get_move_time_seconds(
        self,
    ) -> float | None:
        """
        MOVE 開始到 Reach Event 的時間。
        """

        if (
            self.move_started_at_ms is None
            or self.reach_at_ms is None
        ):
            return None

        return (
            self.reach_at_ms
            - self.move_started_at_ms
        ) / 1000.0

    def get_recovery_time_seconds(
        self,
    ) -> float | None:
        """
        Reach Event 到正式返回中心的時間。

        這比「確認反轉幀到中心」更接近實際回中心時間。
        """

        if (
            self.reach_at_ms is None
            or self.returned_at_ms is None
        ):
            return None

        return (
            self.returned_at_ms
            - self.reach_at_ms
        ) / 1000.0

    def get_total_time_seconds(
        self,
    ) -> float | None:
        """
        MOVE 開始到正式返回中心的總時間。
        """

        if (
            self.move_started_at_ms is None
            or self.returned_at_ms is None
        ):
            return None

        return (
            self.returned_at_ms
            - self.move_started_at_ms
        ) / 1000.0