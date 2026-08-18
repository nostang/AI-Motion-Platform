"""Standalone SVG renderer for the internal High Clear Pose artifact."""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree as ET

from src.visualization.clear_pose_visualization import LANDMARK_NAMES


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
CANVAS_WIDTH = 1440
CANVAS_HEIGHT = 900
CARD_WIDTH = 380
CARD_HEIGHT = 530
CARD_Y = 255
CARD_X_POSITIONS = (90, 530, 970)
POSE_AREA_Y = 350
POSE_AREA_WIDTH = 328
POSE_AREA_HEIGHT = 320
POSE_PADDING = 8
NORMALIZED_X_ASPECT_RATIO = 16.0 / 9.0
MINIMUM_RENDERABLE_POINTS = 3

STAGES = (
    {
        "stage": "preparation",
        "number": "01",
        "english": "PREPARATION",
        "chinese": "準備姿勢",
        "observation": "側身準備",
    },
    {
        "stage": "swing",
        "number": "02",
        "english": "SWING",
        "chinese": "揮拍階段",
        "observation": "揮拍流暢度",
    },
    {
        "stage": "finish",
        "number": "03",
        "english": "FINISH",
        "chinese": "動作完成",
        "observation": "重心轉移",
    },
)

CONNECTIONS = (
    ("nose", "left_shoulder"),
    ("nose", "right_shoulder"),
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
)

STYLES = """
text { font-family: Inter, 'Noto Sans TC', system-ui, sans-serif; fill: #09271c; }
.canvas { fill: #075d3b; }
.court-line { fill: none; stroke: #f1fbf5; stroke-width: 2; opacity: .16; }
.panel-shadow { fill: #033422; }
.panel { fill: #f1fbf5; stroke: #ffffff; stroke-width: 4; }
.eyebrow { fill: #075d3b; font: 800 14px ui-monospace, monospace; letter-spacing: 4px; }
.title { fill: #09271c; font-size: 48px; font-weight: 900; letter-spacing: -1px; }
.subtitle { fill: #617b70; font-size: 17px; font-weight: 650; }
.meta { fill: #617b70; font: 750 12px ui-monospace, monospace; letter-spacing: 1.5px; }
.sequence-line { stroke: #075d3b; stroke-width: 3; opacity: .45; }
.sequence-dot { fill: #d8ff52; stroke: #09271c; stroke-width: 3; }
.card-shadow { fill: #033422; opacity: .20; }
.pose-card { fill: #e6f1eb; stroke: #075d3b; stroke-width: 4; }
.stage-number-box { fill: #d8ff52; stroke: #09271c; stroke-width: 4; }
.stage-number { fill: #09271c; font: 900 16px ui-monospace, monospace; }
.stage-en { fill: #043f2a; font: 900 21px ui-monospace, monospace; letter-spacing: 1.5px; }
.stage-zh { fill: #617b70; font-size: 16px; font-weight: 750; }
.pose-field { fill: #f1fbf5; stroke: #9db7ab; stroke-width: 2; }
.pose-court-line { stroke: #9db7ab; stroke-width: 2; opacity: .30; }
.pose-corner { fill: none; stroke: #075d3b; stroke-width: 3; opacity: .24; }
.pose-accent { fill: #d8ff52; }
.torso-shape { fill: #075d3b; opacity: .13; }
.skeleton-line {
  fill: none;
  stroke: #075d3b;
  stroke-width: 10;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.racket-side-outline { stroke: #09271c; stroke-width: 17; stroke-linecap: round; }
.skeleton-line.racket-side { stroke: #d8ff52; stroke-width: 10; }
.racket-wrist-focus { fill: #d8ff52; fill-opacity: .18; stroke: #b6df24; stroke-width: 3; }
.joint { fill: #075d3b; stroke: #f1fbf5; stroke-width: 2; }
.joint.head-joint { fill: #f1fbf5; stroke: #075d3b; stroke-width: 6; }
.joint.racket-side-joint { fill: #d8ff52; stroke: #09271c; stroke-width: 4; }
.observation-rule { stroke: #075d3b; stroke-width: 3; opacity: .42; }
.observation-marker { fill: #d8ff52; }
.observation-label { fill: #075d3b; font-size: 14px; font-weight: 900; letter-spacing: 1.5px; }
.observation-value { fill: #043f2a; font-size: 23px; font-weight: 900; }
.timestamp { fill: #617b70; font: 750 13px ui-monospace, monospace; }
.racket-legend-line { stroke: #09271c; stroke-width: 10; stroke-linecap: round; }
.racket-legend-highlight { stroke: #d8ff52; stroke-width: 5; stroke-linecap: round; }
.unavailable { fill: #617b70; font-size: 14px; font-weight: 700; }
.fallback-box { fill: #e6f1eb; stroke: #9db7ab; stroke-width: 3; }
.fallback-title { fill: #043f2a; font-size: 26px; font-weight: 850; }
.fallback-copy { fill: #617b70; font-size: 16px; font-weight: 650; }
.footer { fill: #617b70; font: 750 11px ui-monospace, monospace; letter-spacing: 1.2px; }
""".strip()


