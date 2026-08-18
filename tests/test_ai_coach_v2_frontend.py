from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_HTML = PROJECT_ROOT / "frontend" / "report.html"
REPORT_JS = PROJECT_ROOT / "frontend" / "js" / "report.js"
API_JS = PROJECT_ROOT / "frontend" / "js" / "api.js"
STYLE_CSS = PROJECT_ROOT / "frontend" / "css" / "style.css"


def test_report_contains_all_five_ai_coach_v2_blocks():
    html = REPORT_HTML.read_text(encoding="utf-8")

    for heading in (
        "本次亮點",
        "優先改善",
        "建議訓練菜單",
        "下次測驗觀察重點",
        "近期變化",
    ):
        assert heading in html
    assert "系統不會追蹤是否完成" in html


def test_report_fetches_additive_coach_v2_and_preserves_v1_fallback():
    api_source = API_JS.read_text(encoding="utf-8")
    report_source = REPORT_JS.read_text(encoding="utf-8")

    assert "/coach-v2" in api_source
    assert "renderCoachV2" in report_source
    assert "preserving existing Coach" in report_source
    assert "loadKeyMotion(assessmentId, motion)" in report_source
    assert "loadCoachV2(assessmentId)" in report_source


def test_coach_v2_layout_is_responsive_and_uses_existing_palette():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".coach-v2" in css
    assert "var(--lime)" in css
    assert "var(--court-deep)" in css
    assert "@media (max-width: 720px)" in css
