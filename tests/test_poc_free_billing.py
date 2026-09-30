from datetime import datetime, timezone

from src.api.postgres_repository import PostgresVideoAnalysisRepository


class RecordingCursor:
    def __init__(self):
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.statements.append(sql)


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_standalone_poc_analysis_never_touches_goo_wallet(monkeypatch, tmp_path):
    repository = PostgresVideoAnalysisRepository(
        "postgresql://unused",
        tmp_path,
        billing_mode="free",
    )
    connection = RecordingConnection()
    monkeypatch.setattr(repository, "_connect", lambda: connection)
    now = datetime.now(timezone.utc)

    charge = repository.create_analysis(
        user_id=1,
        analysis_id=101,
        video_url="/tmp/source.mov",
        analysis_type="footwork",
        processing_status="uploaded",
        progress=0,
        current_stage="queued",
        created_at=now,
        updated_at=now,
    )

    assert charge == {
        "charge_kind": "poc_free",
        "points": 0,
        "entitlement_id": None,
    }
    executed_sql = "\n".join(connection.cursor_instance.statements).lower()
    assert "insert into video_analyses" in executed_sql
    assert "goo_wallets" not in executed_sql
    assert "analysis_charges" not in executed_sql


def test_standalone_poc_quote_is_always_free(tmp_path):
    repository = PostgresVideoAnalysisRepository(
        "postgresql://unused",
        tmp_path,
        billing_mode="free",
    )

    quote = repository.quote_analysis(1, "footwork")

    assert quote["billing_mode"] == "free"
    assert quote["charge_kind"] == "poc_free"
    assert quote["required_points"] == 0
    assert quote["can_start"] is True
