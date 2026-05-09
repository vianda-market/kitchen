-- =============================================================================
-- demo_baseline.sql — Layer A of the demo-day data seed (PE + AR + US, v3)
--
-- Purpose: Inserts only the SQL-only entities that must exist BEFORE the
-- kitchen API is started and the Postman collection runs (Layer B).
--
--   • The demo supplier institution (PE/AR/US markets, shared)
--   • The demo super-admin user (authenticates all Postman steps)
--   • Supplier entity office addresses per market (needed by institution_entity)
--   • Restaurant cluster addresses per market (needed by PUT /restaurants/by-key)
--   • Institution entities per market (PE, AR, US)
--
-- Addresses have no PUT /by-key endpoint so they live here.
-- Everything else (restaurant, products, plates, plans, customers,
-- subscriptions, orders, reviews) goes through the API in Layer B.
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
--   0001  — Institution / admin user / institution entities (per market)
--   0010  — PE addresses  (1 office + 5 restaurants)
--   0020  — AR addresses  (1 office + 5 restaurants)
--   0030  — US addresses  (1 office + 5 restaurants)
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
    institution_id, name, institution_type,
    is_archived, status,
    created_date, created_by, modified_by, modified_date
)
VALUES (
    'dddddddd-dec0-0001-0000-000000000001',
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
-- SECTION 3 — Addresses for supplier entity office + demo restaurants
--
-- address_id sub-range: dddddddd-dec0-0010-XXXX-...
--
--   dddddddd-dec0-0010-0000-000000000001  Supplier entity office — San Isidro, Lima, PE
--   dddddddd-dec0-0010-0000-000000000002  Restaurant PE R1       — Miraflores, Lima, PE (Av. Larco)
--   dddddddd-dec0-0010-0000-000000000003  Restaurant PE R2       — San Isidro, Lima, PE (Miguel Dasso 137)
--   dddddddd-dec0-0010-0000-000000000004  Restaurant PE R3       — San Isidro, Lima, PE (Coronel Andrés Reyes 218)
--   dddddddd-dec0-0010-0000-000000000005  Restaurant PE R4       — San Isidro, Lima, PE (Manuel Bañón 295)
--   dddddddd-dec0-0010-0000-000000000006  Restaurant PE R5       — San Isidro, Lima, PE (Conquistadores 510)
--
-- city_metadata_id resolved at runtime via GeoNames join.
-- Cluster centroid: lat -12.0978, lon -77.0383 (Calle Miguel Dasso, San Isidro)
-- All 4 cluster addresses are within ~300 m of each other.
-- =============================================================================

DO $$
DECLARE
    v_lima_city_id UUID;
    v_demo_inst    UUID := 'dddddddd-dec0-0001-0000-000000000001';
    v_system       UUID := 'dddddddd-dddd-dddd-dddd-dddddddddddd';
BEGIN
    -- Resolve Lima city_metadata_id
    SELECT cm.city_metadata_id INTO v_lima_city_id
    FROM core.city_metadata cm
    JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id
    WHERE gc.ascii_name = 'Lima' AND cm.country_iso = 'PE'
    LIMIT 1;

    IF v_lima_city_id IS NULL THEN
        RAISE EXCEPTION 'Lima city_metadata not found — reference data may not be loaded';
    END IF;

    -- -------------------------------------------------------------------------
    -- Address: Supplier entity office — San Isidro, Lima
    -- (lat -12.0977, lon -77.0353 — San Isidro financial district)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0010-0000-000000000001',
        v_demo_inst,
        v_lima_city_id,
        ARRAY['entity_address'::address_type_enum],
        'PE', 'Lima', 'Lima', 'Lima 27',
        'ave'::street_type_enum, 'Javier Prado Este', '3580',
        'America/Lima',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant PE R1 — Miraflores, Lima
    -- (lat -12.1191, lon -77.0290 — Miraflores, Av. Larco)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0010-0000-000000000002',
        v_demo_inst,
        v_lima_city_id,
        ARRAY['restaurant'::address_type_enum],
        'PE', 'Lima', 'Lima', 'Lima 18',
        'ave'::street_type_enum, 'Larco', '345',
        'America/Lima',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant PE R2 — San Isidro, Miguel Dasso 137
    -- (lat -12.0975, lon -77.0381 — Calle Miguel Dasso, San Isidro)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0010-0000-000000000003',
        v_demo_inst,
        v_lima_city_id,
        ARRAY['restaurant'::address_type_enum],
        'PE', 'Lima', 'Lima', 'Lima 27',
        'st'::street_type_enum, 'Miguel Dasso', '137',
        'America/Lima',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant PE R3 — San Isidro, Coronel Andrés Reyes 218
    -- (lat -12.0972, lon -77.0389 — ~150 m from Miguel Dasso)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0010-0000-000000000004',
        v_demo_inst,
        v_lima_city_id,
        ARRAY['restaurant'::address_type_enum],
        'PE', 'Lima', 'Lima', 'Lima 27',
        'st'::street_type_enum, 'Coronel Andres Reyes', '218',
        'America/Lima',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant PE R4 — San Isidro, Manuel Bañón 295
    -- (lat -12.0980, lon -77.0375 — ~100 m from Miguel Dasso)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0010-0000-000000000005',
        v_demo_inst,
        v_lima_city_id,
        ARRAY['restaurant'::address_type_enum],
        'PE', 'Lima', 'Lima', 'Lima 27',
        'st'::street_type_enum, 'Manuel Banon', '295',
        'America/Lima',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant PE R5 — San Isidro, Conquistadores 510
    -- (lat -12.0968, lon -77.0395 — ~200 m from Miguel Dasso)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0010-0000-000000000006',
        v_demo_inst,
        v_lima_city_id,
        ARRAY['restaurant'::address_type_enum],
        'PE', 'Lima', 'Lima', 'Lima 27',
        'st'::street_type_enum, 'Conquistadores', '510',
        'America/Lima',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

END $$;

-- =============================================================================
-- SECTION 3b — Addresses for AR supplier entity office + demo restaurants
--
-- address_id sub-range: dddddddd-dec0-0020-XXXX-...
--
--   dddddddd-dec0-0020-0000-000000000001  Supplier entity office — Microcentro, CABA, AR
--   dddddddd-dec0-0020-0000-000000000002  Restaurant AR R1  — Lavalle 402, CABA  (cluster anchor)
--   dddddddd-dec0-0020-0000-000000000003  Restaurant AR R2  — Reconquista 380, CABA
--   dddddddd-dec0-0020-0000-000000000004  Restaurant AR R3  — Florida 355, CABA
--   dddddddd-dec0-0020-0000-000000000005  Restaurant AR R4  — San Martin 280, CABA
--   dddddddd-dec0-0020-0000-000000000006  Restaurant AR R5  — 25 de Mayo 489, CABA
--
-- Cluster centroid: lat -34.6038, lon -58.3760 (Lavalle / Reconquista, Microcentro)
-- All 5 restaurant addresses are within ~300 m of each other.
-- =============================================================================

DO $$
DECLARE
    v_bsas_city_id UUID;
    v_demo_inst    UUID := 'dddddddd-dec0-0001-0000-000000000001';
    v_system       UUID := 'dddddddd-dddd-dddd-dddd-dddddddddddd';
BEGIN
    -- Resolve Buenos Aires city_metadata_id
    SELECT cm.city_metadata_id INTO v_bsas_city_id
    FROM core.city_metadata cm
    JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id
    WHERE gc.ascii_name = 'Buenos Aires' AND cm.country_iso = 'AR'
    LIMIT 1;

    IF v_bsas_city_id IS NULL THEN
        RAISE EXCEPTION 'Buenos Aires city_metadata not found — reference data may not be loaded';
    END IF;

    -- -------------------------------------------------------------------------
    -- Address: Supplier entity office — Microcentro, CABA
    -- (lat -34.6037, lon -58.3816 — Florida/Corrientes corner, Microcentro)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0020-0000-000000000001',
        v_demo_inst,
        v_bsas_city_id,
        ARRAY['entity_address'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1005AAA',
        'st'::street_type_enum, 'Florida', '455',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant AR R1 — Lavalle 402, Microcentro CABA
    -- (lat -34.6038, lon -58.3760 — cluster anchor, Calle Lavalle)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0020-0000-000000000002',
        v_demo_inst,
        v_bsas_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1047AAJ',
        'st'::street_type_enum, 'Lavalle', '402',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant AR R2 — Reconquista 380, Microcentro CABA
    -- (lat -34.6027, lon -58.3737 — ~240 m from Lavalle 402)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0020-0000-000000000003',
        v_demo_inst,
        v_bsas_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1003ABJ',
        'st'::street_type_enum, 'Reconquista', '380',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant AR R3 — Florida 355, Microcentro CABA
    -- (lat -34.6040, lon -58.3744 — ~180 m from Lavalle 402)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0020-0000-000000000004',
        v_demo_inst,
        v_bsas_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1005AAA',
        'st'::street_type_enum, 'Florida', '355',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant AR R4 — San Martin 280, Microcentro CABA
    -- (lat -34.6034, lon -58.3750 — ~120 m from Lavalle 402)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0020-0000-000000000005',
        v_demo_inst,
        v_bsas_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1004AAE',
        'st'::street_type_enum, 'San Martin', '280',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant AR R5 — 25 de Mayo 489, Microcentro CABA
    -- (lat -34.6020, lon -58.3748 — ~280 m from Lavalle 402)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0020-0000-000000000006',
        v_demo_inst,
        v_bsas_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1002ABF',
        'st'::street_type_enum, '25 de Mayo', '489',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

END $$;

-- =============================================================================
-- SECTION 3c — Addresses for US supplier entity office + demo restaurants
--
-- address_id sub-range: dddddddd-dec0-0030-XXXX-...
--
--   dddddddd-dec0-0030-0000-000000000001  Supplier entity office — Seattle WA, US
--   dddddddd-dec0-0030-0000-000000000002  Restaurant US R1  — 1428 Pike Pl, Seattle (anchor)
--   dddddddd-dec0-0030-0000-000000000003  Restaurant US R2  — 1st Ave & Pike St, Seattle
--   dddddddd-dec0-0030-0000-000000000004  Restaurant US R3  — Post Alley, Seattle
--   dddddddd-dec0-0030-0000-000000000005  Restaurant US R4  — 1500 Pike Pl, Seattle
--   dddddddd-dec0-0030-0000-000000000006  Restaurant US R5  — Stewart St, Seattle
--
-- Cluster centroid: lat 47.6088, lon -122.3402 (Pike Place Market)
-- All 5 restaurant addresses are within ~300 m of each other.
-- =============================================================================

DO $$
DECLARE
    v_seattle_city_id UUID;
    v_demo_inst       UUID := 'dddddddd-dec0-0001-0000-000000000001';
    v_system          UUID := 'dddddddd-dddd-dddd-dddd-dddddddddddd';
BEGIN
    -- Resolve Seattle city_metadata_id
    SELECT cm.city_metadata_id INTO v_seattle_city_id
    FROM core.city_metadata cm
    JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id
    WHERE gc.ascii_name = 'Seattle' AND cm.country_iso = 'US'
    LIMIT 1;

    IF v_seattle_city_id IS NULL THEN
        RAISE EXCEPTION 'Seattle city_metadata not found — reference data may not be loaded';
    END IF;

    -- -------------------------------------------------------------------------
    -- Address: Supplier entity office — Downtown Seattle
    -- (lat 47.6062, lon -122.3321 — 2nd Ave, downtown Seattle)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0030-0000-000000000001',
        v_demo_inst,
        v_seattle_city_id,
        ARRAY['entity_address'::address_type_enum],
        'US', 'Washington', 'Seattle', '98101',
        'ave'::street_type_enum, '2nd Ave', '800',
        'America/Los_Angeles',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant US R1 — 1428 Pike Pl, Pike Place Market
    -- (lat 47.6088, lon -122.3402 — cluster anchor)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0030-0000-000000000002',
        v_demo_inst,
        v_seattle_city_id,
        ARRAY['restaurant'::address_type_enum],
        'US', 'Washington', 'Seattle', '98101',
        'pl'::street_type_enum, 'Pike Pl', '1428',
        'America/Los_Angeles',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant US R2 — 1916 Pike Pl (Post Alley, Pike Place area)
    -- (lat 47.6095, lon -122.3420 — ~200 m from anchor)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0030-0000-000000000003',
        v_demo_inst,
        v_seattle_city_id,
        ARRAY['restaurant'::address_type_enum],
        'US', 'Washington', 'Seattle', '98101',
        'pl'::street_type_enum, 'Pike Pl', '1916',
        'America/Los_Angeles',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant US R3 — 1st Ave & Pike St (Pike Place vicinity)
    -- (lat 47.6082, lon -122.3420 — ~200 m from anchor)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0030-0000-000000000004',
        v_demo_inst,
        v_seattle_city_id,
        ARRAY['restaurant'::address_type_enum],
        'US', 'Washington', 'Seattle', '98101',
        'ave'::street_type_enum, '1st Ave', '94',
        'America/Los_Angeles',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant US R4 — 1500 Pike Pl
    -- (lat 47.6099, lon -122.3415 — ~250 m from anchor)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0030-0000-000000000005',
        v_demo_inst,
        v_seattle_city_id,
        ARRAY['restaurant'::address_type_enum],
        'US', 'Washington', 'Seattle', '98101',
        'pl'::street_type_enum, 'Pike Pl', '1500',
        'America/Los_Angeles',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

    -- -------------------------------------------------------------------------
    -- Address: Restaurant US R5 — 2000 Western Ave (Stewart St / Western Ave corner)
    -- (lat 47.6101, lon -122.3426 — ~280 m from anchor)
    -- -------------------------------------------------------------------------
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'dddddddd-dec0-0030-0000-000000000006',
        v_demo_inst,
        v_seattle_city_id,
        ARRAY['restaurant'::address_type_enum],
        'US', 'Washington', 'Seattle', '98121',
        'ave'::street_type_enum, 'Western Ave', '2000',
        'America/Los_Angeles',
        FALSE, 'active'::status_enum,
        v_system, v_system
    )
    ON CONFLICT (address_id) DO UPDATE SET
        modified_by   = v_system,
        modified_date = CURRENT_TIMESTAMP;

END $$;

-- =============================================================================
-- SECTION 4 — Institution entity (PE legal entity, PEN currency)
--
-- institution_entity_id: dddddddd-dec0-0001-0000-000000000003
--
-- payout_onboarding_status = 'complete' so restaurant creation does not
-- fail the activation gate (same pattern as dev_fixtures.sql).
-- =============================================================================

INSERT INTO ops.institution_entity_info (
    institution_entity_id, institution_id, address_id,
    currency_metadata_id, tax_id, name,
    payout_onboarding_status,
    is_archived, status, created_by, modified_by
)
VALUES (
    'dddddddd-dec0-0001-0000-000000000003',
    'dddddddd-dec0-0001-0000-000000000001',
    'dddddddd-dec0-0010-0000-000000000001',
    '66666666-6666-6666-6666-666666666602',  -- PEN currency_metadata
    '20601234567',
    'Vianda Demo Peru SAC',
    'complete',
    FALSE, 'active'::status_enum,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd'
)
ON CONFLICT (institution_entity_id) DO UPDATE SET
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

-- =============================================================================
-- SECTION 5 — Institution entity (AR legal entity, ARS currency)
--
-- institution_entity_id: dddddddd-dec0-0001-0000-000000000004
-- =============================================================================

INSERT INTO ops.institution_entity_info (
    institution_entity_id, institution_id, address_id,
    currency_metadata_id, tax_id, name,
    payout_onboarding_status,
    is_archived, status, created_by, modified_by
)
VALUES (
    'dddddddd-dec0-0001-0000-000000000004',
    'dddddddd-dec0-0001-0000-000000000001',
    'dddddddd-dec0-0020-0000-000000000001',
    '66666666-6666-6666-6666-666666666601',  -- ARS currency_metadata
    '30-71234567-9',
    'Vianda Demo Argentina SRL',
    'complete',
    FALSE, 'active'::status_enum,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd'
)
ON CONFLICT (institution_entity_id) DO UPDATE SET
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

-- =============================================================================
-- SECTION 6 — Institution entity (US legal entity, USD currency)
--
-- institution_entity_id: dddddddd-dec0-0001-0000-000000000005
-- =============================================================================

INSERT INTO ops.institution_entity_info (
    institution_entity_id, institution_id, address_id,
    currency_metadata_id, tax_id, name,
    payout_onboarding_status,
    is_archived, status, created_by, modified_by
)
VALUES (
    'dddddddd-dec0-0001-0000-000000000005',
    'dddddddd-dec0-0001-0000-000000000001',
    'dddddddd-dec0-0030-0000-000000000001',
    '55555555-5555-5555-5555-555555555555',  -- USD currency_metadata
    '82-1234567',
    'Vianda Demo US LLC',
    'complete',
    FALSE, 'active'::status_enum,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd'
)
ON CONFLICT (institution_entity_id) DO UPDATE SET
    name          = EXCLUDED.name,
    status        = EXCLUDED.status,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;

-- =============================================================================
-- SUMMARY
-- =============================================================================

DO $$
DECLARE
    v_inst_count   INT;
    v_user_count   INT;
    v_addr_count   INT;
    v_entity_count INT;
BEGIN
    SELECT COUNT(*) INTO v_inst_count
    FROM core.institution_info
    WHERE institution_id::text LIKE 'dddddddd-dec0%';

    SELECT COUNT(*) INTO v_user_count
    FROM core.user_info
    WHERE user_id::text LIKE 'dddddddd-dec0%';

    SELECT COUNT(*) INTO v_addr_count
    FROM core.address_info
    WHERE address_id::text LIKE 'dddddddd-dec0%';

    SELECT COUNT(*) INTO v_entity_count
    FROM ops.institution_entity_info
    WHERE institution_entity_id::text LIKE 'dddddddd-dec0%';

    RAISE NOTICE
        'demo_baseline.sql complete: % institution(s), % user(s), % address(es) [3 offices + 15 restaurants across PE/AR/US], % entity(ies) with dec0 prefix.',
        v_inst_count, v_user_count, v_addr_count, v_entity_count;
END $$;
