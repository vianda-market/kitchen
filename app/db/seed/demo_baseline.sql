-- =============================================================================
-- demo_baseline.sql — Layer A of the demo-day data seed (PE + AR + US, v3)
--
-- Purpose: Inserts only the SQL-only entities that must exist BEFORE the
-- kitchen API is started and the Postman collection runs (Layer B).
--
--   • The demo supplier institution (PE/AR/US markets, shared)
--   • Secondary supplier institutions (PE/AR/US, one per market)
--   • The demo super-admin user (authenticates all Postman steps)
--
-- Addresses, institution entities, and restaurant setup now live in Layer B
-- (900_DEMO_DAY_SEED.postman_collection.json). Every demo address is created
-- via the production Mapbox suggest → create flow, exercising live geocoding
-- and the MapboxGeocodeCache (seeds/mapbox_geocode_cache.json).
--
-- Everything else (restaurant, products, plates, plans, customers,
-- subscriptions, orders, reviews) also goes through the API in Layer B.
--
-- Secondary supplier billing backfill lives in Layer C (demo_billing_backfill.sql),
-- which runs after Layer B because secondary entity UUIDs are assigned at
-- Newman runtime and must be resolved by canonical_key.
--
-- NOT SAFE for staging or production.  A header guard enforces this.
--
-- Run via:  bash scripts/load_demo_data.sh  (preferred)
--
-- =============================================================================
--
-- UUID SCHEME
-- -----------
-- All demo UUIDs share the prefix:  dddddddd-dec0-NNNN-XXXX-YYYYYYYYYYYY
--
-- NNNN sub-ranges:
--   0001  — Primary institution / admin user / primary institution entities
--   0002  — Secondary institutions (PE/AR/US) and their entities
--   0050  — institution_bill_info rows (2 per market secondary supplier; seeded by Layer C)
--
-- Secondary institution UUID map (0002 sub-range — institutions only; entities are Newman-created):
--   dddddddd-dec0-0002-0000-000000000001  PE secondary institution (Cocina Andina S.A.C.)
--   dddddddd-dec0-0002-0000-000000000002  AR secondary institution (Cocina de Recoleta S.R.L.)
--   dddddddd-dec0-0002-0000-000000000003  US secondary institution (Capitol Hill Kitchen LLC)
--   (entities 4/5/6 previously hardcoded here; now created dynamically via Newman by-key upsert)
--
-- Reference UUIDs (NOT dec0, do NOT purge):
--   Vianda Enterprises institution:   11111111-1111-1111-1111-111111111111
--   Market AR:                        00000000-0000-0000-0000-000000000002
--   Market PE:                        00000000-0000-0000-0000-000000000003
--   Market US:                        00000000-0000-0000-0000-000000000004
--   ARS currency:                     66666666-6666-6666-6666-666666666601
--   PEN currency:                     66666666-6666-6666-6666-666666666602
--   USD currency:                     55555555-5555-5555-5555-555555555555
--   System superadmin (modifier):     dddddddd-dddd-dddd-dddd-dddddddddddd
--
-- =============================================================================

SET search_path = core, ops, customer, billing, audit, public;

-- -----------------------------------------------------------------------------
-- GUARD: Refuse to run on any DB that is not kitchen or kitchen_dev
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF current_database() NOT IN ('kitchen', 'kitchen_dev') THEN
        RAISE EXCEPTION
            'demo_baseline.sql refuses to run on database "%". '
            'Only kitchen or kitchen_dev are permitted.',
            current_database();
    END IF;
END $$;

-- =============================================================================
-- SECTION 1 — Demo supplier institution (PE + AR + US, shared)
--
-- institution_id: dddddddd-dec0-0001-0000-000000000001
-- Markets: PE (primary), AR, US
-- =============================================================================

