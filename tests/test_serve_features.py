from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.features.serve_features import (
    ServeFeatureTracker,
)


def landmarks(
    right_wrist_x: float,
    right_wrist_y: float,
    *,
    left_wrist_x: float = 0.35,
    left_wrist_y: float = 0.50,
):
    points = [
        SimpleNamespace(x=0.5, y=0.5)
        for _ in range(33)
    ]

    points[11] = SimpleNamespace(x=0.42, y=0.30)
    points[12] = SimpleNamespace(x=0.58, y=0.30)
    points[23] = SimpleNamespace(x=0.45, y=0.60)
    points[24] = SimpleNamespace(x=0.55, y=0.60)
    points[15] = SimpleNamespace(
        x=left_wrist_x,
        y=left_wrist_y,
    )
    points[16] = SimpleNamespace(
        x=right_wrist_x,
        y=right_wrist_y,
    )

    return points


def build_features(
    positions: list[tuple[float, float]],
    *,
    frame_ms: int = 33,
):
    tracker = ServeFeatureTracker()

    for index, (x, y) in enumerate(positions):
        tracker.observe(
            landmarks(x, y),
            index * frame_ms,
        )

    return tracker.build()


def serve_motion() -> list[tuple[float, float]]:
    # 單次連續揮拍：準備 → 加速 → 擊球 → 隨揮。
    return [
        (0.60, 0.48),
        (0.60, 0.48),
        (0.60, 0.48),
        (0.61, 0.47),
        (0.63, 0.45),
        (0.67, 0.41),
        (0.73, 0.36),
        (0.80, 0.32),
        (0.86, 0.31),
        (0.90, 0.34),
        (0.91, 0.39),
        (0.89, 0.44),
        (0.85, 0.48),
        (0.82, 0.50),
        (0.82, 0.50),
        (0.82, 0.50),
    ]


class ServeFeatureTests(unittest.TestCase):
    def test_extracts_features(self) -> None:
        result = build_features(serve_motion())

        self.assertEqual(
            result["status"],
            "EXTRACTED",
        )
        self.assertGreater(
            result["swing_path_length"],
            0,
        )
        self.assertIsNotNone(
            result["wrist_speed_variation"],
        )

    def test_static_padding_does_not_change_smoothness(
        self,
    ) -> None:
        motion = serve_motion()

        baseline = build_features(motion)

        padded = build_features(
            [motion[0]] * 20
            + motion
            + [motion[-1]] * 20
        )

        self.assertAlmostEqual(
            baseline["wrist_speed_variation"],
            padded["wrist_speed_variation"],
            delta=0.05,
        )

    def test_replay_does_not_double_swing_path(
        self,
    ) -> None:
        motion = serve_motion()

        single = build_features(motion)

        replay = build_features(
            motion
            + [motion[-1]] * 10
            + motion
        )

        self.assertLessEqual(
            replay["swing_path_length"],
            single["swing_path_length"] * 1.20,
        )

    def test_uniform_slowdown_preserves_smoothness(
        self,
    ) -> None:
        motion = serve_motion()

        normal = build_features(
            motion,
            frame_ms=33,
        )
        slow = build_features(
            motion,
            frame_ms=99,
        )

        self.assertAlmostEqual(
            normal["wrist_speed_variation"],
            slow["wrist_speed_variation"],
            delta=0.01,
        )

    def test_reports_single_analysis_window(
        self,
    ) -> None:
        # 前後提供足夠的靜止樣本，讓完整影片長度
        # 大於正式窗口最低要求 1.5 秒。
        result = build_features(
            [serve_motion()[0]] * 25
            + serve_motion()
            + [serve_motion()[-1]] * 25
        )

        window = result["analysis_window"]

        self.assertEqual(
            window["status"],
            "DETECTED",
        )
        self.assertEqual(
            window["completeness_status"],
            "COMPLETE",
        )
        self.assertGreaterEqual(
            window["duration_ms"],
            window["minimum_required_ms"],
        )
        self.assertLess(
            window["sample_count"],
            result["sample_count"],
        )
        self.assertIn(
            result["active_side_estimate"],
            ("left", "right"),
        )


    def test_automatic_side_is_used_without_annotation(
        self,
    ) -> None:
        tracker = ServeFeatureTracker()

        for index, (left_x, left_y) in enumerate(
            serve_motion()
        ):
            tracker.observe(
                landmarks(
                    0.60,
                    0.48,
                    left_wrist_x=left_x,
                    left_wrist_y=left_y,
                ),
                index * 100,
            )

        result = tracker.build()

        self.assertEqual(
            result["active_side_estimate"],
            "left",
        )
        self.assertEqual(
            result["dominant_hand"]["estimated"],
            "left",
        )
        self.assertEqual(
            result["dominant_hand"]["status"],
            "ESTIMATED",
        )

    def test_human_racket_side_overrides_automatic_side(
        self,
    ) -> None:
        tracker = ServeFeatureTracker(
            racket_side="right",
        )

        for index, (left_x, left_y) in enumerate(
            serve_motion()
        ):
            tracker.observe(
                landmarks(
                    0.60,
                    0.48,
                    left_wrist_x=left_x,
                    left_wrist_y=left_y,
                ),
                index * 100,
            )

        result = tracker.build()
        hand = result["dominant_hand"]

        self.assertEqual(
            result["active_side_estimate"],
            "right",
        )
        self.assertEqual(
            hand["estimated"],
            "right",
        )
        self.assertEqual(
            hand["status"],
            "HUMAN_CONFIRMED",
        )
        self.assertEqual(
            hand["source"],
            "HUMAN_ANNOTATION",
        )
        self.assertEqual(
            hand["confidence"],
            1.0,
        )
        self.assertEqual(
            hand["automatic_estimate"]["estimated"],
            "left",
        )

    def test_visualization_frame_mapping_does_not_change_features(self) -> None:
        baseline = ServeFeatureTracker()
        mapped = ServeFeatureTracker()

        for index, (x, y) in enumerate(serve_motion()):
            pose = landmarks(x, y)
            baseline.observe(pose, index * 33)
            mapped.observe(
                pose,
                index * 33,
                analysis_frame_index=index,
                source_frame_index=index + 120,
            )

        self.assertEqual(mapped.build(), baseline.build())
        self.assertEqual(mapped.samples[0]["analysis_frame_index"], 0)
        self.assertEqual(mapped.samples[0]["source_frame_index"], 120)
        for name in (
            "nose",
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
            "left_hip",
            "right_hip",
            "left_knee",
            "right_knee",
            "left_ankle",
            "right_ankle",
        ):
            self.assertIn(f"{name}_x", mapped.samples[0])
            self.assertIn(f"{name}_y", mapped.samples[0])

if __name__ == "__main__":
    unittest.main()
