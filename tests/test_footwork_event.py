from __future__ import annotations

import unittest

from src.event.footwork_event import (
    FootworkEvent,
    FootworkState,
)


class FootworkEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = FootworkEvent(
            move_offset_threshold=0.08,
            return_offset_threshold=0.05,
            base_zone_offset_threshold=0.08,
            smoothing_window=1,
            reversal_confirm_frames=2,
            reversal_min_drop=0.012,
            ready_confirm_frames=2,
            base_transition_confirm_frames=2,
        )
        self.frame = 0

    def update(self, offset: float) -> FootworkState:
        self.frame += 1
        return self.event.update(
            center_calibrated=True,
            center_offset=offset,
            current_position=(offset, 0.0),
            timestamp_ms=self.frame * 100,
            frame_index=self.frame,
        )

    def enter_ready(self) -> None:
        self.update(0.0)
        self.update(0.0)

        self.assertEqual(
            self.event.state,
            FootworkState.READY,
        )

    def create_reach(self) -> None:
        self.update(0.09)
        self.update(0.20)
        self.update(0.17)
        self.update(0.14)

        self.assertEqual(
            self.event.state,
            FootworkState.RECOVER,
        )
        self.assertTrue(
            self.event.reach_detected_this_frame,
        )

    def enter_base_then_move_outward(self) -> None:
        # 只是進入 Base Zone，不能提早結束 Event。
        self.update(0.08)
        self.update(0.075)

        self.assertFalse(
            self.event.completed_this_frame,
        )

        # 再次往外移動，才確認 Base Zone Transition。
        self.update(0.09)
        self.update(0.11)

        self.assertTrue(
            self.event.completed_this_frame,
        )

    def test_strict_center_completes_full_return(self) -> None:
        self.enter_ready()
        self.create_reach()

        self.update(0.04)
        self.update(0.04)

        self.assertTrue(
            self.event.completed_this_frame,
        )
        self.assertEqual(
            self.event.completion_reason,
            "STRICT_CENTER",
        )
        self.assertIsNotNone(
            self.event.returned_at_ms,
        )
        self.assertIsNotNone(
            self.event.get_recovery_time_seconds(),
        )

    def test_base_zone_completes_without_full_return(self) -> None:
        self.enter_ready()
        self.create_reach()
        self.enter_base_then_move_outward()

        self.assertEqual(
            self.event.completion_reason,
            "BASE_ZONE",
        )
        self.assertIsNone(
            self.event.returned_at_ms,
        )
        self.assertIsNone(
            self.event.get_recovery_time_seconds(),
        )
        self.assertEqual(
            self.event.state,
            FootworkState.READY,
        )

    def test_new_event_can_start_after_base_zone(self) -> None:
        self.enter_ready()
        self.create_reach()
        self.enter_base_then_move_outward()

        self.assertEqual(self.event.event_id, 1)

        self.update(0.13)

        self.assertEqual(self.event.event_id, 2)
        self.assertEqual(
            self.event.state,
            FootworkState.MOVE,
        )


if __name__ == "__main__":
    unittest.main()