def _svg_element(
    parent: ET.Element,
    tag: str,
    attributes: Mapping[str, Any] | None = None,
    *,
    text: str | None = None,
) -> ET.Element:
    element = ET.SubElement(
        parent,
        f"{{{SVG_NAMESPACE}}}{tag}",
        {
            key: str(value)
            for key, value in (attributes or {}).items()
        },
    )
    if text is not None:
        element.text = text
    return element


def _valid_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clean_landmarks(snapshot: Any) -> dict[str, tuple[float, float]]:
    if not isinstance(snapshot, Mapping):
        return {}

    raw_landmarks = snapshot.get("landmarks")
    if not isinstance(raw_landmarks, Mapping):
        return {}

    cleaned: dict[str, tuple[float, float]] = {}
    for name in LANDMARK_NAMES:
        point = raw_landmarks.get(name)
        if not isinstance(point, Mapping):
            continue
        x = _valid_number(point.get("x"))
        y = _valid_number(point.get("y"))
        if x is None or y is None or not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            continue
        cleaned[name] = (x * NORMALIZED_X_ASPECT_RATIO, y)
    return cleaned


def _has_renderable_skeleton(
    landmarks: Mapping[str, tuple[float, float]],
) -> bool:
    if len(landmarks) < MINIMUM_RENDERABLE_POINTS:
        return False
    return any(start in landmarks and end in landmarks for start, end in CONNECTIONS)


def _bounds(
    landmarks: Mapping[str, tuple[float, float]],
) -> tuple[float, float, float, float]:
    x_values = [point[0] for point in landmarks.values()]
    y_values = [point[1] for point in landmarks.values()]
    return min(x_values), min(y_values), max(x_values), max(y_values)


def _snapshot_by_stage(artifact: Mapping[str, Any]) -> dict[str, Any]:
    snapshots = artifact.get("snapshots")
    if not isinstance(snapshots, Sequence) or isinstance(snapshots, (str, bytes)):
        return {}

    result: dict[str, Any] = {}
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            continue
        stage = snapshot.get("stage")
        if isinstance(stage, str) and stage not in result:
            result[stage] = snapshot
    return result


def _timestamp_label(snapshot: Any) -> str:
    if not isinstance(snapshot, Mapping):
        return "--"
    timestamp_ms = _valid_number(snapshot.get("timestamp_ms"))
    if timestamp_ms is None or timestamp_ms < 0:
        return "--"
    return f"{timestamp_ms / 1000.0:.2f}s"


def _add_text(
    parent: ET.Element,
    x: float,
    y: float,
    value: str,
    css_class: str,
    **attributes: Any,
) -> ET.Element:
    return _svg_element(
        parent,
        "text",
        {"x": x, "y": y, "class": css_class, **attributes},
        text=value,
    )


def _add_frame(root: ET.Element, racket_side: str) -> None:
    _svg_element(root, "rect", {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "class": "canvas"})
    court = _svg_element(root, "g", {"aria-hidden": "true"})
    _svg_element(court, "path", {"d": "M720 0V900 M0 450H1440", "class": "court-line"})
    _svg_element(
        court,
        "rect",
        {
            "x": 155,
            "y": 75,
            "width": 1130,
            "height": 750,
            "class": "court-line",
        },
    )

    _svg_element(
        root,
        "rect",
        {
            "x": 64,
            "y": 74,
            "width": 1340,
            "height": 780,
            "class": "panel-shadow",
        },
    )
    _svg_element(root, "rect", {"x": 50, "y": 60, "width": 1340, "height": 780, "class": "panel"})
    _svg_element(root, "rect", {"x": 90, "y": 104, "width": 12, "height": 64, "fill": "#d8ff52"})
    _add_text(root, 124, 116, "KEY MOTION", "eyebrow")
    _add_text(root, 124, 160, "關鍵動作", "title")
    _add_text(root, 124, 190, "三個代表姿勢，快速理解動作節奏", "subtitle")

    side_label = racket_side.upper() if racket_side in {"left", "right"} else "UNKNOWN"
    _add_text(
        root,
        1350,
        116,
        f"HIGH CLEAR  /  RACKET SIDE: {side_label}",
        "meta",
        **{"text-anchor": "end"},
    )
    _svg_element(
        root,
        "line",
        {
            "x1": 1160,
            "y1": 153,
            "x2": 1200,
            "y2": 153,
            "class": "racket-legend-line",
        },
    )
    _svg_element(
        root,
        "line",
        {
            "x1": 1160,
            "y1": 153,
            "x2": 1200,
            "y2": 153,
            "class": "racket-legend-highlight",
        },
    )
    _add_text(root, 1214, 157, "持拍側手臂", "meta")
    _add_text(root, 1350, 190, "01  →  02  →  03", "meta", **{"text-anchor": "end"})


