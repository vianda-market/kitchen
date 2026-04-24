CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;
-- pg_trgm powers GIN trigram indexes on external.geonames_city.ascii_name
-- for the superadmin cascading city picker (type-ahead search against ~68k cities).
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- PostGIS enables spatial queries on ops.restaurant_info.location (GIST index, ST_DWithin, ST_MakeEnvelope).
CREATE EXTENSION IF NOT EXISTS postgis;
-- pgtap extension (optional - only needed for test files in app/db/tests/)
-- Uncomment and install pgtap if you need to run database tests:
-- CREATE EXTENSION IF NOT EXISTS pgtap;

-- UUID7: All new rows use uuidv7() for time-ordered IDs.
-- PostgreSQL 18+: uuidv7() is built-in. No action needed.
-- PostgreSQL < 18: run docs/archived/db_migrations/uuid7_function.sql before this schema.

-- =============================================================================
-- SCHEMAS (logical namespaces — search_path set at DB level in build_kitchen_db.sh)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS core;      -- system foundation
CREATE SCHEMA IF NOT EXISTS ops;       -- supplier / restaurant
CREATE SCHEMA IF NOT EXISTS customer;  -- customer journey
CREATE SCHEMA IF NOT EXISTS billing;   -- financial layer
CREATE SCHEMA IF NOT EXISTS audit;     -- trigger-managed history (app never writes directly)
CREATE SCHEMA IF NOT EXISTS external;  -- raw mirrors of third-party reference data (GeoNames, ISO 4217); read-only from app code
-- public: reserved for extensions only (uuid-ossp, citext, pgcrypto, etc.)

-- =============================================================================
-- DROP TABLES FIRST (with CASCADE to handle dependencies)
-- =============================================================================

-- Drop country/city/currency metadata tables (children of external.* raw tables)
DROP TABLE IF EXISTS audit.country_metadata_history CASCADE;
DROP TABLE IF EXISTS audit.city_metadata_history CASCADE;
DROP TABLE IF EXISTS audit.currency_metadata_history CASCADE;
DROP TABLE IF EXISTS core.country_metadata CASCADE;
DROP TABLE IF EXISTS core.city_metadata CASCADE;
DROP TABLE IF EXISTS core.currency_metadata CASCADE;

