from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]


def test_wallet_usage_report_counts_only_actual_analysis_debits():
    repository = (MODULE_DIR / "src/api/postgres_repository.py").read_text(encoding="utf-8")
    report = repository.split("def get_admin_wallet_usage_report", 1)[1].split("def quote_analysis", 1)[0]
    assert "transaction_type = 'analysis_debit'" in report
    assert "t.amount < 0" in report
    assert "lifetime_consumed_points" in report
    assert "period_consumed_points" in report
    assert "AT TIME ZONE 'Asia/Taipei'" in report


def test_wallet_usage_endpoint_requires_internal_key_and_bounded_period():
    source = (MODULE_DIR / "src/api/app.py").read_text(encoding="utf-8")
    route = source.split("def internal_admin_wallet_usage", 1)[1].split("APP_ENV =", 1)[0]
    assert "_internal_key_is_valid(x_internal_api_key)" in route
    assert "(to_date - from_date).days > 366" in route
    assert "get_admin_wallet_usage_report" in route
