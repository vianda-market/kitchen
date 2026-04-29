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
DROP TABLE IF EXISTS audit.referral_transaction_history CASCADE;
DROP TABLE IF EXISTS customer.referral_transaction CASCADE;
DROP TABLE IF EXISTS audit.referral_info_history CASCADE;
DROP TABLE IF EXISTS audit.referral_config_history CASCADE;
DROP TABLE IF EXISTS customer.referral_info CASCADE;
DROP TABLE IF EXISTS customer.referral_config CASCADE;
DROP TABLE IF EXISTS audit.discretionary_history CASCADE;
DROP TABLE IF EXISTS billing.discretionary_info CASCADE;
DROP TABLE IF EXISTS billing.client_transaction CASCADE;
DROP TABLE IF EXISTS customer.user_favorite_info CASCADE;
DROP TABLE IF EXISTS customer.plate_review_info CASCADE;
DROP TABLE IF EXISTS audit.plate_pickup_live_history CASCADE;
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
DROP TABLE IF EXISTS ops.restaurant_lead_cuisine CASCADE;
DROP TABLE IF EXISTS ops.restaurant_lead CASCADE;
DROP TABLE IF EXISTS core.lead_interest CASCADE;
-- core.employer_domain REMOVED (replaced by email_domain on institution_entity_info)
DROP TABLE IF EXISTS core.employer_benefits_program CASCADE;
DROP TABLE IF EXISTS audit.payment_attempt_history CASCADE;
DROP TABLE IF EXISTS billing.payment_attempt CASCADE;
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

\echo 'Creating enum type: payment_provider_enum'
CREATE TYPE payment_provider_enum AS ENUM (
    'stripe',
    'mercado_pago'
);

