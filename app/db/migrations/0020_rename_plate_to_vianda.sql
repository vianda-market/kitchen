-- Migration 0020: Rename plate → vianda (DB teardown + rebuild).
--
-- This migration renames every plate_* table, column, trigger, and function
-- to the vianda_* namespace, matching the brand rename in kitchen#273.
--
-- STRATEGY: teardown + rebuild (no data preservation).
--   This migration drops all plate_* tables (cascading) and recreates them
--   under the vianda_* names via the updated schema.sql / trigger.sql /
--   index.sql files. Any existing data in these tables is lost.
--
-- APPLY:
--   Simplest path — full DB rebuild:
--     bash app/db/build_kitchen_db.sh   # for local dev
--     bash app/db/build_dev_db.sh       # for the dev environment
--   On environments that cannot tolerate a full rebuild, run the explicit
--   rename block below (requires superuser for trigger/function recreation).
--
-- ─── Explicit rename path (data-destructive) ──────────────────────────────

-- 1. Drop old triggers first to avoid FK/trigger cascade conflicts.
DROP TRIGGER IF EXISTS vianda_info_set_expected_payout_local_currency_trigger ON ops.vianda_info;
DROP TRIGGER IF EXISTS vianda_info_set_expected_payout_local_currency_trigger ON ops.plate_info;
DROP TRIGGER IF EXISTS plate_info_set_expected_payout_local_currency_trigger ON ops.plate_info;
DROP TRIGGER IF EXISTS vianda_history_trigger ON ops.vianda_info;
DROP TRIGGER IF EXISTS vianda_history_trigger ON ops.plate_info;
DROP TRIGGER IF EXISTS plate_history_trigger ON ops.plate_info;
DROP TRIGGER IF EXISTS trg_vianda_selection_ct ON customer.vianda_selection_info;
DROP TRIGGER IF EXISTS trg_plate_selection_ct ON customer.plate_selection_info;
DROP TRIGGER IF EXISTS vianda_selection_history_trigger ON customer.vianda_selection_info;
DROP TRIGGER IF EXISTS plate_selection_history_trigger ON customer.plate_selection_info;
DROP TRIGGER IF EXISTS vianda_kitchen_days_history_trigger ON ops.vianda_kitchen_days;
DROP TRIGGER IF EXISTS plate_kitchen_days_history_trigger ON ops.plate_kitchen_days;

-- 2. Drop old functions.
DROP FUNCTION IF EXISTS plate_info_set_expected_payout_local_currency_func() CASCADE;
DROP FUNCTION IF EXISTS plate_history_trigger_func() CASCADE;
DROP FUNCTION IF EXISTS log_plate_selection_txn() CASCADE;
DROP FUNCTION IF EXISTS plate_selection_history_trigger_func() CASCADE;
DROP FUNCTION IF EXISTS plate_kitchen_days_history_trigger_func() CASCADE;

-- 3. Drop old tables (CASCADE removes FKs in dependent tables).
DROP TABLE IF EXISTS audit.plate_history CASCADE;
DROP TABLE IF EXISTS audit.plate_kitchen_days_history CASCADE;
DROP TABLE IF EXISTS audit.plate_selection_history CASCADE;
DROP TABLE IF EXISTS audit.plate_pickup_live_history CASCADE;
DROP TABLE IF EXISTS customer.plate_review_info CASCADE;
DROP TABLE IF EXISTS customer.plate_pickup_live CASCADE;
DROP TABLE IF EXISTS customer.plate_selection_info CASCADE;
DROP TABLE IF EXISTS ops.plate_kitchen_days CASCADE;
DROP TABLE IF EXISTS ops.plate_info CASCADE;

-- 4. Rename columns on core.user_messaging_preferences that carried plate_ names.
--    (These columns exist only if the DB predates this migration.)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
          AND table_name   = 'user_messaging_preferences'
          AND column_name  = 'notify_plate_readiness_alert'
    ) THEN
        ALTER TABLE core.user_messaging_preferences
            RENAME COLUMN notify_plate_readiness_alert TO notify_vianda_readiness_alert;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'core'
          AND table_name   = 'user_messaging_preferences'
          AND column_name  = 'can_participate_in_plate_pickups'
    ) THEN
        ALTER TABLE core.user_messaging_preferences
            RENAME COLUMN can_participate_in_plate_pickups TO can_participate_in_vianda_pickups;
    END IF;
END $$;

-- 5. Update the status_enum value 'plate' → 'vianda' if it exists.
--    (PostgreSQL does not support renaming enum values before 14; ALTER TYPE … RENAME VALUE
--     is available from PG14. The enum value is stored as text in schema.sql.)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = 'entity_type_enum' AND e.enumlabel = 'plate'
    ) THEN
        UPDATE pg_enum SET enumlabel = 'vianda'
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'entity_type_enum')
          AND enumlabel = 'plate';
    END IF;
END $$;

-- 6. Apply updated schema.sql to create vianda_* tables, then trigger.sql and
--    index.sql for triggers, history tables, and indexes.
--    This step is performed automatically by build_kitchen_db.sh / build_dev_db.sh.
--    When running incremental migrations (migrate.sh), ensure schema.sql, trigger.sql,
--    and index.sql are applied in full after this migration completes.
