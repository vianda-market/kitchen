-- =============================================================================
-- demo_billing_backfill.sql — Layer C of the demo-day data seed (v1)
--
-- Purpose: Inserts billing backfill rows for the three secondary supplier
-- institutions (PE / AR / US).  This file runs AFTER Layer B (Newman), because
-- the secondary institution entities are created dynamically by Newman
-- (PUT /api/v1/institution-entities/by-key) with DB-assigned UUIDs that are
-- unknown at Layer A time.
--
-- Each secondary institution gets 2 bills (1 pending + 1 paid) to populate
-- the vianda-platform Billing / Invoices / Payouts demo pages.
--
-- The settlement pipeline (folder 45 in Newman) produces bills for the PRIMARY
-- supplier only.  Secondary suppliers have no orders, so nothing is produced
-- by the pipeline for them — hence this backfill.
--
-- Entity resolution: looks up institution_entity_id via canonical_key, which
-- is written by Newman.  If a canonical_key is missing (Layer B did not run),
-- this script raises a descriptive error rather than inserting NULLs.
--
-- institution_bill_id sub-range: dddddddd-dec0-0050-XXXX-...
-- bill_resolution_enum values:  pending | paid | rejected | failed
--
-- NOT SAFE for staging or production.  A header guard enforces this.
--
-- Run via:  bash scripts/load_demo_data.sh  (invoked automatically as step 5)
-- =============================================================================

-- =============================================================================
-- ENVIRONMENT GUARD
-- =============================================================================

DO $$
BEGIN
    IF current_setting('app.env', TRUE) NOT IN ('dev', '', NULL) THEN
        RAISE EXCEPTION
            'demo_billing_backfill.sql is dev-only. current app.env = %',
            current_setting('app.env', TRUE);
    END IF;
END $$;

-- =============================================================================
-- RESOLVE ENTITY IDs FROM CANONICAL KEYS
-- =============================================================================

DO $$
DECLARE
    v_pe2_entity_id UUID;
    v_ar2_entity_id UUID;
    v_us2_entity_id UUID;
BEGIN
    SELECT institution_entity_id INTO v_pe2_entity_id
    FROM ops.institution_entity_info
    WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_PE2';

    IF v_pe2_entity_id IS NULL THEN
        RAISE EXCEPTION
            'demo_billing_backfill.sql: entity with canonical_key DEMO_INSTITUTION_ENTITY_PE2 not found. '
            'Run Layer B (Newman) before Layer C.';
    END IF;

    SELECT institution_entity_id INTO v_ar2_entity_id
    FROM ops.institution_entity_info
    WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_AR2';

    IF v_ar2_entity_id IS NULL THEN
        RAISE EXCEPTION
            'demo_billing_backfill.sql: entity with canonical_key DEMO_INSTITUTION_ENTITY_AR2 not found. '
            'Run Layer B (Newman) before Layer C.';
    END IF;

    SELECT institution_entity_id INTO v_us2_entity_id
    FROM ops.institution_entity_info
    WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_US2';

    IF v_us2_entity_id IS NULL THEN
        RAISE EXCEPTION
            'demo_billing_backfill.sql: entity with canonical_key DEMO_INSTITUTION_ENTITY_US2 not found. '
            'Run Layer B (Newman) before Layer C.';
    END IF;

    RAISE NOTICE 'Resolved PE2 entity: %', v_pe2_entity_id;
    RAISE NOTICE 'Resolved AR2 entity: %', v_ar2_entity_id;
    RAISE NOTICE 'Resolved US2 entity: %', v_us2_entity_id;
END $$;

-- =============================================================================
-- SECTION C — Billing backfill rows (secondary suppliers)
-- =============================================================================

