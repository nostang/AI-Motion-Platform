from __future__ import annotations

import copy
import math
import unittest
from xml.etree import ElementTree as ET

from src.visualization.clear_pose_renderer import (
    SVG_NAMESPACE,
    render_clear_pose_svg,
)
from src.visualization.clear_pose_visualization import LANDMARK_NAMES


def sample_artifact() -> dict:
    snapshots = []
    for index, (stage, label, focus) in enumerate(
        (
            ("preparation", "準備姿勢", "sideways_preparation"),
            ("swing", "揮拍階段", "swing_smoothness"),
            ("finish", "動作完成", "weight_transfer"),
        )
    ):
        landmarks = {
            name: {
                "x": 0.35 + landmark_index * 0.015 + index * 0.01,
                "y": 0.20 + landmark_index * 0.045,
            }
            for landmark_index, name in enumerate(LANDMARK_NAMES)
        }
        snapshots.append(
            {
                "stage": stage,
                "label": label,
                "timestamp_ms": (index + 1) * 1000,
                "focus": focus,
                "landmarks": landmarks,
            }
        )

    return {
        "status": "READY",
        "version": "clear-explainable-pose-v0.1",
        "motion_type": "clear",
        "racket_side": "right",
        "snapshots": snapshots,
    }


class ClearPoseRendererTests(unittest.TestCase):
    def test_ready_artifact_renders_three_ordered_stages(self) -> None:
        svg = render_clear_pose_svg(sample_artifact())

        self.assertIn("<svg", svg)
        positions = [
            svg.index(f'data-stage="{stage}"')
            for stage in ("preparation", "swing", "finish")
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("PREPARATION", svg)
        self.assertIn("SWING", svg)
        self.assertIn("FINISH", svg)
        self.assertEqual(svg.count("AI 觀察"), 3)
        self.assertNotIn("FEATURE FOCUS", svg)

    def test_racket_side_arm_has_highlight_class(self) -> None:
        svg = render_clear_pose_svg(sample_artifact())
        root = ET.fromstring(svg)
        highlighted = root.findall(
            f".//{{{SVG_NAMESPACE}}}line[@class='skeleton-line racket-side']"
        )

        self.assertEqual(len(highlighted), 6)
        self.assertTrue(
            all("right_" in line.attrib["data-connection"] for line in highlighted)
        )
        self.assertEqual(svg.count('class="racket-side-outline"'), 6)
        self.assertEqual(svg.count('class="racket-wrist-focus"'), 3)

    def test_all_valid_landmarks_are_rendered(self) -> None:
        artifact = sample_artifact()
        artifact["snapshots"][0]["landmarks"]["left_eye"] = {
            "x": 0.5,
            "y": 0.1,
        }

        svg = render_clear_pose_svg(artifact)
        root = ET.fromstring(svg)
        joints = root.findall(f".//{{{SVG_NAMESPACE}}}circle[@data-landmark]")

        self.assertEqual(len(joints), len(LANDMARK_NAMES) * 3)
        self.assertEqual(
            {joint.attrib["data-landmark"] for joint in joints},
            set(LANDMARK_NAMES),
        )
        self.assertNotIn("left_eye", svg)

    def test_missing_landmark_skips_only_affected_geometry(self) -> None:
        artifact = sample_artifact()
        del artifact["snapshots"][1]["landmarks"]["right_elbow"]

        svg = render_clear_pose_svg(artifact)

        self.assertIn('data-stage="swing"', svg)
        self.assertNotIn(
            'data-connection="right_shoulder-right_elbow"',
            svg.split('data-stage="finish"', maxsplit=1)[0].split(
                'data-stage="swing"', maxsplit=1
            )[1],
        )

    def test_invalid_coordinates_do_not_crash(self) -> None:
        artifact = sample_artifact()
        landmarks = artifact["snapshots"][0]["landmarks"]
        landmarks["nose"]["x"] = math.nan
        landmarks["left_wrist"]["y"] = "bad"
        landmarks["right_ankle"]["x"] = 3.0

        svg = render_clear_pose_svg(artifact)

        self.assertIn('data-stage="preparation"', svg)
        self.assertNotIn("nan", svg.lower())

    def test_not_ready_and_malformed_artifacts_use_fallback(self) -> None:
        for artifact in (
            {"status": "NOT_READY", "snapshots": []},
            None,
            {"status": "READY", "snapshots": "invalid"},
        ):
            with self.subTest(artifact=artifact):
                svg = render_clear_pose_svg(artifact)
                self.assertIn("Pose visualization unavailable", svg)

    def test_renderer_does_not_modify_artifact(self) -> None:
        artifact = sample_artifact()
        original = copy.deepcopy(artifact)

        render_clear_pose_svg(artifact)

        self.assertEqual(artifact, original)

    def test_output_avoids_unsupported_event_claims(self) -> None:
        svg = render_clear_pose_svg(sample_artifact()).lower()

        self.assertNotIn("contact", svg)
        self.assertNotIn("impact", svg)
        self.assertNotIn("擊球瞬間", svg)


if __name__ == "__main__":
    unittest.main()
