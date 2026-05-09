-- Migration 0018: Add canonical_key to customer.subscription_info
-- Enables PUT /employer/employee-link/by-key idempotent upsert endpoint.
-- The "employee link" is an employer-sponsored subscription: a Customer Comensal
-- user in an employer institution with an active subscription. The canonical_key
-- identifies the logical fixture row so the demo loader can upsert without
-- accumulating duplicate subscriptions.

-- Add column to main table
ALTER TABLE customer.subscription_info
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Partial unique index (sparse: only indexed when non-null)
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_canonical_key
ON customer.subscription_info (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN customer.subscription_info.canonical_key IS
'Stable human-readable key for idempotent upsert via PUT /employer/employee-link/by-key. '
'NULL for subscriptions created via normal flows (POST /subscriptions, POST /employer/employees/{id}/subscribe). '
'Convention: EMPLOYER_<INSTITUTION_SLUG>_EE_<USERNAME_SLUG>_LINK. '
'Once set, never rename — renaming creates a new row and orphans the old one.';