\echo 'Creating enum type: payment_attempt_status_enum'
CREATE TYPE payment_attempt_status_enum AS ENUM (
    'pending',
    'processing',
    'succeeded',
    'failed',
    'cancelled',
    'refunded'
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
COMMENT ON TABLE core.schema_migration IS
    'Tracks applied incremental migration files. Populated by migrate.sh; one row per migration '
    'script. Used to determine which migrations are pending on a given DB instance.';
COMMENT ON COLUMN core.schema_migration.version IS
    'Integer migration version number. Primary key. Monotonically increasing; assigned by migrate.sh.';
COMMENT ON COLUMN core.schema_migration.name IS
    'Human-readable migration name (filename without extension).';
COMMENT ON COLUMN core.schema_migration.applied_at IS
    'UTC timestamp when the migration was applied to this DB instance.';
COMMENT ON COLUMN core.schema_migration.checksum IS
    'SHA-256 checksum of the migration SQL file. Detects post-apply tampering.';

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
COMMENT ON TABLE core.national_holidays IS
    'Country-level public holidays used to block kitchen operations (no orders/pickups on these dates). '
    'Populated via the nager.date API cron (nager_date source) and by manual admin entry. '
    'Soft-deleted via is_archived; unique active index prevents duplicate (country, date) pairs.';
COMMENT ON COLUMN core.national_holidays.holiday_id IS
    'UUIDv7 primary key. Time-ordered for efficient range queries.';
COMMENT ON COLUMN core.national_holidays.country_code IS
    'ISO 3166-1 alpha-2 country code identifying which country observes this holiday. '
    'Constrained to 2 chars despite VARCHAR(3) type — the CHECK enforces 2-char length.';
COMMENT ON COLUMN core.national_holidays.holiday_name IS
    'Display name for the holiday (e.g. ''Día de la Independencia'').';
COMMENT ON COLUMN core.national_holidays.holiday_date IS
    'Calendar date of the holiday. Used to gate kitchen operations.';
COMMENT ON COLUMN core.national_holidays.is_recurring IS
    'TRUE if this holiday recurs on the same month/day every year (e.g. Christmas). '
    'FALSE for fixed-date entries from nager_date.';
COMMENT ON COLUMN core.national_holidays.recurring_month IS
    'Month (1–12) for recurring holidays. NULL when is_recurring=FALSE.';
COMMENT ON COLUMN core.national_holidays.recurring_day IS
    'Day-of-month (1–31) for recurring holidays. NULL when is_recurring=FALSE.';
COMMENT ON COLUMN core.national_holidays.status IS
    'Lifecycle status (active/inactive). active = currently blocks kitchen operations.';
COMMENT ON COLUMN core.national_holidays.is_archived IS
    'Soft-delete tombstone. Archived rows are excluded from kitchen operation checks.';
COMMENT ON COLUMN core.national_holidays.created_date IS
    'UTC timestamp when the row was first inserted.';
COMMENT ON COLUMN core.national_holidays.created_by IS
    'UUID of the user who created this holiday record. NULL for system-generated (nager_date import).';
COMMENT ON COLUMN core.national_holidays.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.national_holidays.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN core.national_holidays.source IS
    '''manual'' = admin-entered; ''nager_date'' = imported from the nager.date public holiday API. '
    'nager_date rows are never recurring (CHECK constraint).';

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
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    canonical_key VARCHAR(200) NULL
);
COMMENT ON TABLE core.institution_info IS
    'Top-level entity for supplier, employer, customer, and internal institutions. '
    'One institution = one set of admin users, one login. Country-specific concerns '
    '(legal entities, currencies) live on ops.institution_entity_info. '
    'Multi-market assignment via core.institution_market junction.';
COMMENT ON COLUMN core.institution_info.institution_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.institution_info.name IS
    'Display name for the institution (e.g. restaurant or employer brand name). Max 50 chars.';
COMMENT ON COLUMN core.institution_info.institution_type IS
    'Discriminator: ''supplier'' (restaurant operator), ''employer'' (corporate meal program), '
    '''customer'' (B2C consumer group), or ''internal'' (Vianda staff). Controls permission scoping.';
COMMENT ON COLUMN core.institution_info.is_archived IS
    'Soft-delete tombstone. Archived institutions are hidden from all active queries.';
COMMENT ON COLUMN core.institution_info.status IS
    'Lifecycle status (active/inactive). Toggled by admin; inactive institutions cannot transact.';
COMMENT ON COLUMN core.institution_info.created_date IS
    'UTC timestamp when the institution was registered.';
COMMENT ON COLUMN core.institution_info.created_by IS
    'UUID of the user who created the institution. NULL for programmatic creation.';
COMMENT ON COLUMN core.institution_info.support_email_suppressed_until IS
    'UTC timestamp until which automated support emails are suppressed for this institution. '
    'Set by the stall-detection cron to enforce 3-day cooldowns between outreach emails.';
COMMENT ON COLUMN core.institution_info.last_support_email_date IS
    'UTC timestamp of the last automated support email sent to this institution.';
COMMENT ON COLUMN core.institution_info.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.institution_info.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN core.institution_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture institutions '
    '(e.g. ''E2E_INSTITUTION_SUPPLIER''). Used by the '
    'PUT /api/v1/institutions/by-key upsert endpoint to make Postman seed runs '
    'idempotent. NULL for ad-hoc institutions created via the normal POST endpoint.';

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
COMMENT ON TABLE core.employer_benefits_program IS
    'Employer meal benefit configuration. Supports three-tier cascade: '
    'institution_entity_id IS NULL = institution-level defaults; NOT NULL = entity-level override. '
    'Currency-tied fields (benefit_cap, minimum_monthly_fee, stripe_*) exist only at entity level. '
    'Unique constraint: (institution_id, institution_entity_id).';
COMMENT ON COLUMN core.employer_benefits_program.program_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.employer_benefits_program.institution_id IS
    'FK to core.institution_info. The employer institution that owns this program.';
COMMENT ON COLUMN core.employer_benefits_program.institution_entity_id IS
    'FK to ops.institution_entity_info. NULL = institution-level defaults; NOT NULL = entity-level override. '
    'Entity overrides are used for multi-country employers where currency-tied fields differ per country.';
COMMENT ON COLUMN core.employer_benefits_program.benefit_rate IS
    'Percentage (0–100) of meal plan cost subsidized by the employer. '
    '100 = fully employer-paid; 0 = no subsidy (employee pays full price).';
COMMENT ON COLUMN core.employer_benefits_program.benefit_cap IS
    'Maximum benefit amount per cap period in the entity''s local currency. NULL = no cap. '
    'Only meaningful at the entity level where currency is known.';
COMMENT ON COLUMN core.employer_benefits_program.benefit_cap_period IS
    'Period over which benefit_cap applies (''monthly''). Used by billing to reset cap tracking.';
COMMENT ON COLUMN core.employer_benefits_program.price_discount IS
    'Additional percentage discount (0–100) on the plan price for employer employees. '
    'Separate from benefit_rate — reduces the base price before subsidy is applied.';
COMMENT ON COLUMN core.employer_benefits_program.minimum_monthly_fee IS
    'Minimum monthly employer invoice amount in local currency. NULL = no minimum. '
    'Enforced at month-end reconciliation in the employer billing cron.';
COMMENT ON COLUMN core.employer_benefits_program.billing_cycle IS
    'Billing frequency for employer invoices (''monthly'').';
COMMENT ON COLUMN core.employer_benefits_program.billing_day IS
    'Day of month (1–28) on which employer invoices are generated. NULL uses default.';
COMMENT ON COLUMN core.employer_benefits_program.billing_day_of_week IS
    'Day of week (0=Sunday … 6=Saturday) for weekly billing cycles. NULL for monthly.';
COMMENT ON COLUMN core.employer_benefits_program.enrollment_mode IS
    'How employees are enrolled: ''managed'' (admin-controlled) or ''open'' (self-service by email domain).';
COMMENT ON COLUMN core.employer_benefits_program.allow_early_renewal IS
    'Whether employees on this program can trigger early subscription renewal. '
    'Tied to subscription.early_renewal_threshold logic.';
COMMENT ON COLUMN core.employer_benefits_program.stripe_customer_id IS
    'Stripe Customer ID for the employer entity''s billing account. NULL until payment is set up.';
COMMENT ON COLUMN core.employer_benefits_program.stripe_payment_method_id IS
    'Stripe PaymentMethod ID for automated employer invoice collection. NULL until configured.';
COMMENT ON COLUMN core.employer_benefits_program.payment_method_type IS
    'Descriptor for the payment method type (e.g. ''card'', ''bank_transfer''). Informational.';
COMMENT ON COLUMN core.employer_benefits_program.is_active IS
    'Whether this program is currently active. Inactive programs do not process new enrollments.';
COMMENT ON COLUMN core.employer_benefits_program.is_archived IS
    'Soft-delete tombstone. Archived programs are hidden from all queries.';
COMMENT ON COLUMN core.employer_benefits_program.status IS
    'Lifecycle status enum (active/inactive). Redundant with is_active for pattern consistency.';
COMMENT ON COLUMN core.employer_benefits_program.created_date IS
    'UTC timestamp when the program was created.';
COMMENT ON COLUMN core.employer_benefits_program.created_by IS
    'UUID of the user who created the program. NULL for programmatic creation.';
COMMENT ON COLUMN core.employer_benefits_program.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.employer_benefits_program.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE core.lead_interest IS
    'Pre-signup interest registrations from prospective customers, employers, and suppliers. '
    'Collected via the marketing site interest forms before the user has a Vianda account. '
    'Surfaced in the admin lead interest dashboard.';
COMMENT ON COLUMN core.lead_interest.lead_interest_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.lead_interest.email IS
    'Case-insensitive email address of the prospect. citext — uniqueness checks are case-folded.';
COMMENT ON COLUMN core.lead_interest.country_code IS
    'ISO 3166-1 alpha-2 country code the prospect selected on the interest form.';
COMMENT ON COLUMN core.lead_interest.city_name IS
    'Free-text city name as entered by the prospect. Not normalized — may differ from geonames canonical names.';
COMMENT ON COLUMN core.lead_interest.zipcode IS
    'Postal/ZIP code provided by the prospect. NULL if not collected.';
COMMENT ON COLUMN core.lead_interest.zipcode_only IS
    'TRUE when the prospect provided a zipcode but no city name (zipcode-only interest mode).';
COMMENT ON COLUMN core.lead_interest.interest_type IS
    'Lead type: ''customer'' (consumer), ''employer'' (corporate program buyer), or ''supplier'' (restaurant operator).';
COMMENT ON COLUMN core.lead_interest.business_name IS
    'Company or restaurant name. Present for employer and supplier leads; NULL for customer leads.';
COMMENT ON COLUMN core.lead_interest.message IS
    'Optional free-text message from the prospect.';
COMMENT ON COLUMN core.lead_interest.cuisine_id IS
    'FK to ops.cuisine. Optional cuisine preference for customer leads.';
COMMENT ON COLUMN core.lead_interest.employee_count_range IS
    'Company size range for employer leads (e.g. ''51-100'', ''101-500''). NULL for other lead types.';
COMMENT ON COLUMN core.lead_interest.status IS
    '''active'' = not yet contacted; ''notified'' = outreach email sent; ''unsubscribed'' = opt-out.';
COMMENT ON COLUMN core.lead_interest.source IS
    'Acquisition channel: ''web'' (marketing site form), ''api'' (direct API), etc.';
COMMENT ON COLUMN core.lead_interest.notified_date IS
    'UTC timestamp when the outreach notification email was last sent. NULL if not yet contacted.';
COMMENT ON COLUMN core.lead_interest.is_archived IS
    'Soft-delete tombstone. Archived leads are excluded from active queries and exports.';
COMMENT ON COLUMN core.lead_interest.created_date IS
    'UTC timestamp when the lead interest was registered.';
COMMENT ON COLUMN core.lead_interest.modified_date IS
    'UTC timestamp of the most recent update.';

\echo 'Creating table: ops.restaurant_lead'
CREATE TABLE IF NOT EXISTS ops.restaurant_lead (
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
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_status ON ops.restaurant_lead(lead_status);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_country ON ops.restaurant_lead(country_code);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_email ON ops.restaurant_lead(contact_email);
COMMENT ON TABLE ops.restaurant_lead IS
    'Restaurant supplier application leads submitted via the marketing site. '
    'Captures contact info, business profile, and vetting answers before a supplier account is created. '
    'On approval, institution_id is populated and a full supplier institution is provisioned.';
COMMENT ON COLUMN ops.restaurant_lead.restaurant_lead_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.restaurant_lead.business_name IS
    'Restaurant or business trade name as submitted by the applicant.';
COMMENT ON COLUMN ops.restaurant_lead.contact_name IS
    'Full name of the primary contact at the restaurant.';
COMMENT ON COLUMN ops.restaurant_lead.contact_email IS
    'Case-insensitive email address of the applicant. citext — uniqueness checks are case-folded.';
COMMENT ON COLUMN ops.restaurant_lead.contact_phone IS
    'Phone number of the applicant. Free-form; not validated for E.164 format at this layer.';
COMMENT ON COLUMN ops.restaurant_lead.country_code IS
    'ISO 3166-1 alpha-2 country code where the restaurant operates.';
COMMENT ON COLUMN ops.restaurant_lead.city_name IS
    'City name as entered by the applicant. Not normalized against geonames.';
COMMENT ON COLUMN ops.restaurant_lead.years_in_operation IS
    'Number of years the restaurant has been in operation. Non-negative integer.';
COMMENT ON COLUMN ops.restaurant_lead.employee_count_range IS
    'Restaurant staff count range (e.g. ''1-5'', ''6-20''). Informational for vetting.';
COMMENT ON COLUMN ops.restaurant_lead.kitchen_capacity_daily IS
    'Maximum number of meals the kitchen can prepare per day. Used in capacity vetting.';
COMMENT ON COLUMN ops.restaurant_lead.website_url IS
    'Restaurant website or social media URL. Optional; informational for vetting.';
COMMENT ON COLUMN ops.restaurant_lead.referral_source IS
    'How the applicant heard about Vianda (enum). Used for acquisition attribution.';
COMMENT ON COLUMN ops.restaurant_lead.message IS
    'Optional free-text message from the applicant.';
COMMENT ON COLUMN ops.restaurant_lead.vetting_answers IS
    'JSONB blob of country-specific vetting question answers. Schema is flexible until '
    'questions are finalized per country. Do not rely on a fixed structure across markets.';
COMMENT ON COLUMN ops.restaurant_lead.lead_status IS
    'Workflow state: ''submitted'' → ''in_review'' → ''approved'' / ''rejected''.';
COMMENT ON COLUMN ops.restaurant_lead.rejection_reason IS
    'Admin-entered reason for rejection. NULL when lead_status is not ''rejected''.';
COMMENT ON COLUMN ops.restaurant_lead.reviewed_by IS
    'FK to core.user_info — internal reviewer who processed this lead. NULL until reviewed.';
COMMENT ON COLUMN ops.restaurant_lead.reviewed_at IS
    'UTC timestamp when the lead was reviewed (approved or rejected).';
COMMENT ON COLUMN ops.restaurant_lead.institution_id IS
    'FK to core.institution_info. Populated on approval — links the lead to the provisioned supplier institution. '
    'NULL while the lead is still pending.';
COMMENT ON COLUMN ops.restaurant_lead.gclid IS
    'Google Click ID captured at lead submission for conversion attribution.';
COMMENT ON COLUMN ops.restaurant_lead.fbclid IS
    'Facebook Click ID captured at lead submission.';
COMMENT ON COLUMN ops.restaurant_lead.fbc IS
    'Facebook browser cookie (_fbc) captured at lead submission. Up to 500 chars.';
COMMENT ON COLUMN ops.restaurant_lead.fbp IS
    'Facebook pixel cookie (_fbp) captured at lead submission.';
COMMENT ON COLUMN ops.restaurant_lead.event_id IS
    'Deduplication event ID for server-side Conversions API calls.';
COMMENT ON COLUMN ops.restaurant_lead.source_platform IS
    'Ad platform that drove the lead (e.g. ''google'', ''meta''). Used to route conversion uploads.';
COMMENT ON COLUMN ops.restaurant_lead.is_archived IS
    'Soft-delete tombstone. Archived leads are excluded from active queries.';
COMMENT ON COLUMN ops.restaurant_lead.created_date IS
    'UTC timestamp when the lead was submitted.';
COMMENT ON COLUMN ops.restaurant_lead.modified_date IS
    'UTC timestamp of the most recent update.';

-- ops.restaurant_lead_cuisine junction (many-to-many with cuisine, created later)
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
COMMENT ON TABLE core.workplace_group IS
    'Groups of coworkers at the same office location, used for coworker pickup coordination in the B2C app. '
    'Employees join a workplace group to see and coordinate with coworkers who are also ordering lunch.';
COMMENT ON COLUMN core.workplace_group.workplace_group_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.workplace_group.name IS
    'Display name for the workplace group (e.g. company or office name). Trigram-indexed for search.';
COMMENT ON COLUMN core.workplace_group.email_domain IS
    'Email domain for auto-joining (e.g. ''vianda.market''). NULL = no domain gating. '
    'Unique partial index prevents two active groups claiming the same domain.';
COMMENT ON COLUMN core.workplace_group.require_domain_verification IS
    'When TRUE, users must have a verified email matching email_domain to join this group.';
COMMENT ON COLUMN core.workplace_group.is_archived IS
    'Soft-delete tombstone. Archived groups are hidden from discovery and cannot accept new members.';
COMMENT ON COLUMN core.workplace_group.status IS
    'Lifecycle status (active/inactive). Inactive groups do not appear in user-facing pickers.';
COMMENT ON COLUMN core.workplace_group.created_date IS
    'UTC timestamp when the group was created.';
COMMENT ON COLUMN core.workplace_group.created_by IS
    'UUID of the user who created the group. NULL for programmatic creation.';
COMMENT ON COLUMN core.workplace_group.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.workplace_group.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key VARCHAR(200) NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    -- Note: employer_entity_id FK to ops.institution_entity_info added via deferred ALTER (entity table created later)
);

COMMENT ON COLUMN core.user_info.canonical_key IS
'Optional stable human-readable identifier for seed/fixture users '
'(e.g. ''E2E_USER_SUPPLIER_ADMIN''). Used by the '
'PUT /api/v1/users/by-key upsert endpoint to make Postman seed runs '
'idempotent. NULL for ad-hoc users created via the normal POST endpoint. '
'Never use this field for self-registration or customer-facing flows.';

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

-- ops.restaurant_lead
ALTER TABLE ops.restaurant_lead
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
COMMENT ON TABLE core.address_subpremise IS
    'Per-user subpremise detail for a shared address (floor, apartment unit, default flag). '
    'Separated from address_info to allow multiple users to share the same base address '
    'while maintaining their own delivery preferences. One row per (address_id, user_id) pair.';
COMMENT ON COLUMN core.address_subpremise.subpremise_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.address_subpremise.address_id IS
    'FK to core.address_info. The base address this subpremise detail belongs to.';
COMMENT ON COLUMN core.address_subpremise.user_id IS
    'FK to core.user_info. The user whose subpremise preferences are stored here.';
COMMENT ON COLUMN core.address_subpremise.floor IS
    'Floor or storey of the building (e.g. ''3'', ''PB''). Optional; NULL if not applicable.';
COMMENT ON COLUMN core.address_subpremise.apartment_unit IS
    'Apartment, suite, or unit number (e.g. ''4A'', ''Suite 200''). Optional.';
COMMENT ON COLUMN core.address_subpremise.is_default IS
    'TRUE if this is the user''s default pickup/delivery address. At most one default per user.';
COMMENT ON COLUMN core.address_subpremise.map_center_label IS
    'User-selected map center label for pickup location disambiguation: ''home'', ''other'', or NULL (defaults to home). '
    'Drives map center-of-gravity selection in the B2C app pickup flow.';
COMMENT ON COLUMN core.address_subpremise.created_date IS
    'UTC timestamp when the subpremise record was created.';
COMMENT ON COLUMN core.address_subpremise.created_by IS
    'UUID of the user who created this record. NULL for programmatic creation.';
COMMENT ON COLUMN core.address_subpremise.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.address_subpremise.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE core.currency_rate_raw IS
    'Raw exchange rate snapshots fetched by the currency refresh cron from the open.er-api.com API. '
    'Append-only log; is_valid=FALSE marks stale or erroneous rows. '
    'Rates here feed the currency_conversion_usd column on core.currency_metadata via the ops flow.';
COMMENT ON COLUMN core.currency_rate_raw.currency_rate_raw_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.currency_rate_raw.fetched_at IS
    'UTC timestamp when this rate was fetched from the API.';
COMMENT ON COLUMN core.currency_rate_raw.base_currency IS
    'ISO 4217 code of the base currency (always ''USD'' in current implementation).';
COMMENT ON COLUMN core.currency_rate_raw.target_currency IS
    'ISO 4217 code of the target currency being quoted (e.g. ''ARS'', ''BRL'').';
COMMENT ON COLUMN core.currency_rate_raw.rate IS
    'Exchange rate: 1 base_currency = rate target_currency units (e.g. 850.0 for 1 USD = 850 ARS).';
COMMENT ON COLUMN core.currency_rate_raw.api_source IS
    'Identifier of the data provider (''open.er-api'' default). Future: may support alternative providers.';
COMMENT ON COLUMN core.currency_rate_raw.api_date IS
    'Date the API reports for this rate (may differ from fetched_at due to weekend/holiday roll-forward).';
COMMENT ON COLUMN core.currency_rate_raw.raw_payload IS
    'Full JSON response body from the API. Stored for auditability and re-processing without refetch.';
COMMENT ON COLUMN core.currency_rate_raw.is_valid IS
    'FALSE = this row is stale, erroneous, or superseded. Only valid rows are used for rate promotion.';
COMMENT ON COLUMN core.currency_rate_raw.notes IS
    'Optional human-readable annotation (e.g. reason for invalidation). NULL for normal rows.';

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
COMMENT ON TABLE core.currency_metadata IS
    'Vianda pricing policy layer on top of external.iso4217_currency. One row per currency Vianda '
    'has enabled for operational use. Stores the credit-to-local-currency conversion rate and the '
    'operational USD exchange rate (snapshotted by cron; not real-time). FKed by core.market_info.';
COMMENT ON COLUMN core.currency_metadata.currency_metadata_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.currency_metadata.currency_code IS
    'ISO 4217 alpha code. Unique FK to external.iso4217_currency.code. '
    'Display name and minor_unit are always derived via JOIN — not stored redundantly here.';
COMMENT ON COLUMN core.currency_metadata.credit_value_local_currency IS
    'Vianda pricing policy: how many local currency units equal one Vianda credit. '
    'Example: if 1 credit = 500 ARS, this column is 500. Used in plan pricing and invoice calculations.';
COMMENT ON COLUMN core.currency_metadata.currency_conversion_usd IS
    'Operational USD exchange rate: how many local currency units equal 1 USD. '
    'Snapshotted from the currency refresh cron; not real-time. '
    'Used for cross-currency invoice reporting and plan cost estimates in USD.';
COMMENT ON COLUMN core.currency_metadata.is_archived IS
    'Soft-delete tombstone. Archived currencies are not available for new markets or entities.';
COMMENT ON COLUMN core.currency_metadata.status IS
    'Lifecycle status (active/inactive). Inactive currencies are hidden from pickers.';
COMMENT ON COLUMN core.currency_metadata.created_date IS
    'UTC timestamp when the currency was enabled in Vianda.';
COMMENT ON COLUMN core.currency_metadata.created_by IS
    'UUID of the user who enabled this currency. NULL for seed data.';
COMMENT ON COLUMN core.currency_metadata.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.currency_metadata.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key VARCHAR(200) NULL,                    -- Optional stable seed/fixture identifier (e.g. 'E2E_MARKET_AR')
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (country_code) REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    FOREIGN KEY (currency_metadata_id) REFERENCES core.currency_metadata(currency_metadata_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE core.market_info IS
    'Vianda operational markets — one row per country Vianda operates in. '
    'One market = one country code + one currency + one default language. '
    'Unique per country_code. Drives subscription scoping, restaurant visibility, and locale defaults. '
    'Market status (active/inactive) controls whether the country surfaces to customers.';
COMMENT ON COLUMN core.market_info.market_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.market_info.country_code IS
    'ISO 3166-1 alpha-2 country code. Unique per market. FK to external.geonames_country.iso_alpha2. '
    '''XG'' for the synthetic Global pseudo-market.';
COMMENT ON COLUMN core.market_info.currency_metadata_id IS
    'FK to core.currency_metadata. The operational currency for this market. '
    'Drives plan pricing, invoice amounts, and currency display across the market.';
COMMENT ON COLUMN core.market_info.language IS
    'Default UI language for this market: ''en'', ''es'', or ''pt''. '
    'Used as locale default before user preferences are set (signup, pre-auth marketing site).';
COMMENT ON COLUMN core.market_info.phone_dial_code IS
    'E.164 international dialing prefix for this market (e.g. ''+54'' for Argentina). '
    'Surfaced in the /leads/countries response as ''phone_dial_code'' for phone input forms. '
    'NULL for pseudo-markets (e.g. XG/Global) that have no real dial code.';
COMMENT ON COLUMN core.market_info.phone_local_digits IS
    'Maximum number of national digits after the dial code (e.g. 10 for Argentina). '
    'Used as maxLength hint in phone number input fields. NULL for pseudo-markets.';
COMMENT ON COLUMN core.market_info.is_archived IS
    'Soft-delete tombstone. Archived markets are excluded from all active queries.';
COMMENT ON COLUMN core.market_info.status IS
    '''active'' = currently serving customers (surfaces in /leads/countries); '
    '''inactive'' = configured but not serving (surfaces in /leads/supplier-countries only). '
    'Source of truth for market operational status.';
COMMENT ON COLUMN core.market_info.created_date IS
    'UTC timestamp when the market was configured.';
COMMENT ON COLUMN core.market_info.created_by IS
    'UUID of the user who created the market. NULL for seed data.';
COMMENT ON COLUMN core.market_info.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.market_info.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN core.market_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture markets '
    '(e.g. ''E2E_MARKET_AR''). Used by the PUT /api/v1/markets/by-key upsert endpoint '
    'to make Postman seed runs idempotent. NULL for ad-hoc markets created via the '
    'normal POST endpoint. Unique when not null (enforced by partial index uq_market_info_canonical_key).';

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
COMMENT ON TABLE core.address_info IS
    'Physical addresses for restaurants (supplier), employer offices, and customer residences. '
    'Immutable core (street, city, province) — only administrative fields (address_type, is_archived) '
    'are updated after creation. Subpremise details (floor, apartment) live in core.address_subpremise. '
    'Timezone is populated at write time from external.geonames_city.timezone via the city_metadata_id FK chain.';
COMMENT ON COLUMN core.address_info.address_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.address_info.institution_id IS
    'FK to core.institution_info. Every address belongs to exactly one institution.';
COMMENT ON COLUMN core.address_info.user_id IS
    'FK to core.user_info. Required only for Customer Comensal home/other addresses; '
    'NULL for supplier restaurant and employer office addresses.';
COMMENT ON COLUMN core.address_info.workplace_group_id IS
    'FK to core.workplace_group. Links an employer office address to a workplace group '
    'for coworker pickup coordination. NULL for all non-office addresses.';
COMMENT ON COLUMN core.address_info.address_type IS
    'Array of address type enum values. Multiple types allowed (e.g. restaurant + entity_billing). '
    'Values: restaurant, entity_billing, entity_address, customer_home, customer_employer, customer_other.';
COMMENT ON COLUMN core.address_info.country_code IS
    'ISO 3166-1 alpha-2 country code. FK to external.geonames_country.iso_alpha2.';
COMMENT ON COLUMN core.address_info.province IS
    'Display-only province/state string. Structural province data lives on '
    'external.geonames_admin1 via the city_metadata → geonames_city.admin1_code chain.';
COMMENT ON COLUMN core.address_info.city IS
    'DEPRECATED (PR2) — use city_metadata_id FK instead. Kept for legacy service queries '
    'and tests that INSERT raw addresses. Will be removed in a future migration.';
COMMENT ON COLUMN core.address_info.city_metadata_id IS
    'FK to core.city_metadata. NOT NULL as of PR4c — every address must resolve to a known city. '
    'Composite FK also enforces that country_code matches city_metadata.country_iso.';
COMMENT ON COLUMN core.address_info.postal_code IS
    'Postal/ZIP code. Format varies by country (e.g. ''1425'' in AR, ''10001'' in US).';
COMMENT ON COLUMN core.address_info.street_type IS
    'Street type enum (st, ave, blvd, etc.). Used for address formatting in UI.';
COMMENT ON COLUMN core.address_info.street_name IS
    'Street name without the type prefix (e.g. ''Corrientes'', ''5th Avenue'').';
COMMENT ON COLUMN core.address_info.building_number IS
    'Street number / building number (e.g. ''1234'', ''42B'').';
COMMENT ON COLUMN core.address_info.timezone IS
    'IANA timezone identifier, populated at write time from external.geonames_city.timezone '
    'via the city_metadata_id → geonames_city FK chain (e.g. ''America/Argentina/Buenos_Aires''). '
    'Source of truth for restaurant kitchen-day scheduling and pickup window calculations.';
COMMENT ON COLUMN core.address_info.is_archived IS
    'Soft-delete tombstone. Archived addresses are excluded from active queries.';
COMMENT ON COLUMN core.address_info.status IS
    'Lifecycle status (active/inactive). Inactive addresses are not selectable in new assignments.';
COMMENT ON COLUMN core.address_info.created_date IS
    'UTC timestamp when the address was created.';
COMMENT ON COLUMN core.address_info.created_by IS
    'UUID of the user who created the address. NULL for programmatic creation.';
COMMENT ON COLUMN core.address_info.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.address_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE core.country_metadata IS
    'Vianda audience flags and display overrides on top of external.geonames_country. '
    'One row per country Vianda has explicitly promoted via the superadmin flow. '
    'Controls which countries appear in the customer, supplier, and employer audience lists. '
    'Display name resolver: metadata override → external.geonames_alternate_name → canonical name.';
COMMENT ON COLUMN core.country_metadata.country_metadata_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.country_metadata.country_iso IS
    'ISO 3166-1 alpha-2 country code. Unique. FK to external.geonames_country.iso_alpha2.';
COMMENT ON COLUMN core.country_metadata.market_id IS
    'FK to core.market_info. NULL = country is in audience lists but has no operational market yet. '
    'Non-NULL = this country is an active or inactive Vianda market.';
COMMENT ON COLUMN core.country_metadata.display_name_override IS
    'Optional Vianda-curated display name override in English. NULL = use GeoNames canonical name. '
    'Use only when Vianda explicitly disagrees with GeoNames (rare).';
COMMENT ON COLUMN core.country_metadata.display_name_i18n IS
    'Optional JSON object of locale-specific display name overrides: {"en": "...", "es": "...", "pt": "..."}. '
    'NULL = fall back to geonames_alternate_name table for localization.';
COMMENT ON COLUMN core.country_metadata.is_customer_audience IS
    'TRUE = country appears in /leads/markets default (customer-facing country selector).';
COMMENT ON COLUMN core.country_metadata.is_supplier_audience IS
    'TRUE = country appears in /leads/markets?audience=supplier (supplier application form dropdown).';
COMMENT ON COLUMN core.country_metadata.is_employer_audience IS
    'TRUE = country is eligible for employer audience flows. Reserved for future employer lead capture.';
COMMENT ON COLUMN core.country_metadata.is_archived IS
    'Soft-delete tombstone. Archived countries are excluded from all audience queries.';
COMMENT ON COLUMN core.country_metadata.status IS
    '''pending'' = promoted for interest forms but no active supplier yet; '
    '''active'' = has real activity. Flipped by service code, not a trigger.';
COMMENT ON COLUMN core.country_metadata.created_date IS
    'UTC timestamp when this country was promoted into Vianda metadata.';
COMMENT ON COLUMN core.country_metadata.created_by IS
    'UUID of the user who created this record. NULL for seed data.';
COMMENT ON COLUMN core.country_metadata.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.country_metadata.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE core.city_metadata IS
    'Vianda display flags and overrides on top of external.geonames_city. '
    'One row per city Vianda has explicitly promoted. Controls which cities appear in '
    'the signup picker, supplier form, and customer interest form. '
    'is_served is a derived flag set by service code when the first active restaurant lands. '
    'Display name resolver: metadata override → geonames_alternate_name → canonical name.';
COMMENT ON COLUMN core.city_metadata.city_metadata_id IS
    'UUIDv7 primary key. Time-ordered. '
    'UUID ''aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'' = synthetic Global city for B2B users.';
COMMENT ON COLUMN core.city_metadata.geonames_id IS
    'FK to external.geonames_city.geonames_id. Unique. Connects metadata to the canonical GeoNames city record.';
COMMENT ON COLUMN core.city_metadata.country_iso IS
    'ISO 3166-1 alpha-2 country code. FK to external.geonames_country.iso_alpha2. '
    'Part of the composite UNIQUE (city_metadata_id, country_iso) used for address consistency FKs.';
COMMENT ON COLUMN core.city_metadata.display_name_override IS
    'Optional Vianda-curated city display name override in English. NULL = use GeoNames canonical name.';
COMMENT ON COLUMN core.city_metadata.display_name_i18n IS
    'Optional JSON object of locale-specific display overrides: {"en": "...", "es": "...", "pt": "..."}. '
    'NULL = fall back to geonames_alternate_name table for localization.';
COMMENT ON COLUMN core.city_metadata.show_in_signup_picker IS
    'TRUE = city appears in the B2C customer signup city picker. '
    'Replaces the old city_info ''is this a signup-selectable city?'' role.';
COMMENT ON COLUMN core.city_metadata.show_in_supplier_form IS
    'TRUE = city appears in the supplier lead capture city dropdown on the marketing site.';
COMMENT ON COLUMN core.city_metadata.show_in_customer_form IS
    'TRUE = city appears in the customer interest capture city dropdown.';
COMMENT ON COLUMN core.city_metadata.is_served IS
    'Derived flag: TRUE when ≥1 active restaurant with plates + QR code exists in this city. '
    'Set by service code on restaurant activation; not maintained by a DB trigger.';
COMMENT ON COLUMN core.city_metadata.is_archived IS
    'Soft-delete tombstone. Archived cities are excluded from all picker queries.';
COMMENT ON COLUMN core.city_metadata.status IS
    '''pending'' = promoted but no active restaurant yet; ''active'' = has at least one active restaurant. '
    'Flipped by service code on first restaurant activation.';
COMMENT ON COLUMN core.city_metadata.created_date IS
    'UTC timestamp when this city was promoted into Vianda metadata.';
COMMENT ON COLUMN core.city_metadata.created_by IS
    'UUID of the user who promoted this city. NULL for seed data.';
COMMENT ON COLUMN core.city_metadata.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.city_metadata.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE core.user_info IS
    'All Vianda users: Internal staff, Supplier admins/operators, Customer Comensals, and Employer HR users. '
    'One user = one login. Role determined by role_type + role_name. '
    'Customer-specific employer linkage via employer_entity_id.';
COMMENT ON COLUMN core.user_info.user_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.user_info.institution_id IS
    'FK to core.institution_info. Every user belongs to exactly one institution.';
COMMENT ON COLUMN core.user_info.role_type IS
    'Broad access tier: ''internal'' (global access), ''supplier'', ''employer'', or ''customer''.';
COMMENT ON COLUMN core.user_info.role_name IS
    'Operation-level role within role_type: ''super_admin'', ''admin'', ''manager'', ''operator'', ''comensal'', ''global_manager''.';
COMMENT ON COLUMN core.user_info.username IS
    'Case-insensitive login username. citext — uniqueness is case-folded.';
COMMENT ON COLUMN core.user_info.email IS
    'Case-insensitive email address. citext. Used for login and notifications.';
COMMENT ON COLUMN core.user_info.hashed_password IS
    'Bcrypt-hashed password. Never exposed in API responses.';
COMMENT ON COLUMN core.user_info.first_name IS
    'User''s given name. Optional; used for display in UI and email greetings.';
COMMENT ON COLUMN core.user_info.last_name IS
    'User''s family name. Optional; combined with first_name for display.';
COMMENT ON COLUMN core.user_info.mobile_number IS
    'E.164-formatted mobile phone number (e.g. ''+541112345678''). Optional. '
    'CHECK constraint enforces E.164 format. Used for push notification and support contact.';
COMMENT ON COLUMN core.user_info.mobile_number_verified IS
    'Whether the mobile number has been verified via OTP. Unverified numbers cannot receive SMS.';
COMMENT ON COLUMN core.user_info.mobile_number_verified_at IS
    'UTC timestamp when the mobile number was verified. NULL if not yet verified.';
COMMENT ON COLUMN core.user_info.email_verified IS
    'Whether the email address has been verified. Unverified users may have limited access.';
COMMENT ON COLUMN core.user_info.email_verified_at IS
    'UTC timestamp when the email was verified. NULL if not yet verified.';
COMMENT ON COLUMN core.user_info.employer_entity_id IS
    'FK to ops.institution_entity_info. For Customer Comensals: links to their employer entity '
    'for benefit-plan resolution and enrollment gating. NULL for all non-customer users.';
COMMENT ON COLUMN core.user_info.employer_address_id IS
    'FK to core.address_info. Customer''s employer office address for pickup coordination. '
    'Derived from employer entity on enrollment; used as default pickup address.';
COMMENT ON COLUMN core.user_info.workplace_group_id IS
    'FK to core.workplace_group. Customer''s coworker group for pickup coordination. '
    'Used to show which coworkers are also ordering on the same day.';
COMMENT ON COLUMN core.user_info.support_email_suppressed_until IS
    'UTC timestamp until which automated support emails are suppressed. '
    'Used by the customer engagement cron to enforce 3-day cooldowns per user.';
COMMENT ON COLUMN core.user_info.last_support_email_date IS
    'UTC timestamp of the last automated support/engagement email sent to this user.';
COMMENT ON COLUMN core.user_info.referral_code IS
    'Unique referral code for sharing with friends (e.g. ''JUANM5X''). '
    'Generated on account creation. Used in /users/me/referral and referral reward flow.';
COMMENT ON COLUMN core.user_info.referred_by_code IS
    'Referral code of the user who referred this user. NULL if not referred. '
    'Stored at signup; triggers reward eligibility check in the referral service.';
COMMENT ON COLUMN core.user_info.is_archived IS
    'Soft-delete tombstone. Archived users cannot log in.';
COMMENT ON COLUMN core.user_info.status IS
    'Lifecycle status (active/inactive). Inactive users are blocked from login.';
COMMENT ON COLUMN core.user_info.created_date IS
    'UTC timestamp when the user account was created.';
COMMENT ON COLUMN core.user_info.created_by IS
    'UUID of the user who created this account. NULL for self-registration.';
COMMENT ON COLUMN core.user_info.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info (self-referential).';
COMMENT ON COLUMN core.user_info.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN core.user_info.market_id IS
    'FK to core.market_info. Primary market for this user — used for B2C restaurant/plan scoping. '
    'Added via deferred ALTER after market_info is created.';
COMMENT ON COLUMN core.user_info.locale IS
    'Preferred UI locale (''en'', ''es'', ''pt''). Defaults to market language on signup. '
    'Drives Accept-Language and enum label resolution.';
COMMENT ON COLUMN core.user_info.city_metadata_id IS
    'FK to core.city_metadata. User''s primary city for plan/restaurant scoping. '
    'Default: Global synthetic city (aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa) for B2B users.';

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
COMMENT ON TABLE core.institution_market IS
    'Junction table assigning institutions to markets. Replaces the former institution_info.market_id '
    'single-market column. An institution can operate in multiple markets. '
    'Entity creation validates that the entity''s address country is in an assigned market.';
COMMENT ON COLUMN core.institution_market.institution_id IS
    'FK to core.institution_info. Part of composite primary key.';
COMMENT ON COLUMN core.institution_market.market_id IS
    'FK to core.market_info. Part of composite primary key.';
COMMENT ON COLUMN core.institution_market.is_primary IS
    'TRUE = this is the institution''s primary market (used for default currency and language). '
    'At most one primary market per institution is recommended.';
COMMENT ON COLUMN core.institution_market.created_date IS
    'UTC timestamp when the institution was assigned to this market.';

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
COMMENT ON TABLE core.user_market_assignment IS
    'Multi-market assignment for internal users (v2). One row per (user, market) pair. '
    'Internal users can be assigned to multiple markets for cross-market admin access. '
    'B2C customers use user_info.market_id (single primary market); this table is for internal.';
COMMENT ON COLUMN core.user_market_assignment.assignment_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.user_market_assignment.user_id IS
    'FK to core.user_info. The user being assigned to the market.';
COMMENT ON COLUMN core.user_market_assignment.market_id IS
    'FK to core.market_info. The market being assigned.';
COMMENT ON COLUMN core.user_market_assignment.is_primary IS
    'TRUE = this is the user''s primary market (default scope for reports and dashboards).';
COMMENT ON COLUMN core.user_market_assignment.created_at IS
    'UTC timestamp when the assignment was created.';

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
COMMENT ON TABLE core.user_messaging_preferences IS
    'Per-user notification and social visibility preferences for the B2C mobile app. '
    'One row per user; auto-created with defaults on first access. '
    'Drives push notification routing and coworker pickup coordination visibility.';
COMMENT ON COLUMN core.user_messaging_preferences.user_id IS
    'PK + FK to core.user_info. One row per user.';
COMMENT ON COLUMN core.user_messaging_preferences.notify_coworker_pickup_alert IS
    'Whether to send push notifications when a coworker offers to pick up the user''s plate.';
COMMENT ON COLUMN core.user_messaging_preferences.notify_plate_readiness_alert IS
    'Whether to send push notifications when the user''s plate is ready for pickup (handed-out state).';
COMMENT ON COLUMN core.user_messaging_preferences.notify_promotions_push IS
    'Whether to send promotional push notifications.';
COMMENT ON COLUMN core.user_messaging_preferences.notify_promotions_email IS
    'Whether to send promotional emails.';
COMMENT ON COLUMN core.user_messaging_preferences.coworkers_can_see_my_orders IS
    'Whether coworkers in the same workplace group can see that the user has an active order. '
    'FALSE = the user is invisible to coworker pickup coordination.';
COMMENT ON COLUMN core.user_messaging_preferences.can_participate_in_plate_pickups IS
    'Whether the user can offer to pick up coworkers'' plates. '
    'FALSE = user is excluded from the coworker pickup offer flow.';
COMMENT ON COLUMN core.user_messaging_preferences.created_date IS
    'UTC timestamp when the preferences row was created.';
COMMENT ON COLUMN core.user_messaging_preferences.modified_date IS
    'UTC timestamp of the most recent preferences update.';

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
COMMENT ON TABLE core.user_fcm_token IS
    'Firebase Cloud Messaging (FCM) device tokens for push notifications. '
    'One row per device token; a user may have multiple tokens (one per device). '
    'Tokens are unique — the UNIQUE constraint prevents duplicate registrations.';
COMMENT ON COLUMN core.user_fcm_token.fcm_token_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.user_fcm_token.user_id IS
    'FK to core.user_info. The user who registered this device token.';
COMMENT ON COLUMN core.user_fcm_token.token IS
    'FCM registration token for the device (up to 500 chars). '
    'Unique — one row per device. Token rotation is handled by DELETE + re-register.';
COMMENT ON COLUMN core.user_fcm_token.platform IS
    'Device platform: ''ios'', ''android'', or ''web''. Used to select the correct FCM notification channel.';
COMMENT ON COLUMN core.user_fcm_token.created_date IS
    'UTC timestamp when the token was first registered.';
COMMENT ON COLUMN core.user_fcm_token.updated_date IS
    'UTC timestamp of the most recent token update (e.g. re-registration on app launch).';

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
COMMENT ON TABLE customer.credential_recovery IS
    'One-time recovery tokens for password reset. Each row is a single-use code '
    'delivered to the user by email; invalidated on use or expiry.';
COMMENT ON COLUMN customer.credential_recovery.credential_recovery_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.credential_recovery.user_id IS
    'FK to core.user_info. The user who requested the password reset.';
COMMENT ON COLUMN customer.credential_recovery.recovery_code IS
    'Random one-time code (up to 10 chars) delivered to the user. '
    'Unique index prevents brute-force code re-use across users.';
COMMENT ON COLUMN customer.credential_recovery.token_expiry IS
    'UTC timestamp after which this code is no longer accepted.';
COMMENT ON COLUMN customer.credential_recovery.is_used IS
    'TRUE once the code has been validated and the password changed.';
COMMENT ON COLUMN customer.credential_recovery.used_date IS
    'UTC timestamp when the code was consumed. NULL if not yet used.';
COMMENT ON COLUMN customer.credential_recovery.status IS
    'Record lifecycle from status_enum (active/inactive). Soft disable without deletion.';
COMMENT ON COLUMN customer.credential_recovery.is_archived IS
    'Soft-delete tombstone. Archived rows are excluded from active recovery lookups.';
COMMENT ON COLUMN customer.credential_recovery.created_date IS
    'UTC timestamp when the recovery request was created.';

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
COMMENT ON TABLE customer.email_change_request IS
    'One-time verification tokens for email address changes. The new email is held '
    'here pending verification; committed to core.user_info on success.';
COMMENT ON COLUMN customer.email_change_request.email_change_request_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.email_change_request.user_id IS
    'FK to core.user_info. The user requesting the email change.';
COMMENT ON COLUMN customer.email_change_request.new_email IS
    'Candidate email address (citext — case-insensitive). Written to user_info.email on verification.';
COMMENT ON COLUMN customer.email_change_request.verification_code IS
    'Random one-time code (up to 10 chars) sent to new_email to prove ownership.';
COMMENT ON COLUMN customer.email_change_request.token_expiry IS
    'UTC timestamp after which this code is no longer accepted.';
COMMENT ON COLUMN customer.email_change_request.is_used IS
    'TRUE once the verification code has been consumed and the email updated.';
COMMENT ON COLUMN customer.email_change_request.used_date IS
    'UTC timestamp when the code was consumed. NULL if not yet used.';
COMMENT ON COLUMN customer.email_change_request.status IS
    'Record lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN customer.email_change_request.is_archived IS
    'Soft-delete tombstone. Archived rows are excluded from active verification lookups.';
COMMENT ON COLUMN customer.email_change_request.created_date IS
    'UTC timestamp when the change request was created.';

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
COMMENT ON TABLE customer.pending_customer_signup IS
    'Staging row for an in-progress customer self-signup. Holds the candidate account data '
    'and a one-time email verification code. Committed to core.user_info on verification; '
    'expires automatically via token_expiry. Never exposed in API responses.';
COMMENT ON COLUMN customer.pending_customer_signup.pending_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.pending_customer_signup.email IS
    'Candidate email (citext — case-insensitive). Unique partial index prevents duplicate pending signups for the same email.';
COMMENT ON COLUMN customer.pending_customer_signup.verification_code IS
    'Random one-time code sent to the email to confirm ownership. Unique — used as lookup key.';
COMMENT ON COLUMN customer.pending_customer_signup.token_expiry IS
    'UTC timestamp after which this pending signup is invalid. Indexed for expiry-sweep queries.';
COMMENT ON COLUMN customer.pending_customer_signup.used IS
    'TRUE once the code has been verified and the user row created. Partial index on (email) WHERE used = FALSE prevents concurrent pending signups.';
COMMENT ON COLUMN customer.pending_customer_signup.created_at IS
    'UTC timestamp when the signup request was submitted.';
COMMENT ON COLUMN customer.pending_customer_signup.username IS
    'Candidate username (citext — case-insensitive). Checked for uniqueness against core.user_info at commit time.';
COMMENT ON COLUMN customer.pending_customer_signup.hashed_password IS
    'bcrypt-hashed password. Stored here temporarily; moved to core.user_info on success.';
COMMENT ON COLUMN customer.pending_customer_signup.first_name IS
    'Candidate first name. Optional at signup; can be filled later in profile.';
COMMENT ON COLUMN customer.pending_customer_signup.last_name IS
    'Candidate last name. Optional at signup; can be filled later in profile.';
COMMENT ON COLUMN customer.pending_customer_signup.mobile_number IS
    'E.164-format phone number (+country digits, 7–15 digits). Optional at signup.';
COMMENT ON COLUMN customer.pending_customer_signup.market_id IS
    'FK to core.market_info. The market (country) the user signed up in; copied to user_info on commit.';
COMMENT ON COLUMN customer.pending_customer_signup.city_metadata_id IS
    'FK to core.city_metadata. The city the user selected at signup; copied to user_info on commit.';
COMMENT ON COLUMN customer.pending_customer_signup.referral_code IS
    'Referrer code supplied at signup time (max 20 chars). Used to credit the referrer after the first qualifying plan purchase.';

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
COMMENT ON TABLE core.geolocation_info IS
    'Geographic coordinates and place metadata for a physical address. '
    'One row per address; coordinates obtained via the Mapbox or Google Maps geocoding gateway. '
    'Used for restaurant map rendering, proximity search, and ad zone matching.';
COMMENT ON COLUMN core.geolocation_info.geolocation_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.geolocation_info.address_id IS
    'FK to core.address_info. The address this geolocation record belongs to.';
COMMENT ON COLUMN core.geolocation_info.latitude IS
    'Geographic latitude in decimal degrees (DOUBLE PRECISION, ~15 significant digits). '
    'Used for map rendering and haversine distance calculations.';
COMMENT ON COLUMN core.geolocation_info.longitude IS
    'Geographic longitude in decimal degrees (DOUBLE PRECISION, ~15 significant digits).';
COMMENT ON COLUMN core.geolocation_info.place_id IS
    'Provider place ID from the geocoding gateway. Mapbox mapbox_id can exceed 255 chars — hence VARCHAR(500). '
    'Used to retrieve full place details on subsequent lookups.';
COMMENT ON COLUMN core.geolocation_info.viewport IS
    'JSONB bounding box returned by the geocoding provider (e.g. {northeast: {lat, lng}, southwest: {lat, lng}}). '
    'Used to set map zoom level on initial render.';
COMMENT ON COLUMN core.geolocation_info.formatted_address_google IS
    'Human-readable formatted address string from the geocoding provider '
    '(e.g. ''Av. Corrientes 1234, Buenos Aires, Argentina''). '
    'Surfaced in API responses as ''formatted_address''; used in QR code views and address pickers.';
COMMENT ON COLUMN core.geolocation_info.is_archived IS
    'Soft-delete tombstone. Archived geolocation records are excluded from active queries.';
COMMENT ON COLUMN core.geolocation_info.status IS
    'Lifecycle status (active/inactive).';
COMMENT ON COLUMN core.geolocation_info.created_date IS
    'UTC timestamp when the geolocation was geocoded. Note: TIMESTAMP (without time zone) — treat as UTC.';
COMMENT ON COLUMN core.geolocation_info.created_by IS
    'UUID of the user who triggered the geocoding. NULL for programmatic creation.';
COMMENT ON COLUMN core.geolocation_info.modified_by IS
    'UUID of the last user to modify this row. FK to core.user_info.';
COMMENT ON COLUMN core.geolocation_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key              VARCHAR(200) NULL,
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

COMMENT ON TABLE ops.institution_entity_info IS
    'Legal/fiscal boundary for a supplier or employer institution in one country. '
    'One row per country the institution operates in. '
    'Owns tax identity, currency, payout config, and email domain for enrollment. '
    'Part of the three-tier cascade: institution_info → institution_entity_info → restaurant_info / employer_benefits_program.';
COMMENT ON COLUMN ops.institution_entity_info.institution_entity_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.institution_entity_info.institution_id IS
    'FK to core.institution_info. The parent institution that owns this legal entity.';
COMMENT ON COLUMN ops.institution_entity_info.address_id IS
    'FK to core.address_info. Registered office address for this legal entity.';
COMMENT ON COLUMN ops.institution_entity_info.currency_metadata_id IS
    'FK to core.currency_metadata. The operating currency for this entity''s market.';
COMMENT ON COLUMN ops.institution_entity_info.tax_id IS
    'Tax identification number (RFC, RUT, NIF, etc.) for the entity''s jurisdiction.';
COMMENT ON COLUMN ops.institution_entity_info.name IS
    'Legal entity name as registered with the tax authority.';
COMMENT ON COLUMN ops.institution_entity_info.payout_provider_account_id IS
    'External account ID at the payout aggregator (e.g. Stripe Connect account ID). NULL until onboarding completes.';
COMMENT ON COLUMN ops.institution_entity_info.payout_aggregator IS
    'Payout provider slug (e.g. ''stripe''). NULL if payout not yet configured.';
COMMENT ON COLUMN ops.institution_entity_info.payout_onboarding_status IS
    'Current payout onboarding state (e.g. ''pending'', ''restricted'', ''complete''). Sourced from the provider webhook.';
COMMENT ON COLUMN ops.institution_entity_info.email_domain IS
    'Domain used for domain-gated employer enrollment (e.g. ''acme.com''). NULL for suppliers. Unique across active entities.';
COMMENT ON COLUMN ops.institution_entity_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture institution entities '
    '(e.g. ''E2E_INSTITUTION_ENTITY_SUPPLIER''). Used by the '
    'PUT /api/v1/institution-entities/by-key upsert endpoint to make Postman seed runs '
    'idempotent. NULL for ad-hoc entities created via the normal POST endpoint.';
COMMENT ON COLUMN ops.institution_entity_info.is_archived IS
    'Soft-delete tombstone. Archived entities are excluded from active payout and enrollment flows.';
COMMENT ON COLUMN ops.institution_entity_info.status IS
    'Lifecycle status (active_enum). Controls visibility in supplier and employer management UIs.';
COMMENT ON COLUMN ops.institution_entity_info.created_date IS
    'UTC timestamp when the entity row was first inserted.';
COMMENT ON COLUMN ops.institution_entity_info.created_by IS
    'FK to core.user_info. NULL if created via migration or seed script.';
COMMENT ON COLUMN ops.institution_entity_info.modified_by IS
    'FK to core.user_info. Last user to update this entity record.';
COMMENT ON COLUMN ops.institution_entity_info.modified_date IS
    'UTC timestamp of the most recent update. Maintained by the application layer.';

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

COMMENT ON TABLE ops.cuisine IS
    'Cuisine taxonomy used to categorise restaurants (e.g. Mexican, Italian, Vegan). '
    'Supports a single level of hierarchy via parent_cuisine_id. '
    'Seeded from a curated list; suppliers may propose additions via ops.cuisine_suggestion.';
COMMENT ON COLUMN ops.cuisine.cuisine_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.cuisine.cuisine_name IS
    'Canonical display name in the market''s primary language.';
COMMENT ON COLUMN ops.cuisine.cuisine_name_i18n IS
    'JSONB map of locale → translated cuisine name (e.g. {"es": "Mexicana", "pt": "Mexicana"}). NULL until translations are provided.';
COMMENT ON COLUMN ops.cuisine.slug IS
    'URL-safe unique identifier derived from cuisine_name. Used in API filters and frontend routing.';
COMMENT ON COLUMN ops.cuisine.parent_cuisine_id IS
    'Self-referencing FK to ops.cuisine. NULL for top-level cuisines. Used for sub-cuisine grouping (e.g. Tacos under Mexican).';
COMMENT ON COLUMN ops.cuisine.description IS
    'Short description of the cuisine style, shown on restaurant detail pages.';
COMMENT ON COLUMN ops.cuisine.origin_source IS
    'Provenance of this cuisine entry: ''seed'' (curated at launch) or ''supplier'' (promoted from a cuisine_suggestion).';
COMMENT ON COLUMN ops.cuisine.display_order IS
    'Optional sort weight for UI ordering. NULL = alphabetical fallback.';
COMMENT ON COLUMN ops.cuisine.is_archived IS
    'Soft-delete tombstone. Archived cuisines are hidden from selection dropdowns.';
COMMENT ON COLUMN ops.cuisine.status IS
    'Lifecycle status (status_enum). Controls visibility in restaurant setup and filtering UIs.';
COMMENT ON COLUMN ops.cuisine.created_date IS
    'UTC timestamp when the cuisine row was first inserted.';
COMMENT ON COLUMN ops.cuisine.created_by IS
    'FK to core.user_info. NULL if created via seed script.';
COMMENT ON COLUMN ops.cuisine.modified_by IS
    'FK to core.user_info. Last user to update this cuisine record.';
COMMENT ON COLUMN ops.cuisine.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key VARCHAR(200) NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

COMMENT ON TABLE ops.restaurant_info IS
    'A restaurant (kitchen) that delivers meals on the platform. '
    'Belongs to an institution_entity_info (legal entity) and a cuisine category. '
    'Owns its address, kitchen hours, image assets, rating aggregates, and PostGIS location point.';
COMMENT ON COLUMN ops.restaurant_info.restaurant_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.restaurant_info.institution_id IS
    'FK to core.institution_info. The supplier institution that operates this restaurant.';
COMMENT ON COLUMN ops.restaurant_info.institution_entity_id IS
    'FK to ops.institution_entity_info. The legal entity (market-level) that owns this restaurant.';
COMMENT ON COLUMN ops.restaurant_info.address_id IS
    'FK to core.address_info. Physical address of the kitchen/pickup location.';
COMMENT ON COLUMN ops.restaurant_info.name IS
    'Display name of the restaurant shown to consumers and in admin UIs.';
COMMENT ON COLUMN ops.restaurant_info.cuisine_id IS
    'FK to ops.cuisine. Primary cuisine category. NULL if not yet assigned.';
COMMENT ON COLUMN ops.restaurant_info.pickup_instructions IS
    'Free-text instructions shown to the consumer at pickup (e.g. "Ring bell on arrival").';
COMMENT ON COLUMN ops.restaurant_info.tagline IS
    'Short marketing tagline shown on restaurant cards. Primary-locale version.';
COMMENT ON COLUMN ops.restaurant_info.tagline_i18n IS
    'JSONB map of locale → translated tagline. NULL until translations are provided.';
COMMENT ON COLUMN ops.restaurant_info.is_featured IS
    'When TRUE, restaurant is boosted in explore listings. Managed by internal admins.';
COMMENT ON COLUMN ops.restaurant_info.cover_image_url IS
    'CDN URL of the restaurant''s cover image. Rendered on restaurant cards and detail pages.';
COMMENT ON COLUMN ops.restaurant_info.average_rating IS
    'Denormalised average star rating computed from plate_review_info. Updated by cron or post-review trigger.';
COMMENT ON COLUMN ops.restaurant_info.review_count IS
    'Denormalised count of approved plate reviews. Updated alongside average_rating.';
COMMENT ON COLUMN ops.restaurant_info.verified_badge IS
    'When TRUE, restaurant has passed quality verification. Shown as a badge on detail pages.';
COMMENT ON COLUMN ops.restaurant_info.spotlight_label IS
    'Short promotional label (e.g. "New", "Popular"). Primary-locale version.';
COMMENT ON COLUMN ops.restaurant_info.spotlight_label_i18n IS
    'JSONB map of locale → translated spotlight label.';
COMMENT ON COLUMN ops.restaurant_info.member_perks IS
    'Array of member perk strings shown on the restaurant detail page. Primary-locale version.';
COMMENT ON COLUMN ops.restaurant_info.member_perks_i18n IS
    'JSONB map of locale → array of translated member perk strings.';
COMMENT ON COLUMN ops.restaurant_info.require_kiosk_code_verification IS
    'When TRUE, the kiosk flow requires a QR/code scan for pickup confirmation.';
COMMENT ON COLUMN ops.restaurant_info.kitchen_open_time IS
    'Wall-clock time when the kitchen starts accepting orders. Interpreted in address_info.timezone. Naive TIME (no zone stored).';
COMMENT ON COLUMN ops.restaurant_info.kitchen_close_time IS
    'Wall-clock time when the kitchen stops accepting orders. Interpreted in address_info.timezone. Naive TIME (no zone stored).';
COMMENT ON COLUMN ops.restaurant_info.location IS
    'PostGIS Point (SRID 4326, WGS84 lon/lat) for geo proximity and bounding-box filtering. NULL until geocoded.';
COMMENT ON COLUMN ops.restaurant_info.is_archived IS
    'Soft-delete tombstone. Archived restaurants are hidden from consumer explore and supplier management.';
COMMENT ON COLUMN ops.restaurant_info.status IS
    'Lifecycle status (status_enum). Controls whether the restaurant is live for ordering.';
COMMENT ON COLUMN ops.restaurant_info.created_date IS
    'UTC timestamp when the restaurant row was first inserted.';
COMMENT ON COLUMN ops.restaurant_info.created_by IS
    'FK to core.user_info. NULL if created via migration or seed script.';
COMMENT ON COLUMN ops.restaurant_info.modified_by IS
    'FK to core.user_info. Last user to update this restaurant record.';
COMMENT ON COLUMN ops.restaurant_info.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN ops.restaurant_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture restaurants '
    '(e.g. ''E2E_RESTAURANT_CAMBALACHE''). Used by the '
    'PUT /api/v1/restaurants/by-key upsert endpoint to make Postman seed runs '
    'idempotent. NULL for ad-hoc restaurants created via the normal POST endpoint.';

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

COMMENT ON TABLE ops.cuisine_suggestion IS
    'Supplier-submitted proposals for new cuisine categories not yet in ops.cuisine. '
    'Workflow: pending → approved (creates/maps a cuisine) or rejected. '
    'Internal admins review; resolved_cuisine_id is set on approval.';
COMMENT ON COLUMN ops.cuisine_suggestion.suggestion_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.cuisine_suggestion.suggested_name IS
    'Name proposed by the supplier for the new cuisine category.';
COMMENT ON COLUMN ops.cuisine_suggestion.suggested_by IS
    'FK to core.user_info. The supplier user who submitted the suggestion.';
COMMENT ON COLUMN ops.cuisine_suggestion.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant on whose behalf the suggestion was submitted. NULL if the restaurant was later deleted.';
COMMENT ON COLUMN ops.cuisine_suggestion.suggestion_status IS
    'Workflow state: ''pending'' awaits review; ''approved'' mapped to a cuisine; ''rejected'' dismissed.';
COMMENT ON COLUMN ops.cuisine_suggestion.reviewed_by IS
    'FK to core.user_info. Internal admin who reviewed the suggestion. NULL until reviewed.';
COMMENT ON COLUMN ops.cuisine_suggestion.reviewed_date IS
    'UTC timestamp when the review decision was recorded.';
COMMENT ON COLUMN ops.cuisine_suggestion.review_notes IS
    'Free-text notes from the reviewer explaining the decision.';
COMMENT ON COLUMN ops.cuisine_suggestion.resolved_cuisine_id IS
    'FK to ops.cuisine. Set on approval to point at the cuisine created or matched for this suggestion.';
COMMENT ON COLUMN ops.cuisine_suggestion.is_archived IS
    'Soft-delete tombstone. Archived suggestions are excluded from the review queue.';
COMMENT ON COLUMN ops.cuisine_suggestion.status IS
    'Lifecycle status (status_enum). Mirrors is_archived for consistency with other ops tables.';
COMMENT ON COLUMN ops.cuisine_suggestion.created_date IS
    'UTC timestamp when the suggestion was submitted.';
COMMENT ON COLUMN ops.cuisine_suggestion.created_by IS
    'FK to core.user_info. Matches suggested_by for supplier-submitted entries; may differ for admin-created stubs.';
COMMENT ON COLUMN ops.cuisine_suggestion.modified_by IS
    'FK to core.user_info. Last user to update this suggestion (typically the reviewer).';
COMMENT ON COLUMN ops.cuisine_suggestion.modified_date IS
    'UTC timestamp of the most recent update.';

\echo 'Creating table: ops.restaurant_lead_cuisine'
CREATE TABLE IF NOT EXISTS ops.restaurant_lead_cuisine (
    restaurant_lead_id UUID NOT NULL REFERENCES ops.restaurant_lead(restaurant_lead_id) ON DELETE CASCADE,
    cuisine_id UUID NOT NULL REFERENCES ops.cuisine(cuisine_id) ON DELETE CASCADE,
    PRIMARY KEY (restaurant_lead_id, cuisine_id)
);
COMMENT ON TABLE ops.restaurant_lead_cuisine IS
    'Junction table linking restaurant leads to their cuisine tags. '
    'A lead can be tagged with multiple cuisines from ops.cuisine. '
    'Cascades deletes from both restaurant_lead and cuisine.';
COMMENT ON COLUMN ops.restaurant_lead_cuisine.restaurant_lead_id IS
    'FK to ops.restaurant_lead. Part of composite primary key.';
COMMENT ON COLUMN ops.restaurant_lead_cuisine.cuisine_id IS
    'FK to ops.cuisine. Part of composite primary key.';

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
    canonical_key VARCHAR(200) NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

COMMENT ON TABLE ops.qr_code IS
    'QR codes generated for restaurant pickup kiosks. '
    'Each QR code encodes a payload used by the kiosk app to identify the restaurant. '
    'One active QR code per restaurant at a time (older codes archived on regeneration).';
COMMENT ON COLUMN ops.qr_code.qr_code_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.qr_code.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant this QR code belongs to.';
COMMENT ON COLUMN ops.qr_code.qr_code_payload IS
    'The string encoded in the QR image (e.g. a signed token or restaurant identifier). Scanned by the kiosk app.';
COMMENT ON COLUMN ops.qr_code.qr_code_image_url IS
    'CDN URL of the rendered QR code image for download or display.';
COMMENT ON COLUMN ops.qr_code.image_storage_path IS
    'Internal storage path of the QR image file (GCS object key or local path).';
COMMENT ON COLUMN ops.qr_code.qr_code_checksum IS
    'SHA-256 (or similar) checksum of the QR image file for integrity verification.';
COMMENT ON COLUMN ops.qr_code.is_archived IS
    'Soft-delete tombstone. Archived QR codes are superseded by a newer code for the same restaurant.';
COMMENT ON COLUMN ops.qr_code.status IS
    'Lifecycle status (status_enum). Only active QR codes are accepted by the kiosk scanner.';
COMMENT ON COLUMN ops.qr_code.created_date IS
    'UTC timestamp when the QR code was generated.';
COMMENT ON COLUMN ops.qr_code.created_by IS
    'FK to core.user_info. NULL if generated by a cron job or migration.';
COMMENT ON COLUMN ops.qr_code.modified_by IS
    'FK to core.user_info. Last user to update this QR code record.';
COMMENT ON COLUMN ops.qr_code.canonical_key IS
    'Optional stable human-readable identifier for idempotent upserts '
    '(e.g. E2E_QR_CAMBALACHE). NULL for ad-hoc QR codes created via '
    'POST /qr-codes. Set by PUT /qr-codes/by-key seed/fixture endpoint.';
COMMENT ON COLUMN ops.qr_code.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key VARCHAR(200) NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

COMMENT ON TABLE ops.product_info IS
    'Supplier-owned meal product (dish) definition. '
    'A product is a reusable recipe; one product can be offered at multiple restaurants as separate plate_info rows. '
    'Holds name, ingredient list, dietary flags, description, and image assets.';
COMMENT ON COLUMN ops.product_info.product_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.product_info.institution_id IS
    'FK to core.institution_info. The supplier institution that owns this product recipe.';
COMMENT ON COLUMN ops.product_info.name IS
    'Display name of the product in the market''s primary language.';
COMMENT ON COLUMN ops.product_info.name_i18n IS
    'JSONB map of locale → translated product name. NULL until translations are provided.';
COMMENT ON COLUMN ops.product_info.ingredients IS
    'Free-text ingredient list in the primary locale. Displayed on the plate detail screen.';
COMMENT ON COLUMN ops.product_info.ingredients_i18n IS
    'JSONB map of locale → translated ingredient list text.';
COMMENT ON COLUMN ops.product_info.description IS
    'Short description of the product shown on explore and plate detail screens.';
COMMENT ON COLUMN ops.product_info.description_i18n IS
    'JSONB map of locale → translated product description.';
COMMENT ON COLUMN ops.product_info.dietary IS
    'Array of dietary attribute slugs (e.g. ''vegan'', ''gluten_free'') for consumer filtering.';
COMMENT ON COLUMN ops.product_info.is_archived IS
    'Soft-delete tombstone. Archived products are hidden from supplier product lists and cannot be linked to new plates.';
COMMENT ON COLUMN ops.product_info.status IS
    'Lifecycle status (status_enum). Controls whether the product is visible in the platform and app.';
COMMENT ON COLUMN ops.product_info.image_storage_path IS
    'Internal storage path of the full-resolution product image.';
COMMENT ON COLUMN ops.product_info.image_checksum IS
    'SHA-256 checksum of the image file for deduplication and integrity verification.';
COMMENT ON COLUMN ops.product_info.image_url IS
    'CDN URL of the full-resolution product image rendered on plate detail screens.';
COMMENT ON COLUMN ops.product_info.image_thumbnail_storage_path IS
    'Internal storage path of the thumbnail image.';
COMMENT ON COLUMN ops.product_info.image_thumbnail_url IS
    'CDN URL of the thumbnail image used on explore cards and lists.';
COMMENT ON COLUMN ops.product_info.created_date IS
    'UTC timestamp when the product was first created.';
COMMENT ON COLUMN ops.product_info.created_by IS
    'FK to core.user_info. NULL if created via migration or seed script.';
COMMENT ON COLUMN ops.product_info.modified_by IS
    'FK to core.user_info. Last user to update this product record.';
COMMENT ON COLUMN ops.product_info.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN ops.product_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture products '
    '(e.g. ''E2E_PRODUCT_BIG_BURGUER''). Used by the '
    'PUT /api/v1/products/by-key upsert endpoint to make Postman seed runs '
    'idempotent. NULL for ad-hoc products created via the normal POST endpoint.';

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
    canonical_key VARCHAR(200) NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES ops.product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

COMMENT ON TABLE ops.plate_info IS
    'A specific offering of a product at a restaurant, with its own pricing and credit cost. '
    'Represents the menu item the consumer sees: one product can be offered as multiple plates '
    'across different restaurants or price tiers. Linked to plate_kitchen_days for scheduling.';
COMMENT ON COLUMN ops.plate_info.plate_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.plate_info.product_id IS
    'FK to ops.product_info. The recipe/product this plate is based on.';
COMMENT ON COLUMN ops.plate_info.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant offering this plate.';
COMMENT ON COLUMN ops.plate_info.price IS
    'Local-currency price charged to subscribers without a benefit plan subsidy (double precision for compatibility with legacy data).';
COMMENT ON COLUMN ops.plate_info.credit IS
    'Credit cost deducted from the subscriber''s subscription balance when this plate is selected.';
COMMENT ON COLUMN ops.plate_info.expected_payout_local_currency IS
    'Expected payout to the supplier in local currency after platform fees. Used in financial reporting.';
COMMENT ON COLUMN ops.plate_info.delivery_time_minutes IS
    'Estimated minutes from order confirmation to plate readiness at the kitchen. Used to set pickup_time_range.';
COMMENT ON COLUMN ops.plate_info.is_archived IS
    'Soft-delete tombstone. Archived plates cannot be selected by subscribers.';
COMMENT ON COLUMN ops.plate_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture plates '
    '(e.g. ''RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA''). Used by the '
    'PUT /api/v1/plates/by-key upsert endpoint to make Postman seed runs '
    'idempotent. NULL for ad-hoc plates created via the normal POST endpoint.';
COMMENT ON COLUMN ops.plate_info.status IS
    'Lifecycle status (status_enum). Controls whether the plate is shown in explore results.';
COMMENT ON COLUMN ops.plate_info.created_date IS
    'UTC timestamp when the plate offering was first created.';
COMMENT ON COLUMN ops.plate_info.created_by IS
    'FK to core.user_info. NULL if created via migration or seed script.';
COMMENT ON COLUMN ops.plate_info.modified_by IS
    'FK to core.user_info. Last user to update this plate record.';
COMMENT ON COLUMN ops.plate_info.modified_date IS
    'UTC timestamp of the most recent update.';

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

COMMENT ON TABLE ops.restaurant_holidays IS
    'Dates on which a restaurant does not operate (public holidays, planned closures). '
    'Supports one-off dates and recurring annual patterns (recurring_month + recurring_day). '
    'Entries with source=''national_sync'' are populated by a cron job from the national_holidays reference table.';
COMMENT ON COLUMN ops.restaurant_holidays.holiday_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.restaurant_holidays.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant that is closed on this date.';
COMMENT ON COLUMN ops.restaurant_holidays.country_code IS
    'ISO 3166-1 alpha-2 country code of the applicable jurisdiction (e.g. ''MX'', ''AR'').';
COMMENT ON COLUMN ops.restaurant_holidays.holiday_date IS
    'The specific calendar date of the closure. For recurring entries, this holds the next or most recent occurrence.';
COMMENT ON COLUMN ops.restaurant_holidays.holiday_name IS
    'Human-readable name of the holiday or closure reason (e.g. "Christmas Day", "Staff Training").';
COMMENT ON COLUMN ops.restaurant_holidays.is_recurring IS
    'When TRUE, the holiday repeats annually on recurring_month / recurring_day.';
COMMENT ON COLUMN ops.restaurant_holidays.recurring_month IS
    'Month (1–12) of the annual recurrence. NULL for one-off closures.';
COMMENT ON COLUMN ops.restaurant_holidays.recurring_day IS
    'Day-of-month (1–31) of the annual recurrence. NULL for one-off closures.';
COMMENT ON COLUMN ops.restaurant_holidays.status IS
    'Lifecycle status (status_enum). Inactive entries are excluded from closure checks.';
COMMENT ON COLUMN ops.restaurant_holidays.is_archived IS
    'Soft-delete tombstone.';
COMMENT ON COLUMN ops.restaurant_holidays.created_date IS
    'UTC timestamp when the holiday entry was created.';
COMMENT ON COLUMN ops.restaurant_holidays.created_by IS
    'FK to core.user_info. NULL if inserted by a cron job.';
COMMENT ON COLUMN ops.restaurant_holidays.modified_by IS
    'FK to core.user_info. Last user (or system account) to update this holiday record.';
COMMENT ON COLUMN ops.restaurant_holidays.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN ops.restaurant_holidays.source IS
    'Provenance: ''manual'' (admin-entered) or ''national_sync'' (populated by national holidays cron).';

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
    canonical_key VARCHAR(200) NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
    -- Uniqueness (plate_id, kitchen_day) enforced only for non-archived rows via partial unique index in index.sql
    -- canonical_key uniqueness enforced via uq_plate_kitchen_days_canonical_key partial index in index.sql
);

COMMENT ON TABLE ops.plate_kitchen_days IS
    'Scheduling rows that map a plate to the kitchen days it is available. '
    'One row per (plate, day) combination. Drives the explore filter ("available today") '
    'and the subscription selection flow that shows which plates can be ordered on a given kitchen_day.';
COMMENT ON COLUMN ops.plate_kitchen_days.plate_kitchen_day_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.plate_kitchen_days.plate_id IS
    'FK to ops.plate_info. The plate this scheduling row belongs to.';
COMMENT ON COLUMN ops.plate_kitchen_days.kitchen_day IS
    'The day of the week (kitchen_day_enum) on which this plate is available. '
    'kitchen_day_enum uses the platform''s operating-day vocabulary (Monday–Friday or market-specific).';
COMMENT ON COLUMN ops.plate_kitchen_days.status IS
    'Lifecycle status (status_enum). Inactive rows are excluded from available-day lookups.';
COMMENT ON COLUMN ops.plate_kitchen_days.is_archived IS
    'Soft-delete tombstone. Archived scheduling rows are ignored by the explore and selection flows.';
COMMENT ON COLUMN ops.plate_kitchen_days.canonical_key IS
    'Optional stable identifier for seed/fixture rows managed by PUT /plate-kitchen-days/by-key. '
    'NULL for ad-hoc rows created by suppliers. When set, must be UPPER_SNAKE_CASE and unique '
    'across all non-NULL rows (enforced by the uq_plate_kitchen_days_canonical_key partial index).';
COMMENT ON COLUMN ops.plate_kitchen_days.created_date IS
    'UTC timestamp when the scheduling row was first inserted.';
COMMENT ON COLUMN ops.plate_kitchen_days.created_by IS
    'FK to core.user_info. NULL if created via migration or seed script.';
COMMENT ON COLUMN ops.plate_kitchen_days.modified_by IS
    'FK to core.user_info. Last user to update this scheduling row.';
COMMENT ON COLUMN ops.plate_kitchen_days.modified_date IS
    'UTC timestamp of the most recent update.';

\echo 'Creating table: audit.plate_kitchen_days_history'
CREATE TABLE IF NOT EXISTS audit.plate_kitchen_days_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_kitchen_day_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    canonical_key VARCHAR(200) NULL,
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
COMMENT ON TABLE customer.plate_selection_info IS
    'A customer meal reservation for a specific plate on a specific kitchen day. '
    'One active row per user per kitchen day (enforced in application logic). '
    'Becomes a plate_pickup_live row when the customer scans the QR code at pickup time.';
COMMENT ON COLUMN customer.plate_selection_info.plate_selection_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.plate_selection_info.user_id IS
    'FK to core.user_info. The customer who made the reservation.';
COMMENT ON COLUMN customer.plate_selection_info.plate_id IS
    'FK to ops.plate_info. The plate edition reserved.';
COMMENT ON COLUMN customer.plate_selection_info.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant serving the plate.';
COMMENT ON COLUMN customer.plate_selection_info.product_id IS
    'FK to ops.product_info. The product (recipe) behind the plate.';
COMMENT ON COLUMN customer.plate_selection_info.qr_code_id IS
    'FK to ops.qr_code. The QR code the user must scan at the restaurant to start pickup.';
COMMENT ON COLUMN customer.plate_selection_info.credit IS
    'Credit cost deducted from the user subscription balance when this reservation is made.';
COMMENT ON COLUMN customer.plate_selection_info.kitchen_day IS
    'Day-of-week the kitchen operates from kitchen_day_enum (e.g. monday, tuesday). '
    'Determines which plate edition is active.';
COMMENT ON COLUMN customer.plate_selection_info.pickup_date IS
    'Calendar date (DATE, no time) of the pickup day. Derived from kitchen_day at reservation time.';
COMMENT ON COLUMN customer.plate_selection_info.pickup_time_range IS
    'Human-readable time window string (e.g. ''11:30-12:00'') for the chosen pickup window.';
COMMENT ON COLUMN customer.plate_selection_info.pickup_intent IS
    'Coworker pickup coordination mode: ''self'' (default), ''offer'' (volunteer to carry), or ''request'' (needs someone to bring it).';
COMMENT ON COLUMN customer.plate_selection_info.flexible_on_time IS
    'Only meaningful when pickup_intent = ''request''. TRUE = user is flexible ±30 min on pickup time.';
COMMENT ON COLUMN customer.plate_selection_info.is_archived IS
    'Soft-delete tombstone. Archived reservations (e.g. cancellations) are excluded from active queries.';
COMMENT ON COLUMN customer.plate_selection_info.status IS
    'Lifecycle state from status_enum (active/inactive).';
COMMENT ON COLUMN customer.plate_selection_info.created_date IS
    'UTC timestamp when the reservation was placed.';
COMMENT ON COLUMN customer.plate_selection_info.created_by IS
    'FK to core.user_info. UUID of the user who created the reservation; NULL for system-created rows.';
COMMENT ON COLUMN customer.plate_selection_info.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.plate_selection_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE customer.coworker_pickup_notification IS
    'Records a push notification sent to a coworker to alert them that a colleague '
    'with pickup_intent=''offer'' is available at their restaurant. One row per (plate_selection, notified_user) pair. '
    'Read-only after insert — no updates needed.';
COMMENT ON COLUMN customer.coworker_pickup_notification.notification_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.coworker_pickup_notification.plate_selection_id IS
    'FK to customer.plate_selection_info. The offering pickup that triggered the notification.';
COMMENT ON COLUMN customer.coworker_pickup_notification.notifier_user_id IS
    'FK to core.user_info. The user with pickup_intent=''offer'' who initiated the alert.';
COMMENT ON COLUMN customer.coworker_pickup_notification.notified_user_id IS
    'FK to core.user_info. The coworker who received the notification.';
COMMENT ON COLUMN customer.coworker_pickup_notification.created_date IS
    'UTC timestamp when the notification was dispatched.';

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
COMMENT ON TABLE customer.notification_banner IS
    'In-app notification banners surfaced to the user while the app is foregrounded. '
    'Max 5 active at once (service layer); deduplication via UNIQUE(user_id, dedup_key). '
    'Frontends poll GET /notifications/active; acknowledge via POST /notifications/{id}/acknowledge.';
COMMENT ON COLUMN customer.notification_banner.notification_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.notification_banner.user_id IS
    'FK to core.user_info (ON DELETE CASCADE). The user this banner is for.';
COMMENT ON COLUMN customer.notification_banner.notification_type IS
    'Banner category from notification_banner_type_enum: survey_available, peer_pickup_volunteer, reservation_reminder.';
COMMENT ON COLUMN customer.notification_banner.priority IS
    'Display priority from notification_banner_priority_enum: normal or high. High-priority banners sort first.';
COMMENT ON COLUMN customer.notification_banner.payload IS
    'JSONB envelope with banner-type-specific data (e.g. plate_name, pickup_window). '
    'Schema is per notification_type; frontends read fields by type.';
COMMENT ON COLUMN customer.notification_banner.action_type IS
    'Slug describing the frontend action to perform when tapped (e.g. open_survey, view_pickup).';
COMMENT ON COLUMN customer.notification_banner.action_label IS
    'Localised call-to-action button label shown on the banner (e.g. ''Rate your plate'').';
COMMENT ON COLUMN customer.notification_banner.client_types IS
    'Array of client identifiers that should display this banner (e.g. {b2c-mobile,b2c-web}). '
    'Backend-owned filter; frontends pass their client type and only receive relevant banners.';
COMMENT ON COLUMN customer.notification_banner.action_status IS
    'Lifecycle state from notification_banner_action_status_enum: active → dismissed/opened/completed/expired.';
COMMENT ON COLUMN customer.notification_banner.expires_at IS
    'UTC timestamp after which the banner is no longer shown (even if action_status = active).';
COMMENT ON COLUMN customer.notification_banner.acknowledged_at IS
    'UTC timestamp when the user acknowledged the banner. NULL while still active.';
COMMENT ON COLUMN customer.notification_banner.dedup_key IS
    'Domain-specific key (e.g. survey:<plate_pickup_id>) that prevents duplicate banners '
    'for the same event via UNIQUE(user_id, dedup_key).';
COMMENT ON COLUMN customer.notification_banner.created_date IS
    'UTC timestamp when the banner was created.';
COMMENT ON COLUMN customer.notification_banner.modified_date IS
    'UTC timestamp of the most recent update (e.g. status change on acknowledgement).';

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
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
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
COMMENT ON TABLE customer.plate_pickup_live IS
    'Live pickup session created when a customer scans the restaurant QR code. '
    'Tracks the full lifecycle: QR scan → arrival → (optional kiosk handoff) → completion. '
    'Used by B2B daily-orders view (restaurant staff) and B2C order history.';
COMMENT ON COLUMN customer.plate_pickup_live.plate_pickup_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.plate_pickup_live.plate_selection_id IS
    'FK to customer.plate_selection_info. The reservation that this pickup fulfils.';
COMMENT ON COLUMN customer.plate_pickup_live.user_id IS
    'FK to core.user_info. The customer picking up.';
COMMENT ON COLUMN customer.plate_pickup_live.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant where pickup occurs.';
COMMENT ON COLUMN customer.plate_pickup_live.plate_id IS
    'FK to ops.plate_info. The plate being picked up.';
COMMENT ON COLUMN customer.plate_pickup_live.product_id IS
    'FK to ops.product_info. The product (recipe) for this pickup.';
COMMENT ON COLUMN customer.plate_pickup_live.qr_code_id IS
    'FK to ops.qr_code. The QR code scanned to create this pickup session.';
COMMENT ON COLUMN customer.plate_pickup_live.qr_code_payload IS
    'Signed URL payload encoded in the QR code image. Surfaced in enriched pickup responses '
    'for the B2C order history screen so the user can re-scan if needed.';
COMMENT ON COLUMN customer.plate_pickup_live.is_archived IS
    'Soft-delete tombstone. Archived pickup records are excluded from active queries.';
COMMENT ON COLUMN customer.plate_pickup_live.status IS
    'Lifecycle state from status_enum (active/inactive).';
COMMENT ON COLUMN customer.plate_pickup_live.was_collected IS
    'TRUE once the pickup is fully completed (plate handed to customer). '
    'Used by order history and no-show detection.';
COMMENT ON COLUMN customer.plate_pickup_live.arrival_time IS
    'UTC timestamp when the customer scanned the QR code (pickup session started). '
    'Used for countdown timer start in the B2C app.';
COMMENT ON COLUMN customer.plate_pickup_live.completion_time IS
    'UTC timestamp when the pickup was completed (was_collected set to TRUE).';
COMMENT ON COLUMN customer.plate_pickup_live.expected_completion_time IS
    'UTC countdown deadline: arrival_time + PICKUP_COUNTDOWN_SECONDS setting. '
    'Surfaced in restaurant daily-orders for staff timer display.';
COMMENT ON COLUMN customer.plate_pickup_live.confirmation_code IS
    '6-digit numeric kiosk code for Layer 2 hand-off verification. '
    'Generated at QR scan; consumed by POST /restaurant-staff/verify-and-handoff.';
COMMENT ON COLUMN customer.plate_pickup_live.completion_type IS
    'How the pickup was closed: user_confirmed, user_disputed, timer_expired, '
    'confirmation_timeout, or kitchen_day_close. Stored for analytics.';
COMMENT ON COLUMN customer.plate_pickup_live.extensions_used IS
    'Number of timer extensions the customer has consumed (max PICKUP_MAX_EXTENSIONS, default 3).';
COMMENT ON COLUMN customer.plate_pickup_live.code_verified IS
    'TRUE once the kiosk confirmation code has been validated by restaurant staff.';
COMMENT ON COLUMN customer.plate_pickup_live.code_verified_time IS
    'UTC timestamp when the kiosk code was verified. NULL if kiosk verification is not used.';
COMMENT ON COLUMN customer.plate_pickup_live.handed_out_time IS
    'UTC timestamp when the plate was physically handed out (Handed Out lifecycle step). '
    'Separates "customer is here" (arrival) from "plate given" (handed_out) from "customer confirms" (completion).';
COMMENT ON COLUMN customer.plate_pickup_live.window_start IS
    'Start of the scheduled pickup window (wall-clock). Set when the pickup session '
    'is created from reservation data. NULL for pickups created before this column '
    'was added, or when no window has been assigned.';
COMMENT ON COLUMN customer.plate_pickup_live.window_end IS
    'End of the scheduled pickup window (wall-clock). Paired with window_start. '
    'NULL for pickups created before this column was added, or when no window has '
    'been assigned.';
COMMENT ON COLUMN customer.plate_pickup_live.created_date IS
    'UTC timestamp when the pickup session was created (QR scan moment).';
COMMENT ON COLUMN customer.plate_pickup_live.created_by IS
    'FK to core.user_info. UUID of the user who created the session; NULL for system-created rows.';
COMMENT ON COLUMN customer.plate_pickup_live.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.plate_pickup_live.modified_date IS
    'UTC timestamp of the most recent update.';

\echo 'Creating table: audit.plate_pickup_live_history'
CREATE TABLE IF NOT EXISTS audit.plate_pickup_live_history (
    event_id                 UUID        PRIMARY KEY DEFAULT uuidv7(),
    plate_pickup_id          UUID        NOT NULL,
    plate_selection_id       UUID        NOT NULL,
    user_id                  UUID        NOT NULL,
    restaurant_id            UUID        NOT NULL,
    plate_id                 UUID        NOT NULL,
    product_id               UUID        NOT NULL,
    qr_code_id               UUID        NOT NULL,
    qr_code_payload          VARCHAR(255) NOT NULL,
    is_archived              BOOLEAN     NOT NULL DEFAULT FALSE,
    status                   status_enum NOT NULL DEFAULT 'active'::status_enum,
    was_collected            BOOLEAN     DEFAULT FALSE,
    arrival_time             TIMESTAMPTZ,
    completion_time          TIMESTAMPTZ,
    expected_completion_time TIMESTAMPTZ,
    confirmation_code        VARCHAR(10),
    completion_type          VARCHAR(20),
    extensions_used          INTEGER     DEFAULT 0,
    code_verified            BOOLEAN     DEFAULT FALSE,
    code_verified_time       TIMESTAMPTZ,
    handed_out_time          TIMESTAMPTZ,
    window_start             TIMESTAMPTZ,
    window_end               TIMESTAMPTZ,
    created_date             TIMESTAMPTZ NOT NULL,
    created_by               UUID        NULL,
    modified_by              UUID        NOT NULL,
    modified_date            TIMESTAMPTZ NOT NULL,
    is_current               BOOLEAN     NOT NULL DEFAULT TRUE,
    valid_until              TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plate_pickup_id)
        REFERENCES customer.plate_pickup_live(plate_pickup_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by)
        REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_pickup_live_history_pickup
    ON audit.plate_pickup_live_history(plate_pickup_id)
    WHERE is_current = TRUE;

COMMENT ON TABLE audit.plate_pickup_live_history IS
    'Trigger-managed history mirror of customer.plate_pickup_live. Never written by application code.';
COMMENT ON COLUMN audit.plate_pickup_live_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.plate_pickup_live_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.plate_pickup_live_history.valid_until IS
    'UTC timestamp until which this row was current. ''infinity'' for the current row.';
COMMENT ON COLUMN audit.plate_pickup_live_history.window_start IS
    'Mirror of customer.plate_pickup_live.window_start.';
COMMENT ON COLUMN audit.plate_pickup_live_history.window_end IS
    'Mirror of customer.plate_pickup_live.window_end.';

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
COMMENT ON TABLE customer.plate_review_info IS
    'Post-pickup ratings submitted by customers. One review per plate_pickup_live row; '
    'immutable after creation. Aggregated into ops.plate_info.average_rating and review_count '
    'for the explore feed. Supplier-facing enriched view (GET /plate-reviews/by-institution/enriched) '
    'strips customer PII.';
COMMENT ON COLUMN customer.plate_review_info.plate_review_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.plate_review_info.user_id IS
    'FK to core.user_info. The customer who submitted the review.';
COMMENT ON COLUMN customer.plate_review_info.plate_id IS
    'FK to ops.plate_info. The plate edition being reviewed. Indexed for aggregate queries.';
COMMENT ON COLUMN customer.plate_review_info.plate_pickup_id IS
    'FK to customer.plate_pickup_live. The completed pickup that this review covers. One-to-one.';
COMMENT ON COLUMN customer.plate_review_info.stars_rating IS
    'Overall star rating 1–5 (CHECK enforced). Aggregated into plate average_rating.';
COMMENT ON COLUMN customer.plate_review_info.portion_size_rating IS
    'Portion size rating 1–3 (1=too small, 2=just right, 3=too much). CHECK enforced.';
COMMENT ON COLUMN customer.plate_review_info.would_order_again IS
    'Optional boolean: would the customer order this plate again? NULL = not answered.';
COMMENT ON COLUMN customer.plate_review_info.comment IS
    'Optional free-text feedback for the restaurant (max 500 chars). '
    'Visible to restaurant via enriched review endpoint; NOT shown in B2C app.';
COMMENT ON COLUMN customer.plate_review_info.is_archived IS
    'Soft-delete tombstone. Archived reviews are excluded from aggregate calculations.';
COMMENT ON COLUMN customer.plate_review_info.created_date IS
    'UTC timestamp when the review was submitted.';
COMMENT ON COLUMN customer.plate_review_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE customer.portion_complaint IS
    'Customer complaint filed when a plate_review_info.portion_size_rating = 1 (too small). '
    'Optional photo stored in GCS customer bucket; resolution managed by Internal ops.';
COMMENT ON COLUMN customer.portion_complaint.complaint_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.portion_complaint.plate_pickup_id IS
    'FK to customer.plate_pickup_live. The pickup the complaint is about.';
COMMENT ON COLUMN customer.portion_complaint.plate_review_id IS
    'FK to customer.plate_review_info. The associated review (nullable — complaint can exist without a review row in edge cases).';
COMMENT ON COLUMN customer.portion_complaint.user_id IS
    'FK to core.user_info. The customer who filed the complaint.';
COMMENT ON COLUMN customer.portion_complaint.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant responsible for the portion.';
COMMENT ON COLUMN customer.portion_complaint.photo_storage_path IS
    'GCS object path for the complaint photo (e.g. customers/{user_id}/complaints/{complaint_id}/photo.jpg). '
    'NULL if no photo was attached. Surfaced in PortionComplaintResponseSchema.';
COMMENT ON COLUMN customer.portion_complaint.complaint_text IS
    'Optional free-text description of the portion issue (max 1000 chars).';
COMMENT ON COLUMN customer.portion_complaint.resolution_status IS
    'Internal resolution state: open (default), investigating, resolved, dismissed. '
    'Managed by Internal ops; not configurable via a typed enum to allow future values.';
COMMENT ON COLUMN customer.portion_complaint.created_date IS
    'UTC timestamp when the complaint was filed.';
COMMENT ON COLUMN customer.portion_complaint.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE customer.user_favorite_info IS
    'Customer-saved favourites. Polymorphic junction: entity_type determines whether '
    'entity_id is a plate or restaurant. UNIQUE(user_id, entity_type, entity_id) prevents duplicate favourites.';
COMMENT ON COLUMN customer.user_favorite_info.favorite_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.user_favorite_info.user_id IS
    'FK to core.user_info (ON DELETE CASCADE). The customer who saved the favourite.';
COMMENT ON COLUMN customer.user_favorite_info.entity_type IS
    'Polymorphic type discriminator from favorite_entity_type_enum: plate or restaurant.';
COMMENT ON COLUMN customer.user_favorite_info.entity_id IS
    'UUID of the favourited entity. Resolves to ops.plate_info or ops.restaurant_info depending on entity_type. '
    'No FK constraint (polymorphic); application layer enforces referential integrity.';
COMMENT ON COLUMN customer.user_favorite_info.created_date IS
    'UTC timestamp when the favourite was saved.';

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
COMMENT ON TABLE customer.pickup_preferences IS
    'Coworker pickup coordination preferences per plate_selection_info row. '
    'Records whether the user wants to carry a coworker''s plate (offer) or needs one carried (request), '
    'and whether they were matched with another user. Never exposed directly in API responses; '
    'used internally by the matching service and surfaced as pickup_type in daily-orders.';
COMMENT ON COLUMN customer.pickup_preferences.preference_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.pickup_preferences.plate_selection_id IS
    'FK to customer.plate_selection_info. The reservation this preference belongs to.';
COMMENT ON COLUMN customer.pickup_preferences.user_id IS
    'FK to core.user_info. The user expressing this pickup preference.';
COMMENT ON COLUMN customer.pickup_preferences.pickup_type IS
    'Coordination role from pickup_type_enum: offer (will carry for coworker) or request (needs someone to carry).';
COMMENT ON COLUMN customer.pickup_preferences.target_pickup_time IS
    'UTC timestamp of the preferred pickup time for matching. NULL when flexible.';
COMMENT ON COLUMN customer.pickup_preferences.time_window_minutes IS
    'Tolerance window in minutes around target_pickup_time (default ±30 min) for matching.';
COMMENT ON COLUMN customer.pickup_preferences.is_matched IS
    'TRUE once the matching service has paired this preference with another user.';
COMMENT ON COLUMN customer.pickup_preferences.matched_with_preference_id IS
    'FK to customer.pickup_preferences (self-referential). The paired counterpart preference. '
    'NULL until matched; ON DELETE SET NULL to gracefully handle cancellations.';
COMMENT ON COLUMN customer.pickup_preferences.is_archived IS
    'Soft-delete tombstone. Archived preferences are excluded from active matching.';
COMMENT ON COLUMN customer.pickup_preferences.status IS
    'Record lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN customer.pickup_preferences.created_date IS
    'UTC timestamp when the preference was created.';
COMMENT ON COLUMN customer.pickup_preferences.created_by IS
    'FK to core.user_info. UUID of the user who created this preference; NULL for system rows.';
COMMENT ON COLUMN customer.pickup_preferences.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.pickup_preferences.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key VARCHAR(200) NULL,
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
COMMENT ON TABLE customer.plan_info IS
    'Subscription plan catalogue. Each plan belongs to one market (country) and defines the '
    'credit grant, price, rollover rules, and localised marketing copy. '
    'Cannot be assigned to the Global (XG) pseudo-market — enforced by CHECK constraint.';
COMMENT ON COLUMN customer.plan_info.plan_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.plan_info.market_id IS
    'FK to core.market_info. The market (country) this plan is sold in. '
    'Global market (UUID ending …0001) is excluded by CHECK constraint.';
COMMENT ON COLUMN customer.plan_info.name IS
    'Default (fallback) plan name. Localised alternatives in name_i18n.';
COMMENT ON COLUMN customer.plan_info.name_i18n IS
    'JSONB locale map {en: ''...'', es: ''...'', pt: ''...''}. Backend resolves the correct locale at response time.';
COMMENT ON COLUMN customer.plan_info.marketing_description IS
    'Default marketing description shown on the plan selection screen. Localised in marketing_description_i18n.';
COMMENT ON COLUMN customer.plan_info.marketing_description_i18n IS
    'JSONB locale map for marketing_description.';
COMMENT ON COLUMN customer.plan_info.features IS
    'Default array of feature bullet points. Localised in features_i18n.';
COMMENT ON COLUMN customer.plan_info.features_i18n IS
    'JSONB locale map {en: [...], es: [...]} for features.';
COMMENT ON COLUMN customer.plan_info.cta_label IS
    'Default call-to-action button label (e.g. ''Subscribe''). Localised in cta_label_i18n.';
COMMENT ON COLUMN customer.plan_info.cta_label_i18n IS
    'JSONB locale map for cta_label.';
COMMENT ON COLUMN customer.plan_info.credit IS
    'Number of meal credits granted per subscription renewal.';
COMMENT ON COLUMN customer.plan_info.price IS
    'Plan price in the market local currency (DOUBLE PRECISION). Used with credit_cost_* for display.';
COMMENT ON COLUMN customer.plan_info.highlighted IS
    'TRUE when this plan is visually featured/recommended in the plan selection UI.';
COMMENT ON COLUMN customer.plan_info.credit_cost_local_currency IS
    'Cost per credit in local currency (price ÷ credit). Pre-computed for display; '
    'derived from price and credit but stored to avoid per-request division.';
COMMENT ON COLUMN customer.plan_info.credit_cost_usd IS
    'Cost per credit converted to USD. Pre-computed using currency_conversion_usd at plan-edit time.';
COMMENT ON COLUMN customer.plan_info.rollover IS
    'TRUE (default) if unused credits carry over to the next period. FALSE = credits expire on renewal.';
COMMENT ON COLUMN customer.plan_info.rollover_cap IS
    'Maximum credits that can roll over (NULL = no cap). Only meaningful when rollover = TRUE.';
COMMENT ON COLUMN customer.plan_info.canonical_key IS
    'Optional stable human-readable identifier for seed/fixture plans '
    '(e.g. ''MARKET_AR_PLAN_STANDARD_50000_ARS''). Used by the '
    'PUT /api/v1/plans/by-key upsert endpoint to make Postman seed runs '
    'idempotent. NULL for ad-hoc plans created via the normal POST endpoint. '
    'Unique when not null (enforced by partial index uq_plan_info_canonical_key).';
COMMENT ON COLUMN customer.plan_info.is_archived IS
    'Soft-delete tombstone. Archived plans are hidden from plan selection but retained for subscription history.';
COMMENT ON COLUMN customer.plan_info.status IS
    'Lifecycle state from status_enum (active/inactive). Inactive plans are not offered to new subscribers.';
COMMENT ON COLUMN customer.plan_info.created_date IS
    'UTC timestamp when the plan was created.';
COMMENT ON COLUMN customer.plan_info.created_by IS
    'FK to core.user_info. UUID of the admin who created the plan; NULL for system-seeded plans.';
COMMENT ON COLUMN customer.plan_info.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.plan_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
    canonical_key VARCHAR(200) NULL,
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
COMMENT ON TABLE billing.discretionary_info IS
    'Manual credit or debit adjustments issued by admins. Each row is either a Client-side '
    'adjustment (user_id set, restaurant_id NULL) or a Supplier-side adjustment '
    '(restaurant_id set, user_id NULL). Backed by discretionary_resolution_info for approval.';
COMMENT ON COLUMN billing.discretionary_info.discretionary_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.discretionary_info.user_id IS
    'FK to core.user_info. Set for Client-side adjustments; NULL for Supplier-side.';
COMMENT ON COLUMN billing.discretionary_info.restaurant_id IS
    'FK to ops.restaurant_info. Set for Supplier-side adjustments; NULL for Client-side.';
COMMENT ON COLUMN billing.discretionary_info.approval_id IS
    'FK to billing.discretionary_resolution_info. Populated once an admin approves or rejects.';
COMMENT ON COLUMN billing.discretionary_info.category IS
    'Adjustment classification from discretionary_reason_enum (e.g. marketing_campaign, credit_refund).';
COMMENT ON COLUMN billing.discretionary_info.reason IS
    'Free-form admin-entered explanation for the adjustment.';
COMMENT ON COLUMN billing.discretionary_info.amount IS
    'Monetary amount of the adjustment in market currency. Positive = credit, negative = debit.';
COMMENT ON COLUMN billing.discretionary_info.comment IS
    'Optional additional notes from the approving admin.';
COMMENT ON COLUMN billing.discretionary_info.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.discretionary_info.status IS
    'Approval workflow state from discretionary_status_enum (pending / approved / rejected).';
COMMENT ON COLUMN billing.discretionary_info.created_date IS
    'UTC timestamp when the adjustment was created.';
COMMENT ON COLUMN billing.discretionary_info.created_by IS
    'FK to core.user_info. Admin who submitted the adjustment; NULL for system-generated rows.';
COMMENT ON COLUMN billing.discretionary_info.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN billing.discretionary_info.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';

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
COMMENT ON TABLE billing.discretionary_resolution_info IS
    'Admin approval decisions for billing.discretionary_info requests. One row per resolution event.';
COMMENT ON COLUMN billing.discretionary_resolution_info.approval_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.discretionary_resolution_info.discretionary_id IS
    'FK to billing.discretionary_info. The adjustment being resolved.';
COMMENT ON COLUMN billing.discretionary_resolution_info.resolution IS
    'Outcome from discretionary_status_enum (approved / rejected / pending).';
COMMENT ON COLUMN billing.discretionary_resolution_info.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.discretionary_resolution_info.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.discretionary_resolution_info.resolved_by IS
    'FK to core.user_info. Admin who made the approval decision.';
COMMENT ON COLUMN billing.discretionary_resolution_info.resolved_date IS
    'UTC timestamp when the resolution was recorded.';
COMMENT ON COLUMN billing.discretionary_resolution_info.created_date IS
    'UTC timestamp when this resolution row was created.';
COMMENT ON COLUMN billing.discretionary_resolution_info.resolution_comment IS
    'Optional free-form note from the resolving admin.';

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
COMMENT ON TABLE billing.client_transaction IS
    'Ledger of credit movements for individual users (consumers). Source of wallet balance for '
    'client-facing billing. Not exposed directly in API responses; balance is derived.';
COMMENT ON COLUMN billing.client_transaction.transaction_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.client_transaction.user_id IS
    'FK to core.user_info. The consumer whose balance this transaction affects.';
COMMENT ON COLUMN billing.client_transaction.source IS
    'Originating event type (e.g. ''plate_selection'', ''discretionary_promotion'', ''referral_program'').';
COMMENT ON COLUMN billing.client_transaction.plate_selection_id IS
    'FK to customer.plate_selection_info. Populated when source = ''plate_selection''; NULL otherwise.';
COMMENT ON COLUMN billing.client_transaction.discretionary_id IS
    'FK to billing.discretionary_info. Populated when source = ''discretionary''; NULL otherwise.';
COMMENT ON COLUMN billing.client_transaction.credit IS
    'Amount credited (positive) or debited (negative) to the user wallet in market currency.';
COMMENT ON COLUMN billing.client_transaction.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.client_transaction.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.client_transaction.created_date IS
    'UTC timestamp when the transaction was recorded.';
COMMENT ON COLUMN billing.client_transaction.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';
COMMENT ON COLUMN billing.client_transaction.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.client_transaction.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE customer.referral_config IS
    'Per-market referral programme configuration. At most one active config per market '
    '(unique partial index on market_id WHERE is_archived = FALSE). '
    'Managed by Internal admins; read by the referral service when rewarding referrers.';
COMMENT ON COLUMN customer.referral_config.referral_config_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.referral_config.market_id IS
    'FK to core.market_info. The market this configuration applies to.';
COMMENT ON COLUMN customer.referral_config.is_enabled IS
    'Master toggle for the referral programme in this market. FALSE = referral codes generate no rewards.';
COMMENT ON COLUMN customer.referral_config.referrer_bonus_rate IS
    'Percentage of the referee''s first qualifying plan price awarded to the referrer (1–100). Default 15.';
COMMENT ON COLUMN customer.referral_config.referrer_bonus_cap IS
    'Maximum bonus credits a referrer can earn per single referral (NULL = uncapped).';
COMMENT ON COLUMN customer.referral_config.referrer_monthly_cap IS
    'Maximum number of successful referrals a single referrer can be rewarded in a calendar month (NULL = uncapped). Default 5.';
COMMENT ON COLUMN customer.referral_config.min_plan_price_to_qualify IS
    'Minimum plan price (local currency) the referee must pay for the referral to qualify. Default 0.';
COMMENT ON COLUMN customer.referral_config.cooldown_days IS
    'Minimum days that must elapse between two referrals from the same referrer. Default 0 (no cooldown).';
COMMENT ON COLUMN customer.referral_config.held_reward_expiry_hours IS
    'Hours after qualifying that the reward remains in ''held'' state before auto-releasing. Default 48.';
COMMENT ON COLUMN customer.referral_config.pending_expiry_days IS
    'Days after referral creation that a pending referral expires if never qualified. Default 90.';
COMMENT ON COLUMN customer.referral_config.is_archived IS
    'Soft-delete tombstone. Archived configs are excluded from active referral processing.';
COMMENT ON COLUMN customer.referral_config.status IS
    'Record lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN customer.referral_config.created_date IS
    'UTC timestamp when the config was created.';
COMMENT ON COLUMN customer.referral_config.created_by IS
    'FK to core.user_info. UUID of the admin who created the config; NULL for seeded rows.';
COMMENT ON COLUMN customer.referral_config.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.referral_config.modified_date IS
    'UTC timestamp of the most recent update.';

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
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referrer_user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (referee_user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_referral_info_referrer ON customer.referral_info(referrer_user_id);
CREATE INDEX IF NOT EXISTS idx_referral_info_referee ON customer.referral_info(referee_user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_info_referee_unique ON customer.referral_info(referee_user_id) WHERE referral_status NOT IN ('cancelled');
COMMENT ON TABLE customer.referral_info IS
    'Records a referral event: one referrer brought one referee to the platform. '
    'Lifecycle: pending → qualified (referee paid qualifying plan) → rewarded (bonus issued) '
    'or expired / cancelled. One non-cancelled referral per referee enforced by unique partial index.';
COMMENT ON COLUMN customer.referral_info.referral_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.referral_info.referrer_user_id IS
    'FK to core.user_info. The user whose referral code was used (earns the bonus).';
COMMENT ON COLUMN customer.referral_info.referee_user_id IS
    'FK to core.user_info. The new user who signed up with the referral code.';
COMMENT ON COLUMN customer.referral_info.referral_code_used IS
    'The referral code string as used at signup (matches core.user_info.referral_code of the referrer).';
COMMENT ON COLUMN customer.referral_info.market_id IS
    'FK to core.market_info. The market in which the referral occurred.';
COMMENT ON COLUMN customer.referral_info.referral_status IS
    'Lifecycle state from referral_status_enum: pending, qualified, rewarded, expired, cancelled.';
COMMENT ON COLUMN customer.referral_info.bonus_credits_awarded IS
    'Credits actually awarded to the referrer. NULL until status = rewarded.';
COMMENT ON COLUMN customer.referral_info.bonus_plan_price IS
    'The referee''s qualifying plan price (local currency) used to compute the bonus. NULL until qualified.';
COMMENT ON COLUMN customer.referral_info.bonus_rate_applied IS
    'The referrer_bonus_rate (%) from referral_config that was in effect at reward time. NULL until rewarded.';
COMMENT ON COLUMN customer.referral_info.qualified_date IS
    'UTC timestamp when the referral transitioned to qualified. NULL if not yet qualified.';
COMMENT ON COLUMN customer.referral_info.rewarded_date IS
    'UTC timestamp when the bonus was credited to the referrer. NULL if not yet rewarded.';
COMMENT ON COLUMN customer.referral_info.reward_held_until IS
    'UTC timestamp until which the reward is on hold (held_reward_expiry_hours from config). '
    'NULL once released or if no hold applies.';
COMMENT ON COLUMN customer.referral_info.expired_date IS
    'UTC timestamp when the referral expired (pending_expiry_days exceeded). NULL if not expired.';
COMMENT ON COLUMN customer.referral_info.cancelled_date IS
    'UTC timestamp when the referral was manually cancelled. NULL if not cancelled.';
COMMENT ON COLUMN customer.referral_info.is_archived IS
    'Soft-delete tombstone. Archived rows are excluded from active referral queries.';
COMMENT ON COLUMN customer.referral_info.status IS
    'Record lifecycle from status_enum (active/inactive). Distinct from referral_status.';
COMMENT ON COLUMN customer.referral_info.created_date IS
    'UTC timestamp when the referral was recorded (at signup).';
COMMENT ON COLUMN customer.referral_info.created_by IS
    'FK to core.user_info. UUID of the user who triggered the creation; NULL for system rows.';
COMMENT ON COLUMN customer.referral_info.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.referral_info.modified_date IS
    'UTC timestamp of the most recent update.';

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

\echo 'Creating table: customer.referral_transaction'
CREATE TABLE IF NOT EXISTS customer.referral_transaction (
    referral_transaction_id UUID PRIMARY KEY DEFAULT uuidv7(),
    referral_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referral_id) REFERENCES customer.referral_info(referral_id) ON DELETE RESTRICT,
    FOREIGN KEY (transaction_id) REFERENCES billing.client_transaction(transaction_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    CONSTRAINT uq_referral_transaction_referral_id UNIQUE (referral_id)
);
CREATE INDEX IF NOT EXISTS idx_referral_transaction_referral_id ON customer.referral_transaction(referral_id);
CREATE INDEX IF NOT EXISTS idx_referral_transaction_transaction_id ON customer.referral_transaction(transaction_id);
COMMENT ON TABLE customer.referral_transaction IS
    'Bridge table linking a referral reward to its credit transaction. '
    'Replaces the former direct FKs on customer.referral_info.transaction_id and '
    'billing.client_transaction.referral_id that formed a circular dependency. '
    'One row per rewarded referral (UNIQUE on referral_id).';
COMMENT ON COLUMN customer.referral_transaction.referral_transaction_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.referral_transaction.referral_id IS
    'FK to customer.referral_info. The referral that was rewarded.';
COMMENT ON COLUMN customer.referral_transaction.transaction_id IS
    'FK to billing.client_transaction. The credit transaction created for this reward.';
COMMENT ON COLUMN customer.referral_transaction.is_archived IS
    'Soft-delete tombstone.';
COMMENT ON COLUMN customer.referral_transaction.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN customer.referral_transaction.created_date IS
    'UTC timestamp when the bridge row was created.';
COMMENT ON COLUMN customer.referral_transaction.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';
COMMENT ON COLUMN customer.referral_transaction.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN customer.referral_transaction.modified_date IS
    'UTC timestamp of the most recent update.';

\echo 'Creating table: audit.referral_transaction_history'
CREATE TABLE IF NOT EXISTS audit.referral_transaction_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    referral_transaction_id UUID NOT NULL,
    referral_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (referral_transaction_id) REFERENCES customer.referral_transaction(referral_transaction_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.referral_transaction_history IS
    'Trigger-managed history mirror of customer.referral_transaction. Never written by application code.';
COMMENT ON COLUMN audit.referral_transaction_history.event_id IS
    'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.referral_transaction_history.is_current IS
    'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.referral_transaction_history.valid_until IS
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
COMMENT ON TABLE customer.referral_code_assignment IS
    'Transient table that binds a referral code to a device fingerprint before the user signs up. '
    'Written when the user taps a referral deep link (POST /referrals/assign-code). '
    'Consumed at signup and marked used; entries expire after 48 hours (enforced in application code, not a DB column).';
COMMENT ON COLUMN customer.referral_code_assignment.assignment_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.referral_code_assignment.device_id IS
    'Device fingerprint (max 255 chars) identifying the pre-auth user. '
    'Unique partial index on (device_id) WHERE used = FALSE ensures one active assignment per device.';
COMMENT ON COLUMN customer.referral_code_assignment.referral_code IS
    'The referral code (max 20 chars) associated with this device.';
COMMENT ON COLUMN customer.referral_code_assignment.used IS
    'TRUE once the code has been consumed at signup and copied into pending_customer_signup.referral_code.';
COMMENT ON COLUMN customer.referral_code_assignment.created_at IS
    'UTC timestamp when the assignment was created. Used for the 48-hour expiry check at signup.';

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
COMMENT ON TABLE customer.subscription_info IS
    'Active and historical meal subscriptions. One non-archived subscription per user per market '
    '(unique partial index). Holds the credit balance, renewal date, and hold/pause state. '
    'Audit-trailed via audit.subscription_history.';
COMMENT ON COLUMN customer.subscription_info.subscription_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.subscription_info.user_id IS
    'FK to core.user_info. The subscriber.';
COMMENT ON COLUMN customer.subscription_info.market_id IS
    'FK to core.market_info. The market (country) this subscription is for. '
    'Unique partial index (user_id, market_id) WHERE is_archived = FALSE prevents duplicate active subscriptions.';
COMMENT ON COLUMN customer.subscription_info.plan_id IS
    'FK to customer.plan_info. The plan the user is subscribed to.';
COMMENT ON COLUMN customer.subscription_info.renewal_date IS
    'UTC timestamp of the next scheduled renewal. Default: now + 30 days. '
    'Updated by the renewal cron after each successful charge.';
COMMENT ON COLUMN customer.subscription_info.balance IS
    'Current meal credit balance. Decremented by plate_selection_info.credit on reservation; '
    'topped up on renewal. Can temporarily go negative during order processing.';
COMMENT ON COLUMN customer.subscription_info.subscription_status IS
    'Operational lifecycle: active, on_hold, pending, cancelled. '
    'Distinct from the status_enum column (kept for backward compatibility).';
COMMENT ON COLUMN customer.subscription_info.hold_start_date IS
    'UTC timestamp when the subscription was paused (PUT /subscriptions/{id}/hold). '
    'NULL when not on hold.';
COMMENT ON COLUMN customer.subscription_info.hold_end_date IS
    'UTC timestamp when the hold expires and the subscription resumes. '
    'NULL = indefinite hold. Max 3 months from hold_start_date (application-enforced).';
COMMENT ON COLUMN customer.subscription_info.early_renewal_threshold IS
    'Credit balance floor that triggers early renewal (integer >= 1). '
    'NULL = period-end only (no early renewal). '
    'Updated via PATCH /subscriptions/me/renewal-preferences.';
COMMENT ON COLUMN customer.subscription_info.is_archived IS
    'Soft-delete tombstone. Archived subscriptions are excluded from the active-subscription unique index.';
COMMENT ON COLUMN customer.subscription_info.status IS
    'Record lifecycle from status_enum (active/inactive). Retained for backward compatibility; '
    'subscription_status is the authoritative operational state.';
COMMENT ON COLUMN customer.subscription_info.created_date IS
    'UTC timestamp when the subscription was first created.';
COMMENT ON COLUMN customer.subscription_info.created_by IS
    'FK to core.user_info. UUID of the user who created the subscription; NULL for system-created rows.';
COMMENT ON COLUMN customer.subscription_info.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.subscription_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
    -- Phase 1 new columns: FK to billing.payment_attempt (nullable until Phase 2)
    payment_attempt_id UUID NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    -- Legacy columns kept for Phase 1 compatibility; will be dropped in Phase 2
    payment_provider VARCHAR(50) NOT NULL DEFAULT 'stripe',
    external_payment_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES customer.subscription_info(subscription_id) ON DELETE RESTRICT
    -- FK to billing.payment_attempt added after that table is created (deferred below)
);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_subscription_id ON customer.subscription_payment(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_external_id ON customer.subscription_payment(external_payment_id);
COMMENT ON TABLE customer.subscription_payment IS
    'Immutable payment event record created when a subscription charge is initiated. '
    'One row per payment attempt; duplicates avoided by external_payment_id uniqueness at the provider. '
    'Used to populate billing.client_bill_info and for payment confirmation webhooks.';
COMMENT ON COLUMN customer.subscription_payment.subscription_payment_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.subscription_payment.subscription_id IS
    'FK to customer.subscription_info. The subscription being paid for.';
COMMENT ON COLUMN customer.subscription_payment.payment_provider IS
    'Payment provider identifier (e.g. ''stripe''). Extensible for future providers.';
COMMENT ON COLUMN customer.subscription_payment.external_payment_id IS
    'Provider-assigned payment identifier (e.g. Stripe PaymentIntent ID). '
    'Indexed for webhook lookup by external ID.';
COMMENT ON COLUMN customer.subscription_payment.status IS
    'Payment state: pending, succeeded, failed. Updated by webhook handler.';
COMMENT ON COLUMN customer.subscription_payment.amount_cents IS
    'Charge amount in the smallest currency unit (e.g. cents for USD/ARS). '
    'Surfaced in SubscriptionWithPaymentResponseSchema.amount_cents.';
COMMENT ON COLUMN customer.subscription_payment.currency IS
    'ISO 4217 currency code for this charge (e.g. ARS, USD). '
    'Surfaced in SubscriptionWithPaymentResponseSchema.currency.';
COMMENT ON COLUMN customer.subscription_payment.created_at IS
    'UTC timestamp when the payment record was created.';
COMMENT ON COLUMN customer.subscription_payment.payment_attempt_id IS
    'FK to billing.payment_attempt. NULL until the first attempt is linked. '
    'Phase 1: nullable. Phase 2: NOT NULL after cron + webhook are refactored.';
COMMENT ON COLUMN customer.subscription_payment.attempt_number IS
    'Attempt counter (1-based). 1 for the initial attempt; increments on retry.';

\echo 'Creating table: billing.payment_attempt'
CREATE TABLE IF NOT EXISTS billing.payment_attempt (
    payment_attempt_id      UUID PRIMARY KEY DEFAULT uuidv7(),
    provider                payment_provider_enum NOT NULL,
    provider_payment_id     TEXT NULL,
    idempotency_key         TEXT NULL,
    amount_cents            INTEGER NOT NULL,
    currency                CHAR(3) NOT NULL,
    payment_status          payment_attempt_status_enum NOT NULL DEFAULT 'pending',
    provider_status         TEXT NULL,
    failure_reason          TEXT NULL,
    provider_fee_cents      INTEGER NULL,
    is_archived             BOOLEAN NOT NULL DEFAULT FALSE,
    status                  status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID NULL,
    modified_by             UUID NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_payment_attempt_provider_payment_id
    ON billing.payment_attempt(provider_payment_id)
    WHERE provider_payment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payment_attempt_payment_status
    ON billing.payment_attempt(payment_status);
COMMENT ON TABLE billing.payment_attempt IS
    'Financial record for a single payment attempt. Provider-specific: one row per attempt '
    'regardless of provider (Stripe, Mercado Pago, etc.). Written by webhook handlers. '
    'Linked to customer.subscription_payment via payment_attempt_id FK.';
COMMENT ON COLUMN billing.payment_attempt.payment_attempt_id IS 'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.payment_attempt.provider IS 'Payment provider that processed this attempt.';
COMMENT ON COLUMN billing.payment_attempt.provider_payment_id IS 'Provider-assigned ID (e.g. Stripe pi_…). Indexed for webhook lookup.';
COMMENT ON COLUMN billing.payment_attempt.idempotency_key IS 'Idempotency key sent to the provider to prevent duplicate charges.';
COMMENT ON COLUMN billing.payment_attempt.amount_cents IS 'Charge amount in smallest currency unit.';
COMMENT ON COLUMN billing.payment_attempt.currency IS 'ISO 4217 3-letter currency code.';
COMMENT ON COLUMN billing.payment_attempt.payment_status IS 'Financial state of this attempt.';
COMMENT ON COLUMN billing.payment_attempt.provider_status IS 'Raw status string from the provider (debug/fidelity).';
COMMENT ON COLUMN billing.payment_attempt.failure_reason IS 'Human-readable failure reason from the provider, if failed.';
COMMENT ON COLUMN billing.payment_attempt.provider_fee_cents IS 'Provider transaction fee in smallest currency unit, if known.';
COMMENT ON COLUMN billing.payment_attempt.status IS 'Admin/audit lifecycle status (active/inactive). Separate from payment_status.';

\echo 'Creating table: audit.payment_attempt_history'
CREATE TABLE IF NOT EXISTS audit.payment_attempt_history (
    event_id                UUID PRIMARY KEY DEFAULT uuidv7(),
    payment_attempt_id      UUID NOT NULL,
    provider                payment_provider_enum NOT NULL,
    provider_payment_id     TEXT NULL,
    idempotency_key         TEXT NULL,
    amount_cents            INTEGER NOT NULL,
    currency                CHAR(3) NOT NULL,
    payment_status          payment_attempt_status_enum NOT NULL,
    provider_status         TEXT NULL,
    failure_reason          TEXT NULL,
    provider_fee_cents      INTEGER NULL,
    is_archived             BOOLEAN NOT NULL,
    status                  status_enum NOT NULL,
    created_date            TIMESTAMPTZ NOT NULL,
    created_by              UUID NULL,
    modified_by             UUID NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL,
    is_current              BOOLEAN,
    valid_until             TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (payment_attempt_id) REFERENCES billing.payment_attempt(payment_attempt_id) ON DELETE RESTRICT
);
COMMENT ON TABLE audit.payment_attempt_history IS
    'Trigger-managed history mirror of billing.payment_attempt. Never written by application code.';
COMMENT ON COLUMN audit.payment_attempt_history.event_id IS 'UUIDv7 primary key for this history row. Time-ordered.';
COMMENT ON COLUMN audit.payment_attempt_history.is_current IS 'TRUE while this row represents the current state of the source row. Set to FALSE when a newer history row is inserted.';
COMMENT ON COLUMN audit.payment_attempt_history.valid_until IS 'UTC timestamp until which this row was current. ''infinity'' for the current row.';

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
COMMENT ON TABLE customer.payment_method IS
    'Aggregator record linking a user to a specific payment method. '
    'method_type determines the provider (Stripe, Mercado Pago, etc.); '
    'provider-specific detail lives in customer.external_payment_method. '
    'The is_default flag marks the preferred payment method for automatic charges.';
COMMENT ON COLUMN customer.payment_method.payment_method_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.payment_method.user_id IS
    'FK to core.user_info. The customer who owns this payment method.';
COMMENT ON COLUMN customer.payment_method.method_type IS
    'Provider slug (max 50 chars) from PaymentMethodProvider enum: stripe, mercado_pago, payu. '
    'Determines which external table holds the provider detail.';
COMMENT ON COLUMN customer.payment_method.method_type_id IS
    'Optional UUID linking to a provider-specific sub-record. NULL for simple card-only flows.';
COMMENT ON COLUMN customer.payment_method.address_id IS
    'FK to core.address_info. Billing address associated with this payment method. '
    'NULL if no billing address was captured.';
COMMENT ON COLUMN customer.payment_method.is_archived IS
    'Soft-delete tombstone. Archived payment methods are excluded from active payment flows.';
COMMENT ON COLUMN customer.payment_method.status IS
    'Lifecycle state from status_enum (active/inactive/pending).';
COMMENT ON COLUMN customer.payment_method.is_default IS
    'TRUE for the user''s preferred card. At most one default per user (application-enforced). '
    'Surfaced in PaymentMethodResponseSchema and CustomerPaymentMethodItemSchema.';
COMMENT ON COLUMN customer.payment_method.created_date IS
    'UTC timestamp when the payment method was added.';
COMMENT ON COLUMN customer.payment_method.created_by IS
    'FK to core.user_info. UUID of the user who added this method; NULL for system rows.';
COMMENT ON COLUMN customer.payment_method.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.payment_method.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE customer.external_payment_method IS
    'Provider-specific details for a customer payment method. One-to-one with customer.payment_method '
    '(UNIQUE on payment_method_id). Holds the masked card display fields (last4, brand) and '
    'the opaque provider identifier used for charging.';
COMMENT ON COLUMN customer.external_payment_method.external_payment_method_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN customer.external_payment_method.payment_method_id IS
    'FK to customer.payment_method (UNIQUE). The aggregator record this detail belongs to.';
COMMENT ON COLUMN customer.external_payment_method.provider IS
    'Payment provider slug (e.g. ''stripe''). Paired with external_id for uniqueness across providers.';
COMMENT ON COLUMN customer.external_payment_method.external_id IS
    'Provider-assigned payment method identifier (e.g. Stripe pm_xxx). '
    'UNIQUE(provider, external_id) prevents duplicate records.';
COMMENT ON COLUMN customer.external_payment_method.last4 IS
    'Last 4 digits of the card number. Surfaced in CustomerPaymentMethodItemSchema.last4 and '
    'PaymentMethodEnrichedResponseSchema.last4 for display purposes.';
COMMENT ON COLUMN customer.external_payment_method.brand IS
    'Card network brand (e.g. ''visa'', ''mastercard''). Surfaced alongside last4 for display.';
COMMENT ON COLUMN customer.external_payment_method.provider_customer_id IS
    'Provider-side customer identifier (e.g. Stripe cus_xxx). '
    'Intentionally omitted from all API responses — internal system field only.';
COMMENT ON COLUMN customer.external_payment_method.created_at IS
    'UTC timestamp when this provider detail was first recorded.';
COMMENT ON COLUMN customer.external_payment_method.updated_at IS
    'UTC timestamp of the most recent update (e.g. card expiry refresh from webhook).';

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
COMMENT ON TABLE customer.user_payment_provider IS
    'Links a user to their payment provider account (e.g. Stripe Customer object). '
    'One active account per (user, provider) pair — unique partial index WHERE is_archived = FALSE. '
    'provider_customer_id is intentionally omitted from all API responses.';
COMMENT ON COLUMN customer.user_payment_provider.user_payment_provider_id IS
    'UUIDv7 primary key. Time-ordered. Surfaced in UserPaymentProviderResponseSchema.';
COMMENT ON COLUMN customer.user_payment_provider.user_id IS
    'FK to core.user_info. The customer who owns this provider account.';
COMMENT ON COLUMN customer.user_payment_provider.provider IS
    'Payment provider slug (e.g. ''stripe''). Part of the unique active-account constraint.';
COMMENT ON COLUMN customer.user_payment_provider.provider_customer_id IS
    'Provider-side customer identifier (e.g. Stripe cus_xxx). '
    'Internal system field — never returned in API responses. '
    'UNIQUE(provider, provider_customer_id) WHERE is_archived = FALSE prevents one user sharing another''s provider account.';
COMMENT ON COLUMN customer.user_payment_provider.is_archived IS
    'Soft-delete tombstone. Archived records are excluded from uniqueness checks.';
COMMENT ON COLUMN customer.user_payment_provider.status IS
    'Record lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN customer.user_payment_provider.created_date IS
    'UTC timestamp when the provider account was linked. Surfaced in UserPaymentProviderResponseSchema.created_date.';
COMMENT ON COLUMN customer.user_payment_provider.created_by IS
    'FK to core.user_info. UUID of the user who linked the provider; NULL for system rows.';
COMMENT ON COLUMN customer.user_payment_provider.modified_by IS
    'FK to core.user_info. UUID of the last user to write this row.';
COMMENT ON COLUMN customer.user_payment_provider.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.client_bill_info IS
    'One bill per subscription payment cycle for a consumer. Links a subscription payment event '
    'to the plan, user, and currency at the time of billing.';
COMMENT ON COLUMN billing.client_bill_info.client_bill_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.client_bill_info.subscription_payment_id IS
    'FK to customer.subscription_payment. The payment event that generated this bill.';
COMMENT ON COLUMN billing.client_bill_info.subscription_id IS
    'FK to customer.subscription_info. The active subscription at billing time.';
COMMENT ON COLUMN billing.client_bill_info.user_id IS
    'FK to core.user_info. The consumer being billed.';
COMMENT ON COLUMN billing.client_bill_info.plan_id IS
    'FK to customer.plan_info. The plan the consumer was on at billing time.';
COMMENT ON COLUMN billing.client_bill_info.currency_metadata_id IS
    'FK to core.currency_metadata. Currency in effect at billing time.';
COMMENT ON COLUMN billing.client_bill_info.amount IS
    'Total billed amount in market currency.';
COMMENT ON COLUMN billing.client_bill_info.currency_code IS
    'ISO 4217 currency code denormalized at write time.';
COMMENT ON COLUMN billing.client_bill_info.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.client_bill_info.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.client_bill_info.created_date IS
    'UTC timestamp when the bill was created.';
COMMENT ON COLUMN billing.client_bill_info.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';
COMMENT ON COLUMN billing.client_bill_info.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.client_bill_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.restaurant_transaction IS
    'Ledger of per-order financial events for supplier restaurants. Each row represents one '
    'order, discretionary credit, or other event that contributes to the restaurant balance. '
    'Consumed by the settlement pipeline to compute payouts.';
COMMENT ON COLUMN billing.restaurant_transaction.transaction_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.restaurant_transaction.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant whose balance this event affects.';
COMMENT ON COLUMN billing.restaurant_transaction.plate_selection_id IS
    'FK to customer.plate_selection_info. The order that generated this transaction; NULL for non-order events.';
COMMENT ON COLUMN billing.restaurant_transaction.discretionary_id IS
    'FK to billing.discretionary_info. The discretionary adjustment; NULL for order-based events.';
COMMENT ON COLUMN billing.restaurant_transaction.currency_metadata_id IS
    'FK to core.currency_metadata. Currency in effect at transaction time.';
COMMENT ON COLUMN billing.restaurant_transaction.was_collected IS
    'TRUE once the transaction has been included in a settlement run.';
COMMENT ON COLUMN billing.restaurant_transaction.ordered_timestamp IS
    'UTC timestamp when the order was placed.';
COMMENT ON COLUMN billing.restaurant_transaction.collected_timestamp IS
    'UTC timestamp when the transaction was swept into a settlement; NULL until collected.';
COMMENT ON COLUMN billing.restaurant_transaction.arrival_time IS
    'UTC timestamp when the diner arrived at the restaurant.';
COMMENT ON COLUMN billing.restaurant_transaction.completion_time IS
    'UTC timestamp when the order was marked complete.';
COMMENT ON COLUMN billing.restaurant_transaction.expected_completion_time IS
    'UTC timestamp of the expected order completion (kitchen prep deadline).';
COMMENT ON COLUMN billing.restaurant_transaction.transaction_type IS
    'Classification from transaction_type_enum (e.g. order, no_show, discretionary).';
COMMENT ON COLUMN billing.restaurant_transaction.credit IS
    'Base amount credited to the restaurant before discounts, in market currency.';
COMMENT ON COLUMN billing.restaurant_transaction.no_show_discount IS
    'Amount deducted for a no-show event; NULL for non-no-show transactions.';
COMMENT ON COLUMN billing.restaurant_transaction.currency_code IS
    'ISO 4217 currency code denormalized at write time.';
COMMENT ON COLUMN billing.restaurant_transaction.final_amount IS
    'Net amount after any discounts (credit minus no_show_discount).';
COMMENT ON COLUMN billing.restaurant_transaction.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.restaurant_transaction.status IS
    'Row lifecycle from status_enum (active/inactive/pending).';
COMMENT ON COLUMN billing.restaurant_transaction.created_date IS
    'UTC timestamp when the transaction was recorded.';
COMMENT ON COLUMN billing.restaurant_transaction.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';
COMMENT ON COLUMN billing.restaurant_transaction.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.restaurant_transaction.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.restaurant_balance_info IS
    'Running balance for each supplier restaurant. One row per restaurant (PK = restaurant_id). '
    'Updated atomically with each transaction. Zeroed out when the settlement pipeline runs.';
COMMENT ON COLUMN billing.restaurant_balance_info.restaurant_id IS
    'PK and FK to ops.restaurant_info. One balance row per restaurant.';
COMMENT ON COLUMN billing.restaurant_balance_info.currency_metadata_id IS
    'FK to core.currency_metadata. Currency of the balance.';
COMMENT ON COLUMN billing.restaurant_balance_info.transaction_count IS
    'Number of unsettled transactions included in the current balance.';
COMMENT ON COLUMN billing.restaurant_balance_info.balance IS
    'Current outstanding balance in market currency. Reset to zero after each settlement run.';
COMMENT ON COLUMN billing.restaurant_balance_info.currency_code IS
    'ISO 4217 currency code denormalized at write time.';
COMMENT ON COLUMN billing.restaurant_balance_info.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.restaurant_balance_info.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.restaurant_balance_info.created_date IS
    'UTC timestamp when this balance row was first created.';
COMMENT ON COLUMN billing.restaurant_balance_info.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';
COMMENT ON COLUMN billing.restaurant_balance_info.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.restaurant_balance_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.institution_bill_info IS
    'Periodic bill issued to a supplier institution for a given billing period. Aggregates '
    'settled restaurant transactions for one institution_entity across a period. '
    'The resolution field tracks whether the bill has been invoiced and paid.';
COMMENT ON COLUMN billing.institution_bill_info.institution_bill_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.institution_bill_info.institution_id IS
    'FK to core.institution_info. The institution being billed.';
COMMENT ON COLUMN billing.institution_bill_info.institution_entity_id IS
    'FK to ops.institution_entity_info. The legal entity within the institution (per-country).';
COMMENT ON COLUMN billing.institution_bill_info.currency_metadata_id IS
    'FK to core.currency_metadata. Currency in effect for this bill.';
COMMENT ON COLUMN billing.institution_bill_info.transaction_count IS
    'Number of restaurant transactions included in this bill.';
COMMENT ON COLUMN billing.institution_bill_info.amount IS
    'Total billed amount in market currency.';
COMMENT ON COLUMN billing.institution_bill_info.currency_code IS
    'ISO 4217 currency code denormalized at write time.';
COMMENT ON COLUMN billing.institution_bill_info.period_start IS
    'UTC start of the billing period (inclusive).';
COMMENT ON COLUMN billing.institution_bill_info.period_end IS
    'UTC end of the billing period (inclusive).';
COMMENT ON COLUMN billing.institution_bill_info.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.institution_bill_info.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.institution_bill_info.resolution IS
    'Payment resolution state from bill_resolution_enum (pending / invoiced / paid / cancelled).';
COMMENT ON COLUMN billing.institution_bill_info.tax_doc_external_id IS
    'External tax document identifier (e.g. AFIP/SUNAT document number) once the invoice is issued.';
COMMENT ON COLUMN billing.institution_bill_info.created_date IS
    'UTC timestamp when the bill was created by the billing pipeline.';
COMMENT ON COLUMN billing.institution_bill_info.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for pipeline-generated rows.';
COMMENT ON COLUMN billing.institution_bill_info.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.institution_bill_info.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.institution_bill_payout IS
    'Tracks payout transfers from Vianda to supplier institutions. Each row is one transfer '
    'attempt via an external payment provider (e.g. Stripe). Idempotency key prevents double-pays.';
COMMENT ON COLUMN billing.institution_bill_payout.bill_payout_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.institution_bill_payout.institution_bill_id IS
    'FK to billing.institution_bill_info. The bill being paid.';
COMMENT ON COLUMN billing.institution_bill_payout.provider IS
    'Payment provider identifier (e.g. ''stripe'').';
COMMENT ON COLUMN billing.institution_bill_payout.provider_transfer_id IS
    'External transfer reference from the payment provider (e.g. Stripe transfer ID). NULL until the provider confirms.';
COMMENT ON COLUMN billing.institution_bill_payout.amount IS
    'Amount transferred in the bill''s currency.';
COMMENT ON COLUMN billing.institution_bill_payout.currency_code IS
    'ISO 4217 currency code for the transfer.';
COMMENT ON COLUMN billing.institution_bill_payout.status IS
    'Transfer state from bill_payout_status_enum (pending / succeeded / failed).';
COMMENT ON COLUMN billing.institution_bill_payout.idempotency_key IS
    'Unique key passed to the payment provider to prevent duplicate transfers.';
COMMENT ON COLUMN billing.institution_bill_payout.created_at IS
    'UTC timestamp when this payout row was created.';
COMMENT ON COLUMN billing.institution_bill_payout.completed_at IS
    'UTC timestamp when the provider confirmed the transfer; NULL until resolved.';
COMMENT ON COLUMN billing.institution_bill_payout.modified_by IS
    'FK to core.user_info. Admin who last updated this row; NULL for system-initiated rows.';

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
COMMENT ON TABLE billing.market_payout_aggregator IS
    'Market-level payout configuration used by the billing pipeline. One row per market. '
    'Controls the payout provider, invoice requirements, max unmatched bill age, and the '
    'default kitchen-hours window that supplier restaurant records inherit at create time.';
COMMENT ON COLUMN billing.market_payout_aggregator.market_id IS
    'PK and FK to core.market_info. One configuration row per market.';
COMMENT ON COLUMN billing.market_payout_aggregator.aggregator IS
    'Payment aggregator identifier for this market (e.g. ''stripe'').';
COMMENT ON COLUMN billing.market_payout_aggregator.is_active IS
    'TRUE when payout processing is enabled for this market.';
COMMENT ON COLUMN billing.market_payout_aggregator.require_invoice IS
    'Market-level default: TRUE = supplier must submit an invoice before payout is released. '
    'Can be overridden per supplier via billing.supplier_terms.require_invoice.';
COMMENT ON COLUMN billing.market_payout_aggregator.max_unmatched_bill_days IS
    'Maximum days a bill may remain unmatched to an invoice before automatic follow-up is triggered.';
COMMENT ON COLUMN billing.market_payout_aggregator.kitchen_open_time IS
    'Default kitchen open time (wall-clock, naive) used when creating new supplier restaurant records.';
COMMENT ON COLUMN billing.market_payout_aggregator.kitchen_close_time IS
    'Default kitchen close time (wall-clock, naive) used when creating new supplier restaurant records.';
COMMENT ON COLUMN billing.market_payout_aggregator.notes IS
    'Free-form admin notes about this market''s payout configuration.';
COMMENT ON COLUMN billing.market_payout_aggregator.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.market_payout_aggregator.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.market_payout_aggregator.created_date IS
    'UTC timestamp when this configuration row was created.';
COMMENT ON COLUMN billing.market_payout_aggregator.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.market_payout_aggregator.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.institution_settlement IS
    'Per-restaurant payout computation for one kitchen day within a billing run. '
    'Multiple settlement rows roll up into one billing.institution_bill_info per entity. '
    'References audit.restaurant_balance_history (balance_event_id) to anchor the balance '
    'snapshot used at settlement time. Not exposed in any API response; used by billing pipeline only.';
COMMENT ON COLUMN billing.institution_settlement.settlement_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.institution_settlement.institution_entity_id IS
    'FK to ops.institution_entity_info. The legal entity to which this settlement is credited.';
COMMENT ON COLUMN billing.institution_settlement.restaurant_id IS
    'FK to ops.restaurant_info. The restaurant whose earnings are settled.';
COMMENT ON COLUMN billing.institution_settlement.period_start IS
    'UTC start of the settlement period (inclusive).';
COMMENT ON COLUMN billing.institution_settlement.period_end IS
    'UTC end of the settlement period (inclusive).';
COMMENT ON COLUMN billing.institution_settlement.kitchen_day IS
    'The calendar date (YYYY-MM-DD as string) this settlement covers, in market local time.';
COMMENT ON COLUMN billing.institution_settlement.amount IS
    'Total payout amount for this restaurant for this kitchen day, in market currency.';
COMMENT ON COLUMN billing.institution_settlement.currency_code IS
    'ISO 4217 currency code denormalized at write time.';
COMMENT ON COLUMN billing.institution_settlement.currency_metadata_id IS
    'FK to core.currency_metadata. Currency configuration at settlement time.';
COMMENT ON COLUMN billing.institution_settlement.transaction_count IS
    'Number of finalized transactions included in this settlement row.';
COMMENT ON COLUMN billing.institution_settlement.balance_event_id IS
    'FK to audit.restaurant_balance_history.event_id. Links to the balance snapshot computed '
    'immediately before this settlement zeroed out the balance.';
COMMENT ON COLUMN billing.institution_settlement.settlement_number IS
    'Human-readable settlement reference code (e.g. ''SET-20240101-001'') for admin reporting.';
COMMENT ON COLUMN billing.institution_settlement.settlement_run_id IS
    'UUID grouping all settlement rows created in the same billing cron run. Useful for debugging.';
COMMENT ON COLUMN billing.institution_settlement.institution_bill_id IS
    'FK to billing.institution_bill_info. Set once this settlement is rolled up into a bill.';
COMMENT ON COLUMN billing.institution_settlement.country_code IS
    'ISO 3166-1 alpha-2 country code of the restaurant''s entity. Denormalized for reporting.';
COMMENT ON COLUMN billing.institution_settlement.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.institution_settlement.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.institution_settlement.created_at IS
    'UTC timestamp when the settlement record was created by the billing pipeline.';
COMMENT ON COLUMN billing.institution_settlement.created_by IS
    'FK to core.user_info. UUID of the actor who created this row; NULL for pipeline-generated rows.';
COMMENT ON COLUMN billing.institution_settlement.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.institution_settlement.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.supplier_invoice IS
    'Supplier-submitted invoices for payout compliance. Each invoice covers a period of work '
    'by one institution entity. Country-specific details are stored in extension tables '
    '(supplier_invoice_ar, supplier_invoice_pe, supplier_invoice_us). '
    'document_storage_path holds the internal GCS path; API responses expose a signed URL instead.';
COMMENT ON COLUMN billing.supplier_invoice.supplier_invoice_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.supplier_invoice.institution_entity_id IS
    'FK to ops.institution_entity_info. The legal entity that submitted this invoice.';
COMMENT ON COLUMN billing.supplier_invoice.country_code IS
    'ISO 3166-1 alpha-2 country code. Determines which extension table holds compliance details.';
COMMENT ON COLUMN billing.supplier_invoice.invoice_type IS
    'Invoice classification from supplier_invoice_type_enum (e.g. standard, credit_note).';
COMMENT ON COLUMN billing.supplier_invoice.external_invoice_number IS
    'Supplier-assigned invoice number from their internal system; NULL if not provided.';
COMMENT ON COLUMN billing.supplier_invoice.issued_date IS
    'Calendar date the supplier issued the invoice, in local time.';
COMMENT ON COLUMN billing.supplier_invoice.amount IS
    'Total invoice amount in the invoice currency (12 digits, 2 decimal places).';
COMMENT ON COLUMN billing.supplier_invoice.currency_code IS
    'ISO 4217 currency code of the invoice.';
COMMENT ON COLUMN billing.supplier_invoice.tax_amount IS
    'Tax component of the invoice amount; NULL if not applicable.';
COMMENT ON COLUMN billing.supplier_invoice.tax_rate IS
    'Applicable tax rate as a percentage (e.g. 21.00 for 21%); NULL if not applicable.';
COMMENT ON COLUMN billing.supplier_invoice.document_storage_path IS
    'Internal GCS object path for the uploaded invoice file. '
    'API responses expose a time-limited signed URL (document_url) instead of this path.';
COMMENT ON COLUMN billing.supplier_invoice.document_format IS
    'File format of the uploaded document (e.g. ''pdf'', ''xml'').';
COMMENT ON COLUMN billing.supplier_invoice.status IS
    'Review state from supplier_invoice_status_enum (pending_review / approved / rejected).';
COMMENT ON COLUMN billing.supplier_invoice.rejection_reason IS
    'Admin-entered reason if status = rejected; NULL otherwise.';
COMMENT ON COLUMN billing.supplier_invoice.reviewed_by IS
    'FK to core.user_info. Admin who completed the review; NULL until reviewed.';
COMMENT ON COLUMN billing.supplier_invoice.reviewed_at IS
    'UTC timestamp when the review decision was recorded; NULL until reviewed.';
COMMENT ON COLUMN billing.supplier_invoice.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.supplier_invoice.created_date IS
    'UTC timestamp when the invoice was submitted.';
COMMENT ON COLUMN billing.supplier_invoice.created_by IS
    'FK to core.user_info. Actor who submitted this invoice; NULL for system-generated rows.';
COMMENT ON COLUMN billing.supplier_invoice.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.supplier_invoice.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.bill_invoice_match IS
    'Many-to-many join between institution bills and supplier invoices. Records which invoice '
    'covers (part of) which bill, enabling partial matching across periods.';
COMMENT ON COLUMN billing.bill_invoice_match.match_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.bill_invoice_match.institution_bill_id IS
    'FK to billing.institution_bill_info. The bill being matched.';
COMMENT ON COLUMN billing.bill_invoice_match.supplier_invoice_id IS
    'FK to billing.supplier_invoice. The invoice covering part of the bill.';
COMMENT ON COLUMN billing.bill_invoice_match.matched_amount IS
    'Amount of the invoice applied to this bill (partial matches allowed).';
COMMENT ON COLUMN billing.bill_invoice_match.matched_by IS
    'FK to core.user_info. Admin who recorded the match.';
COMMENT ON COLUMN billing.bill_invoice_match.matched_at IS
    'UTC timestamp when the match was recorded.';

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
COMMENT ON TABLE billing.supplier_invoice_ar IS
    'Argentina-specific compliance extension for billing.supplier_invoice. '
    'Holds AFIP CAE fields required for electronic invoicing (factura electrónica). '
    'One row per Argentina supplier invoice.';
COMMENT ON COLUMN billing.supplier_invoice_ar.supplier_invoice_id IS
    'PK and FK to billing.supplier_invoice. Shares the parent row''s UUIDv7.';
COMMENT ON COLUMN billing.supplier_invoice_ar.cae_code IS
    'AFIP-issued Código de Autorización Electrónica (CAE) for this invoice.';
COMMENT ON COLUMN billing.supplier_invoice_ar.cae_expiry_date IS
    'Expiry date of the CAE code issued by AFIP.';
COMMENT ON COLUMN billing.supplier_invoice_ar.afip_point_of_sale IS
    'AFIP point-of-sale number (punto de venta) used to issue this invoice.';
COMMENT ON COLUMN billing.supplier_invoice_ar.supplier_cuit IS
    'CUIT (tax ID) of the supplier issuing the invoice.';
COMMENT ON COLUMN billing.supplier_invoice_ar.recipient_cuit IS
    'CUIT of the recipient (Vianda entity); NULL if not required.';
COMMENT ON COLUMN billing.supplier_invoice_ar.afip_document_type IS
    'AFIP document type code (e.g. ''01'' for Factura A); NULL if not applicable.';

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
COMMENT ON TABLE billing.supplier_invoice_pe IS
    'Peru-specific compliance extension for billing.supplier_invoice. '
    'Holds SUNAT fields required for electronic invoicing (comprobante electrónico). '
    'One row per Peru supplier invoice.';
COMMENT ON COLUMN billing.supplier_invoice_pe.supplier_invoice_id IS
    'PK and FK to billing.supplier_invoice. Shares the parent row''s UUIDv7.';
COMMENT ON COLUMN billing.supplier_invoice_pe.sunat_serie IS
    'SUNAT series identifier (e.g. ''F001'') for the electronic receipt.';
COMMENT ON COLUMN billing.supplier_invoice_pe.sunat_correlativo IS
    'SUNAT sequential correlative number within the series.';
COMMENT ON COLUMN billing.supplier_invoice_pe.cdr_status IS
    'Constancia de Recepción status returned by SUNAT (e.g. ''accepted'', ''rejected''); NULL until CDR received.';
COMMENT ON COLUMN billing.supplier_invoice_pe.cdr_received_at IS
    'UTC timestamp when the SUNAT CDR response was received; NULL until processed. '
    'Not exposed in API responses.';
COMMENT ON COLUMN billing.supplier_invoice_pe.supplier_ruc IS
    'RUC (tax ID) of the supplier issuing the invoice.';
COMMENT ON COLUMN billing.supplier_invoice_pe.recipient_ruc IS
    'RUC of the recipient (Vianda entity); NULL if not required.';

\echo 'Creating table: billing.supplier_invoice_us'
CREATE TABLE IF NOT EXISTS billing.supplier_invoice_us (
    supplier_invoice_id     UUID        PRIMARY KEY,
    tax_year                SMALLINT    NOT NULL,
    FOREIGN KEY (supplier_invoice_id) REFERENCES billing.supplier_invoice(supplier_invoice_id) ON DELETE RESTRICT
);
COMMENT ON TABLE billing.supplier_invoice_us IS
    'United States-specific compliance extension for billing.supplier_invoice. '
    'Holds the IRS tax year for 1099-NEC reporting. One row per US supplier invoice.';
COMMENT ON COLUMN billing.supplier_invoice_us.supplier_invoice_id IS
    'PK and FK to billing.supplier_invoice. Shares the parent row''s UUIDv7.';
COMMENT ON COLUMN billing.supplier_invoice_us.tax_year IS
    'IRS tax year this invoice is reported under (e.g. 2024). Used for 1099-NEC aggregation.';

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
COMMENT ON TABLE billing.supplier_w9 IS
    'IRS W-9 form data collected from US-based supplier entities. One row per institution_entity '
    '(UNIQUE constraint). document_storage_path holds the internal GCS path; API responses '
    'expose a signed URL (document_url) instead.';
COMMENT ON COLUMN billing.supplier_w9.w9_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.supplier_w9.institution_entity_id IS
    'FK to ops.institution_entity_info. UNIQUE — one W-9 per entity.';
COMMENT ON COLUMN billing.supplier_w9.legal_name IS
    'Legal business name as it appears on the W-9.';
COMMENT ON COLUMN billing.supplier_w9.business_name IS
    'DBA or trade name; NULL if the business operates under the legal name only.';
COMMENT ON COLUMN billing.supplier_w9.tax_classification IS
    'IRS entity classification (e.g. ''sole_proprietor'', ''llc'', ''c_corp'').';
COMMENT ON COLUMN billing.supplier_w9.ein_last_four IS
    'Last four digits of the EIN (Employer Identification Number). Full EIN is not stored.';
COMMENT ON COLUMN billing.supplier_w9.address_line IS
    'Full mailing address as provided on the W-9.';
COMMENT ON COLUMN billing.supplier_w9.document_storage_path IS
    'Internal GCS object path for the uploaded W-9 scan. '
    'API responses expose a time-limited signed URL (document_url) instead of this path.';
COMMENT ON COLUMN billing.supplier_w9.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.supplier_w9.collected_at IS
    'UTC timestamp when the W-9 was submitted by the supplier.';
COMMENT ON COLUMN billing.supplier_w9.created_by IS
    'FK to core.user_info. Actor who submitted this W-9; NULL for system-generated rows.';
COMMENT ON COLUMN billing.supplier_w9.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN billing.supplier_w9.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';

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
COMMENT ON TABLE billing.employer_bill IS
    'Periodic bill charged to an employer institution for the benefit subsidy it owes. '
    'One bill per institution_entity per billing cycle. Line items live in employer_bill_line. '
    'Stripe invoice tracking is via stripe_invoice_id.';
COMMENT ON COLUMN billing.employer_bill.employer_bill_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.employer_bill.institution_id IS
    'FK to core.institution_info. The employer institution being billed.';
COMMENT ON COLUMN billing.employer_bill.institution_entity_id IS
    'FK to ops.institution_entity_info. The legal entity within the institution (per-country/currency).';
COMMENT ON COLUMN billing.employer_bill.billing_period_start IS
    'Start date of the billing period (inclusive), in market local time.';
COMMENT ON COLUMN billing.employer_bill.billing_period_end IS
    'End date of the billing period (inclusive), in market local time.';
COMMENT ON COLUMN billing.employer_bill.billing_cycle IS
    'Cycle identifier (e.g. ''monthly'', ''weekly'').';
COMMENT ON COLUMN billing.employer_bill.total_renewal_events IS
    'Count of subscription renewals included in this bill.';
COMMENT ON COLUMN billing.employer_bill.gross_employer_share IS
    'Sum of employer subsidy amounts across all line items, before discount.';
COMMENT ON COLUMN billing.employer_bill.price_discount IS
    'Percentage discount applied to the gross employer share (integer, 0–100).';
COMMENT ON COLUMN billing.employer_bill.discounted_amount IS
    'Gross employer share after applying price_discount.';
COMMENT ON COLUMN billing.employer_bill.minimum_fee_applied IS
    'TRUE if a minimum fee floor was enforced, overriding the discounted_amount.';
COMMENT ON COLUMN billing.employer_bill.billed_amount IS
    'Final amount charged to the employer after all adjustments and minimums.';
COMMENT ON COLUMN billing.employer_bill.currency_code IS
    'ISO 4217 currency code for this bill.';
COMMENT ON COLUMN billing.employer_bill.stripe_invoice_id IS
    'Stripe invoice ID for this bill; NULL until the invoice is created in Stripe.';
COMMENT ON COLUMN billing.employer_bill.payment_status IS
    'Payment state from employer_bill_payment_status_enum (pending / paid / failed / cancelled).';
COMMENT ON COLUMN billing.employer_bill.paid_date IS
    'UTC timestamp when payment was confirmed; NULL until paid.';
COMMENT ON COLUMN billing.employer_bill.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.employer_bill.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.employer_bill.created_date IS
    'UTC timestamp when the bill was generated.';
COMMENT ON COLUMN billing.employer_bill.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for pipeline-generated rows.';
COMMENT ON COLUMN billing.employer_bill.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.employer_bill.modified_date IS
    'UTC timestamp of the most recent update.';

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
COMMENT ON TABLE billing.employer_bill_line IS
    'One line per subscription renewal event within an employer bill. '
    'Records the plan price, benefit rate, and computed benefit amount at renewal time. '
    'Immutable once created — no audit history table (billing_line is append-only).';
COMMENT ON COLUMN billing.employer_bill_line.line_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.employer_bill_line.employer_bill_id IS
    'FK to billing.employer_bill. The parent bill this line belongs to.';
COMMENT ON COLUMN billing.employer_bill_line.subscription_id IS
    'FK to customer.subscription_info. The subscription that renewed.';
COMMENT ON COLUMN billing.employer_bill_line.user_id IS
    'FK to core.user_info. The employee who renewed.';
COMMENT ON COLUMN billing.employer_bill_line.plan_id IS
    'FK to customer.plan_info. The plan at renewal time.';
COMMENT ON COLUMN billing.employer_bill_line.plan_price IS
    'Plan price at the time of renewal, in the bill''s currency.';
COMMENT ON COLUMN billing.employer_bill_line.benefit_rate IS
    'Employer benefit rate as an integer percentage (e.g. 50 = 50% subsidy).';
COMMENT ON COLUMN billing.employer_bill_line.benefit_cap IS
    'Maximum benefit amount per renewal period; NULL if uncapped.';
COMMENT ON COLUMN billing.employer_bill_line.benefit_cap_period IS
    'Period to which benefit_cap applies (e.g. ''monthly''); NULL if uncapped.';
COMMENT ON COLUMN billing.employer_bill_line.employee_benefit IS
    'Actual employer subsidy amount for this renewal, after applying rate and cap.';
COMMENT ON COLUMN billing.employer_bill_line.renewal_date IS
    'UTC timestamp of the subscription renewal event this line records.';
COMMENT ON COLUMN billing.employer_bill_line.created_date IS
    'UTC timestamp when this line was written by the billing pipeline.';

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
COMMENT ON TABLE billing.supplier_terms IS
    'Payout and invoice configuration per supplier institution. Implements a three-tier cascade: '
    'entity-level override (institution_entity_id IS NOT NULL) → institution default '
    '(institution_entity_id IS NULL) → market default (billing.market_payout_aggregator) → '
    'hardcoded fallback. Unique on (institution_id, institution_entity_id).';
COMMENT ON COLUMN billing.supplier_terms.supplier_terms_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN billing.supplier_terms.institution_id IS
    'FK to core.institution_info. The supplier institution these terms apply to.';
COMMENT ON COLUMN billing.supplier_terms.institution_entity_id IS
    'FK to ops.institution_entity_info. NULL = institution-level defaults; '
    'NOT NULL = entity-level override for that specific legal entity.';
COMMENT ON COLUMN billing.supplier_terms.no_show_discount IS
    'Percentage deducted from payouts for no-show events (0–100).';
COMMENT ON COLUMN billing.supplier_terms.payment_frequency IS
    'How often payouts are issued, from payment_frequency_enum (e.g. daily, weekly).';
COMMENT ON COLUMN billing.supplier_terms.kitchen_open_time IS
    'Override for kitchen open time (wall-clock, naive). NULL = inherit from market_payout_aggregator.';
COMMENT ON COLUMN billing.supplier_terms.kitchen_close_time IS
    'Override for kitchen close time (wall-clock, naive). NULL = inherit from market_payout_aggregator.';
COMMENT ON COLUMN billing.supplier_terms.require_invoice IS
    'Override for invoice requirement. NULL = inherit from market_payout_aggregator.require_invoice.';
COMMENT ON COLUMN billing.supplier_terms.invoice_hold_days IS
    'Override for how many days payouts are held pending invoice submission. '
    'NULL = inherit from market default. Must be > 0 when set.';
COMMENT ON COLUMN billing.supplier_terms.is_archived IS
    'Soft-delete flag. TRUE = logically deleted.';
COMMENT ON COLUMN billing.supplier_terms.status IS
    'Row lifecycle from status_enum (active/inactive).';
COMMENT ON COLUMN billing.supplier_terms.created_date IS
    'UTC timestamp when this terms row was created.';
COMMENT ON COLUMN billing.supplier_terms.created_by IS
    'FK to core.user_info. Actor who created this row; NULL for system-generated rows.';
COMMENT ON COLUMN billing.supplier_terms.modified_by IS
    'FK to core.user_info. UUID of the last actor to write this row.';
COMMENT ON COLUMN billing.supplier_terms.modified_date IS
    'UTC timestamp of the most recent update.';

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

COMMENT ON TABLE ops.ingredient_catalog IS
    'Reference catalog of food ingredients, populated from Open Food Facts (OFF) taxonomy and enriched '
    'with Wikidata images (Phase 5) and USDA FoodData Central nutrition data (Phase 7). '
    'Used for product ingredient labelling and nutrition display.';
COMMENT ON COLUMN ops.ingredient_catalog.ingredient_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.ingredient_catalog.name IS
    'Canonical ingredient name used as the unique lookup key. '
    'Typically the OFF taxonomy name normalised to lower-case; '
    'may be a custom name for ingredients not in OFF.';
COMMENT ON COLUMN ops.ingredient_catalog.name_display IS
    'Consumer-facing display name (title-cased). Shown on plate ingredient lists.';
COMMENT ON COLUMN ops.ingredient_catalog.name_es IS
    'Spanish translation of the ingredient name. NULL until translation pipeline runs.';
COMMENT ON COLUMN ops.ingredient_catalog.name_en IS
    'English translation of the ingredient name. NULL until translation pipeline runs.';
COMMENT ON COLUMN ops.ingredient_catalog.name_pt IS
    'Portuguese translation of the ingredient name. NULL until translation pipeline runs.';
COMMENT ON COLUMN ops.ingredient_catalog.off_taxonomy_id IS
    'Open Food Facts taxonomy identifier (e.g. ''en:tomato''). Unique. NULL for custom ingredients.';
COMMENT ON COLUMN ops.ingredient_catalog.off_wikidata_id IS
    'Wikidata entity ID linked from OFF (e.g. ''Q23501''). Used to fetch the CC-licensed image.';
COMMENT ON COLUMN ops.ingredient_catalog.image_url IS
    'CDN URL of the ingredient image (CC-licensed, sourced from Wikidata). NULL until Phase 5 enrichment runs.';
COMMENT ON COLUMN ops.ingredient_catalog.image_source IS
    'Provenance of the image (e.g. ''wikidata''). NULL until enriched.';
COMMENT ON COLUMN ops.ingredient_catalog.usda_fdc_id IS
    'USDA FoodData Central record ID. Unique. NULL until Phase 7 nutrition enrichment matches this ingredient.';
COMMENT ON COLUMN ops.ingredient_catalog.food_group IS
    'USDA food group classification (e.g. ''Vegetables and Vegetable Products''). NULL until USDA-enriched.';
COMMENT ON COLUMN ops.ingredient_catalog.image_enriched IS
    'Pipeline flag: TRUE once a Wikidata image has been fetched and stored for this ingredient.';
COMMENT ON COLUMN ops.ingredient_catalog.image_skipped IS
    'Pipeline flag: TRUE if the image enrichment step was intentionally skipped (e.g. no Wikidata image found).';
COMMENT ON COLUMN ops.ingredient_catalog.usda_enriched IS
    'Pipeline flag: TRUE once USDA nutrition data has been fetched and linked.';
COMMENT ON COLUMN ops.ingredient_catalog.usda_skipped IS
    'Pipeline flag: TRUE if USDA enrichment was intentionally skipped (e.g. no FDC match found).';
COMMENT ON COLUMN ops.ingredient_catalog.source IS
    'Provenance of the ingredient entry: ''off'' (Open Food Facts import) or ''custom'' (manually added).';
COMMENT ON COLUMN ops.ingredient_catalog.is_verified IS
    'When TRUE, a human has verified the ingredient data quality. Used to filter unverified entries in admin tooling.';
COMMENT ON COLUMN ops.ingredient_catalog.created_date IS
    'UTC timestamp when the ingredient was first imported or created.';
COMMENT ON COLUMN ops.ingredient_catalog.modified_date IS
    'UTC timestamp of the most recent update.';
COMMENT ON COLUMN ops.ingredient_catalog.modified_by IS
    'FK to core.user_info. Last user (or system account) to update this ingredient record.';

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

COMMENT ON TABLE ops.product_ingredient IS
    'Join table linking products to their ingredients in the catalog. '
    'Ordered by sort_order to display ingredients in the intended sequence on plate detail screens.';
COMMENT ON COLUMN ops.product_ingredient.product_ingredient_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.product_ingredient.product_id IS
    'FK to ops.product_info. The product that contains this ingredient.';
COMMENT ON COLUMN ops.product_ingredient.ingredient_id IS
    'FK to ops.ingredient_catalog. The ingredient used in this product.';
COMMENT ON COLUMN ops.product_ingredient.sort_order IS
    'Display order of the ingredient within the product''s ingredient list. Lower values appear first.';
COMMENT ON COLUMN ops.product_ingredient.created_date IS
    'UTC timestamp when the product–ingredient link was created.';
COMMENT ON COLUMN ops.product_ingredient.modified_by IS
    'FK to core.user_info. Last user to update this link (e.g. after reordering ingredients).';

\echo 'Creating table: ops.ingredient_alias'
CREATE TABLE IF NOT EXISTS ops.ingredient_alias (
    alias_id        UUID         PRIMARY KEY DEFAULT uuidv7(),
    ingredient_id   UUID         NOT NULL REFERENCES ops.ingredient_catalog(ingredient_id) ON DELETE CASCADE,
    alias           VARCHAR(150) NOT NULL,
    region_code     VARCHAR(10)  NULL,
    UNIQUE (alias)
);

COMMENT ON TABLE ops.ingredient_alias IS
    'Alternative names (aliases) for ingredients in ops.ingredient_catalog. '
    'Used by the ingredient search and matching pipeline to resolve non-canonical ingredient names '
    'in product ingredient text to catalog entries.';
COMMENT ON COLUMN ops.ingredient_alias.alias_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.ingredient_alias.ingredient_id IS
    'FK to ops.ingredient_catalog. The canonical ingredient this alias resolves to.';
COMMENT ON COLUMN ops.ingredient_alias.alias IS
    'The alternative name (e.g. a regional spelling or colloquial term). Unique globally.';
COMMENT ON COLUMN ops.ingredient_alias.region_code IS
    'Optional ISO 3166-1 alpha-2 region code scoping this alias to a specific market (e.g. ''MX''). '
    'NULL means the alias applies globally.';

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

COMMENT ON TABLE ops.ingredient_nutrition IS
    'Nutrition facts for an ingredient, sourced from USDA FoodData Central (Phase 7 enrichment cron). '
    'One row per (ingredient, source) pair. Values are per per_amount_g grams of the ingredient.';
COMMENT ON COLUMN ops.ingredient_nutrition.nutrition_id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.ingredient_nutrition.ingredient_id IS
    'FK to ops.ingredient_catalog. The ingredient these nutrition facts describe.';
COMMENT ON COLUMN ops.ingredient_nutrition.source IS
    'Data source for these nutrition values (e.g. ''usda''). Allows multiple sources per ingredient in future.';
COMMENT ON COLUMN ops.ingredient_nutrition.per_amount_g IS
    'Reference quantity in grams for which the nutrition values apply. Typically 100 g.';
COMMENT ON COLUMN ops.ingredient_nutrition.energy_kcal IS
    'Energy content in kilocalories per per_amount_g. NULL if not available from source.';
COMMENT ON COLUMN ops.ingredient_nutrition.protein_g IS
    'Protein content in grams per per_amount_g. NULL if not available.';
COMMENT ON COLUMN ops.ingredient_nutrition.fat_g IS
    'Total fat content in grams per per_amount_g. NULL if not available.';
COMMENT ON COLUMN ops.ingredient_nutrition.carbohydrates_g IS
    'Total carbohydrate content in grams per per_amount_g. NULL if not available.';
COMMENT ON COLUMN ops.ingredient_nutrition.fiber_g IS
    'Dietary fiber content in grams per per_amount_g. NULL if not available.';
COMMENT ON COLUMN ops.ingredient_nutrition.sugar_g IS
    'Total sugar content in grams per per_amount_g. NULL if not available.';
COMMENT ON COLUMN ops.ingredient_nutrition.sodium_mg IS
    'Sodium content in milligrams per per_amount_g. NULL if not available.';
COMMENT ON COLUMN ops.ingredient_nutrition.fetched_date IS
    'Calendar date when the nutrition data was fetched from the source. Used to detect stale records.';
COMMENT ON COLUMN ops.ingredient_nutrition.modified_date IS
    'UTC timestamp of the most recent update to this nutrition record.';

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
COMMENT ON TABLE core.ad_click_tracking IS
    'Records ad click identifiers (Google gclid, Meta fbclid/fbc/fbp) captured on the frontend '
    'and associated to a user after login. Used for server-side conversion attribution via '
    'the ARQ worker queue. One row per attribution event; upload status tracked per platform.';
COMMENT ON COLUMN core.ad_click_tracking.id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.ad_click_tracking.user_id IS
    'FK to core.user_info. The user whose click is being tracked.';
COMMENT ON COLUMN core.ad_click_tracking.subscription_id IS
    'FK to the subscription that converted from this click. NULL until conversion confirmed.';
COMMENT ON COLUMN core.ad_click_tracking.gclid IS
    'Google Click ID (gclid) captured from the landing URL at click time.';
COMMENT ON COLUMN core.ad_click_tracking.wbraid IS
    'Google web-to-app click ID (wbraid). Alternative to gclid for iOS privacy-constrained clicks.';
COMMENT ON COLUMN core.ad_click_tracking.gbraid IS
    'Google app-to-web click ID (gbraid). Alternative to gclid for app-originated traffic.';
COMMENT ON COLUMN core.ad_click_tracking.fbclid IS
    'Facebook Click ID (fbclid) captured from the landing URL.';
COMMENT ON COLUMN core.ad_click_tracking.fbc IS
    'Facebook browser cookie value (_fbc). Longer than fbclid — up to 500 chars.';
COMMENT ON COLUMN core.ad_click_tracking.fbp IS
    'Facebook pixel cookie value (_fbp). Stable user identifier across sessions.';
COMMENT ON COLUMN core.ad_click_tracking.event_id IS
    'Deduplication event ID for server-side Conversions API. Prevents double-counting '
    'when both browser pixel and server-side events are sent.';
COMMENT ON COLUMN core.ad_click_tracking.landing_url IS
    'Full landing URL at the time of the click, including query string. Used for debugging.';
COMMENT ON COLUMN core.ad_click_tracking.source_platform IS
    'Ad platform that drove the click (e.g. ''google'', ''meta''). Routes conversion uploads.';
COMMENT ON COLUMN core.ad_click_tracking.captured_at IS
    'UTC timestamp when the click identifiers were captured (frontend POST time).';
COMMENT ON COLUMN core.ad_click_tracking.google_upload_status IS
    'Google Ads upload state: ''pending'' → ''uploaded'' / ''failed''. Partial index covers pending rows.';
COMMENT ON COLUMN core.ad_click_tracking.google_uploaded_at IS
    'UTC timestamp when the Google Ads conversion was successfully uploaded. NULL until uploaded.';
COMMENT ON COLUMN core.ad_click_tracking.meta_upload_status IS
    'Meta CAPI upload state: ''pending'' → ''uploaded'' / ''failed''.';
COMMENT ON COLUMN core.ad_click_tracking.meta_uploaded_at IS
    'UTC timestamp when the Meta CAPI event was successfully uploaded. NULL until uploaded.';
COMMENT ON COLUMN core.ad_click_tracking.created_date IS
    'UTC timestamp when the tracking row was created.';
COMMENT ON COLUMN core.ad_click_tracking.modified_date IS
    'UTC timestamp of the most recent update (e.g. status change on upload).';

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
COMMENT ON TABLE core.ad_zone IS
    'Geographic ad zones defining Vianda''s market-expansion flywheel. Each zone is a '
    'center-point + radius covering a neighborhood or district. Flywheel state drives '
    'which campaign strategies are active for that zone. Metrics and budget allocation '
    'are updated by the zone_metrics_service cron.';
COMMENT ON COLUMN core.ad_zone.id IS
    'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN core.ad_zone.name IS
    'Display name for the zone (e.g. ''Palermo'', ''Miraflores''). Shown in the admin zone list.';
COMMENT ON COLUMN core.ad_zone.country_code IS
    'ISO 3166-1 alpha-2 country code where this zone is located.';
COMMENT ON COLUMN core.ad_zone.city_name IS
    'City name for this zone (e.g. ''Buenos Aires''). Not a FK — free text for flexibility.';
COMMENT ON COLUMN core.ad_zone.neighborhood IS
    'Neighborhood or sub-district name (e.g. ''Palermo Soho''). Optional; NULL for city-level zones.';
COMMENT ON COLUMN core.ad_zone.latitude IS
    'Latitude of the zone center in decimal degrees (7 decimal places).';
COMMENT ON COLUMN core.ad_zone.longitude IS
    'Longitude of the zone center in decimal degrees (7 decimal places).';
COMMENT ON COLUMN core.ad_zone.radius_km IS
    'Radius of the zone in kilometres. Default 2.0 km. Used in haversine distance queries '
    'for restaurant/subscriber/lead counting and audience matching.';
COMMENT ON COLUMN core.ad_zone.flywheel_state IS
    'Current flywheel state: monitoring → supply_acquisition → demand_activation → growth → mature → paused. '
    'Drives which campaign strategies are active. Operators can force any transition.';
COMMENT ON COLUMN core.ad_zone.state_changed_at IS
    'UTC timestamp when the flywheel state last changed.';
COMMENT ON COLUMN core.ad_zone.state_changed_by IS
    'FK to core.user_info — the operator who triggered the last state transition. NULL for system transitions.';
COMMENT ON COLUMN core.ad_zone.notify_me_lead_count IS
    'Count of notify-me leads whose city_name matches this zone. Updated by zone_metrics_service cron.';
COMMENT ON COLUMN core.ad_zone.active_restaurant_count IS
    'Count of active restaurants within the zone radius. Updated by zone_metrics_service cron.';
COMMENT ON COLUMN core.ad_zone.active_subscriber_count IS
    'Count of active subscribers within the zone radius. Updated by zone_metrics_service cron.';
COMMENT ON COLUMN core.ad_zone.estimated_mau IS
    'Estimated Monthly Active Users for this zone. Populated by the Gemini advisor (Phase 22). NULL until estimated.';
COMMENT ON COLUMN core.ad_zone.mau_estimated_at IS
    'UTC timestamp when estimated_mau was last computed.';
COMMENT ON COLUMN core.ad_zone.budget_allocation IS
    'JSONB budget split across campaign strategies as percentages summing to 100. '
    'Default: {"b2c_subscriber": 0, "b2b_employer": 0, "b2b_restaurant": 100}. '
    'Used by the campaign manager to allocate daily_budget_cents across strategies.';
COMMENT ON COLUMN core.ad_zone.daily_budget_cents IS
    'Total daily ad budget for this zone in the smallest currency unit (cents). '
    'Split across strategies per budget_allocation. NULL = no active budget.';
COMMENT ON COLUMN core.ad_zone.meta_ad_set_ids IS
    'JSONB map of strategy → Meta Ad Set ID for this zone. '
    'Empty until Meta campaigns are created for the zone.';
COMMENT ON COLUMN core.ad_zone.google_campaign_ids IS
    'JSONB map of strategy → Google Campaign ID for this zone. '
    'Empty until Google campaigns are created for the zone.';
COMMENT ON COLUMN core.ad_zone.created_by IS
    'How the zone was created: ''operator'' (manual) or ''advisor'' (Gemini-proposed). '
    'VARCHAR — not a user FK because ''advisor'' is a system actor, not a user.';
COMMENT ON COLUMN core.ad_zone.approved_by IS
    'FK to core.user_info — the operator who approved an advisor-proposed zone. NULL for operator-created zones.';
COMMENT ON COLUMN core.ad_zone.created_date IS
    'UTC timestamp when the zone was created.';
COMMENT ON COLUMN core.ad_zone.modified_date IS
    'UTC timestamp of the most recent update.';

-- ─────────────────────────────────────────────────────────────
-- DEFERRED FK: core.address_info.city_metadata_id → core.city_metadata
-- and composite consistency FK on (city_metadata_id, country_code).
-- Added at the end so city_metadata (created earlier in this file, right after
-- audit.market_history) is guaranteed to exist. The column itself was added
-- as a nullable UUID near the top of schema.sql so the audit history table
-- could mirror it via the trigger pattern.
-- ─────────────────────────────────────────────────────────────
\echo 'Adding deferred FK: customer.subscription_payment.payment_attempt_id → billing.payment_attempt'
ALTER TABLE customer.subscription_payment
    ADD CONSTRAINT fk_subscription_payment_payment_attempt_id
    FOREIGN KEY (payment_attempt_id) REFERENCES billing.payment_attempt(payment_attempt_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_subscription_payment_attempt_id
    ON customer.subscription_payment(payment_attempt_id)
    WHERE payment_attempt_id IS NOT NULL;

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
