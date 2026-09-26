from datetime import datetime, timezone
import os
from pathlib import Path

import psycopg
import pytest

from src.api.postgres_repository import PostgresVideoAnalysisRepository


TEST_DATABASE_URL = os.environ.get("TEST_MOTION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_MOTION_DATABASE_URL is required for wallet integration tests",
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _create(repository, user_id, motion_type):
    analysis_id = repository.allocate_analysis_id()
    charge = repository.create_analysis(
        user_id=user_id,
        analysis_id=analysis_id,
        video_url=f"/tmp/{analysis_id}.mp4",
        analysis_type=motion_type,
        processing_status="uploaded",
        progress=0,
        current_stage="uploaded",
        created_at=_now(),
        updated_at=_now(),
    )
    return analysis_id, charge


def test_first_free_points_reservation_refund_and_idempotent_credit(tmp_path):
    user_id = 900001
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (user_id, display_name) VALUES (%s, %s)",
                (user_id, "Goo wallet test user"),
            )

    repository = PostgresVideoAnalysisRepository(TEST_DATABASE_URL, tmp_path)

    failed_free_id, failed_free = _create(repository, user_id, "footwork")
    assert failed_free == {"charge_kind": "first_free", "points": 0, "entitlement_id": None}
    repository.update_status(
        failed_free_id,
        processing_status="failed",
        progress=100,
        current_stage="input_validation",
        updated_at=_now(),
        completed_at=_now(),
        error_message="invalid test video",
    )
    assert repository.quote_analysis(user_id, "footwork")["charge_kind"] == "first_free"

    free_id, free_charge = _create(repository, user_id, "footwork")
    assert free_charge == {"charge_kind": "first_free", "points": 0, "entitlement_id": None}
    repository.update_status(
        free_id,
        processing_status="completed",
        progress=100,
        current_stage="report",
        updated_at=_now(),
        completed_at=_now(),
    )
    assert repository.quote_analysis(user_id, "footwork")["required_points"] == 10

    entitlement = repository.grant_analysis_entitlement(
        user_id=user_id,
        payment_order_id="analysis-order-test-1",
        analysis_type="footwork",
        amount_twd=30,
    )
    duplicate_entitlement = repository.grant_analysis_entitlement(
        user_id=user_id,
        payment_order_id="analysis-order-test-1",
        analysis_type="footwork",
        amount_twd=30,
    )
    assert entitlement["created"] is True
    assert duplicate_entitlement["created"] is False
    assert repository.quote_analysis(user_id, "footwork")["charge_kind"] == "direct_purchase"

    failed_purchase_id, purchase_charge = _create(repository, user_id, "footwork")
    assert purchase_charge["charge_kind"] == "direct_purchase"
    assert purchase_charge["points"] == 0
    repository.update_status(
        failed_purchase_id,
        processing_status="failed",
        progress=100,
        current_stage="analysis",
        updated_at=_now(),
        completed_at=_now(),
        error_message="pipeline failed",
    )
    assert repository.quote_analysis(user_id, "footwork")["charge_kind"] == "direct_purchase"

    purchase_id, purchase_retry_charge = _create(repository, user_id, "footwork")
    assert purchase_retry_charge["charge_kind"] == "direct_purchase"
    repository.update_status(
        purchase_id,
        processing_status="completed",
        progress=100,
        current_stage="report",
        updated_at=_now(),
        completed_at=_now(),
    )
    assert repository.quote_analysis(user_id, "footwork")["charge_kind"] == "points"

    first_credit = repository.credit_wallet(
        user_id=user_id,
        amount=10,
        transaction_type="topup",
        reference_type="payment_order",
        reference_id="order-test-1",
        idempotency_key="topup:order-test-1:credit",
    )
    duplicate_credit = repository.credit_wallet(
        user_id=user_id,
        amount=10,
        transaction_type="topup",
        reference_type="payment_order",
        reference_id="order-test-1",
        idempotency_key="topup:order-test-1:credit",
    )
    assert first_credit["credited"] is True
    assert duplicate_credit["credited"] is False
    assert duplicate_credit["balance"] == 10

    failed_paid_id, paid_charge = _create(repository, user_id, "footwork")
    assert paid_charge == {"charge_kind": "points", "points": 10, "entitlement_id": None}
    assert repository.get_wallet(user_id)["balance"] == 0
    assert repository.get_wallet(user_id)["reserved_balance"] == 10
    repository.update_status(
        failed_paid_id,
        processing_status="failed",
        progress=100,
        current_stage="analysis",
        updated_at=_now(),
        completed_at=_now(),
        error_message="pipeline failed",
    )
    assert repository.get_wallet(user_id)["balance"] == 10
    assert repository.get_wallet(user_id)["reserved_balance"] == 0

    paid_id, _ = _create(repository, user_id, "footwork")
    repository.update_status(
        paid_id,
        processing_status="completed",
        progress=100,
        current_stage="report",
        updated_at=_now(),
        completed_at=_now(),
    )
    wallet = repository.get_wallet(user_id)
    assert wallet["balance"] == 0
    assert wallet["reserved_balance"] == 0

    with psycopg.connect(TEST_DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM goo_transactions
                WHERE idempotency_key = 'topup:order-test-1:credit'
                """
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """
                SELECT amount
                FROM goo_transactions
                WHERE idempotency_key = %s
                """,
                (f"analysis:{paid_id}:debit",),
            )
            assert cursor.fetchone()[0] == -10


def test_event_rewards_are_idempotent_and_capped_per_taipei_week(tmp_path):
    user_id = 900002
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            cursor.execute(
                "INSERT INTO users (user_id, display_name) VALUES (%s, %s)",
                (user_id, "Event reward test user"),
            )

    repository = PostgresVideoAnalysisRepository(TEST_DATABASE_URL, tmp_path)
    first = repository.grant_event_reward(
        user_id=user_id,
        registration_id=910001,
        event_id=920001,
        event_ended_at=datetime(2026, 8, 24, 13, tzinfo=timezone.utc),
    )
    duplicate = repository.grant_event_reward(
        user_id=user_id,
        registration_id=910001,
        event_id=920001,
        event_ended_at=datetime(2026, 8, 24, 13, tzinfo=timezone.utc),
    )
    second = repository.grant_event_reward(
        user_id=user_id,
        registration_id=910002,
        event_id=920002,
        event_ended_at=datetime(2026, 8, 25, 13, tzinfo=timezone.utc),
    )
    capped = repository.grant_event_reward(
        user_id=user_id,
        registration_id=910003,
        event_id=920003,
        event_ended_at=datetime(2026, 8, 26, 13, tzinfo=timezone.utc),
    )

    assert first["credited"] is True
    assert duplicate["status"] == "already_awarded"
    assert second["credited"] is True
    assert second["balance"] == 2
    assert capped["credited"] is False
    assert capped["status"] == "weekly_limit"
    assert repository.get_wallet(user_id)["balance"] == 2

    with psycopg.connect(TEST_DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT amount
                FROM goo_transactions
                WHERE user_id = %s
                  AND reference_type = 'event_registration'
                ORDER BY reference_id
                """,
                (user_id,),
            )
            assert [row[0] for row in cursor.fetchall()] == [1, 1, 0]