-- Drop external raw tables (re-populated from app/db/seed/external/*.tsv)
DROP TABLE IF EXISTS external.geonames_alternate_name CASCADE;
DROP TABLE IF EXISTS external.geonames_city CASCADE;
DROP TABLE IF EXISTS external.geonames_admin1 CASCADE;
DROP TABLE IF EXISTS external.geonames_country CASCADE;
DROP TABLE IF EXISTS external.iso4217_currency CASCADE;

-- Drop ads platform tables
DROP TABLE IF EXISTS core.ad_click_tracking CASCADE;
DROP TABLE IF EXISTS core.ad_zone CASCADE;

-- Drop dependent/history/resolution tables first
DROP TABLE IF EXISTS audit.archival_config_history CASCADE;
DROP TABLE IF EXISTS core.archival_config CASCADE;
DROP TABLE IF EXISTS audit.client_bill_history CASCADE;
DROP TABLE IF EXISTS audit.subscription_history CASCADE;
DROP TABLE IF EXISTS audit.user_history CASCADE;
DROP TABLE IF EXISTS audit.institution_history CASCADE;
DROP TABLE IF EXISTS audit.institution_entity_history CASCADE;
DROP TABLE IF EXISTS audit.address_history CASCADE;
DROP TABLE IF EXISTS audit.restaurant_history CASCADE;
DROP TABLE IF EXISTS ops.qr_code CASCADE;  -- Removed qr_code_history and qr_code_info
DROP TABLE IF EXISTS audit.product_history CASCADE;
DROP TABLE IF EXISTS audit.plan_history CASCADE;
DROP TABLE IF EXISTS audit.institution_bill_history CASCADE;
DROP TABLE IF EXISTS audit.discretionary_resolution_history CASCADE;
DROP TABLE IF EXISTS billing.discretionary_resolution_info CASCADE;
DROP TABLE IF EXISTS audit.restaurant_balance_history CASCADE;
DROP TABLE IF EXISTS audit.plate_history CASCADE;
DROP TABLE IF EXISTS audit.market_history CASCADE;
DROP TABLE IF EXISTS core.city_info CASCADE;
DROP TABLE IF EXISTS core.market_info CASCADE;
DROP TABLE IF EXISTS audit.credit_currency_history CASCADE;
DROP TABLE IF EXISTS role_history CASCADE;
DROP TABLE IF EXISTS audit.geolocation_history CASCADE;
DROP TABLE IF EXISTS status_info CASCADE;
DROP TABLE IF EXISTS status_history CASCADE;
DROP TABLE IF EXISTS transaction_type_info CASCADE;
DROP TABLE IF EXISTS transaction_type_history CASCADE;
-- audit.employer_history REMOVED (multinational institutions normalization)
DROP TABLE IF EXISTS audit.national_holidays_history CASCADE;
DROP TABLE IF EXISTS core.national_holidays CASCADE;
DROP TABLE IF EXISTS audit.restaurant_holidays_history CASCADE;
DROP TABLE IF EXISTS ops.restaurant_holidays CASCADE;
DROP TABLE IF EXISTS audit.plate_kitchen_days_history CASCADE;
DROP TABLE IF EXISTS ops.plate_kitchen_days CASCADE;
DROP TABLE IF EXISTS customer.pickup_preferences CASCADE;

-- Drop tables that are children of other base tables
-- credit_card, bank_account, fintech_wallet, fintech_wallet_auth, appstore_account removed (Stripe/aggregator-only)
DROP TABLE IF EXISTS client_payment_attempt CASCADE;
DROP TABLE IF EXISTS billing.restaurant_transaction CASCADE;
DROP TABLE IF EXISTS institution_payment_attempt CASCADE;
DROP TABLE IF EXISTS customer.referral_code_assignment CASCADE;
DROP TABLE IF EXISTS audit.referral_info_history CASCADE;
DROP TABLE IF EXISTS audit.referral_config_history CASCADE;
DROP TABLE IF EXISTS customer.referral_info CASCADE;
DROP TABLE IF EXISTS customer.referral_config CASCADE;
DROP TABLE IF EXISTS audit.discretionary_history CASCADE;
DROP TABLE IF EXISTS billing.discretionary_info CASCADE;
DROP TABLE IF EXISTS billing.client_transaction CASCADE;
DROP TABLE IF EXISTS customer.user_favorite_info CASCADE;
DROP TABLE IF EXISTS customer.plate_review_info CASCADE;
DROP TABLE IF EXISTS customer.plate_pickup_live CASCADE;
DROP TABLE IF EXISTS fintech_wallet_auth CASCADE;

-- Drop remaining base/parent tables
DROP TABLE IF EXISTS customer.notification_banner CASCADE;
DROP TABLE IF EXISTS customer.coworker_pickup_notification CASCADE;
DROP TABLE IF EXISTS audit.plate_selection_history CASCADE;
DROP TABLE IF EXISTS customer.plate_selection_info CASCADE;
DROP TABLE IF EXISTS plate_selection CASCADE;
DROP TABLE IF EXISTS ops.plate_info CASCADE;
DROP TABLE IF EXISTS audit.employer_bill_history CASCADE;
DROP TABLE IF EXISTS billing.employer_bill_line CASCADE;
DROP TABLE IF EXISTS billing.employer_bill CASCADE;
DROP TABLE IF EXISTS audit.employer_benefits_program_history CASCADE;
DROP TABLE IF EXISTS core.restaurant_lead_cuisine CASCADE;
DROP TABLE IF EXISTS core.restaurant_lead CASCADE;
DROP TABLE IF EXISTS core.lead_interest CASCADE;
-- core.employer_domain REMOVED (replaced by email_domain on institution_entity_info)
DROP TABLE IF EXISTS core.employer_benefits_program CASCADE;
DROP TABLE IF EXISTS billing.client_bill_info CASCADE;
DROP TABLE IF EXISTS customer.subscription_payment CASCADE;
DROP TABLE IF EXISTS customer.subscription_info CASCADE;
DROP TABLE IF EXISTS customer.external_payment_method CASCADE;
DROP TABLE IF EXISTS customer.payment_method CASCADE;
DROP TABLE IF EXISTS audit.user_payment_provider_history CASCADE;
DROP TABLE IF EXISTS customer.user_payment_provider CASCADE;
DROP TABLE IF EXISTS ops.ingredient_nutrition CASCADE;
DROP TABLE IF EXISTS ops.ingredient_alias CASCADE;
DROP TABLE IF EXISTS ops.product_ingredient CASCADE;
DROP TABLE IF EXISTS ops.ingredient_catalog CASCADE;
DROP TABLE IF EXISTS ops.product_info CASCADE;
DROP TABLE IF EXISTS customer.plan_info CASCADE;
DROP TABLE IF EXISTS ops.cuisine_suggestion CASCADE;
DROP TABLE IF EXISTS ops.restaurant_info CASCADE;
DROP TABLE IF EXISTS audit.cuisine_history CASCADE;
DROP TABLE IF EXISTS ops.cuisine CASCADE;
DROP TABLE IF EXISTS core.credit_currency_info CASCADE;
DROP TABLE IF EXISTS audit.supplier_terms_history CASCADE;
DROP TABLE IF EXISTS billing.supplier_terms CASCADE;
DROP TABLE IF EXISTS billing.supplier_w9 CASCADE;
DROP TABLE IF EXISTS billing.bill_invoice_match CASCADE;
DROP TABLE IF EXISTS billing.supplier_invoice_ar CASCADE;
DROP TABLE IF EXISTS billing.supplier_invoice_pe CASCADE;
DROP TABLE IF EXISTS billing.supplier_invoice_us CASCADE;
DROP TABLE IF EXISTS audit.supplier_invoice_history CASCADE;
DROP TABLE IF EXISTS billing.supplier_invoice CASCADE;
DROP TABLE IF EXISTS audit.institution_settlement_history CASCADE;
DROP TABLE IF EXISTS billing.institution_settlement CASCADE;
DROP TABLE IF EXISTS billing.market_payout_aggregator CASCADE;
DROP TABLE IF EXISTS billing.institution_bill_payout CASCADE;
DROP TABLE IF EXISTS billing.institution_bill_info CASCADE;
DROP TABLE IF EXISTS billing.restaurant_balance_info CASCADE;
DROP TABLE IF EXISTS core.geolocation_info CASCADE;
DROP TABLE IF EXISTS core.address_subpremise CASCADE;
DROP TABLE IF EXISTS core.address_info CASCADE;
DROP TABLE IF EXISTS ops.institution_entity_info CASCADE;
DROP TABLE IF EXISTS core.institution_info CASCADE;
DROP TABLE IF EXISTS core.user_market_assignment CASCADE;
DROP TABLE IF EXISTS core.user_fcm_token CASCADE;
DROP TABLE IF EXISTS core.user_messaging_preferences CASCADE;
DROP TABLE IF EXISTS core.user_info CASCADE;
-- core.employer_info REMOVED (replaced by institution_info + institution_entity_info)
DROP TABLE IF EXISTS customer.pending_customer_signup CASCADE;
DROP TABLE IF EXISTS customer.email_change_request CASCADE;
DROP TABLE IF EXISTS customer.credential_recovery CASCADE;
DROP TABLE IF EXISTS role_info CASCADE;
DROP TABLE IF EXISTS core.schema_migration CASCADE;

-- =============================================================================
-- DROP ENUM TYPES (after dropping tables that use them)
-- =============================================================================

DROP TYPE IF EXISTS restaurant_lead_referral_source_enum CASCADE;
DROP TYPE IF EXISTS restaurant_lead_status_enum CASCADE;
DROP TYPE IF EXISTS flywheel_state_enum CASCADE;
DROP TYPE IF EXISTS referral_status_enum CASCADE;
DROP TYPE IF EXISTS notification_banner_type_enum CASCADE;
DROP TYPE IF EXISTS notification_banner_priority_enum CASCADE;
DROP TYPE IF EXISTS notification_banner_action_status_enum CASCADE;
DROP TYPE IF EXISTS interest_type_enum CASCADE;
DROP TYPE IF EXISTS lead_interest_status_enum CASCADE;
DROP TYPE IF EXISTS lead_interest_source_enum CASCADE;
DROP TYPE IF EXISTS employer_bill_payment_status_enum CASCADE;
DROP TYPE IF EXISTS billing_cycle_enum CASCADE;
DROP TYPE IF EXISTS enrollment_mode_enum CASCADE;
DROP TYPE IF EXISTS benefit_cap_period_enum CASCADE;
DROP TYPE IF EXISTS audit_operation_enum CASCADE;
DROP TYPE IF EXISTS discretionary_reason_enum CASCADE;
DROP TYPE IF EXISTS pickup_type_enum CASCADE;
DROP TYPE IF EXISTS kitchen_day_enum CASCADE;
DROP TYPE IF EXISTS transaction_type_enum CASCADE;
DROP TYPE IF EXISTS role_name_enum CASCADE;
DROP TYPE IF EXISTS role_type_enum CASCADE;
DROP TYPE IF EXISTS institution_type_enum CASCADE;
DROP TYPE IF EXISTS discretionary_status_enum CASCADE;
DROP TYPE IF EXISTS status_enum CASCADE;
DROP TYPE IF EXISTS bill_resolution_enum CASCADE;
DROP TYPE IF EXISTS bill_payout_status_enum CASCADE;
DROP TYPE IF EXISTS supplier_invoice_status_enum CASCADE;
DROP TYPE IF EXISTS supplier_invoice_type_enum CASCADE;
DROP TYPE IF EXISTS address_type_enum CASCADE;
DROP TYPE IF EXISTS street_type_enum CASCADE;
DROP TYPE IF EXISTS favorite_entity_type_enum CASCADE;
DROP TYPE IF EXISTS payment_frequency_enum CASCADE;

-- =============================================================================
-- CREATE ENUM TYPES (before creating tables that use them)
-- =============================================================================

\echo 'Creating enum type: address_type_enum'
CREATE TYPE address_type_enum AS ENUM (
    'restaurant',
    'entity_billing',
    'entity_address',
    'customer_home',
    'customer_billing',
    'customer_employer',
    'customer_other'
);

\echo 'Creating enum type: status_enum'
CREATE TYPE status_enum AS ENUM (
    'active',
    'inactive',
    'pending',
    'arrived',
    'handed_out',
    'completed',
    'cancelled',
    'processed'
);

\echo 'Creating enum type: discretionary_status_enum'
CREATE TYPE discretionary_status_enum AS ENUM (
    'pending',
    'cancelled',
    'approved',
    'rejected'
);

\echo 'Creating enum type: bill_resolution_enum'
CREATE TYPE bill_resolution_enum AS ENUM (
    'pending',
    'paid',
    'rejected',
    'failed'
);

\echo 'Creating enum type: bill_payout_status_enum'
CREATE TYPE bill_payout_status_enum AS ENUM (
    'pending',
    'completed',
    'failed'
);

\echo 'Creating enum type: supplier_invoice_status_enum'
CREATE TYPE supplier_invoice_status_enum AS ENUM (
    'pending_review',
    'approved',
    'rejected'
);

\echo 'Creating enum type: supplier_invoice_type_enum'
CREATE TYPE supplier_invoice_type_enum AS ENUM (
    'factura_electronica',
    'cpe',
    '1099_nec'
);

\echo 'Creating enum type: role_type_enum'
CREATE TYPE role_type_enum AS ENUM (
    'internal',
    'supplier',
    'customer',
    'employer'
);

\echo 'Creating enum type: institution_type_enum'
CREATE TYPE institution_type_enum AS ENUM (
    'internal',
    'customer',
    'supplier',
    'employer'
);

\echo 'Creating enum type: role_name_enum'
CREATE TYPE role_name_enum AS ENUM (
    'admin',
    'super_admin',
    'manager',
    'operator',
    'comensal',
    'global_manager'
);

\echo 'Creating enum type: transaction_type_enum'
CREATE TYPE transaction_type_enum AS ENUM (
    'order',
    'credit',
    'debit',
    'refund',
    'discretionary',
    'payment'
);

\echo 'Creating enum type: kitchen_day_enum'
CREATE TYPE kitchen_day_enum AS ENUM (
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday'
);

\echo 'Creating enum type: pickup_type_enum'
CREATE TYPE pickup_type_enum AS ENUM (
    'offer',
    'request',
    'self'
);

\echo 'Creating enum type: street_type_enum'
CREATE TYPE street_type_enum AS ENUM (
    'st',
    'ave',
    'blvd',
    'rd',
    'dr',
    'ln',
    'way',
    'ct',
    'pl',
    'cir'
);

\echo 'Creating enum type: audit_operation_enum'
CREATE TYPE audit_operation_enum AS ENUM (
    'create',
    'update',
    'archive',
    'delete'
);

\echo 'Creating enum type: discretionary_reason_enum'
CREATE TYPE discretionary_reason_enum AS ENUM (
    'marketing_campaign',
    'credit_refund',
    'order_incorrectly_marked',
    'full_order_refund'
);

\echo 'Creating enum type: favorite_entity_type_enum'
CREATE TYPE favorite_entity_type_enum AS ENUM (
    'plate',
    'restaurant'
);

\echo 'Creating enum type: benefit_cap_period_enum'
CREATE TYPE benefit_cap_period_enum AS ENUM (
    'per_renewal',
    'monthly'
);

\echo 'Creating enum type: enrollment_mode_enum'
CREATE TYPE enrollment_mode_enum AS ENUM (
    'managed',
    'domain_gated'
);

\echo 'Creating enum type: billing_cycle_enum'
CREATE TYPE billing_cycle_enum AS ENUM (
    'daily',
    'weekly',
    'monthly'
);

\echo 'Creating enum type: payment_frequency_enum'
CREATE TYPE payment_frequency_enum AS ENUM ('daily', 'weekly', 'biweekly', 'monthly');

\echo 'Creating enum type: employer_bill_payment_status_enum'
CREATE TYPE employer_bill_payment_status_enum AS ENUM (
    'pending',
    'paid',
    'failed',
    'overdue'
);

\echo 'Creating enum type: interest_type_enum'
CREATE TYPE interest_type_enum AS ENUM ('customer', 'employer', 'supplier');

\echo 'Creating enum type: lead_interest_status_enum'
CREATE TYPE lead_interest_status_enum AS ENUM ('active', 'notified', 'unsubscribed');

\echo 'Creating enum type: lead_interest_source_enum'
CREATE TYPE lead_interest_source_enum AS ENUM ('marketing_site', 'b2c_app');

\echo 'Creating enum type: notification_banner_type_enum'
CREATE TYPE notification_banner_type_enum AS ENUM (
    'survey_available',
    'peer_pickup_volunteer',
    'reservation_reminder'
);

\echo 'Creating enum type: notification_banner_priority_enum'
CREATE TYPE notification_banner_priority_enum AS ENUM ('normal', 'high');

\echo 'Creating enum type: notification_banner_action_status_enum'
CREATE TYPE notification_banner_action_status_enum AS ENUM (
    'active',
    'dismissed',
    'opened',
    'completed',
    'expired'
);

\echo 'Creating enum type: referral_status_enum'
CREATE TYPE referral_status_enum AS ENUM (
    'pending',
    'qualified',
    'rewarded',
    'expired',
    'cancelled'
);

\echo 'Creating enum type: flywheel_state_enum'
CREATE TYPE flywheel_state_enum AS ENUM (
    'monitoring',
    'supply_acquisition',
    'demand_activation',
    'growth',
    'mature',
    'paused'
);

\echo 'Creating enum type: restaurant_lead_status_enum'
CREATE TYPE restaurant_lead_status_enum AS ENUM (
    'submitted',
    'under_review',
    'verification_pending',
    'approved',
    'rejected'
);

\echo 'Creating enum type: restaurant_lead_referral_source_enum'
CREATE TYPE restaurant_lead_referral_source_enum AS ENUM (
    'ad',
    'referral',
    'search',
    'other'
);

-- =============================================================================
-- EXTERNAL REFERENCE DATA (raw mirrors of third-party sources; read-only for app)
-- =============================================================================
-- These tables hold verbatim snapshots of external reference data. The app never
-- writes here — they are populated by COPY from TSV snapshots in
-- app/db/seed/external/, generated by app/scripts/import_geonames.py.
-- See app/db/seed/external/README.md and docs/plans/country_city_data_structure.md.
--
-- Tables created in FK dependency order: geonames_country → geonames_admin1 →
-- geonames_city → geonames_alternate_name; iso4217_currency is independent.

\echo 'Creating table: external.iso4217_currency'
CREATE TABLE IF NOT EXISTS external.iso4217_currency (
    code              VARCHAR(3)  PRIMARY KEY,          -- 'USD', 'ARS', 'BRL' — ISO 4217 alpha
    name              VARCHAR(100) NOT NULL,            -- 'US Dollar', 'Argentine Peso'
    numeric_code      INTEGER     NOT NULL,             -- 840, 032, 986 — ISO 4217 numeric (stored as int; leading-zero padding is a display concern)
    minor_unit        SMALLINT    NOT NULL,             -- decimal places used by the currency (2 for most, 0 for JPY/CLP, 3 for some dinars)
    imported_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE external.iso4217_currency IS
    'Read-only raw mirror of the ISO 4217 currency list. Seeded from datasets/currency-codes (TSV). '
    'The app never writes here. Vianda operational config (enabled currencies, exchange rates) lives in '
    'core.currency_metadata, which FKs to this table via currency_code. Source of truth for currency '
    'display names and minor-unit precision used in money formatting.';
COMMENT ON COLUMN external.iso4217_currency.code IS
    'ISO 4217 alphabetic code (e.g. ''USD'', ''ARS'', ''BRL''). Primary key. '
    'Referenced as currency_code FK in core.currency_metadata. '
    'Surfaces in API responses as ''currency_code'' (renamed at the JOIN layer).';
COMMENT ON COLUMN external.iso4217_currency.name IS
    'ISO 4217 official display name in English (e.g. ''US Dollar'', ''Argentine Peso''). '
    'Surfaces in API responses as ''currency_name'' (renamed at the JOIN layer). '
    'Not stored redundantly in core.currency_metadata — always derived via JOIN.';
COMMENT ON COLUMN external.iso4217_currency.numeric_code IS
    'ISO 4217 numeric code (e.g. 840 for USD, 32 for ARS). Stored as INTEGER; '
    'leading-zero padding (e.g. ''032'') is a display concern, not a storage one.';
COMMENT ON COLUMN external.iso4217_currency.minor_unit IS
    'Decimal places the currency uses (e.g. 2 for USD/ARS/BRL, 0 for JPY/CLP, 3 for KWD). '
    'Use for money formatting — determines how many cents/centavos to display.';
COMMENT ON COLUMN external.iso4217_currency.imported_at IS
    'UTC timestamp of the most recent TSV import into this row. Not a business timestamp.';

\echo 'Creating table: external.geonames_country'
CREATE TABLE IF NOT EXISTS external.geonames_country (
    -- Source: https://download.geonames.org/export/dump/countryInfo.txt
    -- Column order matches the source file so the committed TSV can be COPYed directly.
    iso_alpha2        VARCHAR(2)   PRIMARY KEY,         -- 'US', 'AR', 'XG' (NB: 'XG' is Vianda's synthetic Global — ISO 3166-1 user-assigned X-series; see README)
    iso_alpha3        VARCHAR(3)   NOT NULL,            -- 'USA'
    iso_numeric       INTEGER      NOT NULL,            -- 840
    fips              VARCHAR(2),                       -- FIPS 10-4 country code; legacy, rarely used
    name              VARCHAR(200) NOT NULL,            -- canonical GeoNames country name in English
    capital           VARCHAR(200),
    area_sq_km        NUMERIC,
    population        BIGINT,
    continent         VARCHAR(2),                       -- 'NA', 'SA', 'EU', 'AS', 'AF', 'OC', 'AN'
    tld               VARCHAR(10),                      -- '.us'
    currency_code     VARCHAR(3),                       -- may be NULL for territories; joinable to external.iso4217_currency.code
    currency_name     VARCHAR(100),
    phone_prefix      VARCHAR(20),                      -- '1', '54', '54-9'; NULL for some territories
    postal_format     VARCHAR(200),
    postal_regex      TEXT,
    languages         TEXT,                             -- comma-sep ISO 639 codes with country variants, e.g. 'en-US,es-US'
    geonames_id       INTEGER,                          -- GeoNames' own country entity id (used by alternate_name lookups)
    neighbours        TEXT,                             -- comma-sep alpha-2 country codes
    equivalent_fips   VARCHAR(5),
    imported_at       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE external.geonames_country IS
    'Read-only raw mirror of GeoNames countryInfo.txt. Seeded by import_geonames.py; the app never writes here. '
    'Column order matches the source TSV for direct COPY. Includes a synthetic row for ''XG'' (Vianda''s Global '
    'pseudo-market, ISO 3166-1 user-assigned X-series). FK parent for geonames_admin1, geonames_city, '
    'core.country_metadata, and core.address_info.';
COMMENT ON COLUMN external.geonames_country.iso_alpha2 IS
    'ISO 3166-1 alpha-2 country code (e.g. ''US'', ''AR''). Primary key. '
    '''XG'' is Vianda''s synthetic Global pseudo-country (ISO user-assigned X-series). '
    'Referenced as country_code/country_iso FK throughout core.*, ops.*, billing.*.';
COMMENT ON COLUMN external.geonames_country.iso_alpha3 IS
    'ISO 3166-1 alpha-3 country code (e.g. ''USA'', ''ARG''). Included from source file; not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.iso_numeric IS
    'ISO 3166-1 numeric country code (e.g. 840 for US). Included from source file; not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.fips IS
    'FIPS 10-4 country code. Legacy standard; included from source file but not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.name IS
    'Canonical English country name from GeoNames (e.g. ''United States''). '
    'Vianda localizes country names at runtime via pycountry (see app/i18n/locale_names.py), '
    'not by querying this column. Used in the superadmin external-data picker.';
COMMENT ON COLUMN external.geonames_country.capital IS
    'Capital city name from GeoNames source file. Included as-is; not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.area_sq_km IS
    'Country area in square kilometres from GeoNames source file. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.population IS
    'Country population from GeoNames source file. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.continent IS
    'Two-letter continent code (''NA'', ''SA'', ''EU'', ''AS'', ''AF'', ''OC'', ''AN''). Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.tld IS
    'Country-code top-level domain (e.g. ''.us'', ''.ar''). Included from source; not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.currency_code IS
    'ISO 4217 alphabetic currency code for this country from the GeoNames source file. '
    'NULL for some territories. Not used as a FK here — Vianda currency config lives in '
    'core.currency_metadata. Joinable to external.iso4217_currency.code for reference.';
COMMENT ON COLUMN external.geonames_country.currency_name IS
    'Currency display name from GeoNames source file (e.g. ''Dollar''). '
    'Informational only — authoritative currency names come from external.iso4217_currency.name.';
COMMENT ON COLUMN external.geonames_country.phone_prefix IS
    'Dialing prefix digits from GeoNames source (e.g. ''1'', ''54'', ''54-9''). NULL for some territories. '
    'Note: the API response field ''phone_prefix'' on /leads/countries comes from '
    'core.market_info.phone_dial_code, not this column. This column is the raw GeoNames value.';
COMMENT ON COLUMN external.geonames_country.postal_format IS
    'Postal code format string from GeoNames source file. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.postal_regex IS
    'Postal code validation regex from GeoNames source file. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.languages IS
    'Comma-separated ISO 639 language codes with country variants (e.g. ''en-US,es-US''). '
    'Included from source; not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.geonames_id IS
    'GeoNames own entity ID for the country record. Used by geonames_alternate_name lookups '
    'to resolve localized country names. Not a local PK — iso_alpha2 is the PK here.';
COMMENT ON COLUMN external.geonames_country.neighbours IS
    'Comma-separated alpha-2 codes of bordering countries from GeoNames. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.equivalent_fips IS
    'Equivalent FIPS code from GeoNames source file. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_country.imported_at IS
    'UTC timestamp of the most recent TSV import into this row. Not a business timestamp.';

\echo 'Creating table: external.geonames_admin1'
CREATE TABLE IF NOT EXISTS external.geonames_admin1 (
    -- Source: https://download.geonames.org/export/dump/admin1CodesASCII.txt
    -- Source file is 4 cols: 'US.CA\tCalifornia\tCalifornia\t5332921'.
    -- Our import script (app/scripts/import_geonames.py) splits `US.CA` into
    -- country_iso + admin1_code and produces a 6-column TSV matching this schema.
    admin1_full_code  VARCHAR(20)  PRIMARY KEY,         -- 'US.CA' — country_iso + '.' + admin1_code
    country_iso       VARCHAR(2)   NOT NULL
                      REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    admin1_code       VARCHAR(20)  NOT NULL,            -- 'CA' (part after the dot); matches external.geonames_city.admin1_code for joins
    name              VARCHAR(200) NOT NULL,            -- 'California' — may contain diacritics
    ascii_name        VARCHAR(200) NOT NULL,            -- 'California' — ASCII-folded for search
    geonames_id       INTEGER,                          -- GeoNames' entity id for the admin1 region (used by alternate_name lookups)
    imported_at       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_geonames_admin1_country
    ON external.geonames_admin1 (country_iso);
CREATE INDEX IF NOT EXISTS idx_geonames_admin1_country_code
    ON external.geonames_admin1 (country_iso, admin1_code);
COMMENT ON TABLE external.geonames_admin1 IS
    'Read-only raw mirror of GeoNames admin1CodesASCII.txt (first-level administrative divisions: '
    'states, provinces, regions). Seeded by import_geonames.py; the app never writes here. '
    'Used by the superadmin city picker to present province filters and by the address layer '
    'to resolve province names for display.';
COMMENT ON COLUMN external.geonames_admin1.admin1_full_code IS
    'Composite primary key in GeoNames format: country_iso + ''.'' + admin1_code '
    '(e.g. ''US.CA'', ''AR.06''). Unique across all rows.';
COMMENT ON COLUMN external.geonames_admin1.country_iso IS
    'ISO 3166-1 alpha-2 country code. FK to external.geonames_country.iso_alpha2.';
COMMENT ON COLUMN external.geonames_admin1.admin1_code IS
    'GeoNames admin1 subdivision code within the country (e.g. ''CA'' for California). '
    'Join key to geonames_city.admin1_code. Not a FK constraint — geonames_city has '
    'some rows with non-canonical admin1 codes.';
COMMENT ON COLUMN external.geonames_admin1.name IS
    'Admin1 name, may contain diacritics (e.g. ''Río Negro''). Used for display.';
COMMENT ON COLUMN external.geonames_admin1.ascii_name IS
    'ASCII-folded version of name (e.g. ''Rio Negro''). Used for case-insensitive search '
    'in the superadmin picker.';
COMMENT ON COLUMN external.geonames_admin1.geonames_id IS
    'GeoNames entity ID for this admin1 region. Used by geonames_alternate_name lookups '
    'to resolve localized province names. Not a local PK.';
COMMENT ON COLUMN external.geonames_admin1.imported_at IS
    'UTC timestamp of the most recent TSV import into this row. Not a business timestamp.';

\echo 'Creating table: external.geonames_city'
CREATE TABLE IF NOT EXISTS external.geonames_city (
    -- Source: https://download.geonames.org/export/dump/cities5000.zip → cities5000.txt
    -- Pass-through; column order matches the source file verbatim (19 columns).
    -- Field name differences from source spec: `country_code` → `country_iso`.
    geonames_id       INTEGER      PRIMARY KEY,
    name              VARCHAR(200) NOT NULL,            -- canonical name with diacritics ('São Paulo')
    ascii_name        VARCHAR(200) NOT NULL,            -- ASCII-folded ('Sao Paulo') — joinable for fuzzy search
    alternate_names   TEXT,                             -- comma-sep short-list baked into the source row; localization uses external.geonames_alternate_name instead
    latitude          NUMERIC(10, 7),
    longitude         NUMERIC(11, 7),
    feature_class     CHAR(1),                          -- 'P' = populated place (expected for all cities5000 rows)
    feature_code      VARCHAR(10),                      -- 'PPL', 'PPLC' (country capital), 'PPLA' (admin1 capital), etc.
    country_iso       VARCHAR(2)   NOT NULL
                      REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    cc2               TEXT,                             -- alternate country codes for disputed territory (comma-sep)
    admin1_code       VARCHAR(20),                      -- joinable to external.geonames_admin1.admin1_code (not FK-constrained: some cities have a non-canonical admin1)
    admin2_code       VARCHAR(80),
    admin3_code       VARCHAR(20),
    admin4_code       VARCHAR(20),
    population        BIGINT,
    elevation         INTEGER,
    dem               INTEGER,                          -- digital elevation model (meters)
    timezone          VARCHAR(50),                      -- IANA tz name ('America/Sao_Paulo') — source of truth for address_info.timezone
    modification_date DATE,                             -- GeoNames' own last-modified date
    imported_at       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_geonames_city_country_pop
    ON external.geonames_city (country_iso, population DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_geonames_city_country_ascii
    ON external.geonames_city (country_iso, LOWER(ascii_name));
CREATE INDEX IF NOT EXISTS idx_geonames_city_country_admin1
    ON external.geonames_city (country_iso, admin1_code);
-- Trigram index for superadmin type-ahead city picker — matches substrings in ~68k cities cheaply.
CREATE INDEX IF NOT EXISTS idx_geonames_city_ascii_trgm
    ON external.geonames_city USING GIN (ascii_name gin_trgm_ops);
COMMENT ON TABLE external.geonames_city IS
    'Read-only raw mirror of GeoNames cities5000.txt (populated places ≥ 5000 inhabitants, ~68k rows). '
    'Seeded by import_geonames.py; the app never writes here. Column order mirrors the 19-column source '
    'file verbatim (field rename: source ''country_code'' → ''country_iso'' to avoid ambiguity). '
    'FK parent for core.city_metadata (Vianda operational layer). '
    'Timezone column is the source of truth for address_info.timezone — copied at address write time.';
COMMENT ON COLUMN external.geonames_city.geonames_id IS
    'GeoNames integer entity ID for this city. Primary key. Not a UUID — raw upstream ID. '
    'Referenced as FK from core.city_metadata.geonames_id. Synthetic row geonames_id=-1 '
    'exists for the XG/Global pseudo-city.';
COMMENT ON COLUMN external.geonames_city.name IS
    'Canonical city name with diacritics from GeoNames (e.g. ''São Paulo'', ''Buenos Aires''). '
    'Used as display name via COALESCE(city_metadata.display_name_override, geonames_city.name) '
    'in the cities endpoint.';
COMMENT ON COLUMN external.geonames_city.ascii_name IS
    'ASCII-folded city name (e.g. ''Sao Paulo''). Powers the superadmin type-ahead city picker '
    'via the GIN trigram index. Also used for case-insensitive search filters.';
COMMENT ON COLUMN external.geonames_city.alternate_names IS
    'Comma-separated short-list of alternate names baked into the source row. '
    'Informational only — localized names come from external.geonames_alternate_name instead.';
COMMENT ON COLUMN external.geonames_city.latitude IS
    'Geographic latitude (decimal degrees, 7 decimal places). Not yet used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.longitude IS
    'Geographic longitude (decimal degrees, 7 decimal places). Not yet used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.feature_class IS
    'GeoNames feature class. Expected value: ''P'' (populated place) for all cities5000 rows.';
COMMENT ON COLUMN external.geonames_city.feature_code IS
    'GeoNames feature code: ''PPL'' (populated place), ''PPLC'' (country capital), '
    '''PPLA'' (admin1 capital), ''PPLA2'' (admin2 capital), etc.';
COMMENT ON COLUMN external.geonames_city.country_iso IS
    'ISO 3166-1 alpha-2 country code. FK to external.geonames_country.iso_alpha2. '
    'Renamed from ''country_code'' in the source file to avoid column-name ambiguity.';
COMMENT ON COLUMN external.geonames_city.cc2 IS
    'Alternate country codes for disputed or multi-sovereign territory (comma-separated alpha-2). '
    'NULL for most cities. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.admin1_code IS
    'GeoNames admin1 subdivision code (e.g. ''CA'' for California). Joinable to '
    'external.geonames_admin1.admin1_code. Not FK-constrained — some cities carry '
    'non-canonical codes that have no matching admin1 row.';
COMMENT ON COLUMN external.geonames_city.admin2_code IS
    'GeoNames admin2 subdivision code (county/department level). Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.admin3_code IS
    'GeoNames admin3 subdivision code. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.admin4_code IS
    'GeoNames admin4 subdivision code. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.population IS
    'City population from GeoNames. Used for sort order in the city picker (largest cities first).';
COMMENT ON COLUMN external.geonames_city.elevation IS
    'Elevation above sea level in metres (srtm3 data). NULL for many rows. Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.dem IS
    'Digital elevation model value in metres (SRTM3 or GTOPO30). Not used in Vianda business logic.';
COMMENT ON COLUMN external.geonames_city.timezone IS
    'IANA timezone identifier (e.g. ''America/Sao_Paulo'', ''America/Argentina/Buenos_Aires''). '
    'Source of truth for address_info.timezone — copied at address write time via city_metadata_id FK chain. '
    'Also used by market-level timezone fallback in TimezoneService._MARKET_PRIMARY_TIMEZONE.';
COMMENT ON COLUMN external.geonames_city.modification_date IS
    'GeoNames own last-modified date for this row. Not a local write timestamp.';
COMMENT ON COLUMN external.geonames_city.imported_at IS
    'UTC timestamp of the most recent TSV import into this row. Not a business timestamp.';

\echo 'Creating table: external.geonames_alternate_name'
CREATE TABLE IF NOT EXISTS external.geonames_alternate_name (
    -- Source: https://download.geonames.org/export/dump/alternateNamesV2.zip → alternateNamesV2.txt
    -- Pre-filtered by app/scripts/import_geonames.py to:
    --   (a) iso_language IN ('en', 'es', 'pt')     — our supported UI locales
    --   (b) geonameid present in geonames_country / geonames_admin1 / geonames_city
    -- The raw file has ~13M rows globally; the filter drops it to ~50k.
    --
    -- `geonames_id` here is polymorphic — it refers to a country, admin1, or city
    -- entity depending on which of the three source tables published the ID. We
    -- deliberately don't add a FK constraint; the resolver service (place_name_resolver)
    -- looks up by the known entity type for each call site.
    alternate_name_id INTEGER      PRIMARY KEY,         -- GeoNames' own alternateNameId
    geonames_id       INTEGER      NOT NULL,
    iso_language      VARCHAR(7)   NOT NULL,            -- ISO 639 2- or 3-letter code, possibly with region ('pt-BR')
    alternate_name    VARCHAR(400) NOT NULL,            -- the localized name itself ('Brasil', 'São Paulo', 'Ciudad de México')
    is_preferred      BOOLEAN      NOT NULL DEFAULT FALSE,  -- GeoNames-flagged official/preferred name for this language
    is_short          BOOLEAN      NOT NULL DEFAULT FALSE,  -- short form ('California' vs 'State of California')
    is_colloquial     BOOLEAN      NOT NULL DEFAULT FALSE,  -- slang ('Big Apple' for New York) — resolver skips these
    is_historic       BOOLEAN      NOT NULL DEFAULT FALSE,  -- legacy ('Bombay' for Mumbai) — resolver skips these
    imported_at       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_geonames_alt_name_lookup
    ON external.geonames_alternate_name (geonames_id, iso_language)
    WHERE is_historic = FALSE AND is_colloquial = FALSE;
COMMENT ON TABLE external.geonames_alternate_name IS
    'Read-only raw mirror of GeoNames alternateNamesV2.txt, pre-filtered to iso_language IN '
    '(''en'', ''es'', ''pt'') and only geonames_ids present in geonames_country / geonames_admin1 / '
    'geonames_city (~50k rows after filter, down from ~13M globally). Seeded by import_geonames.py; '
    'the app never writes here. geonames_id is polymorphic — may reference a country, admin1, or city '
    'depending on call site. No FK constraint by design (resolver handles entity-type dispatch).';
COMMENT ON COLUMN external.geonames_alternate_name.alternate_name_id IS
    'GeoNames own alternateNameId. Primary key. Not a UUID — raw upstream integer ID.';
COMMENT ON COLUMN external.geonames_alternate_name.geonames_id IS
    'Polymorphic FK: references a country, admin1, or city entity in GeoNames. '
    'No DB-level FK constraint — entity type is resolved by the caller '
    '(place_name_resolver service). Join against geonames_country.geonames_id, '
    'geonames_admin1.geonames_id, or geonames_city.geonames_id as appropriate.';
COMMENT ON COLUMN external.geonames_alternate_name.iso_language IS
    'ISO 639 language code, possibly with region suffix (e.g. ''en'', ''es'', ''pt'', ''pt-BR''). '
    'Pre-filtered to {en, es, pt} at import time to match Vianda''s supported locales.';
COMMENT ON COLUMN external.geonames_alternate_name.alternate_name IS
    'The localized name itself (e.g. ''Brasil'', ''São Paulo'', ''Ciudad de México''). '
    'Used by the place_name_resolver service to render locale-aware place names.';
COMMENT ON COLUMN external.geonames_alternate_name.is_preferred IS
    'GeoNames flag: this is the official/preferred name for the language. '
    'Resolver prefers rows where is_preferred=TRUE when multiple alternates exist.';
COMMENT ON COLUMN external.geonames_alternate_name.is_short IS
    'GeoNames flag: this is a short-form name (e.g. ''California'' vs ''State of California''). '
    'Resolver may prefer short forms for compact UI labels.';
COMMENT ON COLUMN external.geonames_alternate_name.is_colloquial IS
    'GeoNames flag: slang or colloquial name (e.g. ''Big Apple'' for New York). '
    'Resolver skips colloquial names — they are not suitable for formal UI labels.';
COMMENT ON COLUMN external.geonames_alternate_name.is_historic IS
    'GeoNames flag: historic or former name (e.g. ''Bombay'' for Mumbai). '
    'Resolver skips historic names. Partial index idx_geonames_alt_name_lookup '
    'excludes rows where is_historic=TRUE or is_colloquial=TRUE.';
COMMENT ON COLUMN external.geonames_alternate_name.imported_at IS
    'UTC timestamp of the most recent TSV import into this row. Not a business timestamp.';

-- =============================================================================
-- CREATE TABLES (enum types now exist)
-- =============================================================================

-- Migration tracking (used by migrate.sh; populated with baseline on full rebuild)
CREATE TABLE IF NOT EXISTS core.schema_migration (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT NOT NULL
);

-- National holidays table to prevent kitchen operations on these days
CREATE TABLE IF NOT EXISTS core.national_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuidv7(),
    country_code VARCHAR(3) NOT NULL CHECK (length(country_code) = 2),
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER CHECK (recurring_month IS NULL OR recurring_month BETWEEN 1 AND 12),
    recurring_day INTEGER CHECK (recurring_day IS NULL OR recurring_day BETWEEN 1 AND 31),
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ DEFAULT NOW(),
    source VARCHAR(20) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'nager_date')),
    CHECK (
        source <> 'nager_date'
        OR (
            is_recurring = FALSE
            AND recurring_month IS NULL
            AND recurring_day IS NULL
        )
    )
);

-- One active row per (country, calendar date); sync uses UPSERT for nager_date rows
DROP INDEX IF EXISTS idx_national_holidays_country_date;
CREATE UNIQUE INDEX IF NOT EXISTS uq_national_holidays_country_date_active
    ON core.national_holidays (country_code, holiday_date)
    WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_national_holidays_recurring ON core.national_holidays(country_code, recurring_month, recurring_day) WHERE is_recurring AND NOT is_archived;

-- National holidays history table
CREATE TABLE IF NOT EXISTS audit.national_holidays_history (
    history_id UUID PRIMARY KEY DEFAULT uuidv7(),
    holiday_id UUID NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER,
    recurring_day INTEGER,
    status status_enum NOT NULL,
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ DEFAULT NOW(),
    source VARCHAR(20) NOT NULL,
    history_date TIMESTAMPTZ DEFAULT NOW()
);
COMMENT ON TABLE audit.national_holidays_history IS
    'Trigger-managed history mirror of core.national_holidays. Never written by application code.';
COMMENT ON COLUMN audit.national_holidays_history.history_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.national_holidays_history.history_date IS
    'UTC timestamp when this history row was inserted by the trigger.';

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - enums are now stored directly on entities (core.user_info, etc.)

\echo 'Creating table: core.institution_info'
CREATE TABLE IF NOT EXISTS core.institution_info (
    institution_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(50) NOT NULL,
    institution_type institution_type_enum NOT NULL DEFAULT 'supplier'::institution_type_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    support_email_suppressed_until TIMESTAMPTZ NULL,
    last_support_email_date TIMESTAMPTZ NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

\echo 'Creating table: core.address_info'
CREATE TABLE IF NOT EXISTS core.address_info (
    address_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    user_id UUID NULL,  -- Required only for Customer Comensal home/other; nullable for Supplier, Employee, Employer
    workplace_group_id UUID NULL,  -- Links office address to a workplace group; FK added via deferred ALTER after workplace_group exists
    address_type address_type_enum[] NOT NULL,
    country_code VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2; FK to external.geonames_country via deferred ALTER after external schema populates
    province VARCHAR(50) NOT NULL,     -- display-only; structural province data lives on external.geonames_admin1 via city_metadata → geonames_city.admin1_code
    city VARCHAR(50) NULL,             -- DEPRECATED (PR2) — use city_metadata_id FK instead. Kept for legacy service queries + tests that INSERT raw addresses.
    postal_code VARCHAR(20) NOT NULL,
    street_type street_type_enum NOT NULL DEFAULT 'st'::street_type_enum,
    street_name VARCHAR(100) NOT NULL,
    building_number VARCHAR(20) NOT NULL,
    timezone VARCHAR(50) NOT NULL,     -- populated at write time from external.geonames_city.timezone via city_metadata_id
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT
    -- Note: user_id and modified_by FKs added via ALTER TABLE after core.user_info is created
    -- Note: country_code FK to external.geonames_country added via deferred ALTER below
    -- Note: city_metadata_id column + FK added via deferred ALTER after core.city_metadata is created
    -- Note: composite FK (city_metadata_id, country_code) → city_metadata(city_metadata_id, country_iso) added via deferred ALTER
    -- Note: floor, apartment_unit, is_default moved to core.address_subpremise
);

\echo 'Creating table: audit.address_history'
-- Use case: core.address_info still has updates (address_type from linkages, is_archived, status, modified_by/date).
-- Address core (street, city_metadata_id, province, etc.) is immutable; subpremise edits in core.address_subpremise.
CREATE TABLE IF NOT EXISTS audit.address_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    address_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    user_id UUID NULL,
    workplace_group_id UUID NULL,
    address_type address_type_enum[],
    country_code VARCHAR(2),
    province VARCHAR(50),
    city VARCHAR(50),                              -- DEPRECATED (PR2), mirrors core.address_info.city compat column
    city_metadata_id UUID,                         -- mirrors core.address_info.city_metadata_id (added via deferred ALTER on history too)
    postal_code VARCHAR(20),
    street_type street_type_enum,
    street_name VARCHAR(100),
    building_number VARCHAR(20),
    timezone VARCHAR(50),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT
    -- Note: modified_by FK added via ALTER TABLE after core.user_info is created
    -- Note: city_metadata_id is history-mirrored (no FK enforced — history rows must survive city_metadata archival)
    -- Note: floor, apartment_unit, is_default in core.address_subpremise
);
COMMENT ON TABLE audit.address_history IS
    'Trigger-managed history mirror of core.address_info. Never written by application code.';
COMMENT ON COLUMN audit.address_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.address_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.address_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- core.employer_info REMOVED — employer identity is institution_info (type=employer) + institution_entity_info per country.
-- See docs/plans/MULTINATIONAL_INSTITUTIONS.md

\echo 'Creating table: core.employer_benefits_program'
CREATE TABLE IF NOT EXISTS core.employer_benefits_program (
    program_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    -- Three-tier cascade: entity override → institution default
    -- institution_entity_id IS NULL = institution-level defaults
    -- institution_entity_id IS NOT NULL = entity-level override (currency-tied fields: benefit_cap, minimum_monthly_fee, stripe_*)
    institution_entity_id UUID NULL,
    -- Benefit config
    benefit_rate INTEGER NOT NULL CHECK (benefit_rate >= 0 AND benefit_rate <= 100),
    benefit_cap NUMERIC NULL,
    benefit_cap_period benefit_cap_period_enum NOT NULL DEFAULT 'monthly'::benefit_cap_period_enum,
    -- Employer pricing
    price_discount INTEGER NOT NULL DEFAULT 0 CHECK (price_discount >= 0 AND price_discount <= 100),
    minimum_monthly_fee NUMERIC NULL,
    -- Billing config
    billing_cycle billing_cycle_enum NOT NULL DEFAULT 'monthly'::billing_cycle_enum,
    billing_day INTEGER NULL DEFAULT 1 CHECK (billing_day IS NULL OR (billing_day >= 1 AND billing_day <= 28)),
    billing_day_of_week INTEGER NULL CHECK (billing_day_of_week IS NULL OR (billing_day_of_week >= 0 AND billing_day_of_week <= 6)),
    -- Enrollment
    enrollment_mode enrollment_mode_enum NOT NULL DEFAULT 'managed'::enrollment_mode_enum,
    -- Renewal
    allow_early_renewal BOOLEAN NOT NULL DEFAULT FALSE,
    -- Payment (Phase 2)
    stripe_customer_id VARCHAR(255) NULL,
    stripe_payment_method_id VARCHAR(255) NULL,
    payment_method_type VARCHAR(50) NULL,
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    CONSTRAINT uq_employer_program_scope UNIQUE (institution_id, institution_entity_id)
    -- Note: modified_by FK added via ALTER TABLE after core.user_info is created
    -- Note: institution_entity_id FK to ops.institution_entity_info added via deferred ALTER (entity table created later)
);

\echo 'Creating table: audit.employer_benefits_program_history'
CREATE TABLE IF NOT EXISTS audit.employer_benefits_program_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    program_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NULL,
    benefit_rate INTEGER NOT NULL,
    benefit_cap NUMERIC NULL,
    benefit_cap_period benefit_cap_period_enum NOT NULL,
    price_discount INTEGER NOT NULL,
    minimum_monthly_fee NUMERIC NULL,
    billing_cycle billing_cycle_enum NOT NULL,
    billing_day INTEGER NULL,
    billing_day_of_week INTEGER NULL,
    enrollment_mode enrollment_mode_enum NOT NULL,
    allow_early_renewal BOOLEAN NOT NULL,
    stripe_customer_id VARCHAR(255) NULL,
    stripe_payment_method_id VARCHAR(255) NULL,
    payment_method_type VARCHAR(50) NULL,
    is_active BOOLEAN NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (program_id) REFERENCES core.employer_benefits_program(program_id) ON DELETE RESTRICT
    -- Note: modified_by FK not enforced on audit tables (history rows must survive user changes)
);
COMMENT ON TABLE audit.employer_benefits_program_history IS
    'Trigger-managed history mirror of core.employer_benefits_program. Never written by application code.';
COMMENT ON COLUMN audit.employer_benefits_program_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.employer_benefits_program_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.employer_benefits_program_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- core.employer_domain REMOVED — replaced by email_domain column on ops.institution_entity_info.
-- See docs/plans/MULTINATIONAL_INSTITUTIONS.md

\echo 'Creating table: core.lead_interest'
CREATE TABLE IF NOT EXISTS core.lead_interest (
    lead_interest_id UUID PRIMARY KEY DEFAULT uuidv7(),
    email citext NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    city_name VARCHAR(100),
    zipcode VARCHAR(20),
    zipcode_only BOOLEAN NOT NULL DEFAULT FALSE,
    interest_type interest_type_enum NOT NULL DEFAULT 'customer'::interest_type_enum,
    business_name VARCHAR(200),
    message TEXT,
    cuisine_id UUID,
    employee_count_range VARCHAR(20),
    status lead_interest_status_enum NOT NULL DEFAULT 'active'::lead_interest_status_enum,
    source lead_interest_source_enum NOT NULL,
    notified_date TIMESTAMPTZ,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

\echo 'Creating table: core.restaurant_lead'
CREATE TABLE IF NOT EXISTS core.restaurant_lead (
    restaurant_lead_id UUID PRIMARY KEY DEFAULT uuidv7(),
    -- Contact
    business_name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(200) NOT NULL,
    contact_email citext NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    city_name VARCHAR(100) NOT NULL,
    -- Business profile
    years_in_operation INTEGER NOT NULL CHECK (years_in_operation >= 0),
    employee_count_range VARCHAR(20) NOT NULL,
    kitchen_capacity_daily INTEGER NOT NULL CHECK (kitchen_capacity_daily >= 1),
    website_url VARCHAR(500),
    referral_source restaurant_lead_referral_source_enum NOT NULL,
    message TEXT,
    -- Vetting (JSONB for flexibility until questions are finalized per country)
    vetting_answers JSONB NOT NULL DEFAULT '{}',
    -- Status / workflow
    lead_status restaurant_lead_status_enum NOT NULL DEFAULT 'submitted'::restaurant_lead_status_enum,
    rejection_reason TEXT,
    reviewed_by UUID,  -- FK added after user_info exists
    reviewed_at TIMESTAMPTZ,
    -- Link to institution created on approval
    institution_id UUID,  -- FK added after institution_info exists (already created above)
    -- Ad click tracking
    gclid VARCHAR(255),
    fbclid VARCHAR(255),
    fbc VARCHAR(500),
    fbp VARCHAR(255),
    event_id VARCHAR(255),
    source_platform VARCHAR(20),
    -- Standard fields
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_status ON core.restaurant_lead(lead_status);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_country ON core.restaurant_lead(country_code);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_email ON core.restaurant_lead(contact_email);

-- restaurant_lead_cuisine junction (many-to-many with cuisine, created later)
-- Deferred: see after cuisine table is created

\echo 'Creating table: core.workplace_group'
CREATE TABLE IF NOT EXISTS core.workplace_group (
    workplace_group_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name               VARCHAR(100) NOT NULL,
    email_domain       VARCHAR(255) NULL,
    require_domain_verification BOOLEAN NOT NULL DEFAULT FALSE,
    is_archived        BOOLEAN     NOT NULL DEFAULT FALSE,
    status             status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by         UUID        NULL,
    modified_by        UUID        NOT NULL,
    modified_date      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_workplace_group_name ON core.workplace_group USING gin (name gin_trgm_ops);

\echo 'Creating table: audit.workplace_group_history'
CREATE TABLE IF NOT EXISTS audit.workplace_group_history (
    event_id           UUID        PRIMARY KEY DEFAULT uuidv7(),
    workplace_group_id UUID        NOT NULL,
    name               VARCHAR(100) NOT NULL,
    email_domain       VARCHAR(255) NULL,
    require_domain_verification BOOLEAN NOT NULL,
    is_archived        BOOLEAN     NOT NULL,
    status             status_enum NOT NULL,
    created_date       TIMESTAMPTZ NOT NULL,
    created_by         UUID        NULL,
    modified_by        UUID        NOT NULL,
    modified_date      TIMESTAMPTZ NOT NULL,
    is_current         BOOLEAN     DEFAULT TRUE,
    valid_until        TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (workplace_group_id) REFERENCES core.workplace_group(workplace_group_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.workplace_group_history IS
    'Trigger-managed history mirror of core.workplace_group. Never written by application code.';
COMMENT ON COLUMN audit.workplace_group_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.workplace_group_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.workplace_group_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- Deferred FK: address_info.workplace_group_id → workplace_group (address_info created before workplace_group)
\echo 'Adding deferred FK: address_info.workplace_group_id -> workplace_group'
ALTER TABLE core.address_info
    ADD CONSTRAINT fk_address_workplace_group
    FOREIGN KEY (workplace_group_id) REFERENCES core.workplace_group(workplace_group_id) ON DELETE SET NULL;

\echo 'Creating table: core.user_info'
CREATE TABLE IF NOT EXISTS core.user_info (
    user_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,
    role_name role_name_enum NOT NULL,
    username citext NOT NULL,
    email citext NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    mobile_number VARCHAR(16) CHECK (mobile_number IS NULL OR mobile_number ~ E'^\\+[1-9][0-9]{6,14}$'),
    mobile_number_verified BOOLEAN NOT NULL DEFAULT FALSE,
    mobile_number_verified_at TIMESTAMPTZ,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified_at TIMESTAMPTZ,
    -- Employer tracking fields (only applicable to Customer role_type)
    employer_entity_id UUID NULL, -- For end-customers: links to their employer's entity (institution_entity_info)
    employer_address_id UUID NULL REFERENCES core.address_info(address_id) ON DELETE SET NULL,
    -- Workplace group for coworker pickup coordination (B2C)
    workplace_group_id UUID NULL REFERENCES core.workplace_group(workplace_group_id) ON DELETE SET NULL,
    support_email_suppressed_until TIMESTAMPTZ NULL,
    last_support_email_date TIMESTAMPTZ NULL,
    -- Referral tracking
    referral_code VARCHAR(20) UNIQUE,
    referred_by_code VARCHAR(20),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    -- Note: employer_entity_id FK to ops.institution_entity_info added via deferred ALTER (entity table created later)
);

-- =============================================================================
-- DEFERRED FOREIGN KEYS: tables created before core.user_info
-- =============================================================================
\echo 'Adding deferred foreign keys referencing core.user_info'

-- core.national_holidays
ALTER TABLE core.national_holidays
    ADD CONSTRAINT fk_national_holidays_modified_by
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT;

-- core.institution_info
ALTER TABLE core.institution_info
    ADD CONSTRAINT fk_institution_info_modified_by
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT;

-- core.address_info
ALTER TABLE core.address_info
    ADD CONSTRAINT fk_address_info_user_id
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE SET NULL;

ALTER TABLE core.address_info
    ADD CONSTRAINT fk_address_info_modified_by
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT;

-- core.employer_info REMOVED — see MULTINATIONAL_INSTITUTIONS.md

-- core.employer_benefits_program
ALTER TABLE core.employer_benefits_program
    ADD CONSTRAINT fk_employer_benefits_program_modified_by
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT;

-- core.employer_domain REMOVED — see MULTINATIONAL_INSTITUTIONS.md

-- core.restaurant_lead
ALTER TABLE core.restaurant_lead
    ADD CONSTRAINT fk_restaurant_lead_reviewed_by
    FOREIGN KEY (reviewed_by) REFERENCES core.user_info(user_id) ON DELETE SET NULL;

\echo 'Creating table: core.address_subpremise'
CREATE TABLE IF NOT EXISTS core.address_subpremise (
    subpremise_id UUID PRIMARY KEY DEFAULT uuidv7(),
    address_id UUID NOT NULL REFERENCES core.address_info(address_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE CASCADE,
    floor VARCHAR(50) NULL,
    apartment_unit VARCHAR(20) NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    map_center_label VARCHAR(20) NULL,  -- 'home' | 'other' | NULL (NULL = home). User-set label for map center-of-gravity selection.
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (address_id, user_id)
);

-- core.credit_currency_info retired — replaced by external.iso4217_currency (raw) + core.currency_metadata (Vianda policy).
-- See docs/plans/country_city_data_structure.md Currency two-tier section.

\echo 'Creating table: core.currency_rate_raw'
CREATE TABLE IF NOT EXISTS core.currency_rate_raw (
    currency_rate_raw_id UUID PRIMARY KEY DEFAULT uuidv7(),
    fetched_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    base_currency         VARCHAR(10) NOT NULL DEFAULT 'USD',
    target_currency       VARCHAR(10) NOT NULL,
    rate                  NUMERIC(20, 8) NOT NULL,
    api_source            VARCHAR(100) NOT NULL DEFAULT 'open.er-api',
    api_date              DATE NOT NULL,
    raw_payload           JSONB NOT NULL,
    is_valid              BOOLEAN NOT NULL DEFAULT TRUE,
    notes                 VARCHAR(500)
);

CREATE INDEX idx_currency_rate_raw_target_fetched
    ON core.currency_rate_raw(target_currency, fetched_at DESC);

-- =============================================================================
-- CURRENCY METADATA (Vianda pricing policy on top of external.iso4217_currency)
-- =============================================================================
-- Placed before core.market_info because market_info FKs currency_metadata inline.
-- Country/city metadata tables come later (after market_info) because country_metadata
-- FKs market_info, and the layout reads most naturally with the market alongside them.

\echo 'Creating table: core.currency_metadata'
-- PR2a note: currency_name column dropped — display name now derives from
-- external.iso4217_currency.name via JOIN on currency_code (see market_service,
-- entity_service). Services that used core.credit_currency_info.currency_name
-- now use JOIN external.iso4217_currency ic ON ic.code = cc.currency_code.
CREATE TABLE IF NOT EXISTS core.currency_metadata (
    currency_metadata_id        UUID PRIMARY KEY DEFAULT uuidv7(),
    currency_code               VARCHAR(3) NOT NULL UNIQUE
                                REFERENCES external.iso4217_currency(code) ON DELETE RESTRICT,
    credit_value_local_currency NUMERIC NOT NULL,    -- Vianda-owned pricing policy: "1 credit" local currency value
    currency_conversion_usd     NUMERIC NOT NULL,    -- operational USD conversion rate (snapshotted; updated via ops flow)
    is_archived                 BOOLEAN NOT NULL DEFAULT FALSE,
    status                      status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by                  UUID NULL,
    modified_by                 UUID NOT NULL,
    modified_date               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.currency_metadata_history'
CREATE TABLE IF NOT EXISTS audit.currency_metadata_history (
    event_id                    UUID PRIMARY KEY DEFAULT uuidv7(),
    currency_metadata_id        UUID NOT NULL,
    currency_code               VARCHAR(3) NOT NULL,
    credit_value_local_currency NUMERIC NOT NULL,
    currency_conversion_usd     NUMERIC NOT NULL,
    is_archived                 BOOLEAN NOT NULL,
    status                      status_enum NOT NULL,
    created_date                TIMESTAMPTZ NOT NULL,
    created_by                  UUID NULL,
    modified_by                 UUID NOT NULL,
    modified_date               TIMESTAMPTZ NOT NULL,
    is_current                  BOOLEAN DEFAULT TRUE,
    valid_until                 TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.currency_metadata_history IS
    'Trigger-managed history mirror of core.currency_metadata. Never written by application code.';
COMMENT ON COLUMN audit.currency_metadata_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.currency_metadata_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.currency_metadata_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: core.market_info'
-- PR2a/PR2b note: country_name and timezone columns dropped. country_name derives
-- from external.geonames_country.name via JOIN on country_code; operational timezone
-- lives on core.address_info.timezone (per-restaurant) and notification_banner_cron
-- joins restaurant → address to use the restaurant's local timezone. Single-country
-- fallback lookups live in app/services/timezone_service._MARKET_PRIMARY_TIMEZONE.
-- kitchen_open_time + kitchen_close_time moved to billing.market_payout_aggregator
-- (market defaults) and billing.supplier_terms (per-supplier overrides). Resolution:
-- supplier_terms → market_payout_aggregator → hardcoded 09:00/13:30.
CREATE TABLE IF NOT EXISTS core.market_info (
    market_id UUID PRIMARY KEY DEFAULT uuidv7(),
    country_code VARCHAR(2) NOT NULL UNIQUE,            -- ISO 3166-1 alpha-2; FK to external.geonames_country
    currency_metadata_id UUID NOT NULL,                 -- FK to core.currency_metadata (two-tier ISO 4217 layer)
    language VARCHAR(5) NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'es', 'pt')),
    phone_dial_code VARCHAR(6) NULL,                    -- E.164 country prefix e.g. '+54'; NULL for pseudo-markets
    phone_local_digits SMALLINT NULL,                   -- Max national digits after dial code; UI maxLength hint e.g. 10
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (country_code) REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

-- Add foreign key constraint from core.address_info to external.geonames_country (deferred until external schema + all tables exist)
\echo 'Adding foreign key: core.address_info.country_code -> external.geonames_country.iso_alpha2'
ALTER TABLE core.address_info ADD CONSTRAINT fk_address_country_code FOREIGN KEY (country_code) REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT;

-- core.address_info.city_metadata_id column added here (NOT NULL as of PR4c).
-- Single FK + composite-consistency FK added at the bottom of schema.sql, after core.city_metadata exists.
-- PR4c: flipped from nullable to NOT NULL — every address writer is required to provide
-- city_metadata_id; timezone derives from external.geonames_city.timezone via the FK chain.
\echo 'Adding core.address_info.city_metadata_id column (NOT NULL; FK deferred to end of schema.sql)'
ALTER TABLE core.address_info ADD COLUMN city_metadata_id UUID NOT NULL;
CREATE INDEX IF NOT EXISTS idx_address_info_city_metadata_id ON core.address_info(city_metadata_id);

\echo 'Creating table: audit.market_history'
CREATE TABLE IF NOT EXISTS audit.market_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    currency_metadata_id UUID NOT NULL,
    language VARCHAR(5) NOT NULL CHECK (language IN ('en', 'es', 'pt')),
    phone_dial_code VARCHAR(6) NULL,
    phone_local_digits SMALLINT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.market_history IS
    'Trigger-managed history mirror of core.market_info. Never written by application code.';
COMMENT ON COLUMN audit.market_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.market_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.market_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- =============================================================================
-- METADATA LAYER (Vianda flags + policy on top of external.* raw data)
-- =============================================================================
-- One metadata row per country/city/currency Vianda has explicitly promoted via
-- the vianda-platform superadmin flow. See docs/plans/country_city_data_structure.md.
--
-- `status` distinguishes 'pending' (promoted for inclusion in interest forms
-- but no real supplier activity yet) from 'active' (has real activity). Flip
-- from pending→active happens via service code, not a DB trigger, when the
-- first supplier registers in the country / city.
--
-- `display_name_override` and `display_name_i18n` are populated only when Vianda
-- explicitly disagrees with GeoNames. The place_name_resolver service falls back:
--   metadata override → external.geonames_alternate_name → canonical name.

\echo 'Creating table: core.country_metadata'
CREATE TABLE IF NOT EXISTS core.country_metadata (
    country_metadata_id    UUID PRIMARY KEY DEFAULT uuidv7(),
    country_iso            VARCHAR(2) NOT NULL UNIQUE
                           REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    market_id              UUID NULL
                           REFERENCES core.market_info(market_id) ON DELETE SET NULL,  -- NULL = exposed in audience lists but no operational market yet
    display_name_override  VARCHAR(200) NULL,
    display_name_i18n      JSONB NULL,                                                  -- {"en": "...", "es": "...", "pt": "..."} — override hatch; resolver reads alternate_name table by default
    is_customer_audience   BOOLEAN NOT NULL DEFAULT FALSE,                              -- appears in /leads/markets default
    is_supplier_audience   BOOLEAN NOT NULL DEFAULT FALSE,                              -- appears in /leads/markets?audience=supplier
    is_employer_audience   BOOLEAN NOT NULL DEFAULT FALSE,                              -- reserved for future employer flow
    is_archived            BOOLEAN NOT NULL DEFAULT FALSE,
    status                 status_enum NOT NULL DEFAULT 'pending'::status_enum,         -- 'pending' until first real supplier lands; flipped by service code
    created_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by             UUID NULL,
    modified_by            UUID NOT NULL,
    modified_date          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_country_metadata_market
    ON core.country_metadata(market_id) WHERE market_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_country_metadata_supplier_audience
    ON core.country_metadata(country_iso)
    WHERE is_supplier_audience = TRUE AND is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_country_metadata_customer_audience
    ON core.country_metadata(country_iso)
    WHERE is_customer_audience = TRUE AND is_archived = FALSE;

\echo 'Creating table: audit.country_metadata_history'
CREATE TABLE IF NOT EXISTS audit.country_metadata_history (
    event_id               UUID PRIMARY KEY DEFAULT uuidv7(),
    country_metadata_id    UUID NOT NULL,
    country_iso            VARCHAR(2) NOT NULL,
    market_id              UUID NULL,
    display_name_override  VARCHAR(200) NULL,
    display_name_i18n      JSONB NULL,
    is_customer_audience   BOOLEAN NOT NULL,
    is_supplier_audience   BOOLEAN NOT NULL,
    is_employer_audience   BOOLEAN NOT NULL,
    is_archived            BOOLEAN NOT NULL,
    status                 status_enum NOT NULL,
    created_date           TIMESTAMPTZ NOT NULL,
    created_by             UUID NULL,
    modified_by            UUID NOT NULL,
    modified_date          TIMESTAMPTZ NOT NULL,
    is_current             BOOLEAN DEFAULT TRUE,
    valid_until            TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (country_metadata_id) REFERENCES core.country_metadata(country_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.country_metadata_history IS
    'Trigger-managed history mirror of core.country_metadata. Never written by application code.';
COMMENT ON COLUMN audit.country_metadata_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.country_metadata_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.country_metadata_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: core.city_metadata'
CREATE TABLE IF NOT EXISTS core.city_metadata (
    city_metadata_id       UUID PRIMARY KEY DEFAULT uuidv7(),
    geonames_id            INTEGER NOT NULL UNIQUE
                           REFERENCES external.geonames_city(geonames_id) ON DELETE RESTRICT,
    country_iso            VARCHAR(2) NOT NULL
                           REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    display_name_override  VARCHAR(200) NULL,
    display_name_i18n      JSONB NULL,
    show_in_signup_picker  BOOLEAN NOT NULL DEFAULT FALSE,  -- replaces the old city_info "is this a signup-selectable city?" role
    show_in_supplier_form  BOOLEAN NOT NULL DEFAULT FALSE,  -- supplier lead capture dropdown
    show_in_customer_form  BOOLEAN NOT NULL DEFAULT FALSE,  -- customer interest capture dropdown
    is_served              BOOLEAN NOT NULL DEFAULT FALSE,  -- derived flag: ≥1 active restaurant w/ plates + QR
    is_archived            BOOLEAN NOT NULL DEFAULT FALSE,
    status                 status_enum NOT NULL DEFAULT 'pending'::status_enum,  -- 'pending' until first restaurant lands here
    created_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by             UUID NULL,
    modified_by            UUID NOT NULL,
    modified_date          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    -- Composite unique: anything pointing at city_metadata via (city_metadata_id, country_code)
    -- can FK here to enforce country/city consistency on address_info in the next PR.
    UNIQUE (city_metadata_id, country_iso)
);
CREATE INDEX IF NOT EXISTS idx_city_metadata_country
    ON core.city_metadata (country_iso) WHERE is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_city_metadata_country_supplier
    ON core.city_metadata (country_iso)
    WHERE show_in_supplier_form = TRUE AND is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_city_metadata_country_customer
    ON core.city_metadata (country_iso)
    WHERE show_in_customer_form = TRUE AND is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_city_metadata_country_signup
    ON core.city_metadata (country_iso)
    WHERE show_in_signup_picker = TRUE AND is_archived = FALSE;

\echo 'Creating table: audit.city_metadata_history'
CREATE TABLE IF NOT EXISTS audit.city_metadata_history (
    event_id               UUID PRIMARY KEY DEFAULT uuidv7(),
    city_metadata_id       UUID NOT NULL,
    geonames_id            INTEGER NOT NULL,
    country_iso            VARCHAR(2) NOT NULL,
    display_name_override  VARCHAR(200) NULL,
    display_name_i18n      JSONB NULL,
    show_in_signup_picker  BOOLEAN NOT NULL,
    show_in_supplier_form  BOOLEAN NOT NULL,
    show_in_customer_form  BOOLEAN NOT NULL,
    is_served              BOOLEAN NOT NULL,
    is_archived            BOOLEAN NOT NULL,
    status                 status_enum NOT NULL,
    created_date           TIMESTAMPTZ NOT NULL,
    created_by             UUID NULL,
    modified_by            UUID NOT NULL,
    modified_date          TIMESTAMPTZ NOT NULL,
    is_current             BOOLEAN DEFAULT TRUE,
    valid_until            TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (city_metadata_id) REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.city_metadata_history IS
    'Trigger-managed history mirror of core.city_metadata. Never written by application code.';
COMMENT ON COLUMN audit.city_metadata_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.city_metadata_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.city_metadata_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- core.currency_metadata + audit moved above core.market_info (market_info FKs it inline).

-- core.city_info retired — replaced by core.city_metadata (metadata layer on top of external.geonames_city).
-- See docs/plans/country_city_data_structure.md.

\echo 'Adding core.user_info.market_id (required: one market per user, v1)'
ALTER TABLE core.user_info ADD COLUMN market_id UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_user_info_market_id ON core.user_info(market_id);

\echo 'Adding core.user_info.locale (ISO 639-1: en, es, pt)'
ALTER TABLE core.user_info ADD COLUMN locale VARCHAR(5) NOT NULL DEFAULT 'en' CHECK (locale IN ('en', 'es', 'pt'));

\echo 'Adding core.user_info.city_metadata_id (user primary city for scoping; FK to core.city_metadata; default Global for B2B)'
-- Default points at the Global synthetic city_metadata row inserted by reference_data.sql;
-- reusing the historic Global city_info UUID for continuity across seed and tests.
ALTER TABLE core.user_info ADD COLUMN city_metadata_id UUID NOT NULL DEFAULT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_user_info_city_metadata_id ON core.user_info(city_metadata_id);

-- institution_info.market_id REMOVED — replaced by core.institution_market junction table.
-- See docs/plans/MULTINATIONAL_INSTITUTIONS.md

\echo 'Creating table: core.institution_market (multi-market assignment per institution)'
CREATE TABLE IF NOT EXISTS core.institution_market (
    institution_id UUID NOT NULL REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    market_id      UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    is_primary     BOOLEAN NOT NULL DEFAULT FALSE,
    created_date   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (institution_id, market_id)
);
CREATE INDEX IF NOT EXISTS idx_institution_market_market ON core.institution_market(market_id);

\echo 'Creating table: core.user_market_assignment (v2: multi-market per user)'
CREATE TABLE IF NOT EXISTS core.user_market_assignment (
    assignment_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE CASCADE,
    market_id UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, market_id)
);
CREATE INDEX IF NOT EXISTS idx_user_market_assignment_user_id ON core.user_market_assignment(user_id);
CREATE INDEX IF NOT EXISTS idx_user_market_assignment_market_id ON core.user_market_assignment(market_id);

\echo 'Creating table: core.user_messaging_preferences'
CREATE TABLE IF NOT EXISTS core.user_messaging_preferences (
    user_id UUID PRIMARY KEY REFERENCES core.user_info(user_id) ON DELETE CASCADE,
    notify_coworker_pickup_alert BOOLEAN NOT NULL DEFAULT TRUE,
    notify_plate_readiness_alert BOOLEAN NOT NULL DEFAULT TRUE,
    notify_promotions_push BOOLEAN NOT NULL DEFAULT TRUE,
    notify_promotions_email BOOLEAN NOT NULL DEFAULT TRUE,
    coworkers_can_see_my_orders BOOLEAN NOT NULL DEFAULT TRUE,
    can_participate_in_plate_pickups BOOLEAN NOT NULL DEFAULT TRUE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

\echo 'Creating table: core.user_fcm_token'
CREATE TABLE IF NOT EXISTS core.user_fcm_token (
    fcm_token_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    token VARCHAR(500) NOT NULL,
    platform VARCHAR(10) NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (token),
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_fcm_token_user_id ON core.user_fcm_token(user_id);

\echo 'Creating table: audit.institution_history'
CREATE TABLE IF NOT EXISTS audit.institution_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    name VARCHAR(50) NOT NULL,
    institution_type institution_type_enum NOT NULL,
    -- market_id REMOVED — institution markets now in core.institution_market junction
    support_email_suppressed_until TIMESTAMPTZ NULL,
    last_support_email_date TIMESTAMPTZ NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.institution_history IS
    'Trigger-managed history mirror of core.institution_info. Never written by application code.';
COMMENT ON COLUMN audit.institution_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.institution_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.institution_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: audit.user_history'
CREATE TABLE IF NOT EXISTS audit.user_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,
    role_name role_name_enum NOT NULL,
    username citext NOT NULL,
    email citext NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    mobile_number VARCHAR(16),
    mobile_number_verified BOOLEAN NOT NULL DEFAULT FALSE,
    mobile_number_verified_at TIMESTAMPTZ,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified_at TIMESTAMPTZ,
    employer_entity_id UUID NULL, -- For end-customers: links to their employer's entity (institution_entity_info)
    workplace_group_id UUID NULL, -- For coworker pickup coordination (B2C)
    support_email_suppressed_until TIMESTAMPTZ NULL,
    last_support_email_date TIMESTAMPTZ NULL,
    market_id UUID NOT NULL,
    city_metadata_id UUID NOT NULL,
    locale VARCHAR(5) NOT NULL CHECK (locale IN ('en', 'es', 'pt')),
    referral_code VARCHAR(20),
    referred_by_code VARCHAR(20),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.user_history IS
    'Trigger-managed history mirror of core.user_info. Never written by application code.';
COMMENT ON COLUMN audit.user_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.user_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.user_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: customer.credential_recovery'
CREATE TABLE IF NOT EXISTS customer.credential_recovery (
    credential_recovery_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    recovery_code VARCHAR(10) NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_date TIMESTAMPTZ,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_credential_recovery_code ON customer.credential_recovery(recovery_code);
CREATE INDEX IF NOT EXISTS idx_credential_recovery_user_id ON customer.credential_recovery(user_id);

\echo 'Creating table: customer.email_change_request'
CREATE TABLE IF NOT EXISTS customer.email_change_request (
    email_change_request_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    new_email citext NOT NULL,
    verification_code VARCHAR(10) NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_date TIMESTAMPTZ,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: customer.pending_customer_signup'
CREATE TABLE IF NOT EXISTS customer.pending_customer_signup (
    pending_id UUID PRIMARY KEY DEFAULT uuidv7(),
    email citext NOT NULL,
    verification_code VARCHAR(10) NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    username citext NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    mobile_number VARCHAR(16) CHECK (mobile_number IS NULL OR mobile_number ~ E'^\\+[1-9][0-9]{6,14}$'),
    market_id UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    city_metadata_id UUID NOT NULL REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT,
    referral_code VARCHAR(20)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_customer_signup_code ON customer.pending_customer_signup(verification_code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_customer_signup_email_active ON customer.pending_customer_signup(email) WHERE used = FALSE;
CREATE INDEX IF NOT EXISTS idx_pending_customer_signup_expiry ON customer.pending_customer_signup(token_expiry);

\echo 'Creating table: core.geolocation_info'
CREATE TABLE IF NOT EXISTS core.geolocation_info (
    geolocation_id UUID PRIMARY KEY DEFAULT uuidv7(),
    address_id UUID NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    place_id VARCHAR(500) NULL,  -- Mapbox mapbox_id can exceed 255 chars
    viewport JSONB NULL,
    formatted_address_google VARCHAR(500) NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.geolocation_history'
CREATE TABLE IF NOT EXISTS audit.geolocation_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    geolocation_id UUID NOT NULL,
    address_id UUID NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    place_id VARCHAR(500) NULL,  -- matches geolocation_info
    viewport JSONB NULL,
    formatted_address_google VARCHAR(500) NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMP DEFAULT 'infinity',
    FOREIGN KEY (geolocation_id) REFERENCES core.geolocation_info(geolocation_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.geolocation_history IS
    'Trigger-managed history mirror of core.geolocation_info. Never written by application code.';
COMMENT ON COLUMN audit.geolocation_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.geolocation_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.geolocation_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: ops.institution_entity_info'
CREATE TABLE IF NOT EXISTS ops.institution_entity_info (
    institution_entity_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    address_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    tax_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    payout_provider_account_id VARCHAR(255) NULL,
    payout_aggregator          VARCHAR(50)  NULL,
    payout_onboarding_status   VARCHAR(50)  NULL,
    -- Email domain for domain-gated enrollment (employer entities) and future SSO (all entity types)
    email_domain               VARCHAR(255) NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_email_domain
    ON ops.institution_entity_info(email_domain)
    WHERE email_domain IS NOT NULL AND is_archived = FALSE;

\echo 'Creating table: audit.institution_entity_history'
CREATE TABLE IF NOT EXISTS audit.institution_entity_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id UUID NOT NULL,
    institution_id UUID,
    address_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    tax_id VARCHAR(50),
    name VARCHAR(100),
    payout_provider_account_id VARCHAR(255) NULL,
    payout_aggregator          VARCHAR(50)  NULL,
    payout_onboarding_status   VARCHAR(50)  NULL,
    email_domain               VARCHAR(255) NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.institution_entity_history IS
    'Trigger-managed history mirror of ops.institution_entity_info. Never written by application code.';
COMMENT ON COLUMN audit.institution_entity_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.institution_entity_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.institution_entity_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- Deferred FKs: tables created before ops.institution_entity_info that reference it
\echo 'Adding deferred FK: employer_benefits_program.institution_entity_id -> institution_entity_info'
ALTER TABLE core.employer_benefits_program
    ADD CONSTRAINT fk_employer_program_entity_id
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT;

\echo 'Adding deferred FK: user_info.employer_entity_id -> institution_entity_info'
ALTER TABLE core.user_info
    ADD CONSTRAINT fk_user_info_employer_entity_id
    FOREIGN KEY (employer_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE SET NULL;

\echo 'Creating table: ops.cuisine'
CREATE TABLE IF NOT EXISTS ops.cuisine (
    cuisine_id UUID PRIMARY KEY DEFAULT uuidv7(),
    cuisine_name VARCHAR(80) NOT NULL,
    cuisine_name_i18n JSONB,
    slug VARCHAR(80) NOT NULL UNIQUE,
    parent_cuisine_id UUID REFERENCES ops.cuisine(cuisine_id) ON DELETE RESTRICT,
    description VARCHAR(500),
    origin_source VARCHAR(20) NOT NULL DEFAULT 'seed' CHECK (origin_source IN ('seed', 'supplier')),
    display_order INT,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_cuisine_slug ON ops.cuisine(slug);
CREATE INDEX IF NOT EXISTS idx_cuisine_parent ON ops.cuisine(parent_cuisine_id) WHERE parent_cuisine_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cuisine_active ON ops.cuisine(cuisine_id) WHERE NOT is_archived AND status = 'active';

\echo 'Creating table: audit.cuisine_history'
CREATE TABLE IF NOT EXISTS audit.cuisine_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    cuisine_id UUID NOT NULL,
    cuisine_name VARCHAR(80),
    cuisine_name_i18n JSONB,
    slug VARCHAR(80),
    parent_cuisine_id UUID,
    description VARCHAR(500),
    origin_source VARCHAR(20),
    display_order INT,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (cuisine_id) REFERENCES ops.cuisine(cuisine_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.cuisine_history IS
    'Trigger-managed history mirror of ops.cuisine. Never written by application code.';
COMMENT ON COLUMN audit.cuisine_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.cuisine_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.cuisine_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: ops.restaurant_info'
CREATE TABLE IF NOT EXISTS ops.restaurant_info (
    restaurant_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    address_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    cuisine_id UUID REFERENCES ops.cuisine(cuisine_id) ON DELETE SET NULL,
    pickup_instructions VARCHAR(500),
    tagline VARCHAR(500),
    tagline_i18n JSONB,
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    cover_image_url TEXT,
    average_rating NUMERIC(3,1),
    review_count INTEGER NOT NULL DEFAULT 0,
    verified_badge BOOLEAN NOT NULL DEFAULT FALSE,
    spotlight_label VARCHAR(200),
    spotlight_label_i18n JSONB,
    member_perks TEXT[],
    member_perks_i18n JSONB,
    require_kiosk_code_verification BOOLEAN NOT NULL DEFAULT FALSE,
    -- Kitchen hours copied from supplier_terms (or market_payout_aggregator defaults)
    -- at restaurant-create time. Owned by restaurant_info thereafter — no runtime fallback.
    -- TIME is naive wall-clock, interpreted per-restaurant in address_info.timezone at runtime.
    kitchen_open_time  TIME NOT NULL DEFAULT '09:00',
    kitchen_close_time TIME NOT NULL DEFAULT '13:30',
    -- PostGIS point (SRID 4326 = WGS84 lon/lat) for geo proximity and bbox filtering.
    -- NULL = location not yet geocoded. Populated via API or admin tooling.
    location geometry(Point, 4326),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'pending'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.restaurant_history'
CREATE TABLE IF NOT EXISTS audit.restaurant_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    address_id UUID NOT NULL,
    name VARCHAR(100),
    cuisine_id UUID,
    pickup_instructions VARCHAR(500),
    tagline VARCHAR(500),
    tagline_i18n JSONB,
    is_featured BOOLEAN,
    cover_image_url TEXT,
    average_rating NUMERIC(3,1),
    review_count INTEGER,
    verified_badge BOOLEAN,
    spotlight_label VARCHAR(200),
    spotlight_label_i18n JSONB,
    member_perks TEXT[],
    member_perks_i18n JSONB,
    require_kiosk_code_verification BOOLEAN,
    kitchen_open_time  TIME NOT NULL,
    kitchen_close_time TIME NOT NULL,
    location geometry(Point, 4326),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.restaurant_history IS
    'Trigger-managed history mirror of ops.restaurant_info. Never written by application code.';
COMMENT ON COLUMN audit.restaurant_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.restaurant_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.restaurant_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: ops.cuisine_suggestion'
CREATE TABLE IF NOT EXISTS ops.cuisine_suggestion (
    suggestion_id UUID PRIMARY KEY DEFAULT uuidv7(),
    suggested_name VARCHAR(120) NOT NULL,
    suggested_by UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    restaurant_id UUID REFERENCES ops.restaurant_info(restaurant_id) ON DELETE SET NULL,
    suggestion_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (suggestion_status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    reviewed_date TIMESTAMPTZ,
    review_notes VARCHAR(500),
    resolved_cuisine_id UUID REFERENCES ops.cuisine(cuisine_id) ON DELETE SET NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_cuisine_suggestion_pending ON ops.cuisine_suggestion(suggestion_status) WHERE suggestion_status = 'pending';

\echo 'Creating table: core.restaurant_lead_cuisine'
CREATE TABLE IF NOT EXISTS core.restaurant_lead_cuisine (
    restaurant_lead_id UUID NOT NULL REFERENCES core.restaurant_lead(restaurant_lead_id) ON DELETE CASCADE,
    cuisine_id UUID NOT NULL REFERENCES ops.cuisine(cuisine_id) ON DELETE CASCADE,
    PRIMARY KEY (restaurant_lead_id, cuisine_id)
);

\echo 'Creating table: ops.qr_code'
CREATE TABLE IF NOT EXISTS ops.qr_code (
    qr_code_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    qr_code_payload VARCHAR(255) NOT NULL,
    qr_code_image_url VARCHAR(500) NOT NULL,
    image_storage_path VARCHAR(500) NOT NULL,
    qr_code_checksum VARCHAR(128),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: ops.product_info'
CREATE TABLE IF NOT EXISTS ops.product_info (
    product_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_i18n JSONB,
    ingredients VARCHAR(255),
    ingredients_i18n JSONB,
    description VARCHAR(1000),
    description_i18n JSONB,
    dietary TEXT[] NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    image_storage_path VARCHAR(500) NOT NULL DEFAULT 'static/placeholders/product_default.png',
    image_checksum VARCHAR(128) NOT NULL DEFAULT '7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c',
    image_url VARCHAR(500) NOT NULL DEFAULT 'http://localhost:8000/static/placeholders/product_default.png',
    image_thumbnail_storage_path VARCHAR(500) NOT NULL DEFAULT 'static/placeholders/product_default.png',
    image_thumbnail_url VARCHAR(500) NOT NULL DEFAULT 'http://localhost:8000/static/placeholders/product_default.png',
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.product_history'
CREATE TABLE IF NOT EXISTS audit.product_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    product_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_i18n JSONB,
    ingredients VARCHAR(255),
    ingredients_i18n JSONB,
    description VARCHAR(1000),
    description_i18n JSONB,
    dietary TEXT[] NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    image_storage_path VARCHAR(500) NOT NULL,
    image_checksum VARCHAR(128) NOT NULL,
    image_url VARCHAR(500) NOT NULL,
    image_thumbnail_storage_path VARCHAR(500) NOT NULL,
    image_thumbnail_url VARCHAR(500) NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (product_id) REFERENCES ops.product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.product_history IS
    'Trigger-managed history mirror of ops.product_info. Never written by application code.';
COMMENT ON COLUMN audit.product_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.product_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.product_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: ops.plate_info'
CREATE TABLE IF NOT EXISTS ops.plate_info (
    plate_id UUID PRIMARY KEY DEFAULT uuidv7(),
    product_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit INTEGER NOT NULL,
    expected_payout_local_currency NUMERIC NOT NULL DEFAULT 0,
    delivery_time_minutes INTEGER NOT NULL DEFAULT 15,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES ops.product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: ops.restaurant_holidays'
CREATE TABLE IF NOT EXISTS ops.restaurant_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    country_code VARCHAR(3) NOT NULL CHECK (length(country_code) = 2),
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(100) NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER CHECK (recurring_month IS NULL OR recurring_month BETWEEN 1 AND 12),
    recurring_day INTEGER CHECK (recurring_day IS NULL OR recurring_day BETWEEN 1 AND 31),
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(20) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'national_sync')),
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.restaurant_holidays_history'
CREATE TABLE IF NOT EXISTS audit.restaurant_holidays_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    holiday_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(100) NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER,
    recurring_day INTEGER,
    status status_enum NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(20) NOT NULL,
    operation audit_operation_enum NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);
COMMENT ON TABLE audit.restaurant_holidays_history IS
    'Trigger-managed history mirror of ops.restaurant_holidays. Never written by application code.';
COMMENT ON COLUMN audit.restaurant_holidays_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.restaurant_holidays_history.operation IS
    'DML operation that produced this row: ''create'', ''update'', or ''delete''. '
    'From the audit_operation_enum type.';
COMMENT ON COLUMN audit.restaurant_holidays_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.restaurant_holidays_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: ops.plate_kitchen_days'
CREATE TABLE IF NOT EXISTS ops.plate_kitchen_days (
    plate_kitchen_day_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
    -- Uniqueness (plate_id, kitchen_day) enforced only for non-archived rows via partial unique index in index.sql
);

\echo 'Creating table: audit.plate_kitchen_days_history'
CREATE TABLE IF NOT EXISTS audit.plate_kitchen_days_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_kitchen_day_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation audit_operation_enum NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);
COMMENT ON TABLE audit.plate_kitchen_days_history IS
    'Trigger-managed history mirror of ops.plate_kitchen_days. Never written by application code.';
COMMENT ON COLUMN audit.plate_kitchen_days_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.plate_kitchen_days_history.operation IS
    'DML operation that produced this row: ''create'', ''update'', or ''delete''. '
    'From the audit_operation_enum type.';
COMMENT ON COLUMN audit.plate_kitchen_days_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.plate_kitchen_days_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: audit.plate_history'
CREATE TABLE IF NOT EXISTS audit.plate_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_id UUID NOT NULL,
    product_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit INTEGER NOT NULL,
    expected_payout_local_currency NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.plate_history IS
    'Trigger-managed history mirror of ops.plate_info. Never written by application code.';
COMMENT ON COLUMN audit.plate_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.plate_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.plate_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: customer.plate_selection_info'
CREATE TABLE IF NOT EXISTS customer.plate_selection_info (
    plate_selection_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    product_id UUID NOT NULL,
    qr_code_id UUID NOT NULL,
    credit INTEGER NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    pickup_date DATE NOT NULL,
    pickup_time_range VARCHAR(50) NOT NULL,
    pickup_intent VARCHAR(20) NOT NULL DEFAULT 'self' CHECK (pickup_intent IN ('offer', 'request', 'self')),
    flexible_on_time BOOLEAN NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- CHECK constraint on pickup_date DOW vs kitchen_day removed — business logic in Python
    -- (VALID_KITCHEN_DAYS + kitchen_day_enum) is the real guard, and weekend service is planned.
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES ops.product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (qr_code_id) REFERENCES ops.qr_code(qr_code_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.plate_selection_history'
CREATE TABLE IF NOT EXISTS audit.plate_selection_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_selection_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    product_id UUID NOT NULL,
    qr_code_id UUID NOT NULL,
    credit INTEGER NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    pickup_date DATE NOT NULL,
    pickup_time_range VARCHAR(50) NOT NULL,
    pickup_intent VARCHAR(20) NOT NULL DEFAULT 'self',
    flexible_on_time BOOLEAN NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_selection_history_plate_selection ON audit.plate_selection_history(plate_selection_id) WHERE is_current = TRUE;
COMMENT ON TABLE audit.plate_selection_history IS
    'Trigger-managed history mirror of customer.plate_selection_info. Never written by application code.';
COMMENT ON COLUMN audit.plate_selection_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.plate_selection_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.plate_selection_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: customer.coworker_pickup_notification'
CREATE TABLE IF NOT EXISTS customer.coworker_pickup_notification (
    notification_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_selection_id UUID NOT NULL,
    notifier_user_id UUID NOT NULL,
    notified_user_id UUID NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (notifier_user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (notified_user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_coworker_pickup_notification_plate_selection ON customer.coworker_pickup_notification(plate_selection_id);

\echo 'Creating table: customer.notification_banner'
CREATE TABLE IF NOT EXISTS customer.notification_banner (
    notification_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE CASCADE,
    notification_type notification_banner_type_enum NOT NULL,
    priority notification_banner_priority_enum NOT NULL DEFAULT 'normal',
    payload JSONB NOT NULL DEFAULT '{}',
    action_type VARCHAR(50) NOT NULL,
    action_label VARCHAR(100) NOT NULL,
    client_types VARCHAR(20)[] NOT NULL DEFAULT '{b2c-mobile,b2c-web}',
    action_status notification_banner_action_status_enum NOT NULL DEFAULT 'active',
    expires_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    dedup_key VARCHAR(255) NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_notification_banner_user_active
    ON customer.notification_banner(user_id)
    WHERE action_status = 'active';

CREATE INDEX IF NOT EXISTS idx_notification_banner_expires
    ON customer.notification_banner(expires_at)
    WHERE action_status = 'active';

\echo 'Creating table: customer.plate_pickup_live'
CREATE TABLE IF NOT EXISTS customer.plate_pickup_live (
    plate_pickup_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_selection_id UUID NOT NULL,
    user_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    product_id UUID NOT NULL,
    qr_code_id UUID NOT NULL,
    qr_code_payload VARCHAR(255) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    was_collected BOOLEAN DEFAULT FALSE,
    arrival_time TIMESTAMPTZ,
    completion_time TIMESTAMPTZ,
    expected_completion_time TIMESTAMPTZ,
    confirmation_code VARCHAR(10),
    completion_type VARCHAR(20) DEFAULT NULL,
    extensions_used INTEGER DEFAULT 0,
    code_verified BOOLEAN DEFAULT FALSE,
    code_verified_time TIMESTAMPTZ DEFAULT NULL,
    handed_out_time TIMESTAMPTZ DEFAULT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES ops.product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (qr_code_id) REFERENCES ops.qr_code(qr_code_id) ON DELETE RESTRICT
);

\echo 'Creating table: customer.plate_review_info'
CREATE TABLE IF NOT EXISTS customer.plate_review_info (
    plate_review_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    plate_pickup_id UUID NOT NULL,
    stars_rating INTEGER NOT NULL CHECK (stars_rating >= 1 AND stars_rating <= 5),
    portion_size_rating INTEGER NOT NULL CHECK (portion_size_rating >= 1 AND portion_size_rating <= 3),
    would_order_again BOOLEAN DEFAULT NULL,
    comment VARCHAR(500) DEFAULT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_pickup_id) REFERENCES customer.plate_pickup_live(plate_pickup_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_review_plate_id ON customer.plate_review_info(plate_id) WHERE NOT is_archived;

\echo 'Creating table: customer.portion_complaint'
CREATE TABLE IF NOT EXISTS customer.portion_complaint (
    complaint_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_pickup_id UUID NOT NULL,
    plate_review_id UUID,
    user_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    photo_storage_path VARCHAR(500),
    complaint_text VARCHAR(1000),
    resolution_status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_pickup_id) REFERENCES customer.plate_pickup_live(plate_pickup_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT
);

\echo 'Creating table: customer.user_favorite_info'
CREATE TABLE IF NOT EXISTS customer.user_favorite_info (
    favorite_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    entity_type favorite_entity_type_enum NOT NULL,
    entity_id UUID NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, entity_type, entity_id),
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_user_favorite_user_entity ON customer.user_favorite_info(user_id, entity_type);

\echo 'Creating table: customer.pickup_preferences'
CREATE TABLE IF NOT EXISTS customer.pickup_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_selection_id UUID NOT NULL,
    user_id UUID NOT NULL,
    pickup_type pickup_type_enum NOT NULL,
    target_pickup_time TIMESTAMPTZ, -- specific time for matching
    time_window_minutes INTEGER DEFAULT 30, -- ±30 minutes window
    is_matched BOOLEAN DEFAULT FALSE,
    matched_with_preference_id UUID NULL, -- reference to matched preference
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (matched_with_preference_id) REFERENCES customer.pickup_preferences(preference_id) ON DELETE SET NULL,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: customer.plan_info'
CREATE TABLE IF NOT EXISTS customer.plan_info (
    plan_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_i18n JSONB,
    marketing_description VARCHAR(1000),
    marketing_description_i18n JSONB,
    features TEXT[],
    features_i18n JSONB,
    cta_label VARCHAR(200),
    cta_label_i18n JSONB,
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    highlighted BOOLEAN NOT NULL DEFAULT FALSE,
    credit_cost_local_currency DOUBLE PRECISION NOT NULL,
    credit_cost_usd DOUBLE PRECISION NOT NULL,
    rollover BOOLEAN NOT NULL DEFAULT TRUE,
    rollover_cap NUMERIC,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_plan_info_not_global_market CHECK (market_id != '00000000-0000-0000-0000-000000000001'::uuid)
);

\echo 'Creating table: audit.plan_history'
CREATE TABLE IF NOT EXISTS audit.plan_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plan_id UUID NOT NULL,
    market_id UUID NOT NULL,
    name VARCHAR(100),
    name_i18n JSONB,
    marketing_description VARCHAR(1000),
    marketing_description_i18n JSONB,
    features TEXT[],
    features_i18n JSONB,
    cta_label VARCHAR(200),
    cta_label_i18n JSONB,
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    highlighted BOOLEAN NOT NULL DEFAULT FALSE,
    credit_cost_local_currency DOUBLE PRECISION NOT NULL,
    credit_cost_usd DOUBLE PRECISION NOT NULL,
    rollover BOOLEAN NOT NULL,
    rollover_cap NUMERIC,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plan_id) REFERENCES customer.plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.plan_history IS
    'Trigger-managed history mirror of customer.plan_info. Never written by application code.';
COMMENT ON COLUMN audit.plan_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.plan_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.plan_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.discretionary_info'
CREATE TABLE IF NOT EXISTS billing.discretionary_info (
    discretionary_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID,  -- NULL for Supplier requests, required for Client requests
    restaurant_id UUID,  -- NULL for Client requests, required for Supplier requests
    approval_id UUID,
    category discretionary_reason_enum NOT NULL,  -- Classification: Marketing Campaign, Credit Refund, etc.
    reason TEXT,  -- Free-form explanation/details
    amount NUMERIC,
    comment TEXT,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status discretionary_status_enum NOT NULL DEFAULT 'pending'::discretionary_status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    -- Ensure either user_id (Client) or restaurant_id (Supplier) is provided
    CHECK ((user_id IS NOT NULL AND restaurant_id IS NULL) OR (user_id IS NULL AND restaurant_id IS NOT NULL))
);

\echo 'Creating table: audit.discretionary_history'
CREATE TABLE IF NOT EXISTS audit.discretionary_history (
    history_id UUID PRIMARY KEY DEFAULT uuidv7(),
    discretionary_id UUID NOT NULL,
    user_id UUID,  -- NULL for Supplier requests, required for Client requests
    restaurant_id UUID,  -- NULL for Client requests, required for Supplier requests
    approval_id UUID,
    category discretionary_reason_enum NOT NULL,  -- Classification: Marketing Campaign, Credit Refund, etc.
    reason TEXT,  -- Free-form explanation/details
    amount NUMERIC,
    comment TEXT,
    is_archived BOOLEAN NOT NULL,
    status discretionary_status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_date TIMESTAMPTZ,
    modified_by UUID,
    operation audit_operation_enum NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID,
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.discretionary_history IS
    'Trigger-managed history mirror of billing.discretionary_info. Never written by application code.';
COMMENT ON COLUMN audit.discretionary_history.history_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.discretionary_history.operation IS
    'DML operation that produced this row: ''create'', ''update'', or ''delete''. '
    'From the audit_operation_enum type.';
COMMENT ON COLUMN audit.discretionary_history.changed_at IS
    'UTC timestamp when this history row was inserted by the trigger.';
COMMENT ON COLUMN audit.discretionary_history.changed_by IS
    'UUID of the user whose action triggered this audit row. Derived from modified_by on the source row.';

\echo 'Creating table: billing.discretionary_resolution_info'
CREATE TABLE IF NOT EXISTS billing.discretionary_resolution_info (
    approval_id UUID PRIMARY KEY DEFAULT uuidv7(),
    discretionary_id UUID NOT NULL,
    resolution discretionary_status_enum NOT NULL DEFAULT 'pending'::discretionary_status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    resolved_by UUID NOT NULL,
    resolved_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolution_comment TEXT,
    FOREIGN KEY (resolved_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.discretionary_resolution_history'
CREATE TABLE IF NOT EXISTS audit.discretionary_resolution_history (
    history_id UUID PRIMARY KEY DEFAULT uuidv7(),
    approval_id UUID NOT NULL,
    discretionary_id UUID NOT NULL,
    resolution discretionary_status_enum NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    resolved_by UUID NOT NULL,
    resolved_date TIMESTAMPTZ NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    resolution_comment TEXT,
    operation audit_operation_enum NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID,
    FOREIGN KEY (approval_id) REFERENCES billing.discretionary_resolution_info(approval_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.discretionary_resolution_history IS
    'Trigger-managed history mirror of billing.discretionary_resolution_info. Never written by application code.';
COMMENT ON COLUMN audit.discretionary_resolution_history.history_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.discretionary_resolution_history.operation IS
    'DML operation that produced this row: ''create'', ''update'', or ''delete''. '
    'From the audit_operation_enum type.';
COMMENT ON COLUMN audit.discretionary_resolution_history.changed_at IS
    'UTC timestamp when this history row was inserted by the trigger.';
COMMENT ON COLUMN audit.discretionary_resolution_history.changed_by IS
    'UUID of the user whose action triggered this audit row. Derived from resolved_by on the source row.';

\echo 'Creating trigger function: discretionary_info_history_trigger'
CREATE OR REPLACE FUNCTION discretionary_info_history_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
    v_changed_by UUID;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        v_operation := 'create'::audit_operation_enum;
        v_changed_by := NEW.modified_by;
        INSERT INTO audit.discretionary_history (
            discretionary_id,
            user_id,
            restaurant_id,
            approval_id,
            category,
            reason,
            amount,
            comment,
            is_archived,
            status,
            created_date,
            created_by,
            modified_date,
            modified_by,
            operation,
            changed_by
        ) VALUES (
            NEW.discretionary_id,
            NEW.user_id,
            NEW.restaurant_id,
            NEW.approval_id,
            NEW.category,
            NEW.reason,
            NEW.amount,
            NEW.comment,
            NEW.is_archived,
            NEW.status,
            NEW.created_date,
            NEW.created_by,
            NEW.modified_date,
            NEW.modified_by,
            v_operation,
            v_changed_by
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        v_operation := 'update'::audit_operation_enum;
        v_changed_by := NEW.modified_by;
        INSERT INTO audit.discretionary_history (
            discretionary_id,
            user_id,
            restaurant_id,
            approval_id,
            category,
            reason,
            amount,
            comment,
            is_archived,
            status,
            created_date,
            created_by,
            modified_date,
            modified_by,
            operation,
            changed_by
        ) VALUES (
            NEW.discretionary_id,
            NEW.user_id,
            NEW.restaurant_id,
            NEW.approval_id,
            NEW.category,
            NEW.reason,
            NEW.amount,
            NEW.comment,
            NEW.is_archived,
            NEW.status,
            NEW.created_date,
            NEW.created_by,
            NEW.modified_date,
            NEW.modified_by,
            v_operation,
            v_changed_by
        );
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        v_operation := 'delete'::audit_operation_enum;
        v_changed_by := OLD.modified_by;
        INSERT INTO audit.discretionary_history (
            discretionary_id,
            user_id,
            restaurant_id,
            approval_id,
            category,
            reason,
            amount,
            comment,
            is_archived,
            status,
            created_date,
            created_by,
            modified_date,
            modified_by,
            operation,
            changed_by
        ) VALUES (
            OLD.discretionary_id,
            OLD.user_id,
            OLD.restaurant_id,
            OLD.approval_id,
            OLD.category,
            OLD.reason,
            OLD.amount,
            OLD.comment,
            OLD.is_archived,
            OLD.status,
            OLD.created_date,
            OLD.created_by,
            OLD.modified_date,
            OLD.modified_by,
            v_operation,
            v_changed_by
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS discretionary_info_history_trigger ON billing.discretionary_info;
CREATE TRIGGER discretionary_info_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON billing.discretionary_info
FOR EACH ROW EXECUTE FUNCTION discretionary_info_history_trigger();

\echo 'Creating trigger function: discretionary_resolution_info_history_trigger'
CREATE OR REPLACE FUNCTION discretionary_resolution_info_history_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
    v_changed_by UUID;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        v_operation := 'create'::audit_operation_enum;
        v_changed_by := NEW.resolved_by;
        INSERT INTO audit.discretionary_resolution_history (
            approval_id,
            discretionary_id,
            resolution,
            is_archived,
            status,
            resolved_by,
            resolved_date,
            created_date,
            resolution_comment,
            operation,
            changed_by
        ) VALUES (
            NEW.approval_id,
            NEW.discretionary_id,
            NEW.resolution,
            NEW.is_archived,
            NEW.status,
            NEW.resolved_by,
            NEW.resolved_date,
            NEW.created_date,
            NEW.resolution_comment,
            v_operation,
            v_changed_by
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        v_operation := 'update'::audit_operation_enum;
        v_changed_by := NEW.resolved_by;
        INSERT INTO audit.discretionary_resolution_history (
            approval_id,
            discretionary_id,
            resolution,
            is_archived,
            status,
            resolved_by,
            resolved_date,
            created_date,
            resolution_comment,
            operation,
            changed_by
        ) VALUES (
            NEW.approval_id,
            NEW.discretionary_id,
            NEW.resolution,
            NEW.is_archived,
            NEW.status,
            NEW.resolved_by,
            NEW.resolved_date,
            NEW.created_date,
            NEW.resolution_comment,
            v_operation,
            v_changed_by
        );
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        v_operation := 'delete'::audit_operation_enum;
        v_changed_by := OLD.resolved_by;
        INSERT INTO audit.discretionary_resolution_history (
            approval_id,
            discretionary_id,
            resolution,
            is_archived,
            status,
            resolved_by,
            resolved_date,
            created_date,
            resolution_comment,
            operation,
            changed_by
        ) VALUES (
            OLD.approval_id,
            OLD.discretionary_id,
            OLD.resolution,
            OLD.is_archived,
            OLD.status,
            OLD.resolved_by,
            OLD.resolved_date,
            OLD.created_date,
            OLD.resolution_comment,
            v_operation,
            v_changed_by
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS discretionary_resolution_info_history_trigger ON billing.discretionary_resolution_info;
CREATE TRIGGER discretionary_resolution_info_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON billing.discretionary_resolution_info
FOR EACH ROW EXECUTE FUNCTION discretionary_resolution_info_history_trigger();

\echo 'Creating table: billing.client_transaction'
CREATE TABLE IF NOT EXISTS billing.client_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    source VARCHAR(50) NOT NULL,  -- e.g., 'plate_selection' or 'discretionary_promotion'
    plate_selection_id UUID, -- references a plate_selection record when source = 'order'
    discretionary_id UUID, -- references a discretionary record when source = 'discretionary'
    referral_id UUID, -- references a referral record when source = 'referral_program'
    credit NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

-- =============================================================================
-- REFERRAL SYSTEM
-- =============================================================================

\echo 'Creating table: customer.referral_config'
CREATE TABLE IF NOT EXISTS customer.referral_config (
    referral_config_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    referrer_bonus_rate INTEGER NOT NULL DEFAULT 15,
    referrer_bonus_cap NUMERIC NULL,
    referrer_monthly_cap INTEGER NULL DEFAULT 5,
    min_plan_price_to_qualify NUMERIC NOT NULL DEFAULT 0,
    cooldown_days INTEGER NOT NULL DEFAULT 0,
    held_reward_expiry_hours INTEGER NOT NULL DEFAULT 48,
    pending_expiry_days INTEGER NOT NULL DEFAULT 90,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_config_market_active ON customer.referral_config(market_id) WHERE is_archived = FALSE;

\echo 'Creating table: customer.referral_info'
CREATE TABLE IF NOT EXISTS customer.referral_info (
    referral_id UUID PRIMARY KEY DEFAULT uuidv7(),
    referrer_user_id UUID NOT NULL,
    referee_user_id UUID NOT NULL,
    referral_code_used VARCHAR(20) NOT NULL,
    market_id UUID NOT NULL,
    referral_status referral_status_enum NOT NULL DEFAULT 'pending'::referral_status_enum,
    bonus_credits_awarded NUMERIC NULL,
    bonus_plan_price NUMERIC NULL,
    bonus_rate_applied INTEGER NULL,
    qualified_date TIMESTAMPTZ NULL,
    rewarded_date TIMESTAMPTZ NULL,
    reward_held_until TIMESTAMPTZ NULL,
    expired_date TIMESTAMPTZ NULL,
    cancelled_date TIMESTAMPTZ NULL,
    transaction_id UUID NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referrer_user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (referee_user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (transaction_id) REFERENCES billing.client_transaction(transaction_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_referral_info_referrer ON customer.referral_info(referrer_user_id);
CREATE INDEX IF NOT EXISTS idx_referral_info_referee ON customer.referral_info(referee_user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_info_referee_unique ON customer.referral_info(referee_user_id) WHERE referral_status NOT IN ('cancelled');

-- Deferred FK: client_transaction.referral_id -> referral_info (circular dependency)
ALTER TABLE billing.client_transaction
    ADD CONSTRAINT fk_client_transaction_referral
    FOREIGN KEY (referral_id) REFERENCES customer.referral_info(referral_id) ON DELETE RESTRICT;

\echo 'Creating table: audit.referral_config_history'
CREATE TABLE IF NOT EXISTS audit.referral_config_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    referral_config_id UUID NOT NULL,
    market_id UUID NOT NULL,
    is_enabled BOOLEAN NOT NULL,
    referrer_bonus_rate INTEGER NOT NULL,
    referrer_bonus_cap NUMERIC NULL,
    referrer_monthly_cap INTEGER NULL,
    min_plan_price_to_qualify NUMERIC NOT NULL,
    cooldown_days INTEGER NOT NULL,
    held_reward_expiry_hours INTEGER NOT NULL,
    pending_expiry_days INTEGER NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (referral_config_id) REFERENCES customer.referral_config(referral_config_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.referral_config_history IS
    'Trigger-managed history mirror of customer.referral_config. Never written by application code.';
COMMENT ON COLUMN audit.referral_config_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.referral_config_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.referral_config_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: audit.referral_info_history'
CREATE TABLE IF NOT EXISTS audit.referral_info_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    referral_id UUID NOT NULL,
    referrer_user_id UUID NOT NULL,
    referee_user_id UUID NOT NULL,
    referral_code_used VARCHAR(20) NOT NULL,
    market_id UUID NOT NULL,
    referral_status referral_status_enum NOT NULL,
    bonus_credits_awarded NUMERIC NULL,
    bonus_plan_price NUMERIC NULL,
    bonus_rate_applied INTEGER NULL,
    qualified_date TIMESTAMPTZ NULL,
    rewarded_date TIMESTAMPTZ NULL,
    reward_held_until TIMESTAMPTZ NULL,
    transaction_id UUID NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (referral_id) REFERENCES customer.referral_info(referral_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.referral_info_history IS
    'Trigger-managed history mirror of customer.referral_info. Never written by application code.';
COMMENT ON COLUMN audit.referral_info_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.referral_info_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.referral_info_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: customer.referral_code_assignment'
CREATE TABLE IF NOT EXISTS customer.referral_code_assignment (
    assignment_id UUID PRIMARY KEY DEFAULT uuidv7(),
    device_id VARCHAR(255) NOT NULL,
    referral_code VARCHAR(20) NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_assignment_device_active ON customer.referral_code_assignment(device_id) WHERE used = FALSE;
CREATE INDEX IF NOT EXISTS idx_referral_assignment_created ON customer.referral_code_assignment(created_at);

\echo 'Creating table: customer.subscription_info'
CREATE TABLE IF NOT EXISTS customer.subscription_info (
    subscription_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    market_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    renewal_date TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    balance NUMERIC DEFAULT 0,
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'active', 'on_hold', 'pending', 'cancelled'
    hold_start_date TIMESTAMPTZ,  -- When subscription was put on hold
    hold_end_date TIMESTAMPTZ,    -- When subscription will resume (NULL = indefinite)
    early_renewal_threshold INTEGER DEFAULT 10,  -- NULL = period-end only; >= 1 = early renew when balance below this
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'pending'::status_enum,  -- Keep for backward compatibility
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES customer.plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

-- Ensure one active subscription per user per market
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_market_active 
    ON customer.subscription_info(user_id, market_id) 
    WHERE is_archived = FALSE;

-- Index for querying subscriptions by market
CREATE INDEX IF NOT EXISTS idx_subscription_market 
    ON customer.subscription_info(market_id) 
    WHERE is_archived = FALSE;

\echo 'Creating table: audit.subscription_history'
CREATE TABLE IF NOT EXISTS audit.subscription_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    subscription_id UUID  NOT NULL,
    user_id UUID  NOT NULL,
    market_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    renewal_date TIMESTAMPTZ,
    balance NUMERIC DEFAULT 0,
    subscription_status VARCHAR(20) NOT NULL,
    hold_start_date TIMESTAMPTZ,
    hold_end_date TIMESTAMPTZ,
    early_renewal_threshold INTEGER,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (subscription_id) REFERENCES customer.subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.subscription_history IS
    'Trigger-managed history mirror of customer.subscription_info. Never written by application code.';
COMMENT ON COLUMN audit.subscription_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.subscription_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.subscription_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: customer.subscription_payment'
CREATE TABLE IF NOT EXISTS customer.subscription_payment (
    subscription_payment_id UUID PRIMARY KEY DEFAULT uuidv7(),
    subscription_id UUID NOT NULL,
    payment_provider VARCHAR(50) NOT NULL DEFAULT 'stripe',
    external_payment_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES customer.subscription_info(subscription_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_subscription_id ON customer.subscription_payment(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_external_id ON customer.subscription_payment(external_payment_id);

\echo 'Creating table: customer.payment_method'
CREATE TABLE IF NOT EXISTS customer.payment_method (
    payment_method_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    method_type VARCHAR(50) NOT NULL,
    method_type_id UUID,
    address_id UUID,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'pending'::status_enum,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT
);

\echo 'Creating table: customer.external_payment_method'
CREATE TABLE IF NOT EXISTS customer.external_payment_method (
    external_payment_method_id UUID PRIMARY KEY DEFAULT uuidv7(),
    payment_method_id UUID NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    last4 VARCHAR(4),
    brand VARCHAR(50),
    provider_customer_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_external_payment_method_provider_external UNIQUE (provider, external_id),
    FOREIGN KEY (payment_method_id) REFERENCES customer.payment_method(payment_method_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_external_payment_method_payment_method_id ON customer.external_payment_method(payment_method_id);
CREATE INDEX IF NOT EXISTS idx_external_payment_method_provider ON customer.external_payment_method(provider);

\echo 'Creating table: customer.user_payment_provider'
CREATE TABLE IF NOT EXISTS customer.user_payment_provider (
    user_payment_provider_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id              UUID NOT NULL,
    provider             VARCHAR(50)  NOT NULL,   -- 'stripe', 'paypal', etc.
    provider_customer_id VARCHAR(255) NOT NULL,
    is_archived          BOOLEAN NOT NULL DEFAULT FALSE,
    status               status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by           UUID NULL,
    modified_by          UUID NOT NULL,
    modified_date        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)     REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
-- One active provider account per user per provider
CREATE UNIQUE INDEX uq_user_payment_provider_active
    ON customer.user_payment_provider (user_id, provider)
    WHERE is_archived = FALSE;
-- No two users share the same provider account (within a provider)
CREATE UNIQUE INDEX uq_user_payment_provider_provider_customer
    ON customer.user_payment_provider (provider, provider_customer_id)
    WHERE is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_user_payment_provider_user_id ON customer.user_payment_provider(user_id);

\echo 'Creating table: audit.user_payment_provider_history'
CREATE TABLE IF NOT EXISTS audit.user_payment_provider_history (
    event_id                 UUID PRIMARY KEY DEFAULT uuidv7(),
    user_payment_provider_id UUID NOT NULL,
    user_id                  UUID NOT NULL,
    provider                 VARCHAR(50)  NOT NULL,
    provider_customer_id     VARCHAR(255) NOT NULL,
    is_archived              BOOLEAN NOT NULL,
    status                   status_enum NOT NULL,
    created_date             TIMESTAMPTZ NOT NULL,
    created_by               UUID NULL,
    modified_by              UUID NOT NULL,
    modified_date            TIMESTAMPTZ NOT NULL,
    is_current               BOOLEAN DEFAULT TRUE,
    valid_until              TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (user_payment_provider_id)
        REFERENCES customer.user_payment_provider(user_payment_provider_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.user_payment_provider_history IS
    'Trigger-managed history mirror of customer.user_payment_provider. Never written by application code.';
COMMENT ON COLUMN audit.user_payment_provider_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.user_payment_provider_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.user_payment_provider_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.client_bill_info'
CREATE TABLE IF NOT EXISTS billing.client_bill_info (
    client_bill_id UUID PRIMARY KEY DEFAULT uuidv7(),
    subscription_payment_id UUID NOT NULL,
    subscription_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    amount NUMERIC NOT NULL,
    currency_code VARCHAR(10),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_id) REFERENCES customer.subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES customer.plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_payment_id) REFERENCES customer.subscription_payment(subscription_payment_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.client_bill_history'
CREATE TABLE IF NOT EXISTS audit.client_bill_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    client_bill_id UUID NOT NULL,
    subscription_payment_id UUID NOT NULL,
    subscription_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    amount NUMERIC,
    currency_code VARCHAR(10),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (client_bill_id) REFERENCES billing.client_bill_info(client_bill_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.client_bill_history IS
    'Trigger-managed history mirror of billing.client_bill_info. Never written by application code.';
COMMENT ON COLUMN audit.client_bill_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.client_bill_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.client_bill_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.restaurant_transaction'
CREATE TABLE IF NOT EXISTS billing.restaurant_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    plate_selection_id UUID,
    discretionary_id UUID,
    currency_metadata_id UUID NOT NULL,
    was_collected BOOLEAN NOT NULL DEFAULT FALSE,
    ordered_timestamp TIMESTAMPTZ NOT NULL,
    collected_timestamp TIMESTAMPTZ,
    arrival_time TIMESTAMPTZ,
    completion_time TIMESTAMPTZ,
    expected_completion_time TIMESTAMPTZ,
    transaction_type transaction_type_enum NOT NULL,
    credit NUMERIC NOT NULL,
    no_show_discount NUMERIC,
    currency_code VARCHAR(10),
    final_amount NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'pending'::status_enum,
    created_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: billing.restaurant_balance_info'
CREATE TABLE IF NOT EXISTS billing.restaurant_balance_info (
    restaurant_id UUID PRIMARY KEY,
    currency_metadata_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.restaurant_balance_history'
CREATE TABLE IF NOT EXISTS audit.restaurant_balance_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (restaurant_id) REFERENCES billing.restaurant_balance_info(restaurant_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.restaurant_balance_history IS
    'Trigger-managed history mirror of billing.restaurant_balance_info. Never written by application code.';
COMMENT ON COLUMN audit.restaurant_balance_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered. '
    'Referenced by billing.institution_settlement.balance_event_id to link settlements to the balance snapshot they were computed from.';
COMMENT ON COLUMN audit.restaurant_balance_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.restaurant_balance_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.institution_bill_info'
CREATE TABLE IF NOT EXISTS billing.institution_bill_info (
    institution_bill_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    transaction_count INTEGER,
    amount NUMERIC,
    currency_code VARCHAR(10),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    resolution bill_resolution_enum NOT NULL DEFAULT 'pending'::bill_resolution_enum,
    tax_doc_external_id VARCHAR(255),
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.institution_bill_history'
CREATE TABLE IF NOT EXISTS audit.institution_bill_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    currency_metadata_id UUID NOT NULL,
    transaction_count INTEGER,
    amount NUMERIC,
    currency_code VARCHAR(10),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    resolution bill_resolution_enum NOT NULL,
    tax_doc_external_id VARCHAR(255),
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_bill_id) REFERENCES billing.institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.institution_bill_history IS
    'Trigger-managed history mirror of billing.institution_bill_info. Never written by application code.';
COMMENT ON COLUMN audit.institution_bill_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.institution_bill_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.institution_bill_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.institution_bill_payout'
CREATE TABLE IF NOT EXISTS billing.institution_bill_payout (
    bill_payout_id       UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id  UUID        NOT NULL,
    provider             VARCHAR(50) NOT NULL,
    provider_transfer_id VARCHAR(255) NULL,
    amount               NUMERIC     NOT NULL,
    currency_code        VARCHAR(10) NOT NULL,
    status               bill_payout_status_enum NOT NULL DEFAULT 'pending'::bill_payout_status_enum,
    idempotency_key      VARCHAR(255) NOT NULL UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at         TIMESTAMPTZ NULL,
    modified_by          UUID        NULL,
    FOREIGN KEY (institution_bill_id) REFERENCES billing.institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by)         REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_bill_payout_bill_id  ON billing.institution_bill_payout(institution_bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_payout_provider ON billing.institution_bill_payout(provider);
CREATE INDEX IF NOT EXISTS idx_bill_payout_transfer_id ON billing.institution_bill_payout(provider_transfer_id);

\echo 'Creating table: billing.market_payout_aggregator'
CREATE TABLE IF NOT EXISTS billing.market_payout_aggregator (
    market_id                UUID        PRIMARY KEY,
    aggregator               VARCHAR(50) NOT NULL,
    is_active                BOOLEAN     NOT NULL DEFAULT TRUE,
    require_invoice          BOOLEAN     NOT NULL DEFAULT FALSE,
    max_unmatched_bill_days  INTEGER     NOT NULL DEFAULT 30,
    -- Kitchen hours defaults (naive wall-clock; suppliers inherit at create time)
    kitchen_open_time        TIME        NOT NULL DEFAULT '09:00',
    kitchen_close_time       TIME        NOT NULL DEFAULT '13:30',
    notes                    TEXT        NULL,
    -- Audit
    is_archived              BOOLEAN     NOT NULL DEFAULT FALSE,
    status                   status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by              UUID        NOT NULL,
    modified_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id)  REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.market_payout_aggregator_history'
CREATE TABLE IF NOT EXISTS audit.market_payout_aggregator_history (
    event_id                 UUID        PRIMARY KEY DEFAULT uuidv7(),
    market_id                UUID        NOT NULL,
    aggregator               VARCHAR(50) NOT NULL,
    is_active                BOOLEAN     NOT NULL,
    require_invoice          BOOLEAN     NOT NULL,
    max_unmatched_bill_days  INTEGER     NOT NULL,
    kitchen_open_time        TIME        NOT NULL,
    kitchen_close_time       TIME        NOT NULL,
    notes                    TEXT        NULL,
    is_archived              BOOLEAN     NOT NULL,
    status                   status_enum NOT NULL,
    created_date             TIMESTAMPTZ NOT NULL,
    modified_by              UUID        NOT NULL,
    modified_date            TIMESTAMPTZ NOT NULL,
    is_current               BOOLEAN     DEFAULT TRUE,
    valid_until              TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (market_id)  REFERENCES billing.market_payout_aggregator(market_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.market_payout_aggregator_history IS
    'Trigger-managed history mirror of billing.market_payout_aggregator. Never written by application code.';
COMMENT ON COLUMN audit.market_payout_aggregator_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.market_payout_aggregator_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.market_payout_aggregator_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.institution_settlement'
CREATE TABLE IF NOT EXISTS billing.institution_settlement (
    settlement_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    kitchen_day VARCHAR(20) NOT NULL,
    amount NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    currency_metadata_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance_event_id UUID,
    settlement_number VARCHAR(50) NOT NULL,
    settlement_run_id UUID,
    institution_bill_id UUID,
    country_code VARCHAR(10) NOT NULL,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_event_id) REFERENCES audit.restaurant_balance_history(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_bill_id) REFERENCES billing.institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_entity_period ON billing.institution_settlement(institution_entity_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_restaurant_period ON billing.institution_settlement(restaurant_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_bill ON billing.institution_settlement(institution_bill_id);

\echo 'Creating table: audit.institution_settlement_history'
CREATE TABLE IF NOT EXISTS audit.institution_settlement_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    settlement_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    kitchen_day VARCHAR(20) NOT NULL,
    amount NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    currency_metadata_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance_event_id UUID,
    settlement_number VARCHAR(50) NOT NULL,
    settlement_run_id UUID,
    institution_bill_id UUID,
    country_code VARCHAR(10) NOT NULL,
    status status_enum NOT NULL,
    is_archived BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (settlement_id) REFERENCES billing.institution_settlement(settlement_id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_event_id) REFERENCES audit.restaurant_balance_history(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.institution_settlement_history IS
    'Trigger-managed history mirror of billing.institution_settlement. Never written by application code.';
COMMENT ON COLUMN audit.institution_settlement_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.institution_settlement_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.institution_settlement_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- ─────────────────────────────────────────────────────────────
-- SUPPLIER INVOICE COMPLIANCE
-- ─────────────────────────────────────────────────────────────

\echo 'Creating table: billing.supplier_invoice'
CREATE TABLE IF NOT EXISTS billing.supplier_invoice (
    supplier_invoice_id     UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id   UUID        NOT NULL,
    country_code            VARCHAR(2)  NOT NULL,
    invoice_type            supplier_invoice_type_enum NOT NULL,
    external_invoice_number VARCHAR(100) NULL,
    issued_date             DATE        NOT NULL,
    amount                  NUMERIC(12,2) NOT NULL,
    currency_code           VARCHAR(10) NOT NULL,
    tax_amount              NUMERIC(12,2) NULL,
    tax_rate                NUMERIC(5,2) NULL,

    -- Document storage
    document_storage_path   TEXT        NULL,
    document_format         VARCHAR(20) NULL,

    -- Review
    status                  supplier_invoice_status_enum NOT NULL DEFAULT 'pending_review'::supplier_invoice_status_enum,
    rejection_reason        TEXT        NULL,
    reviewed_by             UUID        NULL,
    reviewed_at             TIMESTAMPTZ NULL,

    -- Audit
    is_archived             BOOLEAN     NOT NULL DEFAULT FALSE,
    created_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID        NULL,
    modified_by             UUID        NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewed_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_supplier_invoice_entity ON billing.supplier_invoice(institution_entity_id);
CREATE INDEX IF NOT EXISTS idx_supplier_invoice_status ON billing.supplier_invoice(status);
CREATE INDEX IF NOT EXISTS idx_supplier_invoice_country ON billing.supplier_invoice(country_code);

\echo 'Creating table: audit.supplier_invoice_history'
CREATE TABLE IF NOT EXISTS audit.supplier_invoice_history (
    event_id                UUID        PRIMARY KEY DEFAULT uuidv7(),
    supplier_invoice_id     UUID        NOT NULL,
    institution_entity_id   UUID        NOT NULL,
    country_code            VARCHAR(2)  NOT NULL,
    invoice_type            supplier_invoice_type_enum NOT NULL,
    external_invoice_number VARCHAR(100) NULL,
    issued_date             DATE        NOT NULL,
    amount                  NUMERIC(12,2) NOT NULL,
    currency_code           VARCHAR(10) NOT NULL,
    tax_amount              NUMERIC(12,2) NULL,
    tax_rate                NUMERIC(5,2) NULL,
    document_storage_path   TEXT        NULL,
    document_format         VARCHAR(20) NULL,
    status                  supplier_invoice_status_enum NOT NULL,
    rejection_reason        TEXT        NULL,
    reviewed_by             UUID        NULL,
    reviewed_at             TIMESTAMPTZ NULL,
    is_archived             BOOLEAN     NOT NULL,
    created_date            TIMESTAMPTZ NOT NULL,
    created_by              UUID        NULL,
    modified_by             UUID        NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL,
    is_current              BOOLEAN     DEFAULT TRUE,
    valid_until             TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (supplier_invoice_id) REFERENCES billing.supplier_invoice(supplier_invoice_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.supplier_invoice_history IS
    'Trigger-managed history mirror of billing.supplier_invoice. Never written by application code.';
COMMENT ON COLUMN audit.supplier_invoice_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.supplier_invoice_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.supplier_invoice_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

\echo 'Creating table: billing.bill_invoice_match'
CREATE TABLE IF NOT EXISTS billing.bill_invoice_match (
    match_id                UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id     UUID        NOT NULL,
    supplier_invoice_id     UUID        NOT NULL,
    matched_amount          NUMERIC(12,2) NOT NULL,
    matched_by              UUID        NOT NULL,
    matched_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (institution_bill_id, supplier_invoice_id),
    FOREIGN KEY (institution_bill_id) REFERENCES billing.institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (supplier_invoice_id) REFERENCES billing.supplier_invoice(supplier_invoice_id) ON DELETE RESTRICT,
    FOREIGN KEY (matched_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_bill_invoice_match_bill ON billing.bill_invoice_match(institution_bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_invoice_match_invoice ON billing.bill_invoice_match(supplier_invoice_id);

\echo 'Creating table: billing.supplier_invoice_ar'
CREATE TABLE IF NOT EXISTS billing.supplier_invoice_ar (
    supplier_invoice_id     UUID        PRIMARY KEY,
    cae_code                VARCHAR(50) NOT NULL,
    cae_expiry_date         DATE        NOT NULL,
    afip_point_of_sale      VARCHAR(10) NOT NULL,
    supplier_cuit           VARCHAR(13) NOT NULL,
    recipient_cuit          VARCHAR(13) NULL,
    afip_document_type      VARCHAR(20) NULL,
    FOREIGN KEY (supplier_invoice_id) REFERENCES billing.supplier_invoice(supplier_invoice_id) ON DELETE RESTRICT
);

\echo 'Creating table: billing.supplier_invoice_pe'
CREATE TABLE IF NOT EXISTS billing.supplier_invoice_pe (
    supplier_invoice_id     UUID        PRIMARY KEY,
    sunat_serie             VARCHAR(10) NOT NULL,
    sunat_correlativo       VARCHAR(20) NOT NULL,
    cdr_status              VARCHAR(20) NULL,
    cdr_received_at         TIMESTAMPTZ NULL,
    supplier_ruc            VARCHAR(11) NOT NULL,
    recipient_ruc           VARCHAR(11) NULL,
    FOREIGN KEY (supplier_invoice_id) REFERENCES billing.supplier_invoice(supplier_invoice_id) ON DELETE RESTRICT
);

\echo 'Creating table: billing.supplier_invoice_us'
CREATE TABLE IF NOT EXISTS billing.supplier_invoice_us (
    supplier_invoice_id     UUID        PRIMARY KEY,
    tax_year                SMALLINT    NOT NULL,
    FOREIGN KEY (supplier_invoice_id) REFERENCES billing.supplier_invoice(supplier_invoice_id) ON DELETE RESTRICT
);

\echo 'Creating table: billing.supplier_w9'
CREATE TABLE IF NOT EXISTS billing.supplier_w9 (
    w9_id                   UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id   UUID        NOT NULL UNIQUE,
    legal_name              VARCHAR(255) NOT NULL,
    business_name           VARCHAR(255) NULL,
    tax_classification      VARCHAR(50) NOT NULL,
    ein_last_four           VARCHAR(4)  NOT NULL,
    address_line            TEXT        NOT NULL,
    document_storage_path   TEXT        NULL,
    is_archived             BOOLEAN     NOT NULL DEFAULT FALSE,
    collected_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID        NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by             UUID        NOT NULL,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_supplier_w9_entity ON billing.supplier_w9(institution_entity_id);

-- ─────────────────────────────────────────────────────────────
-- EMPLOYER BILLING
-- ─────────────────────────────────────────────────────────────

\echo 'Creating table: billing.employer_bill'
CREATE TABLE IF NOT EXISTS billing.employer_bill (
    employer_bill_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,  -- bills are per-entity (per-country/currency)
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    billing_cycle VARCHAR(20) NOT NULL,
    total_renewal_events INTEGER NOT NULL DEFAULT 0,
    gross_employer_share NUMERIC NOT NULL DEFAULT 0,
    price_discount INTEGER NOT NULL DEFAULT 0,
    discounted_amount NUMERIC NOT NULL DEFAULT 0,
    minimum_fee_applied BOOLEAN NOT NULL DEFAULT FALSE,
    billed_amount NUMERIC NOT NULL DEFAULT 0,
    currency_code VARCHAR(10) NOT NULL,
    stripe_invoice_id VARCHAR(255) NULL,
    payment_status employer_bill_payment_status_enum NOT NULL DEFAULT 'pending'::employer_bill_payment_status_enum,
    paid_date TIMESTAMPTZ NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_employer_bill_institution ON billing.employer_bill(institution_id);
CREATE INDEX IF NOT EXISTS idx_employer_bill_entity ON billing.employer_bill(institution_entity_id);
CREATE INDEX IF NOT EXISTS idx_employer_bill_period ON billing.employer_bill(billing_period_start, billing_period_end);

\echo 'Creating table: billing.employer_bill_line'
CREATE TABLE IF NOT EXISTS billing.employer_bill_line (
    line_id UUID PRIMARY KEY DEFAULT uuidv7(),
    employer_bill_id UUID NOT NULL,
    subscription_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    plan_price NUMERIC NOT NULL,
    benefit_rate INTEGER NOT NULL,
    benefit_cap NUMERIC NULL,
    benefit_cap_period VARCHAR(20) NULL,
    employee_benefit NUMERIC NOT NULL,
    renewal_date TIMESTAMPTZ NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_bill_id) REFERENCES billing.employer_bill(employer_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_id) REFERENCES customer.subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES customer.plan_info(plan_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_employer_bill_line_bill ON billing.employer_bill_line(employer_bill_id);

\echo 'Creating table: audit.employer_bill_history'
CREATE TABLE IF NOT EXISTS audit.employer_bill_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    employer_bill_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    billing_cycle VARCHAR(20) NOT NULL,
    total_renewal_events INTEGER NOT NULL,
    gross_employer_share NUMERIC NOT NULL,
    price_discount INTEGER NOT NULL,
    discounted_amount NUMERIC NOT NULL,
    minimum_fee_applied BOOLEAN NOT NULL,
    billed_amount NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    stripe_invoice_id VARCHAR(255) NULL,
    payment_status employer_bill_payment_status_enum NOT NULL,
    paid_date TIMESTAMPTZ NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (employer_bill_id) REFERENCES billing.employer_bill(employer_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.employer_bill_history IS
    'Trigger-managed history mirror of billing.employer_bill. Never written by application code.';
COMMENT ON COLUMN audit.employer_bill_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.employer_bill_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.employer_bill_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- ─────────────────────────────────────────────────────────────
-- SUPPLIER TERMS
-- ─────────────────────────────────────────────────────────────

\echo 'Creating table: billing.supplier_terms'
CREATE TABLE IF NOT EXISTS billing.supplier_terms (
    supplier_terms_id       UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_id          UUID        NOT NULL,
    -- Three-tier cascade: entity override → institution default → market default → hardcoded
    -- institution_entity_id IS NULL = institution-level defaults
    -- institution_entity_id IS NOT NULL = entity-level override
    institution_entity_id   UUID        NULL,
    -- Pricing
    no_show_discount        INTEGER     NOT NULL DEFAULT 0 CHECK (no_show_discount >= 0 AND no_show_discount <= 100),
    -- Payment schedule
    payment_frequency       payment_frequency_enum NOT NULL DEFAULT 'daily'::payment_frequency_enum,
    -- Kitchen hours (per-supplier overrides of market defaults; NULL = inherit)
    kitchen_open_time       TIME        NULL,
    kitchen_close_time      TIME        NULL,
    -- Invoice compliance (per-supplier overrides of market defaults)
    require_invoice         BOOLEAN     NULL,
    invoice_hold_days       INTEGER     NULL CHECK (invoice_hold_days IS NULL OR invoice_hold_days > 0),
    -- Audit
    is_archived             BOOLEAN     NOT NULL DEFAULT FALSE,
    status                  status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID        NULL,
    modified_by             UUID        NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    CONSTRAINT uq_supplier_terms_scope UNIQUE (institution_id, institution_entity_id)
);

\echo 'Creating table: audit.supplier_terms_history'
CREATE TABLE IF NOT EXISTS audit.supplier_terms_history (
    event_id                UUID        PRIMARY KEY DEFAULT uuidv7(),
    supplier_terms_id       UUID        NOT NULL,
    institution_id          UUID        NOT NULL,
    institution_entity_id   UUID        NULL,
    no_show_discount        INTEGER     NOT NULL,
    payment_frequency       payment_frequency_enum NOT NULL,
    kitchen_open_time       TIME        NULL,
    kitchen_close_time      TIME        NULL,
    require_invoice         BOOLEAN     NULL,
    invoice_hold_days       INTEGER     NULL,
    is_archived             BOOLEAN     NOT NULL,
    status                  status_enum NOT NULL,
    created_date            TIMESTAMPTZ NOT NULL,
    created_by              UUID        NULL,
    modified_by             UUID        NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL,
    is_current              BOOLEAN     DEFAULT TRUE,
    valid_until             TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (supplier_terms_id) REFERENCES billing.supplier_terms(supplier_terms_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.supplier_terms_history IS
    'Trigger-managed history mirror of billing.supplier_terms. Never written by application code.';
COMMENT ON COLUMN audit.supplier_terms_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.supplier_terms_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.supplier_terms_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';

-- ─────────────────────────────────────────────────────────────
-- INGREDIENT CATALOG
-- ─────────────────────────────────────────────────────────────

\echo 'Creating table: ops.ingredient_catalog'
CREATE TABLE IF NOT EXISTS ops.ingredient_catalog (
    ingredient_id       UUID         PRIMARY KEY DEFAULT uuidv7(),
    name                VARCHAR(150) NOT NULL,
    name_display        VARCHAR(150) NOT NULL,
    name_es             VARCHAR(150) NULL,
    name_en             VARCHAR(150) NULL,
    name_pt             VARCHAR(150) NULL,
    off_taxonomy_id     VARCHAR(100) NULL UNIQUE,
    off_wikidata_id     VARCHAR(30)  NULL,
    -- Image (Phase 5 — Wikidata; full URL; CC licensed, permanent storage permitted)
    image_url           VARCHAR(500) NULL,
    image_source        VARCHAR(20)  NULL,         -- 'wikidata' once enriched
    -- USDA FoodData Central (Phase 7 — nutrition enrichment cron)
    usda_fdc_id         INTEGER      NULL UNIQUE,
    food_group          VARCHAR(100) NULL,          -- e.g. 'Vegetables and Vegetable Products'
    -- Image enrichment pipeline state
    image_enriched      BOOLEAN      NOT NULL DEFAULT FALSE,
    image_skipped       BOOLEAN      NOT NULL DEFAULT FALSE,
    -- USDA enrichment pipeline state
    usda_enriched       BOOLEAN      NOT NULL DEFAULT FALSE,
    usda_skipped        BOOLEAN      NOT NULL DEFAULT FALSE,
    -- Provenance
    source              VARCHAR(20)  NOT NULL DEFAULT 'off',  -- 'off' | 'custom'
    is_verified         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_date        TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by         UUID         NOT NULL REFERENCES core.user_info(user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ingredient_catalog_name
    ON ops.ingredient_catalog (name);
CREATE INDEX IF NOT EXISTS idx_ingredient_catalog_image_enrichment
    ON ops.ingredient_catalog (image_enriched, image_skipped)
    WHERE image_enriched = FALSE AND image_skipped = FALSE;
CREATE INDEX IF NOT EXISTS idx_ingredient_catalog_usda_enrichment
    ON ops.ingredient_catalog (usda_enriched, usda_skipped)
    WHERE usda_enriched = FALSE AND usda_skipped = FALSE;

\echo 'Creating table: ops.product_ingredient'
CREATE TABLE IF NOT EXISTS ops.product_ingredient (
    product_ingredient_id UUID     PRIMARY KEY DEFAULT uuidv7(),
    product_id            UUID     NOT NULL REFERENCES ops.product_info(product_id) ON DELETE CASCADE,
    ingredient_id         UUID     NOT NULL REFERENCES ops.ingredient_catalog(ingredient_id) ON DELETE RESTRICT,
    sort_order            SMALLINT NOT NULL DEFAULT 0,
    created_date          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by           UUID     NOT NULL REFERENCES core.user_info(user_id),
    UNIQUE (product_id, ingredient_id)
);
CREATE INDEX IF NOT EXISTS idx_product_ingredient_product_id
    ON ops.product_ingredient (product_id);
CREATE INDEX IF NOT EXISTS idx_product_ingredient_ingredient_id
    ON ops.product_ingredient (ingredient_id);

\echo 'Creating table: ops.ingredient_alias'
CREATE TABLE IF NOT EXISTS ops.ingredient_alias (
    alias_id        UUID         PRIMARY KEY DEFAULT uuidv7(),
    ingredient_id   UUID         NOT NULL REFERENCES ops.ingredient_catalog(ingredient_id) ON DELETE CASCADE,
    alias           VARCHAR(150) NOT NULL,
    region_code     VARCHAR(10)  NULL,
    UNIQUE (alias)
);

\echo 'Creating table: ops.ingredient_nutrition'
CREATE TABLE IF NOT EXISTS ops.ingredient_nutrition (
    nutrition_id        UUID         PRIMARY KEY DEFAULT uuidv7(),
    ingredient_id       UUID         NOT NULL REFERENCES ops.ingredient_catalog(ingredient_id) ON DELETE CASCADE,
    source              VARCHAR(20)  NOT NULL,  -- 'usda' | future sources
    per_amount_g        SMALLINT     NOT NULL DEFAULT 100,
    energy_kcal         NUMERIC(8,2) NULL,
    protein_g           NUMERIC(8,2) NULL,
    fat_g               NUMERIC(8,2) NULL,
    carbohydrates_g     NUMERIC(8,2) NULL,
    fiber_g             NUMERIC(8,2) NULL,
    sugar_g             NUMERIC(8,2) NULL,
    sodium_mg           NUMERIC(8,2) NULL,
    fetched_date        DATE         NOT NULL,
    modified_date       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ingredient_id, source)
);
CREATE INDEX IF NOT EXISTS idx_ingredient_nutrition_ingredient_id
    ON ops.ingredient_nutrition (ingredient_id);

-- =============================================================================
-- ADS PLATFORM TABLES
-- =============================================================================

\echo 'Creating table: core.ad_click_tracking'
CREATE TABLE IF NOT EXISTS core.ad_click_tracking (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL REFERENCES core.user_info(user_id),
    subscription_id UUID,
    -- Google identifiers
    gclid VARCHAR(255),
    wbraid VARCHAR(255),
    gbraid VARCHAR(255),
    -- Meta identifiers
    fbclid VARCHAR(255),
    fbc VARCHAR(500),
    fbp VARCHAR(255),
    -- Dedup
    event_id VARCHAR(255),
    -- Shared
    landing_url TEXT,
    source_platform VARCHAR(20),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Per-platform upload status
    google_upload_status VARCHAR(50) DEFAULT 'pending',
    google_uploaded_at TIMESTAMPTZ,
    meta_upload_status VARCHAR(50) DEFAULT 'pending',
    meta_uploaded_at TIMESTAMPTZ,
    -- Timestamps
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ad_click_tracking_subscription
    ON core.ad_click_tracking(subscription_id);
CREATE INDEX IF NOT EXISTS idx_ad_click_tracking_user
    ON core.ad_click_tracking(user_id);
CREATE INDEX IF NOT EXISTS idx_ad_click_tracking_pending
    ON core.ad_click_tracking(google_upload_status)
    WHERE google_upload_status = 'pending' OR meta_upload_status = 'pending';

\echo 'Creating table: core.ad_zone'
CREATE TABLE IF NOT EXISTS core.ad_zone (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    -- Identity
    name VARCHAR(100) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    city_name VARCHAR(100) NOT NULL,
    neighborhood VARCHAR(100),
    -- Geometry
    latitude NUMERIC(10,7) NOT NULL,
    longitude NUMERIC(10,7) NOT NULL,
    radius_km NUMERIC(4,2) NOT NULL DEFAULT 2.0,
    -- Flywheel state
    flywheel_state flywheel_state_enum NOT NULL DEFAULT 'monitoring',
    state_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    state_changed_by UUID REFERENCES core.user_info(user_id),
    -- Metrics (updated by cron/advisor)
    notify_me_lead_count INTEGER DEFAULT 0,
    active_restaurant_count INTEGER DEFAULT 0,
    active_subscriber_count INTEGER DEFAULT 0,
    estimated_mau INTEGER,
    mau_estimated_at TIMESTAMPTZ,
    -- Budget
    budget_allocation JSONB DEFAULT '{"b2c_subscriber": 0, "b2b_employer": 0, "b2b_restaurant": 100}',
    daily_budget_cents INTEGER,
    -- Ad platform references
    meta_ad_set_ids JSONB DEFAULT '{}',
    google_campaign_ids JSONB DEFAULT '{}',
    -- Creation
    created_by VARCHAR(30) NOT NULL DEFAULT 'operator',
    approved_by UUID REFERENCES core.user_info(user_id),
    -- Timestamps
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ad_zone_state ON core.ad_zone(flywheel_state);
CREATE INDEX IF NOT EXISTS idx_ad_zone_country ON core.ad_zone(country_code);

-- ─────────────────────────────────────────────────────────────
-- DEFERRED FK: core.address_info.city_metadata_id → core.city_metadata
-- and composite consistency FK on (city_metadata_id, country_code).
-- Added at the end so city_metadata (created earlier in this file, right after
-- audit.market_history) is guaranteed to exist. The column itself was added
-- as a nullable UUID near the top of schema.sql so the audit history table
-- could mirror it via the trigger pattern.
-- ─────────────────────────────────────────────────────────────
\echo 'Adding deferred FKs on core.address_info.city_metadata_id'
ALTER TABLE core.address_info
    ADD CONSTRAINT fk_address_info_city_metadata_id
    FOREIGN KEY (city_metadata_id) REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT;
-- Composite FK enforces that an address's country_code always matches the country_iso
-- of its city_metadata row. Relies on core.city_metadata's UNIQUE (city_metadata_id, country_iso).
ALTER TABLE core.address_info
    ADD CONSTRAINT fk_address_info_city_country_consistent
    FOREIGN KEY (city_metadata_id, country_code) REFERENCES core.city_metadata(city_metadata_id, country_iso) ON DELETE RESTRICT;

-- ─────────────────────────────────────────────────────────────
-- IAM grants are applied by build_kitchen_db.sh via env vars:
--   IAM_OWNER_ACCOUNT → full access (DB object owner role)
--   IAM_ADMIN_EMAIL  → read-only access
-- See build_kitchen_db.sh header for details.
-- ─────────────────────────────────────────────────────────────
