-- Migration 0004: Add canonical_key to user_info
-- Supports idempotent seed upserts via PUT /api/v1/users/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_USER_SUPPLIER_ADMIN'). NULL for users without a canonical key
-- (all pre-existing users and any user created via the normal POST endpoint).

ALTER TABLE core.user_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two users cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_info_canonical_key
ON core.user_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN core.user_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture users '
'(e.g. ''E2E_USER_SUPPLIER_ADMIN''). Used by the '
'PUT /api/v1/users/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc users created via the normal POST endpoint. '
'Never use this field for self-registration or customer-facing flows.';
