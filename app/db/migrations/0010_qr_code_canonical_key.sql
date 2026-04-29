-- Migration 0010: Add canonical_key to ops.qr_code
-- Supports idempotent seed upserts via PUT /api/v1/qr-codes/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_QR_CAMBALACHE'). NULL for QR codes without a canonical key
-- (all pre-existing QR codes and any QR codes created via POST /qr-codes).

ALTER TABLE ops.qr_code
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two QR codes cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_qr_code_canonical_key
ON ops.qr_code (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.qr_code.canonical_key IS
'Optional stable human-readable identifier for seed/fixture QR codes '
'(e.g. ''E2E_QR_CAMBALACHE''). Used by the '
'PUT /api/v1/qr-codes/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc QR codes created via the normal POST endpoint.';
