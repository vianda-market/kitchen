-- Migration 0010: Add canonical_key to restaurant_holidays
-- Supports idempotent seed upserts via PUT /api/v1/restaurant-holidays/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_HOLIDAY_CAMBALACHE_MAINTENANCE'). NULL for holidays without a
-- canonical key (all pre-existing holidays and any manually created ad-hoc holiday).

ALTER TABLE ops.restaurant_holidays
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two restaurant holidays cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_restaurant_holidays_canonical_key
ON ops.restaurant_holidays (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.restaurant_holidays.canonical_key IS
'Optional stable human-readable identifier for seed/fixture holidays '
'(e.g. ''E2E_HOLIDAY_CAMBALACHE_MAINTENANCE''). Used by the '
'PUT /api/v1/restaurant-holidays/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc holidays created via the normal POST endpoint.';