INSERT INTO billing.institution_bill_info (
    institution_bill_id,
    institution_id,
    institution_entity_id,
    currency_metadata_id,
    transaction_count,
    amount,
    currency_code,
    period_start,
    period_end,
    is_archived,
    status,
    resolution,
    tax_doc_external_id,
    created_by,
    modified_by
)
VALUES
    -- PE secondary bill 1: pending (Cocina Andina S.A.C.)
    (
        'dddddddd-dec0-0050-0000-000000000001',
        'dddddddd-dec0-0002-0000-000000000001',  -- PE secondary institution
        (SELECT institution_entity_id FROM ops.institution_entity_info
            WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_PE2'),
        '66666666-6666-6666-6666-666666666602',  -- PEN
        8,
        352.00,
        'PEN',
        '2026-04-01 00:00:00+00',
        '2026-04-30 23:59:59+00',
        FALSE,
        'active'::status_enum,
        'pending'::bill_resolution_enum,
        NULL,
        'dddddddd-dec0-0001-0000-000000000002',
        'dddddddd-dec0-0001-0000-000000000002'
    ),
    -- PE secondary bill 2: paid (Cocina Andina S.A.C.)
    (
        'dddddddd-dec0-0050-0000-000000000002',
        'dddddddd-dec0-0002-0000-000000000001',  -- PE secondary institution
        (SELECT institution_entity_id FROM ops.institution_entity_info
            WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_PE2'),
        '66666666-6666-6666-6666-666666666602',  -- PEN
        12,
        528.00,
        'PEN',
        '2026-03-01 00:00:00+00',
        '2026-03-31 23:59:59+00',
        FALSE,
        'active'::status_enum,
        'paid'::bill_resolution_enum,
        'SUNAT-2026-03-001',
        'dddddddd-dec0-0001-0000-000000000002',
        'dddddddd-dec0-0001-0000-000000000002'
    ),
    -- AR secondary bill 1: pending (Cocina de Recoleta S.R.L.)
    (
        'dddddddd-dec0-0050-0000-000000000003',
        'dddddddd-dec0-0002-0000-000000000002',  -- AR secondary institution
        (SELECT institution_entity_id FROM ops.institution_entity_info
            WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_AR2'),
        '66666666-6666-6666-6666-666666666601',  -- ARS
        6,
        126000.00,
        'ARS',
        '2026-04-01 00:00:00+00',
        '2026-04-30 23:59:59+00',
        FALSE,
        'active'::status_enum,
        'pending'::bill_resolution_enum,
        NULL,
        'dddddddd-dec0-0001-0000-000000000002',
        'dddddddd-dec0-0001-0000-000000000002'
    ),
    -- AR secondary bill 2: paid (Cocina de Recoleta S.R.L.)
    (
        'dddddddd-dec0-0050-0000-000000000004',
        'dddddddd-dec0-0002-0000-000000000002',  -- AR secondary institution
        (SELECT institution_entity_id FROM ops.institution_entity_info
            WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_AR2'),
        '66666666-6666-6666-6666-666666666601',  -- ARS
        9,
        189000.00,
        'ARS',
        '2026-03-01 00:00:00+00',
        '2026-03-31 23:59:59+00',
        FALSE,
        'active'::status_enum,
        'paid'::bill_resolution_enum,
        'AFIP-2026-03-001',
        'dddddddd-dec0-0001-0000-000000000002',
        'dddddddd-dec0-0001-0000-000000000002'
    ),
    -- US secondary bill 1: pending (Capitol Hill Kitchen LLC)
    (
        'dddddddd-dec0-0050-0000-000000000005',
        'dddddddd-dec0-0002-0000-000000000003',  -- US secondary institution
        (SELECT institution_entity_id FROM ops.institution_entity_info
            WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_US2'),
        '55555555-5555-5555-5555-555555555555',  -- USD
        7,
        105.00,
        'USD',
        '2026-04-01 00:00:00+00',
        '2026-04-30 23:59:59+00',
        FALSE,
        'active'::status_enum,
        'pending'::bill_resolution_enum,
        NULL,
        'dddddddd-dec0-0001-0000-000000000002',
        'dddddddd-dec0-0001-0000-000000000002'
    ),
    -- US secondary bill 2: paid (Capitol Hill Kitchen LLC)
    (
        'dddddddd-dec0-0050-0000-000000000006',
        'dddddddd-dec0-0002-0000-000000000003',  -- US secondary institution
        (SELECT institution_entity_id FROM ops.institution_entity_info
            WHERE canonical_key = 'DEMO_INSTITUTION_ENTITY_US2'),
        '55555555-5555-5555-5555-555555555555',  -- USD
        11,
        165.00,
        'USD',
        '2026-03-01 00:00:00+00',
        '2026-03-31 23:59:59+00',
        FALSE,
        'active'::status_enum,
        'paid'::bill_resolution_enum,
        'IRS-W9-2026-03-001',
        'dddddddd-dec0-0001-0000-000000000002',
        'dddddddd-dec0-0001-0000-000000000002'
    )
ON CONFLICT (institution_bill_id) DO UPDATE SET
    amount        = EXCLUDED.amount,
    resolution    = EXCLUDED.resolution,
    modified_by   = EXCLUDED.modified_by,
    modified_date = CURRENT_TIMESTAMP;


-- =============================================================================
-- SUMMARY
-- =============================================================================

DO $$
DECLARE
    v_bill_count INT;
BEGIN
    SELECT COUNT(*) INTO v_bill_count
    FROM billing.institution_bill_info
    WHERE institution_bill_id::text LIKE 'dddddddd-dec0-0050%';

    RAISE NOTICE
        'demo_billing_backfill.sql (Layer C) complete: % secondary supplier bill(s).',
        v_bill_count;
END $$;