def _add_sequence(root: ET.Element) -> None:
    centers = [x + CARD_WIDTH / 2 for x in CARD_X_POSITIONS]
    _svg_element(
        root,
        "line",
        {
            "x1": centers[0],
            "y1": 225,
            "x2": centers[-1],
            "y2": 225,
            "class": "sequence-line",
        },
    )
    for center in centers:
        _svg_element(
            root,
            "circle",
            {"cx": center, "cy": 225, "r": 8, "class": "sequence-dot"},
        )


def _add_pose_field(root: ET.Element, card_x: float) -> None:
    field_x = card_x + 26
    _svg_element(
        root,
        "rect",
        {
            "x": field_x,
            "y": POSE_AREA_Y,
            "width": POSE_AREA_WIDTH,
            "height": POSE_AREA_HEIGHT,
            "class": "pose-field",
        },
    )
    _svg_element(
        root,
        "line",
        {
            "x1": field_x,
            "y1": POSE_AREA_Y + POSE_AREA_HEIGHT * 0.76,
            "x2": field_x + POSE_AREA_WIDTH,
            "y2": POSE_AREA_Y + POSE_AREA_HEIGHT * 0.76,
            "class": "pose-court-line",
        },
    )
    _svg_element(
        root,
        "path",
        {
            "d": (
                f"M{field_x + 18} {POSE_AREA_Y + 42} "
                f"V{POSE_AREA_Y + 18} H{field_x + 42} "
                f"M{field_x + POSE_AREA_WIDTH - 42} {POSE_AREA_Y + 18} "
                f"H{field_x + POSE_AREA_WIDTH - 18} V{POSE_AREA_Y + 42}"
            ),
            "class": "pose-corner",
        },
    )
    _svg_element(
        root,
        "rect",
        {
            "x": field_x + 18,
            "y": POSE_AREA_Y + 18,
            "width": 38,
            "height": 5,
            "class": "pose-accent",
        },
    )


def _screen_points(
    landmarks: Mapping[str, tuple[float, float]],
    *,
    card_x: float,
    scale: float,
) -> dict[str, tuple[float, float]]:
    min_x, min_y, max_x, max_y = _bounds(landmarks)
    source_center_x = (min_x + max_x) / 2.0
    source_center_y = (min_y + max_y) / 2.0
    target_center_x = card_x + 26 + POSE_AREA_WIDTH / 2.0
    target_center_y = POSE_AREA_Y + POSE_AREA_HEIGHT / 2.0
    return {
        name: (
            target_center_x + (point[0] - source_center_x) * scale,
            target_center_y + (point[1] - source_center_y) * scale,
        )
        for name, point in landmarks.items()
    }


def _is_racket_arm_connection(
    start: str,
    end: str,
    racket_side: str,
) -> bool:
    return (start, end) in {
        (f"{racket_side}_shoulder", f"{racket_side}_elbow"),
        (f"{racket_side}_elbow", f"{racket_side}_wrist"),
    }


def _is_racket_arm_joint(name: str, racket_side: str) -> bool:
    return name in {
        f"{racket_side}_shoulder",
        f"{racket_side}_elbow",
        f"{racket_side}_wrist",
    }


