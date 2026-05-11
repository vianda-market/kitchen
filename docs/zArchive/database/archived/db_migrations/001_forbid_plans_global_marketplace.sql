-- Migration: Forbid plans for Global Marketplace
-- Run this on existing databases that may have plans with market_id = Global.
-- 1. Archive existing invalid plans
-- 2. Add CHECK constraint to prevent future inserts

\echo 'Archiving plans with market_id = Global Marketplace...'
UPDATE plan_info
SET is_archived = true, status = 'Inactive'::status_enum
WHERE market_id = '00000000-0000-0000-000000000001'::uuid;

\echo 'Adding CHECK constraint: plan_info.market_id cannot be Global Marketplace'
ALTER TABLE plan_info
ADD CONSTRAINT chk_plan_info_not_global_market
CHECK (market_id != '00000000-0000-0000-000000000001'::uuid);
