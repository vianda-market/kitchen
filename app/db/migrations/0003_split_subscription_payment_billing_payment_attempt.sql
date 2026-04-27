-- Migration 0003: Split customer.subscription_payment + add billing.payment_attempt
-- Phase 1 (issue #74): ADD new billing.payment_attempt table with enum types and audit mirror.
-- ADD payment_attempt_id (FK, nullable) and attempt_number columns to customer.subscription_payment.
-- Old columns (payment_provider, external_payment_id, status, amount_cents, currency) are
-- KEPT in this migration -- they will be dropped in Phase 2 after cron + webhook are refactored.
--
-- The billing schema already exists; no CREATE SCHEMA needed.

-- ---------------------------------------------------------------------------
-- 1. New enum types
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_provider_enum') THEN
        CREATE TYPE payment_provider_enum AS ENUM ('stripe', 'mercado_pago');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_attempt_status_enum') THEN
        CREATE TYPE payment_attempt_status_enum AS ENUM (
            'pending',
            'processing',
            'succeeded',
            'failed',
            'cancelled',
            'refunded'
        );
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- 2. billing.payment_attempt (financial record -- provider-specific)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS billing.payment_attempt (
    payment_attempt_id UUID PRIMARY KEY DEFAULT uuidv7(),
    provider payment_provider_enum NOT NULL, -- noqa: CP05,RF04
    provider_payment_id TEXT NULL,
    idempotency_key TEXT NULL,
    amount_cents INTEGER NOT NULL,
    currency CHAR(3) NOT NULL,
    payment_status payment_attempt_status_enum NOT NULL DEFAULT 'pending', -- noqa: CP05
    provider_status TEXT NULL,
    failure_reason TEXT NULL,
    provider_fee_cents INTEGER NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum, -- noqa: CP05
    created_date TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_payment_attempt_provider_payment_id
ON billing.payment_attempt (provider_payment_id)
WHERE provider_payment_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payment_attempt_payment_status
ON billing.payment_attempt (payment_status);

COMMENT ON TABLE billing.payment_attempt IS
'Financial record for a single payment attempt. Provider-specific: one row per attempt '
'regardless of provider (Stripe, Mercado Pago, etc.). Written by webhook handlers. '
'Linked to customer.subscription_payment via payment_attempt_id FK.';

COMMENT ON COLUMN billing.payment_attempt.payment_attempt_id IS
'UUIDv7 primary key. Time-ordered.';

COMMENT ON COLUMN billing.payment_attempt.provider IS
'Payment provider that processed this attempt.';

COMMENT ON COLUMN billing.payment_attempt.provider_payment_id IS
'Provider-assigned ID (e.g. Stripe pi_...). Indexed for webhook lookup.';

COMMENT ON COLUMN billing.payment_attempt.idempotency_key IS
'Idempotency key sent to the provider to prevent duplicate charges.';

COMMENT ON COLUMN billing.payment_attempt.amount_cents IS
'Charge amount in smallest currency unit.';

COMMENT ON COLUMN billing.payment_attempt.currency IS
'ISO 4217 3-letter currency code.';

COMMENT ON COLUMN billing.payment_attempt.payment_status IS
'Financial state of this attempt.';

COMMENT ON COLUMN billing.payment_attempt.provider_status IS
'Raw status string from the provider (debug/fidelity).';

COMMENT ON COLUMN billing.payment_attempt.failure_reason IS
'Human-readable failure reason from the provider, if failed.';

COMMENT ON COLUMN billing.payment_attempt.provider_fee_cents IS
'Provider transaction fee in smallest currency unit, if known.';

COMMENT ON COLUMN billing.payment_attempt.status IS
'Admin/audit lifecycle status (active/inactive). Separate from payment_status.';

-- ---------------------------------------------------------------------------
-- 3. audit.payment_attempt_history (trigger-managed mirror)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.payment_attempt_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    payment_attempt_id UUID NOT NULL,
    provider payment_provider_enum NOT NULL, -- noqa: CP05,RF04
    provider_payment_id TEXT NULL,
    idempotency_key TEXT NULL,
    amount_cents INTEGER NOT NULL,
    currency CHAR(3) NOT NULL,
    payment_status payment_attempt_status_enum NOT NULL, -- noqa: CP05
    provider_status TEXT NULL,
    failure_reason TEXT NULL,
    provider_fee_cents INTEGER NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL, -- noqa: CP05
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (payment_attempt_id)
    REFERENCES billing.payment_attempt (payment_attempt_id) ON DELETE RESTRICT
);

COMMENT ON TABLE audit.payment_attempt_history IS
'Trigger-managed history mirror of billing.payment_attempt. Never written by application code.';

COMMENT ON COLUMN audit.payment_attempt_history.event_id IS
'UUIDv7 primary key for this history row. Time-ordered.';

COMMENT ON COLUMN audit.payment_attempt_history.is_current IS
'TRUE while this row represents the current state of the source row. FALSE when superseded.';

COMMENT ON COLUMN audit.payment_attempt_history.valid_until IS
'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- ---------------------------------------------------------------------------
-- 4. Audit trigger function + binding
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION payment_attempt_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.payment_attempt_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE payment_attempt_id = OLD.payment_attempt_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.payment_attempt_history (
        event_id,
        payment_attempt_id,
        provider,
        provider_payment_id,
        idempotency_key,
        amount_cents,
        currency,
        payment_status,
        provider_status,
        failure_reason,
        provider_fee_cents,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.payment_attempt_id,
        NEW.provider,
        NEW.provider_payment_id,
        NEW.idempotency_key,
        NEW.amount_cents,
        NEW.currency,
        NEW.payment_status,
        NEW.provider_status,
        NEW.failure_reason,
        NEW.provider_fee_cents,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS payment_attempt_history_trigger ON billing.payment_attempt;
CREATE TRIGGER payment_attempt_history_trigger
AFTER INSERT OR UPDATE ON billing.payment_attempt
FOR EACH ROW
EXECUTE FUNCTION payment_attempt_history_trigger_func();

-- ---------------------------------------------------------------------------
-- 5. Add FK + attempt_number columns to customer.subscription_payment
--    Phase 1: nullable; existing rows unaffected; old columns kept for Phase 2.
-- ---------------------------------------------------------------------------

ALTER TABLE customer.subscription_payment ADD COLUMN IF NOT EXISTS payment_attempt_id UUID NULL;

ALTER TABLE customer.subscription_payment
ADD CONSTRAINT fk_sp_payment_attempt_id
FOREIGN KEY (payment_attempt_id) REFERENCES billing.payment_attempt (payment_attempt_id) ON DELETE RESTRICT;

ALTER TABLE customer.subscription_payment
ADD COLUMN IF NOT EXISTS attempt_number INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_subscription_payment_attempt_id
ON customer.subscription_payment (payment_attempt_id)
WHERE payment_attempt_id IS NOT NULL;

COMMENT ON COLUMN customer.subscription_payment.payment_attempt_id IS
'FK to billing.payment_attempt. NULL until the first attempt is linked. '
'Phase 1: nullable. Phase 2: NOT NULL after cron + webhook are refactored.';

COMMENT ON COLUMN customer.subscription_payment.attempt_number IS
'Attempt counter (1-based). 1 for the initial attempt; increments on retry.';
