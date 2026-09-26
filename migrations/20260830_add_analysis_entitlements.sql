BEGIN;

CREATE TABLE IF NOT EXISTS analysis_entitlements (
    entitlement_id bigserial PRIMARY KEY,
    payment_order_id varchar(100) NOT NULL UNIQUE,
    user_id bigint NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    analysis_type varchar(20) NOT NULL CHECK (analysis_type IN ('footwork', 'serve', 'clear')),
    amount_twd integer NOT NULL CHECK (amount_twd > 0),
    status varchar(20) NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'reserved', 'consumed')),
    analysis_id bigint UNIQUE REFERENCES video_analyses(analysis_id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    consumed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_analysis_entitlements_available
    ON analysis_entitlements (user_id, analysis_type, created_at)
    WHERE status = 'available';

ALTER TABLE analysis_charges
    ADD COLUMN IF NOT EXISTS entitlement_id bigint
        REFERENCES analysis_entitlements(entitlement_id) ON DELETE RESTRICT;

ALTER TABLE analysis_charges DROP CONSTRAINT IF EXISTS analysis_charges_charge_kind_check;
ALTER TABLE analysis_charges ADD CONSTRAINT analysis_charges_charge_kind_check
    CHECK (charge_kind IN ('first_free', 'points', 'direct_purchase'));

COMMIT;
