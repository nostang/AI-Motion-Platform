from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.features.clear_features import ClearFeatureTracker
from src.visualization.clear_pose_visualization import (
    LANDMARK_NAMES,
    build_clear_pose_visualization,
)


def pose_sample(index: int, right_wrist_x: float) -> dict[str, float]:
    sample: dict[str, float] = {
        "timestamp_ms": float(index * 100),
        "analysis_frame_index": index,
        "source_frame_index": index + 100,
    }

    for landmark_index, name in enumerate(LANDMARK_NAMES):
        sample[f"{name}_x"] = landmark_index / 100.0
        sample[f"{name}_y"] = index / 100.0

    sample["right_wrist_x"] = right_wrist_x
    return sample


def pose_landmarks(
    right_wrist_x: float,
    *,
    nose_x: float,
    knee_x: float,
) -> list[SimpleNamespace]:
    points = [
        SimpleNamespace(x=0.5, y=0.5)
        for _ in range(33)
    ]
    points[0] = SimpleNamespace(x=nose_x, y=0.12)
    points[11] = SimpleNamespace(x=0.42, y=0.30)
    points[12] = SimpleNamespace(x=0.58, y=0.30)
    points[13] = SimpleNamespace(x=0.38, y=0.42)
    points[14] = SimpleNamespace(x=0.62, y=0.42)
    points[15] = SimpleNamespace(x=0.35, y=0.48)
    points[16] = SimpleNamespace(x=right_wrist_x, y=0.48)
    points[23] = SimpleNamespace(x=0.45, y=0.60)
    points[24] = SimpleNamespace(x=0.55, y=0.60)
    points[25] = SimpleNamespace(x=knee_x, y=0.75)
    points[26] = SimpleNamespace(x=knee_x + 0.10, y=0.75)
    points[27] = SimpleNamespace(x=0.44, y=0.92)
    points[28] = SimpleNamespace(x=0.56, y=0.92)
    return points


class ClearPoseVisualizationTests(unittest.TestCase):
    def test_builds_three_ordered_snapshots(self) -> None:
        wrist_positions = [0.50, 0.51, 0.52, 0.53, 0.83, 0.84, 0.85, 0.86]
        samples = [
            pose_sample(index, wrist_x)
            for index, wrist_x in enumerate(wrist_positions)
        ]

        result = build_clear_pose_visualization(
            samples,
            racket_side="right",
        )

        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            [snapshot["stage"] for snapshot in result["snapshots"]],
            ["preparation", "swing", "finish"],
        )
        self.assertEqual(
            [snapshot["label"] for snapshot in result["snapshots"]],
            ["準備姿勢", "揮拍階段", "動作完成"],
        )
        self.assertEqual(
            [snapshot["analysis_frame_index"] for snapshot in result["snapshots"]],
            [1, 4, 7],
        )
        self.assertEqual(
            [snapshot["source_frame_index"] for snapshot in result["snapshots"]],
            [101, 104, 107],
        )

    def test_swing_uses_peak_racket_side_wrist_speed(self) -> None:
        wrist_positions = [0.50, 0.90, 1.00, 1.01, 1.02, 1.03, 1.04, 1.05]
        samples = [
            pose_sample(index, wrist_x)
            for index, wrist_x in enumerate(wrist_positions)
        ]
        timestamps = [0, 1000, 1050, 1150, 1250, 1350, 1450, 1550]
        for sample, timestamp_ms in zip(samples, timestamps):
            sample["timestamp_ms"] = float(timestamp_ms)

        result = build_clear_pose_visualization(
            samples,
            racket_side="right",
        )

        swing = result["snapshots"][1]
        # 0.40 over 1 second is slower than 0.10 over 50 ms.
        self.assertEqual(swing["timestamp_ms"], 1050)
        self.assertEqual(swing["label"], "揮拍階段")

    def test_snapshot_landmark_schema(self) -> None:
        samples = [pose_sample(index, 0.5 + index * 0.01) for index in range(8)]

        result = build_clear_pose_visualization(
            samples,
            racket_side="right",
        )

        for snapshot in result["snapshots"]:
            self.assertEqual(
                tuple(snapshot["landmarks"]),
                LANDMARK_NAMES,
            )
            for coordinates in snapshot["landmarks"].values():
                self.assertEqual(set(coordinates), {"x", "y"})
                self.assertIsInstance(coordinates["x"], float)
                self.assertIsInstance(coordinates["y"], float)

    def test_insufficient_samples_are_not_ready(self) -> None:
        result = build_clear_pose_visualization(
            [pose_sample(index, 0.5) for index in range(4)],
            racket_side="right",
        )

        self.assertEqual(result["status"], "NOT_READY")
        self.assertEqual(result["reason"], "INSUFFICIENT_POSE_SAMPLES")
        self.assertEqual(result["snapshots"], [])

    def test_visualization_landmarks_do_not_change_scoring(self) -> None:
        baseline = ClearFeatureTracker(expected_racket_side="right")
        varied_visualization = ClearFeatureTracker(expected_racket_side="right")

        for index in range(12):
            wrist_x = 0.55 + index * 0.02
            baseline.observe(
                pose_landmarks(wrist_x, nose_x=0.50, knee_x=0.44),
                index * 100,
            )
            varied_visualization.observe(
                pose_landmarks(
                    wrist_x,
                    nose_x=0.10 + index * 0.03,
                    knee_x=0.20 + index * 0.02,
                ),
                index * 100,
                analysis_frame_index=index,
                source_frame_index=index + 20,
            )

        self.assertEqual(baseline.build(), varied_visualization.build())
        self.assertIn("nose_x", varied_visualization.samples[0])
        self.assertIn("left_knee_x", varied_visualization.samples[0])


if __name__ == "__main__":
    unittest.main()
