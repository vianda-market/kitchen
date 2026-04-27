-- Migration 0002: Add canonical_key to plan_info
-- Supports idempotent seed upserts via PUT /api/v1/plans/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'MARKET_AR_PLAN_STANDARD_50000_ARS'). NULL for plans without a
-- canonical key (all pre-existing plans and any admin-created ad hoc plan).

ALTER TABLE customer.plan_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two plans cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_info_canonical_key
ON customer.plan_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN customer.plan_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture plans '
'(e.g. ''MARKET_AR_PLAN_STANDARD_50000_ARS''). Used by the '
'PUT /api/v1/plans/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc plans created via the normal POST endpoint.';
