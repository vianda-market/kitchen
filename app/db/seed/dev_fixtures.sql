-- Dev-only test fixtures.
-- Loaded by build_kitchen_db.sh in dev environments only.
-- Never loaded in staging or production.
--
-- Add test restaurants, sample subscriptions, orders, and other scenario
-- data here. This file is NOT applied by migrate.sh.
--
-- Keep reference data (markets, currencies, system users, cuisines) in
-- reference_data.sql — that data is required in every environment.

SET search_path = core, ops, customer, billing, audit, public;

-- (no dev fixtures yet — add test scenarios here as needed)
