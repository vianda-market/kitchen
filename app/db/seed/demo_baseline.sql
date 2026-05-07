-- =============================================================================
-- demo_baseline.sql — Layer A of the demo-day data seed (PE only, v2)
--
-- Purpose: Inserts only the SQL-only entities that must exist BEFORE the
-- kitchen API is started and the Postman collection runs (Layer B).
--
--   • The demo supplier institution (PE market, Lima address)
--   • The demo super-admin user (authenticates all Postman steps)
--   • The supplier entity office address (Lima — needed by institution_entity)
--   • The restaurant address in Miraflores, Lima (needed by PUT /restaurants/by-key)
--   • The institution entity (PE — needed by PUT /restaurants/by-key)
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
--   0001  — Institution / admin user / institution entity
--   0010  — Addresses (supplier office + restaurant)
--
-- Reference UUIDs (NOT dec0, do NOT purge):
--   Vianda Enterprises institution:   11111111-1111-1111-1111-111111111111
--   Market PE:                        00000000-0000-0000-0000-000000000003
--   PEN currency:                     66666666-6666-6666-6666-666666666602
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
-- SECTION 1 — Demo supplier institution (PE)
--
-- institution_id: dddddddd-dec0-0001-0000-000000000001
-- Market: PE only (primary)
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

-- Market assignment: PE only
INSERT INTO core.institution_market (institution_id, market_id, is_primary)
VALUES
    ('dddddddd-dec0-0001-0000-000000000001', '00000000-0000-0000-0000-000000000003', TRUE)  -- PE (primary)
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
        'str'::street_type_enum, 'Miguel Dasso', '137',
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
        'str'::street_type_enum, 'Coronel Andres Reyes', '218',
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
        'str'::street_type_enum, 'Manuel Banon', '295',
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
        'str'::street_type_enum, 'Conquistadores', '510',
        'America/Lima',
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
        'demo_baseline.sql complete: % institution(s), % user(s), % address(es) [1 office + 5 restaurants], % entity(ies) with dec0 prefix.',
        v_inst_count, v_user_count, v_addr_count, v_entity_count;
END $$;
