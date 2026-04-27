-- Migration 0002: Add window_start / window_end TIMESTAMPTZ columns to plate_pickup_live
-- and create matching audit.plate_pickup_live_history table + trigger.
--
-- Context (kitchen#121):
--   PR #120 renamed pickups.window_from/to → expected_from/to because the underlying
--   column was expected_completion_time, not a real window.
--   This migration adds true window_start / window_end columns so kiosk operators
--   can filter pickups by the scheduled arrival window.
--   Both columns are nullable with no backfill — product decides semantics later.
--
-- Filter rebinding (pickups.expected_from/to → window_start/end) is DEFERRED to a
-- follow-up issue. This migration is schema + audit only.

-- ---------------------------------------------------------------------------
-- 1. Add columns to customer.plate_pickup_live
-- ---------------------------------------------------------------------------

ALTER TABLE customer.plate_pickup_live ADD COLUMN IF NOT EXISTS window_start TIMESTAMPTZ;
ALTER TABLE customer.plate_pickup_live ADD COLUMN IF NOT EXISTS window_end TIMESTAMPTZ;

COMMENT ON COLUMN customer.plate_pickup_live.window_start IS
'Start of the scheduled pickup window (wall-clock). Set when the pickup session '
'is created from reservation data. NULL for pickups created before this column '
'was added, or when no window has been assigned.';

COMMENT ON COLUMN customer.plate_pickup_live.window_end IS
'End of the scheduled pickup window (wall-clock). Paired with window_start. '
'NULL for pickups created before this column was added, or when no window has '
'been assigned.';

-- ---------------------------------------------------------------------------
-- 2. Create audit.plate_pickup_live_history
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.plate_pickup_live_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_pickup_id UUID NOT NULL,
    plate_selection_id UUID NOT NULL,
    user_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    product_id UUID NOT NULL,
    qr_code_id UUID NOT NULL,
    qr_code_payload VARCHAR(255) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum, -- noqa: CP05
    was_collected BOOLEAN DEFAULT FALSE,
    arrival_time TIMESTAMPTZ,
    completion_time TIMESTAMPTZ,
    expected_completion_time TIMESTAMPTZ,
    confirmation_code VARCHAR(10),
    completion_type VARCHAR(20),
    extensions_used INTEGER DEFAULT 0,
    code_verified BOOLEAN DEFAULT FALSE,
    code_verified_time TIMESTAMPTZ,
    handed_out_time TIMESTAMPTZ,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plate_pickup_id)
    REFERENCES customer.plate_pickup_live (plate_pickup_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by)
    REFERENCES core.user_info (user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_pickup_live_history_pickup
ON audit.plate_pickup_live_history (plate_pickup_id)
WHERE is_current = TRUE;

COMMENT ON TABLE audit.plate_pickup_live_history IS
'Trigger-managed history mirror of customer.plate_pickup_live. Never written by application code.';

COMMENT ON COLUMN audit.plate_pickup_live_history.event_id IS
'UUIDv7 primary key for this history row. Time-ordered.';

COMMENT ON COLUMN audit.plate_pickup_live_history.is_current IS
'TRUE while this row represents the current state of the source row. FALSE when superseded.';

COMMENT ON COLUMN audit.plate_pickup_live_history.valid_until IS
'UTC timestamp until which this row was current. ''infinity'' for the current row.';

COMMENT ON COLUMN audit.plate_pickup_live_history.window_start IS
'Mirror of customer.plate_pickup_live.window_start.';

COMMENT ON COLUMN audit.plate_pickup_live_history.window_end IS
'Mirror of customer.plate_pickup_live.window_end.';

-- ---------------------------------------------------------------------------
-- 3. Create / replace the audit trigger function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION plate_pickup_live_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.plate_pickup_live_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_pickup_id = OLD.plate_pickup_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.plate_pickup_live_history (
        event_id,
        plate_pickup_id,
        plate_selection_id,
        user_id,
        restaurant_id,
        plate_id,
        product_id,
        qr_code_id,
        qr_code_payload,
        is_archived,
        status,
        was_collected,
        arrival_time,
        completion_time,
        expected_completion_time,
        confirmation_code,
        completion_type,
        extensions_used,
        code_verified,
        code_verified_time,
        handed_out_time,
        window_start,
        window_end,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.plate_pickup_id,
        NEW.plate_selection_id,
        NEW.user_id,
        NEW.restaurant_id,
        NEW.plate_id,
        NEW.product_id,
        NEW.qr_code_id,
        NEW.qr_code_payload,
        NEW.is_archived,
        NEW.status,
        NEW.was_collected,
        NEW.arrival_time,
        NEW.completion_time,
        NEW.expected_completion_time,
        NEW.confirmation_code,
        NEW.completion_type,
        NEW.extensions_used,
        NEW.code_verified,
        NEW.code_verified_time,
        NEW.handed_out_time,
        NEW.window_start,
        NEW.window_end,
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

DROP TRIGGER IF EXISTS plate_pickup_live_history_trigger ON customer.plate_pickup_live;
CREATE TRIGGER plate_pickup_live_history_trigger
AFTER INSERT OR UPDATE ON customer.plate_pickup_live
FOR EACH ROW
EXECUTE FUNCTION plate_pickup_live_history_trigger_func();
