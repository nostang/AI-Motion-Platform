"""PostgreSQL repository for AI Motion VIDEO_ANALYSES.

Repository V2 uses explicit operations instead of a generic save().
It follows the team ERD and keeps SQL out of API / Service layers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class InsufficientGooPointsError(RuntimeError):
    def __init__(self, balance: int, required: int) -> None:
        super().__init__("Goo points balance is insufficient")
        self.balance = int(balance)
        self.required = int(required)


class PostgresVideoAnalysisRepository:
    def __init__(
        self,
        database_url: str,
        storage_root: Path,
        *,
        billing_mode: str | None = None,
    ) -> None:
        self.database_url = database_url
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.billing_mode = (
            billing_mode
            or os.environ.get("AI_MOTION_BILLING_MODE", "free")
        ).strip().lower()
        if self.billing_mode not in {"free", "goo"}:
            raise ValueError("Unsupported AI Motion billing mode")
        self.analysis_price = max(
            1,
            int(os.environ.get("GOO_ANALYSIS_PRICE", "10")),
        )
        self.direct_purchase_price = max(
            1,
            int(os.environ.get("ANALYSIS_PURCHASE_PRICE_TWD", "30")),
        )

    def _connect(self):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
        )

    def task_dir(self, analysis_id: int) -> Path:
        return self.storage_root / str(analysis_id)

    def allocate_analysis_id(self) -> int:
        """Allocate the production analysis identifier from PostgreSQL."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT nextval('video_analyses_analysis_id_seq') AS id")
            row = cur.fetchone()
        return int(row["id"])

    def user_exists(self, user_id: int) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE user_id = %s",
                (user_id,),
            )
            return cur.fetchone() is not None

    def upsert_user(
        self,
        user_id: int,
        line_user_id: str | None,
        display_name: str | None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, line_user_id, display_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET line_user_id = EXCLUDED.line_user_id,
                    display_name = EXCLUDED.display_name,
                    updated_at = NOW()
                """,
                (user_id, line_user_id, display_name),
            )

    def get_wallet(self, user_id: int) -> dict[str, Any]:
        if self.billing_mode == "free":
            return {
                "user_id": user_id,
                "balance": 0,
                "reserved_balance": 0,
                "analysis_price": 0,
                "first_free_available": {
                    analysis_type: True
                    for analysis_type in ("footwork", "serve", "clear")
                },
                "billing_mode": "free",
                "updated_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
            }

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goo_wallets (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            cur.execute(
                """
                SELECT balance, reserved_balance, updated_at
                FROM goo_wallets
                WHERE user_id = %s
                """,
                (user_id,),
            )
            wallet = cur.fetchone()
            cur.execute(
                """
                SELECT analysis_type
                FROM analysis_charges
                WHERE user_id = %s
                  AND charge_kind = 'first_free'
                  AND status IN ('reserved', 'consumed')
                """,
                (user_id,),
            )
            used_types = {row["analysis_type"] for row in cur.fetchall()}

        return {
            "user_id": user_id,
            "balance": int(wallet["balance"]),
            "reserved_balance": int(wallet["reserved_balance"]),
            "analysis_price": self.analysis_price,
            "first_free_available": {
                motion_type: motion_type not in used_types
                for motion_type in ("footwork", "serve", "clear")
            },
            "updated_at": wallet["updated_at"].isoformat(),
        }

    def get_admin_wallet_usage_report(self, from_date, to_date) -> list[dict[str, Any]]:
        """Return read-only Goo usage totals for trusted admin aggregation."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.user_id,
                    COALESCE(w.balance, 0) AS balance,
                    COALESCE(w.reserved_balance, 0) AS reserved_balance,
                    COALESCE(SUM(-t.amount) FILTER (
                        WHERE t.transaction_type = 'analysis_debit' AND t.amount < 0
                    ), 0) AS lifetime_consumed_points,
                    COALESCE(SUM(-t.amount) FILTER (
                        WHERE t.transaction_type = 'analysis_debit'
                          AND t.amount < 0
                          AND t.created_at >= (%s::date::timestamp AT TIME ZONE 'Asia/Taipei')
                          AND t.created_at < ((%s::date + INTERVAL '1 day')::timestamp AT TIME ZONE 'Asia/Taipei')
                    ), 0) AS period_consumed_points,
                    COUNT(*) FILTER (
                        WHERE t.transaction_type = 'analysis_debit'
                          AND t.amount < 0
                          AND t.created_at >= (%s::date::timestamp AT TIME ZONE 'Asia/Taipei')
                          AND t.created_at < ((%s::date + INTERVAL '1 day')::timestamp AT TIME ZONE 'Asia/Taipei')
                    ) AS period_debit_count
                FROM users AS u
                LEFT JOIN goo_wallets AS w ON w.user_id = u.user_id
                LEFT JOIN goo_transactions AS t ON t.user_id = u.user_id
                GROUP BY u.user_id, w.balance, w.reserved_balance
                ORDER BY lifetime_consumed_points DESC, u.user_id
                """,
                (from_date, to_date, from_date, to_date),
            )
            return [
                {
                    "user_id": int(row["user_id"]),
                    "balance": int(row["balance"]),
                    "reserved_balance": int(row["reserved_balance"]),
                    "lifetime_consumed_points": int(row["lifetime_consumed_points"]),
                    "period_consumed_points": int(row["period_consumed_points"]),
                    "period_debit_count": int(row["period_debit_count"]),
                }
                for row in cur.fetchall()
            ]

    def quote_analysis(self, user_id: int, analysis_type: str) -> dict[str, Any]:
        if self.billing_mode == "free":
            return {
                **self.get_wallet(user_id),
                "assessment_type": analysis_type,
                "charge_kind": "poc_free",
                "required_points": 0,
                "purchase_price_twd": 0,
                "can_start": True,
            }

        wallet = self.get_wallet(user_id)
        is_free = bool(
            wallet["first_free_available"].get(analysis_type, False)
        )
        entitlement_available = False
        if not is_free:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM analysis_entitlements
                    WHERE user_id = %s
                      AND analysis_type = %s
                      AND status = 'available'
                    LIMIT 1
                    """,
                    (user_id, analysis_type),
                )
                entitlement_available = cur.fetchone() is not None

        if is_free:
            charge_kind = "first_free"
            required = 0
        elif entitlement_available:
            charge_kind = "direct_purchase"
            required = 0
        else:
            charge_kind = "points"
            required = self.analysis_price
        can_start = is_free or entitlement_available or wallet["balance"] >= required
        return {
            **wallet,
            "analysis_type": analysis_type,
            "charge_kind": charge_kind,
            "required_points": required,
            "purchase_price_twd": self.direct_purchase_price,
            "can_purchase": not can_start,
            "can_start": can_start,
        }

    def grant_analysis_entitlement(
        self,
        *,
        user_id: int,
        payment_order_id: str,
        analysis_type: str,
        amount_twd: int,
    ) -> dict[str, Any]:
        if analysis_type not in {"footwork", "serve", "clear"}:
            raise ValueError("Unsupported analysis type")
        if amount_twd <= 0:
            raise ValueError("Entitlement amount must be positive")

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_entitlements (
                    payment_order_id, user_id, analysis_type, amount_twd
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (payment_order_id) DO NOTHING
                RETURNING entitlement_id
                """,
                (payment_order_id, user_id, analysis_type, amount_twd),
            )
            created = cur.fetchone() is not None
            cur.execute(
                """
                SELECT entitlement_id, payment_order_id, user_id,
                       analysis_type, amount_twd, status, analysis_id
                FROM analysis_entitlements
                WHERE payment_order_id = %s
                """,
                (payment_order_id,),
            )
            entitlement = cur.fetchone()
            if (
                int(entitlement["user_id"]) != int(user_id)
                or entitlement["analysis_type"] != analysis_type
                or int(entitlement["amount_twd"]) != int(amount_twd)
            ):
                raise ValueError("Payment order entitlement does not match")

        return {
            **dict(entitlement),
            "entitlement_id": int(entitlement["entitlement_id"]),
            "user_id": int(entitlement["user_id"]),
            "amount_twd": int(entitlement["amount_twd"]),
            "created": created,
        }

    def credit_wallet(
        self,
        *,
        user_id: int,
        amount: int,
        transaction_type: str,
        reference_type: str,
        reference_id: str,
        idempotency_key: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Wallet credit amount must be positive")
        if transaction_type not in {"topup", "reward", "adjustment"}:
            raise ValueError("Unsupported wallet credit type")

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goo_wallets (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO goo_transactions (
                    user_id, amount, transaction_type, reference_type,
                    reference_id, idempotency_key, metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING transaction_id
                """,
                (
                    user_id,
                    amount,
                    transaction_type,
                    reference_type,
                    reference_id,
                    idempotency_key,
                    Jsonb(dict(metadata or {})),
                ),
            )
            inserted = cur.fetchone() is not None
            if inserted:
                cur.execute(
                    """
                    UPDATE goo_wallets
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (amount, user_id),
                )
            cur.execute(
                """
                SELECT balance, reserved_balance
                FROM goo_wallets
                WHERE user_id = %s
                """,
                (user_id,),
            )
            wallet = cur.fetchone()

        return {
            "user_id": user_id,
            "balance": int(wallet["balance"]),
            "reserved_balance": int(wallet["reserved_balance"]),
            "credited": inserted,
        }

    def grant_event_reward(
        self,
        *,
        user_id: int,
        registration_id: int,
        event_id: int,
        event_ended_at: datetime,
        weekly_limit: int = 2,
    ) -> dict[str, Any]:
        """Grant one attendance point, idempotently, within the event's Taipei week."""
        if registration_id <= 0 or event_id <= 0:
            raise ValueError("Event reward references must be positive")
        if event_ended_at.tzinfo is None or event_ended_at.utcoffset() is None:
            raise ValueError("Event end time must be timezone-aware")
        if weekly_limit <= 0:
            raise ValueError("Weekly reward limit must be positive")

        taipei = ZoneInfo("Asia/Taipei")
        local_end = event_ended_at.astimezone(taipei)
        week_start = local_end.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) - timedelta(days=local_end.weekday())
        next_week = week_start + timedelta(days=7)
        idempotency_key = f"event_reward:registration:{registration_id}"

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goo_wallets (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            # One wallet row serializes simultaneous reward attempts for this user.
            cur.execute(
                """
                SELECT balance, reserved_balance
                FROM goo_wallets
                WHERE user_id = %s
                FOR UPDATE
                """,
                (user_id,),
            )
            wallet = cur.fetchone()
            cur.execute(
                """
                SELECT amount, metadata_json
                FROM goo_transactions
                WHERE idempotency_key = %s
                """,
                (idempotency_key,),
            )
            existing = cur.fetchone()
            if existing is not None:
                existing_status = (existing.get("metadata_json") or {}).get(
                    "reward_status",
                    "awarded" if int(existing["amount"]) > 0 else "weekly_limit",
                )
                return {
                    "user_id": user_id,
                    "balance": int(wallet["balance"]),
                    "reserved_balance": int(wallet["reserved_balance"]),
                    "credited": False,
                    "status": "already_awarded" if int(existing["amount"]) > 0 else existing_status,
                    "weekly_limit": weekly_limit,
                }

            cur.execute(
                """
                SELECT COUNT(*) AS reward_count
                FROM goo_transactions
                WHERE user_id = %s
                  AND transaction_type = 'reward'
                  AND reference_type = 'event_registration'
                  AND amount > 0
                  AND created_at >= %s
                  AND created_at < %s
                """,
                (user_id, week_start, next_week),
            )
            awarded_before = int(cur.fetchone()["reward_count"])
            awarded = awarded_before < weekly_limit
            reward_status = "awarded" if awarded else "weekly_limit"
            amount = 1 if awarded else 0
            cur.execute(
                """
                INSERT INTO goo_transactions (
                    user_id, amount, transaction_type, reference_type,
                    reference_id, idempotency_key, metadata_json, created_at
                )
                VALUES (%s, %s, 'reward', 'event_registration', %s, %s, %s, %s)
                """,
                (
                    user_id,
                    amount,
                    str(registration_id),
                    idempotency_key,
                    Jsonb({
                        "event_id": event_id,
                        "registration_id": registration_id,
                        "reward_status": reward_status,
                        "reward_week_start": week_start.date().isoformat(),
                    }),
                    event_ended_at,
                ),
            )
            if awarded:
                cur.execute(
                    """
                    UPDATE goo_wallets
                    SET balance = balance + 1, updated_at = NOW()
                    WHERE user_id = %s
                    RETURNING balance, reserved_balance
                    """,
                    (user_id,),
                )
                wallet = cur.fetchone()

        return {
            "user_id": user_id,
            "balance": int(wallet["balance"]),
            "reserved_balance": int(wallet["reserved_balance"]),
            "credited": awarded,
            "status": reward_status,
            "weekly_awarded": awarded_before + (1 if awarded else 0),
            "weekly_limit": weekly_limit,
        }

    def _reserve_analysis_charge(
        self,
        cur,
        *,
        user_id: int,
        analysis_id: int,
        analysis_type: str,
    ) -> dict[str, Any]:
        cur.execute(
            """
            INSERT INTO goo_wallets (user_id)
            VALUES (%s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id,),
        )
        cur.execute(
            """
            SELECT balance, reserved_balance
            FROM goo_wallets
            WHERE user_id = %s
            FOR UPDATE
            """,
            (user_id,),
        )
        wallet = cur.fetchone()
        cur.execute(
            """
            SELECT 1
            FROM analysis_charges
            WHERE user_id = %s
              AND analysis_type = %s
              AND charge_kind = 'first_free'
              AND status IN ('reserved', 'consumed')
            LIMIT 1
            """,
            (user_id, analysis_type),
        )
        first_free_used = cur.fetchone() is not None

        if not first_free_used:
            charge_kind = "first_free"
            points = 0
            entitlement_id = None
        else:
            cur.execute(
                """
                SELECT entitlement_id
                FROM analysis_entitlements
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND status = 'available'
                ORDER BY created_at, entitlement_id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (user_id, analysis_type),
            )
            entitlement = cur.fetchone()
            if entitlement:
                charge_kind = "direct_purchase"
                points = 0
                entitlement_id = int(entitlement["entitlement_id"])
                cur.execute(
                    """
                    UPDATE analysis_entitlements
                    SET status = 'reserved', analysis_id = %s, updated_at = NOW()
                    WHERE entitlement_id = %s AND status = 'available'
                    """,
                    (analysis_id, entitlement_id),
                )
            else:
                charge_kind = "points"
                points = self.analysis_price
                entitlement_id = None
                if int(wallet["balance"]) < points:
                    raise InsufficientGooPointsError(wallet["balance"], points)
                cur.execute(
                    """
                    UPDATE goo_wallets
                    SET balance = balance - %s,
                        reserved_balance = reserved_balance + %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (points, points, user_id),
                )

        cur.execute(
            """
            INSERT INTO analysis_charges (
                analysis_id, user_id, analysis_type, charge_kind, points,
                entitlement_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                analysis_id, user_id, analysis_type, charge_kind, points,
                entitlement_id,
            ),
        )
        return {
            "charge_kind": charge_kind,
            "points": points,
            "entitlement_id": entitlement_id,
        }

    def _settle_analysis_charge(self, cur, analysis_id: int, completed: bool) -> None:
        cur.execute(
            """
            SELECT user_id, analysis_type, charge_kind, points, status,
                   entitlement_id
            FROM analysis_charges
            WHERE analysis_id = %s
            FOR UPDATE
            """,
            (analysis_id,),
        )
        charge = cur.fetchone()
        if charge is None or charge["status"] != "reserved":
            return

        points = int(charge["points"])
        if completed:
            if points:
                cur.execute(
                    """
                    UPDATE goo_wallets
                    SET reserved_balance = reserved_balance - %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (points, charge["user_id"]),
                )
            cur.execute(
                """
                INSERT INTO goo_transactions (
                    user_id, amount, transaction_type, reference_type,
                    reference_id, idempotency_key, metadata_json
                )
                VALUES (%s, %s, 'analysis_debit', 'analysis', %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    charge["user_id"],
                    -points,
                    str(analysis_id),
                    f"analysis:{analysis_id}:debit",
                    Jsonb({
                        "analysis_type": charge["analysis_type"],
                        "charge_kind": charge["charge_kind"],
                    }),
                ),
            )
            status = "consumed"
            if charge["entitlement_id"] is not None:
                cur.execute(
                    """
                    UPDATE analysis_entitlements
                    SET status = 'consumed', consumed_at = NOW(), updated_at = NOW()
                    WHERE entitlement_id = %s AND status = 'reserved'
                    """,
                    (charge["entitlement_id"],),
                )
        else:
            if points:
                cur.execute(
                    """
                    UPDATE goo_wallets
                    SET balance = balance + %s,
                        reserved_balance = reserved_balance - %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (points, points, charge["user_id"]),
                )
            status = "released"
            if charge["entitlement_id"] is not None:
                cur.execute(
                    """
                    UPDATE analysis_entitlements
                    SET status = 'available', analysis_id = NULL, updated_at = NOW()
                    WHERE entitlement_id = %s AND status = 'reserved'
                    """,
                    (charge["entitlement_id"],),
                )

        cur.execute(
            """
            UPDATE analysis_charges
            SET status = %s, settled_at = NOW()
            WHERE analysis_id = %s AND status = 'reserved'
            """,
            (status, analysis_id),
        )

    def create_analysis(
        self,
        *,
        user_id: int,
        analysis_id: int,
        video_url: str,
        analysis_type: str,
        processing_status: str,
        progress: int,
        current_stage: str | None,
        created_at,
        updated_at,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO video_analyses (
                    analysis_id,
                    user_id,
                    video_url,
                    analysis_type,
                    processing_status,
                    progress,
                    current_stage,
                    created_at,
                    updated_at
                )
                VALUES (
                    %(analysis_id)s,
                    %(user_id)s,
                    %(video_url)s,
                    %(analysis_type)s,
                    %(processing_status)s,
                    %(progress)s,
                    %(current_stage)s,
                    %(created_at)s,
                    %(updated_at)s
                )
                """,
                {
                    "analysis_id": analysis_id,
                    "user_id": user_id,
                    "video_url": video_url,
                    "analysis_type": analysis_type,
                    "processing_status": processing_status,
                    "progress": progress,
                    "current_stage": current_stage,
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )
            if self.billing_mode == "free":
                charge = {
                    "charge_kind": "poc_free",
                    "points": 0,
                    "entitlement_id": None,
                }
            else:
                charge = self._reserve_analysis_charge(
                    cur,
                    user_id=user_id,
                    analysis_id=analysis_id,
                    analysis_type=analysis_type,
                )
        return charge

    def get_active_analysis(
        self,
        user_id: int,
    ) -> dict[str, Any] | None:
        """Return the newest unfinished job for one member."""

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT analysis_id
                FROM video_analyses
                WHERE user_id = %s
                  AND processing_status IN ('uploaded', 'queued', 'processing')
                ORDER BY created_at DESC, analysis_id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None
        return self.get_analysis(int(row["analysis_id"]))

    def expire_stale_analyses(
        self,
        user_id: int,
        *,
        max_age_minutes: int = 30,
    ) -> list[int]:
        safe_minutes = max(5, min(int(max_age_minutes), 180))

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET processing_status = 'failed',
                    progress = 100,
                    current_stage = 'timeout',
                    error_message = %s,
                    updated_at = NOW(),
                    completed_at = NOW()
                WHERE user_id = %s
                  AND processing_status IN ('uploaded', 'queued', 'processing')
                  AND updated_at < NOW() - (%s * INTERVAL '1 minute')
                RETURNING analysis_id
                """,
                (
                    "分析工作超過預期時間且已停止更新，請重新上傳影片。",
                    user_id,
                    safe_minutes,
                ),
            )
            rows = cur.fetchall()
            for row in rows:
                self._settle_analysis_charge(
                    cur,
                    int(row["analysis_id"]),
                    completed=False,
                )

        return [int(row["analysis_id"]) for row in rows]

    def expire_stale_assessment(
        self,
        analysis_id: int,
        *,
        max_age_minutes: int = 30,
    ) -> bool:
        safe_minutes = max(5, min(int(max_age_minutes), 180))

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET processing_status = 'failed',
                    progress = 100,
                    current_stage = 'timeout',
                    error_message = %s,
                    updated_at = NOW(),
                    completed_at = NOW()
                WHERE analysis_id = %s
                  AND processing_status IN ('uploaded', 'queued', 'processing')
                  AND updated_at < NOW() - (%s * INTERVAL '1 minute')
                """,
                (
                    "分析工作超過預期時間且已停止更新，請重新上傳影片。",
                    analysis_id,
                    safe_minutes,
                ),
            )
            expired = cur.rowcount == 1
            if expired:
                self._settle_analysis_charge(
                    cur,
                    analysis_id,
                    completed=False,
                )
            return expired

    def update_status(
        self,
        analysis_id: int,
        *,
        processing_status: str,
        progress: int,
        current_stage: str | None,
        updated_at,
        completed_at=None,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    processing_status = %(processing_status)s,
                    progress = %(progress)s,
                    current_stage = %(current_stage)s,
                    error_message = %(error_message)s,
                    updated_at = %(updated_at)s,
                    completed_at = %(completed_at)s
                WHERE analysis_id = %(analysis_id)s
                """,
                {
                    "analysis_id": analysis_id,
                    "processing_status": processing_status,
                    "progress": progress,
                    "current_stage": current_stage,
                    "error_message": error_message,
                    "updated_at": updated_at,
                    "completed_at": completed_at,
                },
            )
            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{analysis_id}"
                )
            if processing_status == "completed":
                self._settle_analysis_charge(cur, analysis_id, completed=True)
            elif processing_status == "failed":
                self._settle_analysis_charge(cur, analysis_id, completed=False)

    @staticmethod
    def _overall_score(report: Mapping[str, Any]) -> float | None:
        summary = report.get("summary")
        if isinstance(summary, Mapping):
            value = summary.get("overall_score")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)

        result_summary = report.get("result_summary")
        if isinstance(result_summary, Mapping):
            overall = result_summary.get("overall")
            if isinstance(overall, Mapping):
                value = overall.get("score")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)

        return None

    @staticmethod
    def _feedback(report: Mapping[str, Any]) -> str | None:
        coach = report.get("coach")
        if isinstance(coach, Mapping):
            value = coach.get("overall_message")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def save_report(
        self,
        analysis_id: int,
        report: Mapping[str, Any],
    ) -> None:
        meta = report.get("meta")
        meta = meta if isinstance(meta, Mapping) else {}

        model_version = (
            meta.get("engine_version")
            or report.get("engine_version")
        )
        rule_version = (
            meta.get("config_version")
            or report.get("config_version")
        )

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    overall_score = %(overall_score)s,
                    metrics_json = %(metrics_json)s,
                    feedback = %(feedback)s,
                    model_version = %(model_version)s,
                    rule_version = %(rule_version)s,
                    updated_at = NOW()
                WHERE analysis_id = %(analysis_id)s
                """,
                {
                    "analysis_id": analysis_id,
                    "overall_score": self._overall_score(report),
                    "metrics_json": Jsonb(dict(report)),
                    "feedback": self._feedback(report),
                    "model_version": model_version,
                    "rule_version": rule_version,
                },
            )
            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{analysis_id}"
                )

    def update_video_reference(
        self,
        analysis_id: int,
        video_path: str,
    ) -> None:
        """Update the analysis source path after video normalization."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    video_url = %s,
                    updated_at = NOW()
                WHERE analysis_id = %s
                """,
                (video_path, analysis_id),
            )

            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{analysis_id}"
                )

    def clear_video_reference(
        self,
        analysis_id: int,
    ) -> None:
        """清除已完成分析的暫存影片路徑。"""

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_analyses
                SET
                    video_url = NULL,
                    updated_at = NOW()
                WHERE analysis_id = %s
                """,
                (analysis_id,),
            )

            if cur.rowcount != 1:
                raise KeyError(
                    f"找不到 VIDEO_ANALYSES：{analysis_id}"
                )

    def get_analysis(
        self,
        analysis_id: int,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    analysis_id,
                    user_id,
                    video_url,
                    analysis_type,
                    processing_status,
                    progress,
                    current_stage,
                    overall_score,
                    error_message,
                    created_at,
                    updated_at,
                    completed_at
                FROM video_analyses
                WHERE analysis_id = %s
                """,
                (analysis_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "analysis_id": row["analysis_id"],
            "assessment_id": row["analysis_id"],
            "user_id": row["user_id"],
            "assessment_type": row["analysis_type"],
            "status": row["processing_status"],
            "progress": row["progress"],
            "current_stage": row["current_stage"],
            "overall_score": (
                float(row["overall_score"])
                if row["overall_score"] is not None
                else None
            ),
            "video_path": row["video_url"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "completed_at": (
                row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None
            ),
            "failure": (
                {
                    "code": (
                        "INPUT_VALIDATION_FAILED"
                        if row["current_stage"] == "input_validation"
                        else "ANALYSIS_FAILED"
                    ),
                    "message": row["error_message"],
                    "retryable": True,
                }
                if row["error_message"]
                else None
            ),
        }

    def get_report(
        self,
        analysis_id: int,
        analysis_type: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            if analysis_type is None:
                cur.execute(
                    """
                    SELECT metrics_json
                    FROM video_analyses
                    WHERE analysis_id = %s
                    """,
                    (analysis_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT metrics_json
                    FROM video_analyses
                    WHERE analysis_id = %s
                      AND analysis_type = %s
                    """,
                    (analysis_id, analysis_type),
                )
            row = cur.fetchone()

        if row is None or row["metrics_json"] is None:
            return None
        return dict(row["metrics_json"])

    def get_latest_motion(
        self,
        user_id: int,
        motion_type: str,
    ) -> dict[str, Any] | None:
        """取得使用者某一 Motion 最新的已完成分析。"""

        normalized_type = motion_type.strip().lower()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    analysis_id,
                    analysis_type,
                    processing_status,
                    overall_score,
                    metrics_json,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND processing_status = 'completed'
                  AND metrics_json IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, normalized_type),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "assessment_id": row["analysis_id"],
            "assessment_type": row["analysis_type"],
            "status": row["processing_status"],
            "overall_score": (
                float(row["overall_score"])
                if row["overall_score"] is not None
                else None
            ),
            "report": dict(row["metrics_json"]),
            "created_at": row["created_at"].isoformat(),
            "completed_at": (
                row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None
            ),
        }

    def get_previous_motion(
        self,
        user_id: int,
        motion_type: str,
    ) -> dict[str, Any] | None:
        """取得某一 Motion 前一次已完成且具有完整 Report 的結果。"""

        normalized_type = motion_type.strip().lower()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    analysis_id,
                    analysis_type,
                    processing_status,
                    overall_score,
                    metrics_json,
                    model_version,
                    rule_version,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND processing_status = 'completed'
                  AND metrics_json IS NOT NULL
                ORDER BY created_at DESC, analysis_id DESC
                LIMIT 1 OFFSET 1
                """,
                (user_id, normalized_type),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return {
            "assessment_id": row["analysis_id"],
            "assessment_type": row["analysis_type"],
            "status": row["processing_status"],
            "overall_score": (
                float(row["overall_score"])
                if row["overall_score"] is not None
                else None
            ),
            "report": dict(row["metrics_json"]),
            "model_version": row["model_version"],
            "rule_version": row["rule_version"],
            "created_at": row["created_at"].isoformat(),
            "completed_at": (
                row["completed_at"].isoformat()
                if row["completed_at"] is not None
                else None
            ),
        }

    def get_latest_required_motions(
        self,
        user_id: int,
    ) -> dict[str, dict[str, Any]]:
        """取得 Competency Profile 所需三種 Motion 的最新完成結果。"""

        required = ("footwork", "serve", "clear")
        result: dict[str, dict[str, Any]] = {}

        for motion_type in required:
            item = self.get_latest_motion(
                user_id,
                motion_type,
            )
            if item is not None:
                result[motion_type] = item

        return result


    def get_motion_history(
        self,
        user_id: int,
        motion_type: str,
    ) -> list[dict[str, Any]]:
        """取得同一使用者、同一 Motion 的完整已完成 Assessment History。

        Progress Engine V2 需要永久保存的總分、版本資訊，
        以及 Report JSON 中的 dimension score evidence。
        不需要讀取 AI Coach 文字。
        """

        normalized_type = motion_type.strip().lower()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    analysis_id,
                    analysis_type,
                    overall_score,
                    metrics_json,
                    model_version,
                    rule_version,
                    created_at,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                  AND analysis_type = %s
                  AND processing_status = 'completed'
                  AND overall_score IS NOT NULL
                  AND metrics_json IS NOT NULL
                ORDER BY created_at ASC, analysis_id ASC
                """,
                (user_id, normalized_type),
            )
            rows = cur.fetchall()

        return [
            {
                "assessment_id": row["analysis_id"],
                "motion_type": row["analysis_type"],
                "assessment_type": row["analysis_type"],
                "overall_score": float(row["overall_score"]),
                "report": dict(row["metrics_json"]),
                "model_version": row["model_version"],
                "rule_version": row["rule_version"],
                "created_at": row["created_at"].isoformat(),
                "completed_at": (
                    row["completed_at"].isoformat()
                    if row["completed_at"] is not None
                    else None
                ),
            }
            for row in rows
        ]

    def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    analysis_id,
                    analysis_type,
                    processing_status,
                    progress,
                    current_stage,
                    overall_score,
                    created_at,
                    updated_at,
                    error_message,
                    completed_at
                FROM video_analyses
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, safe_limit),
            )
            rows = cur.fetchall()

        return [
            {
                "assessment_id": row["analysis_id"],
                "assessment_type": row["analysis_type"],
                "status": row["processing_status"],
                "progress": row["progress"],
                "current_stage": row["current_stage"],
                "overall_score": (
                    float(row["overall_score"])
                    if row["overall_score"] is not None
                    else None
                ),
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "failure": (
                    {
                        "code": (
                            "ANALYSIS_TIMEOUT"
                            if row["current_stage"] == "timeout"
                            else "ANALYSIS_FAILED"
                        ),
                        "message": row["error_message"],
                        "retryable": True,
                    }
                    if row["error_message"]
                    else None
                ),
                "completed_at": (
                    row["completed_at"].isoformat()
                    if row["completed_at"] is not None
                    else None
                ),
            }
            for row in rows
        ]
