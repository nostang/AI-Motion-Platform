from __future__ import annotations

from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_HTML = PROJECT_ROOT / "frontend" / "report.html"
REPORT_JS = PROJECT_ROOT / "frontend" / "js" / "report.js"
REPORT_CSS = PROJECT_ROOT / "frontend" / "css" / "style.css"
PLAYER_JS = PROJECT_ROOT / "frontend" / "js" / "motion-sequence-player.js"


def test_motion_sequence_player_behavior_with_node():
    result = subprocess.run(
        [
            "node",
            "--test",
            str(PROJECT_ROOT / "tests" / "js" / "test_motion_sequence_player.js"),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_formal_web_copy_has_no_stage_semantics():
    html = REPORT_HTML.read_text(encoding="utf-8")
    key_motion = html.split('id="keyMotionSection"', 1)[1].split("</section>", 1)[0]

    assert "MOTION SEQUENCE" in key_motion
    assert "動作序列" in key_motion
    assert "從本次分析片段擷取連續代表畫面，查看完整動作變化。" in key_motion
    for forbidden in (
        "PREPARATION",
        "SWING",
        "FINISH",
        "準備姿勢",
        "揮拍階段",
        "動作完成",
        "AI 觀察",
        "contact",
        "impact",
        "擊球瞬間",
    ):
        assert forbidden not in key_motion


def test_sequence_rendering_uses_six_preloaded_frames_and_safe_image_fallback():
    source = REPORT_JS.read_text(encoding="utf-8")

    assert "const motionSequenceFrameCount = 6" in source
    assert "image.loading = \"eager\"" in source
    assert "image.addEventListener(\"error\"" in source
    assert "motionSequencePlayback?.select(frame.index - 1)" in source
    assert 'window.matchMedia?.("(prefers-reduced-motion: reduce)")' in source
    assert "motionSequenceIntervalMs = 425" in source
    assert '!["clear", "serve"].includes(motion)' in source
    assert "sequence?.motion_type !== motion" in source


def test_controls_do_not_refetch_and_skeleton_toggle_is_dom_only():
    source = REPORT_JS.read_text(encoding="utf-8")
    control_block = source[
        source.index('elements.keyMotionSkeletonToggle.addEventListener("click"') :
        source.index("async function loadKeyMotion")
    ]

    assert "getVisualization" not in control_block
    assert "fetch(" not in control_block
    assert "dataset.skeletonVisible" in source


def test_player_is_responsive_and_overlay_uses_image_viewbox():
    source = REPORT_JS.read_text(encoding="utf-8")
    css = REPORT_CSS.read_text(encoding="utf-8")

    assert "point.x * viewBoxWidth" in source
    assert "point.y * viewBoxHeight" in source
    assert "width: min(100%, 960px)" in css
    assert "min-width: 0" in css
    assert "aspect-ratio: 960 / 523" in css
    assert '@media (max-width: 560px)' in css


def test_player_module_has_no_network_api():
    source = PLAYER_JS.read_text(encoding="utf-8")

    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source
    assert "getVisualization" not in source
