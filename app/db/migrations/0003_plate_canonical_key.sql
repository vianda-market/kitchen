-- Migration 0003: Add canonical_key to plate_info
-- Supports idempotent seed upserts via PUT /api/v1/plates/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA'). NULL for plates without a
-- canonical key (all pre-existing plates and any supplier-created ad hoc plate).

ALTER TABLE ops.plate_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two plates cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_plate_info_canonical_key
ON ops.plate_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.plate_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture plates '
'(e.g. ''RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA''). Used by the '
'PUT /api/v1/plates/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc plates created via the normal POST endpoint.';
