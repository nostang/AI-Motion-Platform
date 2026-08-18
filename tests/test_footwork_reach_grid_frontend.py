from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_HTML = PROJECT_ROOT / "frontend" / "report.html"
REPORT_JS = PROJECT_ROOT / "frontend" / "js" / "report.js"
REPORT_CSS = PROJECT_ROOT / "frontend" / "css" / "style.css"


def test_footwork_uses_nine_cell_gallery_without_slideshow_controls():
    html = REPORT_HTML.read_text(encoding="utf-8")
    section = html.split('id="footworkReachSection"', 1)[1].split(
        "</section>", 1
    )[0]

    assert "MOVEMENT REACH GRID" in section
    assert "移動觸及圖" in section
    assert 'id="footworkReachGrid"' in section
    assert 'id="footworkReachSkeletonToggle"' in section
    assert "keyMotionPlayback" not in section
    assert "autoplay" not in section.lower()
    for forbidden in ("PREPARATION", "SWING", "FINISH", "AI 觀察"):
        assert forbidden not in section


def test_grid_renders_fixed_court_layout_and_incomplete_state():
    source = REPORT_JS.read_text(encoding="utf-8")
    css = REPORT_CSS.read_text(encoding="utf-8")

    assert "grid.cells.length !== 9" in source
    assert 'unavailable.textContent = "未完成"' in source
    assert "container.style.gridRow" in source
    assert "container.style.gridColumn" in source
    assert 'renderPoseSvg(\n      landmarks,\n      "none"' in source
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css
    assert '.footwork-reach-grid[data-skeleton-visible="false"]' in css
    assert "min-width: 0" in css
    assert "@media (max-width: 560px)" in css


def test_footwork_loader_does_not_change_clear_or_serve_sequence_path():
    source = REPORT_JS.read_text(encoding="utf-8")

    assert 'if (motion === "footwork")' in source
    assert "renderFootworkReachGrid(response.data, motion)" in source
    assert "renderKeyMotion(response.data, motion)" in source
    assert '!["clear", "serve"].includes(motion)' in source
