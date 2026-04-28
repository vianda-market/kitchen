-- Migration 0005: Add canonical_key to restaurant_info
-- Supports idempotent seed upserts via PUT /api/v1/restaurants/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_RESTAURANT_CAMBALACHE'). NULL for restaurants without a
-- canonical key (all pre-existing restaurants and any supplier-created ad-hoc restaurant).

ALTER TABLE ops.restaurant_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two restaurants cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_restaurant_info_canonical_key
ON ops.restaurant_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.restaurant_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture restaurants '
'(e.g. ''E2E_RESTAURANT_CAMBALACHE''). Used by the '
'PUT /api/v1/restaurants/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc restaurants created via the normal POST endpoint.';