def _add_skeleton(
    root: ET.Element,
    points: Mapping[str, tuple[float, float]],
    *,
    stage: str,
    racket_side: str,
) -> None:
    skeleton = _svg_element(root, "g", {"class": "pose-skeleton", "data-stage": stage})

    torso_names = (
        "left_shoulder",
        "right_shoulder",
        "right_hip",
        "left_hip",
    )
    if all(name in points for name in torso_names):
        torso_points = " ".join(
            f"{points[name][0]:.2f},{points[name][1]:.2f}"
            for name in torso_names
        )
        _svg_element(
            skeleton,
            "polygon",
            {"points": torso_points, "class": "torso-shape"},
        )

    for start, end in CONNECTIONS:
        if start not in points or end not in points:
            continue
        start_x, start_y = points[start]
        end_x, end_y = points[end]
        css_class = "skeleton-line"
        is_racket_arm = _is_racket_arm_connection(start, end, racket_side)
        if is_racket_arm:
            _svg_element(
                skeleton,
                "line",
                {
                    "x1": f"{start_x:.2f}",
                    "y1": f"{start_y:.2f}",
                    "x2": f"{end_x:.2f}",
                    "y2": f"{end_y:.2f}",
                    "class": "racket-side-outline",
                },
            )
            css_class += " racket-side"
        _svg_element(
            skeleton,
            "line",
            {
                "x1": f"{start_x:.2f}",
                "y1": f"{start_y:.2f}",
                "x2": f"{end_x:.2f}",
                "y2": f"{end_y:.2f}",
                "class": css_class,
                "data-connection": f"{start}-{end}",
            },
        )

    racket_wrist = points.get(f"{racket_side}_wrist")
    if racket_wrist is not None:
        _svg_element(
            skeleton,
            "circle",
            {
                "cx": f"{racket_wrist[0]:.2f}",
                "cy": f"{racket_wrist[1]:.2f}",
                "r": 15,
                "class": "racket-wrist-focus",
            },
        )

    for name, (x, y) in points.items():
        css_class = "joint"
        if _is_racket_arm_joint(name, racket_side):
            css_class += " racket-side-joint"
        elif name == "nose":
            css_class += " head-joint"

        if name == "nose":
            radius = 10
        elif _is_racket_arm_joint(name, racket_side):
            radius = 7
        else:
            radius = 4
        _svg_element(
            skeleton,
            "circle",
            {
                "cx": f"{x:.2f}",
                "cy": f"{y:.2f}",
                "r": radius,
                "class": css_class,
                "data-landmark": name,
            },
        )


def _add_card(
    root: ET.Element,
    stage_config: Mapping[str, str],
    snapshot: Any,
    landmarks: Mapping[str, tuple[float, float]],
    *,
    card_x: float,
    scale: float,
    racket_side: str,
) -> None:
    stage = stage_config["stage"]
    card = _svg_element(root, "g", {"class": "stage-card", "data-stage": stage})
    _svg_element(
        card,
        "rect",
        {
            "x": card_x + 8,
            "y": CARD_Y + 9,
            "width": CARD_WIDTH,
            "height": CARD_HEIGHT,
            "class": "card-shadow",
        },
    )
    _svg_element(
        card,
        "rect",
        {
            "x": card_x,
            "y": CARD_Y,
            "width": CARD_WIDTH,
            "height": CARD_HEIGHT,
            "class": "pose-card",
        },
    )
    _svg_element(
        card,
        "rect",
        {
            "x": card_x + 26,
            "y": CARD_Y + 25,
            "width": 48,
            "height": 48,
            "class": "stage-number-box",
        },
    )
    _add_text(
        card,
        card_x + 50,
        CARD_Y + 55,
        stage_config["number"],
        "stage-number",
        **{"text-anchor": "middle"},
    )
    _add_text(card, card_x + 92, CARD_Y + 43, stage_config["english"], "stage-en")
    _add_text(card, card_x + 92, CARD_Y + 69, stage_config["chinese"], "stage-zh")

    _add_pose_field(card, card_x)
    if _has_renderable_skeleton(landmarks):
        points = _screen_points(landmarks, card_x=card_x, scale=scale)
        _add_skeleton(
            card,
            points,
            stage=stage,
            racket_side=racket_side,
        )
    else:
        _add_text(
            card,
            card_x + CARD_WIDTH / 2,
            POSE_AREA_Y + POSE_AREA_HEIGHT / 2,
            "Pose visualization unavailable",
            "unavailable",
            **{"text-anchor": "middle"},
        )

    _svg_element(
        card,
        "line",
        {
            "x1": card_x + 26,
            "y1": 690,
            "x2": card_x + 354,
            "y2": 690,
            "class": "observation-rule",
        },
    )
    _svg_element(
        card,
        "rect",
        {
            "x": card_x + 26,
            "y": 708,
            "width": 7,
            "height": 17,
            "class": "observation-marker",
        },
    )
    _add_text(card, card_x + 44, 722, "AI 觀察", "observation-label")
    _add_text(
        card,
        card_x + 26,
        754,
        stage_config["observation"],
        "observation-value",
    )
    _add_text(
        card,
        card_x + 354,
        752,
        _timestamp_label(snapshot),
        "timestamp",
        **{"text-anchor": "end"},
    )