INSERT INTO core.institution_info (
    institution_id, canonical_key, name, institution_type,
    is_archived, status,
    created_date, created_by, modified_by, modified_date
)
VALUES (
    'dddddddd-dec0-0001-0000-000000000001',
    'DEMO_INSTITUTION_PE_VIANDA_DEMO',
    'Vianda Demo Supplier',
    'supplier'::institution_type_enum,
    FALSE,
    'active'::status_enum,
    CURRENT_TIMESTAMP,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    CURRENT_TIMESTAMP
)
ON CONFLICT (institution_id) DO UPDATE SET
    canonical_key = EXCLUDED.canonical_key,
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

-- Market assignments: PE (primary), AR, US
INSERT INTO core.institution_market (institution_id, market_id, is_primary)
VALUES
    ('dddddddd-dec0-0001-0000-000000000001', '00000000-0000-0000-0000-000000000003', TRUE),   -- PE (primary)
    ('dddddddd-dec0-0001-0000-000000000001', '00000000-0000-0000-0000-000000000002', FALSE),  -- AR
    ('dddddddd-dec0-0001-0000-000000000001', '00000000-0000-0000-0000-000000000004', FALSE)   -- US
ON CONFLICT (institution_id, market_id) DO NOTHING;

-- =============================================================================
-- SECTION 1b — Secondary supplier institutions (PE / AR / US, one per market)
--
-- These are separate institutions from the primary demo supplier.  Each operates
-- in a different neighborhood (Barranco / Recoleta / Capitol Hill) as the
-- "outlier pin" visible on the map alongside the primary cluster.
--
-- Seeded here (not via API) so the institution entities below can set
-- payout_onboarding_status = 'complete' before Newman runs.  The Postman
-- folders (12 Secondary supplier) upsert these same canonical_keys and get
-- back the stable UUIDs below.
--
-- institution_id UUIDs: dddddddd-dec0-0002-0000-00000000000{1,2,3}
-- =============================================================================

-- PE secondary: Cocina Andina S.A.C.
INSERT INTO core.institution_info (
    institution_id, canonical_key, name, institution_type,
    is_archived, status,
    created_date, created_by, modified_by, modified_date
)
VALUES (
    'dddddddd-dec0-0002-0000-000000000001',
    'DEMO_INSTITUTION_PE_COCINA_ANDINA',
    'Cocina Andina S.A.C.',
    'supplier'::institution_type_enum,
    FALSE, 'active'::status_enum,
    CURRENT_TIMESTAMP,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    CURRENT_TIMESTAMP
)
ON CONFLICT (institution_id) DO UPDATE SET
    canonical_key = EXCLUDED.canonical_key,
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

INSERT INTO core.institution_market (institution_id, market_id, is_primary)
VALUES ('dddddddd-dec0-0002-0000-000000000001', '00000000-0000-0000-0000-000000000003', TRUE)
ON CONFLICT (institution_id, market_id) DO NOTHING;

-- AR secondary: Cocina de Recoleta S.R.L.
INSERT INTO core.institution_info (
    institution_id, canonical_key, name, institution_type,
    is_archived, status,
    created_date, created_by, modified_by, modified_date
)
VALUES (
    'dddddddd-dec0-0002-0000-000000000002',
    'DEMO_INSTITUTION_AR_COCINA_RECOLETA',
    'Cocina de Recoleta S.R.L.',
    'supplier'::institution_type_enum,
    FALSE, 'active'::status_enum,
    CURRENT_TIMESTAMP,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    CURRENT_TIMESTAMP
)
ON CONFLICT (institution_id) DO UPDATE SET
    canonical_key = EXCLUDED.canonical_key,
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

INSERT INTO core.institution_market (institution_id, market_id, is_primary)
VALUES ('dddddddd-dec0-0002-0000-000000000002', '00000000-0000-0000-0000-000000000002', TRUE)
ON CONFLICT (institution_id, market_id) DO NOTHING;

