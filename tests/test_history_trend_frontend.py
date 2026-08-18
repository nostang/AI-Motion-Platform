from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_HTML = PROJECT_ROOT / "frontend" / "summary.html"
SUMMARY_JS = PROJECT_ROOT / "frontend" / "js" / "summary.js"
SUMMARY_CSS = PROJECT_ROOT / "frontend" / "css" / "summary.css"


def test_summary_has_history_trend_controls_and_graceful_copy():
    html = SUMMARY_HTML.read_text(encoding="utf-8")

    assert "HISTORY TREND" in html
    assert "歷史趨勢" in html
    assert 'data-history-motion="footwork"' in html
    assert 'data-history-motion="serve"' in html
    assert 'data-history-motion="clear"' in html
    assert "完成更多測驗後，這裡會顯示分數趨勢。" in html


def test_frontend_fetches_additive_endpoint_and_draws_overall_only():
    source = SUMMARY_JS.read_text(encoding="utf-8")
    trend_block = source[
        source.index("function renderHistoryMotion") :
        source.index("function renderProgressHighlights")
    ]

    assert "/history-trend" in source
    assert "point.overall_score" in trend_block
    assert 'svgNode("polyline"' in trend_block
    assert 'svgNode("circle"' in trend_block
    assert "point.completed_at || point.created_at" in trend_block
    assert "dimension" not in trend_block.lower()
    assert "forecast" not in trend_block.lower()


def test_history_chart_is_responsive_and_uses_existing_palette():
    css = SUMMARY_CSS.read_text(encoding="utf-8")

    assert "#historyTrendChart" in css
    assert "width: 100%" in css
    assert "var(--court)" in css
    assert "var(--lime)" in css
    assert "@media (max-width: 620px)" in css
