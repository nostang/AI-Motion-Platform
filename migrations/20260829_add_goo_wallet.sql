BEGIN;

CREATE TABLE IF NOT EXISTS goo_wallets (
    user_id bigint PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    balance integer DEFAULT 0 NOT NULL CHECK (balance >= 0),
    reserved_balance integer DEFAULT 0 NOT NULL CHECK (reserved_balance >= 0),
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS goo_transactions (
    transaction_id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    amount integer NOT NULL,
    transaction_type varchar(30) NOT NULL,
    reference_type varchar(30) NOT NULL,
    reference_id varchar(100) NOT NULL,
    idempotency_key varchar(180) NOT NULL UNIQUE,
    metadata_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT goo_transactions_type_check CHECK (
        transaction_type IN ('topup', 'reward', 'analysis_debit', 'adjustment')
    )
);

CREATE TABLE IF NOT EXISTS analysis_charges (
    analysis_id bigint PRIMARY KEY REFERENCES video_analyses(analysis_id) ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    analysis_type varchar(20) NOT NULL,
    charge_kind varchar(20) NOT NULL CHECK (charge_kind IN ('first_free', 'points')),
    points integer DEFAULT 0 NOT NULL CHECK (points >= 0),
    status varchar(20) DEFAULT 'reserved' NOT NULL CHECK (status IN ('reserved', 'consumed', 'released')),
    created_at timestamptz DEFAULT now() NOT NULL,
    settled_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_goo_transactions_user_created
    ON goo_transactions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_charges_user_type
    ON analysis_charges (user_id, analysis_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_analysis_first_free_active
    ON analysis_charges (user_id, analysis_type)
    WHERE charge_kind = 'first_free' AND status IN ('reserved', 'consumed');

COMMIT;
