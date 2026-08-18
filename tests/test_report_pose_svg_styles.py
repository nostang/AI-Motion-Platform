import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_JS = PROJECT_ROOT / "frontend" / "js" / "report.js"
REPORT_CSS = PROJECT_ROOT / "frontend" / "css" / "style.css"

CORE_PRESENTATION_ATTRIBUTES = (
    "fill:",
    "stroke:",
    '"stroke-width":',
    "opacity:",
)


def _svg_attribute_blocks(source: str, element_name: str) -> list[str]:
    return re.findall(
        rf'svgElement\("{element_name}", \{{(.*?)\n\s*\}}\)',
        source,
        flags=re.DOTALL,
    )


def test_pose_svg_core_styles_are_explicit_attributes():
    source = REPORT_JS.read_text(encoding="utf-8")

    assert "document.createElementNS(svgNamespace, name)" in source
    for element_name, minimum_count in (
        ("polygon", 1),
        ("line", 2),
        ("circle", 2),
    ):
        blocks = _svg_attribute_blocks(source, element_name)
        assert len(blocks) >= minimum_count
        for block in blocks:
            for attribute in CORE_PRESENTATION_ATTRIBUTES:
                assert attribute in block


def test_wrist_focus_ring_is_hollow_and_styled():
    source = REPORT_JS.read_text(encoding="utf-8")
    focus_block = next(
        block
        for block in _svg_attribute_blocks(source, "circle")
        if 'class: "pose-wrist-focus"' in block
    )

    assert 'fill: "none"' in focus_block
    assert "stroke: posePalette.lime" in focus_block
    assert '"stroke-width": 3' in focus_block
    assert "r: 12" in focus_block


def test_core_pose_visibility_does_not_depend_on_report_css():
    css = REPORT_CSS.read_text(encoding="utf-8")

    for selector in (
        ".pose-torso",
        ".pose-limb {",
        ".pose-limb-racket",
        ".pose-joint {",
        ".pose-joint-racket",
        ".pose-wrist-focus",
    ):
        assert selector not in css


def test_v1_image_overlay_uses_raw_image_coordinates_and_contain():
    source = REPORT_JS.read_text(encoding="utf-8")
    css = REPORT_CSS.read_text(encoding="utf-8")

    assert "point.x * viewBoxWidth" in source
    assert "point.y * viewBoxHeight" in source
    assert '"data-coordinate-mode": usesImageCoordinates ? "image" : "centered"' in source
    assert "object-fit: contain" in css


def test_skeleton_toggle_is_accessible_and_does_not_refetch():
    source = REPORT_JS.read_text(encoding="utf-8")
    html = (PROJECT_ROOT / "frontend" / "report.html").read_text(encoding="utf-8")

    assert 'role="switch"' in html
    assert 'aria-checked="true"' in html
    handler = source[source.index('elements.keyMotionSkeletonToggle.addEventListener("click"'):]
    handler = handler[:handler.index("async function loadKeyMotion")]
    assert "getVisualization" not in handler