def _common_scale(
    cleaned_by_stage: Mapping[str, Mapping[str, tuple[float, float]]],
) -> float:
    spans = []
    for landmarks in cleaned_by_stage.values():
        if not _has_renderable_skeleton(landmarks):
            continue
        min_x, min_y, max_x, max_y = _bounds(landmarks)
        spans.append((max_x - min_x, max_y - min_y))

    if not spans:
        return 1.0

    maximum_width = max(width for width, _ in spans)
    maximum_height = max(height for _, height in spans)
    available_width = POSE_AREA_WIDTH - POSE_PADDING * 2
    available_height = POSE_AREA_HEIGHT - POSE_PADDING * 2
    return min(
        available_width / max(maximum_width, 1e-9),
        available_height / max(maximum_height, 1e-9),
    )


def _add_unavailable_preview(root: ET.Element) -> None:
    _svg_element(
        root,
        "rect",
        {
            "x": 290,
            "y": 285,
            "width": 860,
            "height": 350,
            "class": "fallback-box",
        },
    )
    _add_text(
        root,
        720,
        435,
        "Pose visualization unavailable",
        "fallback-title",
        **{"text-anchor": "middle"},
    )
    _add_text(
        root,
        720,
        475,
        "The visualization artifact is not ready or is malformed.",
        "fallback-copy",
        **{"text-anchor": "middle"},
    )


def render_clear_pose_svg(artifact: Any) -> str:
    """Render an artifact to a self-contained, non-interactive SVG string."""

    ET.register_namespace("", SVG_NAMESPACE)
    root = ET.Element(
        f"{{{SVG_NAMESPACE}}}svg",
        {
            "width": str(CANVAS_WIDTH),
            "height": str(CANVAS_HEIGHT),
            "viewBox": f"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}",
            "role": "img",
            "aria-labelledby": "preview-title preview-description",
        },
    )
    _svg_element(
        root,
        "title",
        {"id": "preview-title"},
        text="AI Motion High Clear key motion preview",
    )
    _svg_element(
        root,
        "desc",
        {"id": "preview-description"},
        text="Three representative simplified poses: preparation, swing, and finish.",
    )
    _svg_element(root, "style", text=STYLES)

    artifact_mapping = artifact if isinstance(artifact, Mapping) else {}
    racket_side_value = artifact_mapping.get("racket_side")
    racket_side = racket_side_value if racket_side_value in {"left", "right"} else "unknown"
    _add_frame(root, racket_side)

    if artifact_mapping.get("status") != "READY":
        _add_unavailable_preview(root)
    else:
        snapshots = _snapshot_by_stage(artifact_mapping)
        cleaned_by_stage = {
            stage["stage"]: _clean_landmarks(snapshots.get(stage["stage"]))
            for stage in STAGES
        }
        scale = _common_scale(cleaned_by_stage)
        _add_sequence(root)
        for card_x, stage in zip(CARD_X_POSITIONS, STAGES):
            stage_name = stage["stage"]
            _add_card(
                root,
                stage,
                snapshots.get(stage_name),
                cleaned_by_stage[stage_name],
                card_x=card_x,
                scale=scale,
                racket_side=racket_side,
            )

    _add_text(root, 90, 816, "REPRESENTATIVE POSE  /  INTERNAL PREVIEW V0", "footer")
    _add_text(root, 1350, 816, "TIME  →", "footer", **{"text-anchor": "end"})

    svg = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return svg + "\n"


def render_clear_pose_preview(
    artifact_path: Path,
    output_path: Path,
) -> str:
    """Read an artifact and save a standalone SVG preview."""

    try:
        artifact: Any = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        artifact = {}

    svg = render_clear_pose_svg(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return svg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the internal High Clear Explainable Pose preview."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("output/clear_pose_visualization.json"),
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("output/clear_pose_visualization_preview.svg"),
    )
    args = parser.parse_args()
    render_clear_pose_preview(args.input, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
