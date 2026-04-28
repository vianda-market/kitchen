-- Migration 0007: Add canonical_key to market_info
-- Supports idempotent seed upserts via PUT /api/v1/markets/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_MARKET_AR'). NULL for markets without a canonical key
-- (all pre-existing markets and any admin-created ad-hoc market).

ALTER TABLE core.market_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two markets cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_market_info_canonical_key
ON core.market_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN core.market_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture markets '
'(e.g. ''E2E_MARKET_AR''). Used by the '
'PUT /api/v1/markets/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc markets created via the normal POST endpoint.';
