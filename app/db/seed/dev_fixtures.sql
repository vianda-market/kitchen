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

-- =============================================================================
-- DEV FIXTURE: Buenos Aires supplier with geocoded restaurants
-- Provides seed data for geo filter live verification (§3.4).
--
-- Fixed UUIDs used throughout so the fixture is idempotent and easy to reference
-- in curl / psql queries.
--
-- Supplier institution:  aaaaaaaa-aaaa-0001-0000-000000000001
-- Institution entity:    aaaaaaaa-aaaa-0001-0000-000000000002
-- Supplier address (entity):  aaaaaaaa-aaaa-0001-0000-000000000003
-- Restaurant 1 address:       aaaaaaaa-aaaa-0001-0000-000000000004
-- Restaurant 2 address:       aaaaaaaa-aaaa-0001-0000-000000000005
-- Restaurant 1 (geocoded):    aaaaaaaa-aaaa-0001-0000-000000000010
-- Restaurant 2 (no location): aaaaaaaa-aaaa-0001-0000-000000000011
-- =============================================================================

-- Supplier institution (Argentina)
INSERT INTO core.institution_info (institution_id, name, institution_type, is_archived, status, created_date, created_by, modified_by, modified_date)
VALUES (
    'aaaaaaaa-aaaa-0001-0000-000000000001',
    'Mercado Vianda BA (dev fixture)',
    'supplier'::institution_type_enum,
    FALSE,
    'active'::status_enum,
    CURRENT_TIMESTAMP,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    CURRENT_TIMESTAMP
);

-- Assign institution to AR market
INSERT INTO core.institution_market (institution_id, market_id, is_primary)
VALUES ('aaaaaaaa-aaaa-0001-0000-000000000001', '00000000-0000-0000-0000-000000000002', TRUE);

-- Resolve Buenos Aires city_metadata_id once for reuse across all addresses.
-- This subquery is evaluated at seed time against already-loaded reference data.
DO $$
DECLARE
    v_ba_city_id UUID;
BEGIN
    SELECT cm.city_metadata_id INTO v_ba_city_id
    FROM core.city_metadata cm
    JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id
    WHERE gc.ascii_name = 'Buenos Aires' AND cm.country_iso = 'AR'
    LIMIT 1;

    IF v_ba_city_id IS NULL THEN
        RAISE EXCEPTION 'Buenos Aires city_metadata not found — reference data may not be loaded';
    END IF;

    -- Address for institution entity (Buenos Aires, Argentina)
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'aaaaaaaa-aaaa-0001-0000-000000000003',
        'aaaaaaaa-aaaa-0001-0000-000000000001',
        v_ba_city_id,
        ARRAY['entity_address'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1425',
        'ave'::street_type_enum, 'Corrientes', '1234',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        'dddddddd-dddd-dddd-dddd-dddddddddddd',
        'dddddddd-dddd-dddd-dddd-dddddddddddd'
    );

    -- Restaurant 1 address — Palermo, Buenos Aires (-34.5854, -58.4352)
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'aaaaaaaa-aaaa-0001-0000-000000000004',
        'aaaaaaaa-aaaa-0001-0000-000000000001',
        v_ba_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1425',
        'ave'::street_type_enum, 'Santa Fe', '3200',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        'dddddddd-dddd-dddd-dddd-dddddddddddd',
        'dddddddd-dddd-dddd-dddd-dddddddddddd'
    );

    -- Restaurant 2 address — San Telmo, Buenos Aires (-34.6226, -58.3701)
    INSERT INTO core.address_info (
        address_id, institution_id, city_metadata_id, address_type,
        country_code, province, city, postal_code,
        street_type, street_name, building_number,
        timezone, is_archived, status,
        created_by, modified_by
    ) VALUES (
        'aaaaaaaa-aaaa-0001-0000-000000000005',
        'aaaaaaaa-aaaa-0001-0000-000000000001',
        v_ba_city_id,
        ARRAY['restaurant'::address_type_enum],
        'AR', 'Buenos Aires', 'Buenos Aires', 'C1066',
        'st'::street_type_enum, 'Defensa', '500',
        'America/Argentina/Buenos_Aires',
        FALSE, 'active'::status_enum,
        'dddddddd-dddd-dddd-dddd-dddddddddddd',
        'dddddddd-dddd-dddd-dddd-dddddddddddd'
    );
END $$;

-- Institution entity (AR legal entity, ARS currency)
INSERT INTO ops.institution_entity_info (
    institution_entity_id, institution_id, address_id,
    currency_metadata_id, tax_id, name,
    payout_onboarding_status,
    is_archived, status, created_by, modified_by
) VALUES (
    'aaaaaaaa-aaaa-0001-0000-000000000002',
    'aaaaaaaa-aaaa-0001-0000-000000000001',
    'aaaaaaaa-aaaa-0001-0000-000000000003',
    '66666666-6666-6666-6666-666666666601',  -- ARS currency_metadata
    '20-12345678-9',
    'Mercado Vianda BA Entidad (dev)',
    'complete',  -- Stripe Connect payout-ready (required by activation gate; see app/services/restaurant_visibility.py)
    FALSE, 'active'::status_enum,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd'
);