-- US secondary: Capitol Hill Kitchen LLC
INSERT INTO core.institution_info (
    institution_id, canonical_key, name, institution_type,
    is_archived, status,
    created_date, created_by, modified_by, modified_date
)
VALUES (
    'dddddddd-dec0-0002-0000-000000000003',
    'DEMO_INSTITUTION_US_CAPITOL_HILL_KITCHEN',
    'Capitol Hill Kitchen LLC',
    'supplier'::institution_type_enum,
    FALSE, 'active'::status_enum,
    CURRENT_TIMESTAMP,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    CURRENT_TIMESTAMP
)
ON CONFLICT (institution_id) DO UPDATE SET
    canonical_key = EXCLUDED.canonical_key,
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

INSERT INTO core.institution_market (institution_id, market_id, is_primary)
VALUES ('dddddddd-dec0-0002-0000-000000000003', '00000000-0000-0000-0000-000000000004', TRUE)
ON CONFLICT (institution_id, market_id) DO NOTHING;

-- =============================================================================
-- SECTION 2 — Demo super-admin user
--
-- Username: demo-admin@vianda.market
-- user_id:  dddddddd-dec0-0001-0000-000000000002
--
-- The hashed_password is set to a bcrypt hash of 'PLACEHOLDER' here.
-- load_demo_data.sh immediately overwrites it with a fresh random password
-- hash before starting Newman.
-- =============================================================================

INSERT INTO core.user_info (
    user_id, username, hashed_password,
    first_name, last_name,
    institution_id, role_type, role_name,
    email, mobile_number,
    email_verified, email_verified_at,
    market_id, city_metadata_id, locale,
    is_archived, status,
    created_date, created_by, modified_by, modified_date
)
VALUES (
    'dddddddd-dec0-0001-0000-000000000002',
    'demo-admin@vianda.market',
    -- Bcrypt hash of 'PLACEHOLDER' — overwritten by load_demo_data.sh before Newman runs
    '$2b$12$PJzLzFtIz3PnhOL5p8M9c.oLPbLdYyYP5FMNI7lH7K9MXnbQKA.Su',
    'Demo',
    'Admin',
    '11111111-1111-1111-1111-111111111111',  -- Vianda Enterprises (internal institution)
    'internal'::role_type_enum,
    'super_admin'::role_name_enum,
    'demo-admin@vianda.market',
    NULL,
    TRUE,
    CURRENT_TIMESTAMP,
    '00000000-0000-0000-0000-000000000001',  -- Global market
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',  -- Global city_metadata sentinel
    'es',
    FALSE,
    'active'::status_enum,
    CURRENT_TIMESTAMP,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    CURRENT_TIMESTAMP
)
ON CONFLICT (user_id) DO UPDATE SET
    -- Preserve the password hash on re-runs; load_demo_data.sh overwrites it anyway.
    username      = EXCLUDED.username,
    first_name    = EXCLUDED.first_name,
    last_name     = EXCLUDED.last_name,
    email         = EXCLUDED.email,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

-- Market assignment for demo admin (Global)
INSERT INTO core.user_market_assignment (user_id, market_id, is_primary)
VALUES ('dddddddd-dec0-0001-0000-000000000002', '00000000-0000-0000-0000-000000000001', TRUE)
ON CONFLICT (user_id, market_id) DO NOTHING;



-- =============================================================================
-- SUMMARY
-- =============================================================================

DO $$
DECLARE
    v_inst_count   INT;
    v_user_count   INT;
BEGIN
    SELECT COUNT(*) INTO v_inst_count
    FROM core.institution_info
    WHERE institution_id::text LIKE 'dddddddd-dec0%';

    SELECT COUNT(*) INTO v_user_count
    FROM core.user_info
    WHERE user_id::text LIKE 'dddddddd-dec0%';

    RAISE NOTICE
        'demo_baseline.sql (Layer A) complete: % institution(s), % user(s). Addresses/entities/restaurants seeded by Newman (Layer B). Billing backfill runs as Layer C after Newman.',
        v_inst_count, v_user_count;
END $$;
