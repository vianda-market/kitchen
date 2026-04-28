-- Migration 0009: Add canonical_key to product_info
-- Supports idempotent seed upserts via PUT /api/v1/products/by-key.
-- canonical_key is a human-readable, globally unique string identifier
-- (e.g. 'E2E_PRODUCT_BIG_BURGUER'). NULL for products without a canonical key
-- (all pre-existing products and any supplier-created ad-hoc product).

ALTER TABLE ops.product_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Uniqueness: two products cannot share the same canonical key.
-- Partial index to keep it sparse (only indexed when non-null).
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_info_canonical_key
ON ops.product_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN ops.product_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture products '
'(e.g. ''E2E_PRODUCT_BIG_BURGUER''). Used by the '
'PUT /api/v1/products/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc products created via the normal POST endpoint.';
