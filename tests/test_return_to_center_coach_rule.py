from __future__ import annotations

import unittest

from src.coach.coach_rules import (
    evaluate_return_to_center,
)


class ReturnToCenterCoachRuleTests(unittest.TestCase):
    @staticmethod
    def assessment(events):
        return {
            "expected_event_count": 8,
            "event_count": len(events),
            "all_events_returned_to_center": all(
                event.get("returned_to_center", False)
                for event in events
            ),
            "base_zone_completion_count": sum(
                event.get("completion_reason") == "BASE_ZONE"
                for event in events
            ),
            "events": events,
        }

    @staticmethod
    def strict_event():
        return {
            "completed": True,
            "returned_to_center": True,
            "completion_reason": "STRICT_CENTER",
        }

    @staticmethod
    def base_event():
        return {
            "completed": True,
            "returned_to_center": False,
            "completion_reason": "BASE_ZONE",
        }

    def test_all_strict_center_returns_pass(self):
        result = evaluate_return_to_center(
            self.assessment([
                self.strict_event()
                for _ in range(8)
            ])
        )

        self.assertEqual(result["result"], "PASS")
        self.assertEqual(
            result["evidence"]["strict_center_count"],
            8,
        )
        self.assertEqual(
            result["evidence"]["base_zone_count"],
            0,
        )

    def test_base_zone_returns_need_review(self):
        result = evaluate_return_to_center(
            self.assessment(
                [
                    self.strict_event()
                    for _ in range(6)
                ]
                + [
                    self.base_event()
                    for _ in range(2)
                ]
            )
        )

        self.assertEqual(
            result["result"],
            "NEEDS_REVIEW",
        )
        self.assertEqual(
            result["evidence"]["strict_center_count"],
            6,
        )
        self.assertEqual(
            result["evidence"]["base_zone_count"],
            2,
        )
        self.assertEqual(
            result["evidence"]["incomplete_event_count"],
            0,
        )

    def test_genuinely_incomplete_return_fails(self):
        incomplete = {
            "completed": False,
            "returned_to_center": False,
            "completion_reason": None,
        }

        result = evaluate_return_to_center(
            self.assessment(
                [
                    self.strict_event()
                    for _ in range(7)
                ]
                + [incomplete]
            )
        )

        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(
            result["evidence"]["incomplete_event_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