-- Restaurant 1: geocoded at Palermo, Buenos Aires
-- ST_MakePoint(longitude, latitude) — PostGIS convention: X=lng, Y=lat
INSERT INTO ops.restaurant_info (
    restaurant_id, institution_id, institution_entity_id, address_id,
    name, is_featured, is_archived, status,
    location,
    created_by, modified_by
) VALUES (
    'aaaaaaaa-aaaa-0001-0000-000000000010',
    'aaaaaaaa-aaaa-0001-0000-000000000001',
    'aaaaaaaa-aaaa-0001-0000-000000000002',
    'aaaaaaaa-aaaa-0001-0000-000000000004',
    'La Cocina Porteña (dev)',
    FALSE, FALSE, 'active'::status_enum,
    ST_SetSRID(ST_MakePoint(-58.4352, -34.5854), 4326),  -- Palermo: lng=-58.4352, lat=-34.5854
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd'
);

-- Restaurant 2: no geocoded location (location IS NULL)
INSERT INTO ops.restaurant_info (
    restaurant_id, institution_id, institution_entity_id, address_id,
    name, is_featured, is_archived, status,
    created_by, modified_by
) VALUES (
    'aaaaaaaa-aaaa-0001-0000-000000000011',
    'aaaaaaaa-aaaa-0001-0000-000000000001',
    'aaaaaaaa-aaaa-0001-0000-000000000002',
    'aaaaaaaa-aaaa-0001-0000-000000000005',
    'Bodegón San Telmo (dev, no location)',
    FALSE, FALSE, 'active'::status_enum,
    'dddddddd-dddd-dddd-dddd-dddddddddddd',
    'dddddddd-dddd-dddd-dddd-dddddddddddd'
);

-- =============================================================================
-- DEV FIXTURE: Canonical plates
-- Plates depend on both a product_id and a restaurant_id, both of which are
-- created at test run time (via Postman) rather than seeded here.  Canonical
-- plate fixtures therefore live in the Postman collection (000 E2E Plate
-- Selection) as PUT /api/v1/plates/by-key calls, not as SQL INSERTs.
--
-- canonical_key convention: RESTAURANT_{SLUG}_PLATE_{SLUG}
-- Examples:
--   RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA
--   RESTAURANT_LA_COCINA_PORTENA_PLATE_ENSALADA_GRIEGA
--
-- If you need a fully SQL-driven plate fixture (e.g. for geo tests), create
-- the product and restaurant rows with fixed UUIDs first, then INSERT INTO
-- ops.plate_info ... ON CONFLICT (canonical_key) WHERE canonical_key IS NOT NULL
-- DO UPDATE SET ... — exactly like the plan fixtures below.
-- =============================================================================

-- =============================================================================
-- DEV FIXTURE: Canonical subscription plans
-- One realistic plan per active test market.  Prices are above Stripe's
-- USD-equivalent minimum (~$0.50) with comfortable margin.
--
-- These rows are idempotent (INSERT ... ON CONFLICT DO UPDATE) so running
-- build_kitchen_db.sh multiple times never creates duplicates.
--
-- canonical_key convention: MARKET_{ISO}_PLAN_{DESCRIPTION}_{PRICE}_{CURRENCY}
-- market_id reference data UUIDs (from reference_data.sql):
--   AR: 00000000-0000-0000-0000-000000000002
--   US: 00000000-0000-0000-0000-000000000004
-- =============================================================================

-- credit_cost_local_currency and credit_cost_usd are set automatically by the
-- plan_info_set_credit_cost_trigger before insert; the values below are
-- placeholder zeros that the trigger overwrites.

INSERT INTO customer.plan_info (
    market_id,
    name,
    credit,
    price,
    highlighted,
    rollover,
    rollover_cap,
    canonical_key,
    status,
    credit_cost_local_currency,
    credit_cost_usd,
    modified_by
)
VALUES
    -- Argentina: 50 000 ARS (~$35 USD at Dec 2024 rates) — well above $0.50 minimum
    (
        '00000000-0000-0000-0000-000000000002',
        'Standard AR',
        20,
        50000.00,
        TRUE,
        TRUE,
        NULL,
        'MARKET_AR_PLAN_STANDARD_50000_ARS',
        'active'::status_enum,
        0, 0,
        'dddddddd-dddd-dddd-dddd-dddddddddddd'
    ),
    -- United States: 15 USD — well above $0.50 minimum
    (
        '00000000-0000-0000-0000-000000000004',
        'Standard US',
        20,
        15.00,
        TRUE,
        TRUE,
        NULL,
        'MARKET_US_PLAN_STANDARD_15_USD',
        'active'::status_enum,
        0, 0,
        'dddddddd-dddd-dddd-dddd-dddddddddddd'
    )
ON CONFLICT (canonical_key) WHERE canonical_key IS NOT NULL
DO UPDATE SET
    name              = EXCLUDED.name,
    credit            = EXCLUDED.credit,
    price             = EXCLUDED.price,
    highlighted       = EXCLUDED.highlighted,
    status            = EXCLUDED.status,
    modified_by       = EXCLUDED.modified_by,
    modified_date     = CURRENT_TIMESTAMP;
