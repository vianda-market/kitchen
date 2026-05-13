-- Migration 0012: Add canonical_key to ops.vianda_kitchen_days
-- Part of umbrella issue #190 (entity 8 of 9): idempotent fixture upsert endpoint.
-- Adds a nullable canonical_key column to ops.vianda_kitchen_days and mirrors it
-- in the audit history table. A sparse unique partial index enforces uniqueness
-- without blocking ad-hoc (non-canonical) rows.
-- Canonical keys follow the pattern: E2E_PKD_{VIANDA_SLUG}_{DAY}
-- Example: E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY

ALTER TABLE ops.vianda_kitchen_days
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

COMMENT ON COLUMN ops.vianda_kitchen_days.canonical_key IS
'Optional stable identifier for seed/fixture rows managed by '
'PUT /vianda-kitchen-days/by-key. NULL for ad-hoc rows created by suppliers. '
'When set, must be UPPER_SNAKE_CASE and unique across all non-NULL rows '
'(enforced by the uq_vianda_kitchen_days_canonical_key partial index).';

-- Mirror the column in the audit history table so triggers keep working.
ALTER TABLE audit.vianda_kitchen_days_history
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

COMMENT ON COLUMN audit.vianda_kitchen_days_history.canonical_key IS
'Mirror of ops.vianda_kitchen_days.canonical_key at the time of this history event.';

-- Sparse unique index: canonical_key is unique when not null.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vianda_kitchen_days_canonical_key
ON ops.vianda_kitchen_days (canonical_key)
WHERE canonical_key IS NOT NULL;
