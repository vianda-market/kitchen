-- Migration 0004: Move core.restaurant_lead and core.restaurant_lead_cuisine to ops schema
--
-- Rationale (kitchen #72):
--   restaurant_lead is operational signup-flow data (restaurants that have shown interest
--   but have not onboarded yet). core schema is reserved for primary identity tables
--   (users, institutions, markets, etc.). ops schema holds operational state tables.
--
-- Steps:
--   1. Drop the deferred FK constraint on restaurant_lead (reviewed_by to core.user_info)
--      so that SET SCHEMA is clean.
--   2. SET SCHEMA ops on both tables (Postgres moves indexes automatically).
--   3. Recreate the deferred FK constraint against the new schema location.
--
-- Rollback notes (manual):
--   ALTER TABLE ops.restaurant_lead_cuisine SET SCHEMA core;
--   ALTER TABLE ops.restaurant_lead SET SCHEMA core;

-- Step 1: Drop the deferred FK on reviewed_by.
ALTER TABLE core.restaurant_lead DROP CONSTRAINT IF EXISTS fk_restaurant_lead_reviewed_by;

-- Step 2: Move both tables to ops schema.
ALTER TABLE core.restaurant_lead SET SCHEMA ops;
ALTER TABLE core.restaurant_lead_cuisine SET SCHEMA ops;

-- Step 3: Recreate the deferred FK constraint (now on ops.restaurant_lead).
ALTER TABLE ops.restaurant_lead
ADD CONSTRAINT fk_restaurant_lead_reviewed_by
FOREIGN KEY (reviewed_by) REFERENCES core.user_info (user_id) ON DELETE SET NULL;
