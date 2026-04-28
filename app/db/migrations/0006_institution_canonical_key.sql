-- Migration 0006: Add canonical_key to institution_info
-- Supports idempotent seed upserts via PUT /api/v1/institutions/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_INSTITUTION_SUPPLIER'). NULL for institutions without a
-- canonical key (all pre-existing institutions and any admin-created ad-hoc institution).

ALTER TABLE core.institution_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two institutions cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_institution_info_canonical_key
ON core.institution_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN core.institution_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture institutions '
'(e.g. ''E2E_INSTITUTION_SUPPLIER''). Used by the '
'PUT /api/v1/institutions/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc institutions created via the normal POST endpoint.';
