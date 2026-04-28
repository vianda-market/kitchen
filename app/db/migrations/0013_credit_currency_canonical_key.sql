-- Migration 0013: Add canonical_key to core.currency_metadata
--
-- Adds a nullable canonical_key column so credit currencies can be
-- idempotently upserted via PUT /api/v1/credit-currencies/by-key.
--
-- canonical_key is SEPARATE from currency_code:
--   • currency_code  — ISO 4217 natural identifier (e.g. 'ARS')
--   • canonical_key  — seed-fixture identifier (e.g. 'E2E_CURRENCY_ARS')
--
-- The sparse partial unique index ensures uniqueness only when non-null,
-- preserving the ability to have many ad-hoc rows without a canonical_key.
--
-- Issue: vianda-market/kitchen#190

ALTER TABLE core.currency_metadata
    ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

COMMENT ON COLUMN core.currency_metadata.canonical_key IS
    'Stable seed-fixture identifier for this currency row (e.g. E2E_CURRENCY_ARS). '
    'NULL for ad-hoc currencies created via POST /credit-currencies. '
    'When set, the PUT /credit-currencies/by-key upsert endpoint uses this key '
    'to decide insert-vs-update so the same currency is never duplicated across '
    'Postman / seed runs. Separate from currency_code (the ISO 4217 natural key).';

-- Mirror the column into the audit history table so history snapshots are complete.
ALTER TABLE audit.currency_metadata_history
    ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;
