-- Migration 0003: Add canonical_key to vianda_info
-- Supports idempotent seed upserts via PUT /api/v1/viandas/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'RESTAURANT_LA_COCINA_PORTENA_VIANDA_BONDIOLA'). NULL for viandas without a
-- canonical key (all pre-existing viandas and any supplier-created ad hoc vianda).

ALTER TABLE ops.vianda_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two viandas cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_vianda_info_canonical_key
ON ops.vianda_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.vianda_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture viandas '
'(e.g. ''RESTAURANT_LA_COCINA_PORTENA_VIANDA_BONDIOLA''). Used by the '
'PUT /api/v1/viandas/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc viandas created via the normal POST endpoint.';
