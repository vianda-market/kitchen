-- Migration 0005: Break circular FK between customer.referral_info and billing.client_transaction
--
-- Rationale (kitchen #73):
--   customer.referral_info.transaction_id -> billing.client_transaction (standard FK)
--   billing.client_transaction.referral_id -> customer.referral_info (deferred FK added via ALTER TABLE)
--   This true circular reference required a DEFERRED FK to allow insertion ordering.
--   A bridge table (customer.referral_transaction) decouples both sides, making both FKs
--   non-deferred and removing the tight coupling between the billing and customer schemas.
--
-- Decision: Scenario 2 (true circular FK, both directions confirmed).
--
-- Steps:
--   1. Create customer.referral_transaction bridge table.
--   2. Create audit.referral_transaction_history mirror table.
--   3. Create audit trigger function and binding for the bridge table.
--   4. Backfill: copy existing referral->transaction relationships from customer.referral_info.
--   5. Drop the deferred FK constraint fk_client_transaction_referral from billing.client_transaction.
--   6. Drop the transaction_id column from customer.referral_info (and its audit mirror).
--   7. Drop the referral_id column from billing.client_transaction.
--   8. Add indexes on the bridge table for join performance.
--
-- Rollback notes (manual, data-loss risk if data written after migration):
--   ALTER TABLE customer.referral_info ADD COLUMN transaction_id UUID NULL;
--   ALTER TABLE audit.referral_info_history ADD COLUMN transaction_id UUID NULL;
--   ALTER TABLE billing.client_transaction ADD COLUMN referral_id UUID NULL;
--   (Backfill from customer.referral_transaction then re-add constraints.)
--   DROP TABLE IF EXISTS audit.referral_transaction_history CASCADE;
--   DROP TABLE IF EXISTS customer.referral_transaction CASCADE;

-- ---------------------------------------------------------------------------
-- 1. customer.referral_transaction bridge table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS customer.referral_transaction (
    referral_transaction_id UUID PRIMARY KEY DEFAULT uuidv7(), -- noqa: CP03
    referral_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum, -- noqa: CP05
    created_date TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    FOREIGN KEY (referral_id)
    REFERENCES customer.referral_info (referral_id) ON DELETE RESTRICT,
    FOREIGN KEY (transaction_id)
    REFERENCES billing.client_transaction (transaction_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by)
    REFERENCES core.user_info (user_id) ON DELETE RESTRICT,
    CONSTRAINT uq_referral_transaction_referral_id UNIQUE (referral_id)
);

COMMENT ON TABLE customer.referral_transaction IS
'Bridge table linking a referral reward to its credit transaction. '
'Replaces the former direct FKs on customer.referral_info.transaction_id and '
'billing.client_transaction.referral_id that formed a circular dependency. '
'One row per rewarded referral (UNIQUE on referral_id).';

COMMENT ON COLUMN customer.referral_transaction.referral_transaction_id IS
'UUIDv7 primary key. Time-ordered.';

COMMENT ON COLUMN customer.referral_transaction.referral_id IS
'FK to customer.referral_info. The referral that was rewarded.';

COMMENT ON COLUMN customer.referral_transaction.transaction_id IS
'FK to billing.client_transaction. The credit transaction created for this reward.';

COMMENT ON COLUMN customer.referral_transaction.is_archived IS
'Soft-delete tombstone.';

COMMENT ON COLUMN customer.referral_transaction.status IS
'Row lifecycle from status_enum (active/inactive).';

COMMENT ON COLUMN customer.referral_transaction.created_date IS
'UTC timestamp when the bridge row was created.';

COMMENT ON COLUMN customer.referral_transaction.created_by IS
'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';

COMMENT ON COLUMN customer.referral_transaction.modified_by IS
'FK to core.user_info. UUID of the last actor to write this row.';

COMMENT ON COLUMN customer.referral_transaction.modified_date IS
'UTC timestamp of the most recent update.';

-- ---------------------------------------------------------------------------
-- 2. audit.referral_transaction_history mirror table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.referral_transaction_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(), -- noqa: CP03
    referral_transaction_id UUID NOT NULL,
    referral_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL, -- noqa: CP05
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (referral_transaction_id)
    REFERENCES customer.referral_transaction (referral_transaction_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by)
    REFERENCES core.user_info (user_id) ON DELETE RESTRICT
);

COMMENT ON TABLE audit.referral_transaction_history IS
'Trigger-managed history mirror of customer.referral_transaction. Never written by application code.';

COMMENT ON COLUMN audit.referral_transaction_history.event_id IS
'UUIDv7 primary key for this history row. Time-ordered.';

COMMENT ON COLUMN audit.referral_transaction_history.is_current IS
'TRUE while this row represents the current state of the source row.';

COMMENT ON COLUMN audit.referral_transaction_history.valid_until IS
'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- ---------------------------------------------------------------------------
-- 3. Audit trigger function and binding
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION referral_transaction_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.referral_transaction_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE
            referral_transaction_id = OLD.referral_transaction_id
            AND is_current = TRUE;
    END IF;

    INSERT INTO audit.referral_transaction_history (
        event_id,
        referral_transaction_id,
        referral_id,
        transaction_id,
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
        NEW.referral_transaction_id,
        NEW.referral_id,
        NEW.transaction_id,
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

DROP TRIGGER IF EXISTS referral_transaction_history_trigger
ON customer.referral_transaction;
CREATE TRIGGER referral_transaction_history_trigger
AFTER INSERT OR UPDATE ON customer.referral_transaction
FOR EACH ROW
EXECUTE FUNCTION referral_transaction_history_trigger_func();

-- ---------------------------------------------------------------------------
-- 4. Backfill: copy existing referral->transaction links from referral_info
-- ---------------------------------------------------------------------------

INSERT INTO customer.referral_transaction (
    referral_id,
    transaction_id,
    is_archived,
    status,
    created_by,
    modified_by,
    modified_date
)
SELECT
    ri.referral_id,
    ri.transaction_id,
    FALSE AS is_archived,
    'active'::status_enum AS status, -- noqa: CP05,AL09
    ri.created_by,
    ri.modified_by,
    ri.modified_date
FROM customer.referral_info AS ri
WHERE ri.transaction_id IS NOT NULL
ON CONFLICT (referral_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5. Drop the deferred FK constraint from billing.client_transaction
-- ---------------------------------------------------------------------------

ALTER TABLE billing.client_transaction
DROP CONSTRAINT IF EXISTS fk_client_transaction_referral;

-- ---------------------------------------------------------------------------
-- 6. Drop transaction_id from customer.referral_info and its audit mirror
-- ---------------------------------------------------------------------------

ALTER TABLE customer.referral_info
DROP COLUMN IF EXISTS transaction_id;

ALTER TABLE audit.referral_info_history
DROP COLUMN IF EXISTS transaction_id;

-- ---------------------------------------------------------------------------
-- 7. Drop referral_id from billing.client_transaction
-- ---------------------------------------------------------------------------

ALTER TABLE billing.client_transaction
DROP COLUMN IF EXISTS referral_id;

-- ---------------------------------------------------------------------------
-- 8. Indexes on bridge table for join performance
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_referral_transaction_referral_id
ON customer.referral_transaction (referral_id);

CREATE INDEX IF NOT EXISTS idx_referral_transaction_transaction_id
ON customer.referral_transaction (transaction_id);
