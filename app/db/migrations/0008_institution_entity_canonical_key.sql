-- Migration 0008: Add canonical_key to institution_entity_info
-- Supports idempotent seed upserts via PUT /api/v1/institution-entities/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_INSTITUTION_ENTITY_SUPPLIER'). NULL for entities without a
-- canonical key (all pre-existing entities and any admin-created ad-hoc entity).

ALTER TABLE ops.institution_entity_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two institution entities cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_institution_entity_info_canonical_key
ON ops.institution_entity_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.institution_entity_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture institution entities '
'(e.g. ''E2E_INSTITUTION_ENTITY_SUPPLIER''). Used by the '
'PUT /api/v1/institution-entities/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc entities created via the normal POST endpoint.';
