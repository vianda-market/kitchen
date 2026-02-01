-- app/db/tests/02_initial_seeds.sql
BEGIN;

-- 1. Ensure pgTAP is available
CREATE EXTENSION IF NOT EXISTS pgtap;
\set VERBOSITY verbose

SELECT diag('Testing initial seed data for roles, users, institutions, and currencies');

-- 2. Declare how many tests we expect
--    3 counts + 3 existence checks = 6 (removed role_info tests)
SELECT plan(6);

-- 3. Clean slate for just these tables
TRUNCATE user_info, institution_info, credit_currency_info CASCADE;

-- 4. Run your real seed
\i app/db/seed.sql

-- 5a. Correct row counts
-- role_info test removed - table deprecated
SELECT is((SELECT count(*) FROM user_info)::integer,            2, 'user_info has 2 seeded rows');
SELECT is((SELECT count(*) FROM institution_info)::integer,     2, 'institution_info has 2 seeded rows');
SELECT is((SELECT count(*) FROM credit_currency_info)::integer, 3, 'credit_currency_info has 3 seeded rows');


-- 5b. Specific rows exist
-- role_info existence test removed - table deprecated

SELECT ok(
  EXISTS(
    SELECT 1 FROM user_info
    WHERE user_id = '11111111-1111-1111-1111-111111111111'
  ),
  'Admin user seeded'
);

SELECT ok(
  EXISTS(
    SELECT 1 FROM institution_info
    WHERE institution_id = '33333333-3333-3333-3333-333333333333'
  ),
  'Vianda Enterprises seeded'
);

SELECT ok(
  EXISTS(
    SELECT 1 FROM credit_currency_info
    WHERE currency_code = 'USD'
  ),
  'USD currency seeded'
);

SELECT * FROM finish();

ROLLBACK;
