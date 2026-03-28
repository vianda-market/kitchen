CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS citext;
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
-- public: reserved for extensions only (uuid-ossp, citext, pgcrypto, etc.)

-- =============================================================================
-- DROP TABLES FIRST (with CASCADE to handle dependencies)
-- =============================================================================

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
DROP TABLE IF EXISTS audit.employer_history CASCADE;
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
DROP TABLE IF EXISTS audit.discretionary_history CASCADE;
DROP TABLE IF EXISTS billing.discretionary_info CASCADE;
DROP TABLE IF EXISTS billing.client_transaction CASCADE;
DROP TABLE IF EXISTS customer.user_favorite_info CASCADE;
DROP TABLE IF EXISTS customer.plate_review_info CASCADE;
DROP TABLE IF EXISTS customer.plate_pickup_live CASCADE;
DROP TABLE IF EXISTS fintech_wallet_auth CASCADE;

-- Drop remaining base/parent tables
DROP TABLE IF EXISTS customer.coworker_pickup_notification CASCADE;
DROP TABLE IF EXISTS audit.plate_selection_history CASCADE;
DROP TABLE IF EXISTS customer.plate_selection_info CASCADE;
DROP TABLE IF EXISTS plate_selection CASCADE;
DROP TABLE IF EXISTS ops.plate_info CASCADE;
DROP TABLE IF EXISTS billing.client_bill_info CASCADE;
DROP TABLE IF EXISTS customer.subscription_payment CASCADE;
DROP TABLE IF EXISTS customer.subscription_info CASCADE;
DROP TABLE IF EXISTS customer.external_payment_method CASCADE;
DROP TABLE IF EXISTS customer.payment_method CASCADE;
DROP TABLE IF EXISTS audit.user_payment_provider_history CASCADE;
DROP TABLE IF EXISTS customer.user_payment_provider CASCADE;
DROP TABLE IF EXISTS ops.product_info CASCADE;
DROP TABLE IF EXISTS customer.plan_info CASCADE;
DROP TABLE IF EXISTS ops.restaurant_info CASCADE;
DROP TABLE IF EXISTS core.credit_currency_info CASCADE;
DROP TABLE IF EXISTS audit.institution_settlement_history CASCADE;
DROP TABLE IF EXISTS billing.institution_settlement CASCADE;
DROP TABLE IF EXISTS billing.institution_bill_payout CASCADE;
DROP TABLE IF EXISTS billing.institution_bill_info CASCADE;
DROP TABLE IF EXISTS billing.restaurant_balance_info CASCADE;
DROP TABLE IF EXISTS core.geolocation_info CASCADE;
DROP TABLE IF EXISTS core.address_subpremise CASCADE;
DROP TABLE IF EXISTS core.address_info CASCADE;
DROP TABLE IF EXISTS ops.institution_entity_info CASCADE;
DROP TABLE IF EXISTS core.institution_info CASCADE;
DROP TABLE IF EXISTS core.user_market_assignment CASCADE;
DROP TABLE IF EXISTS core.user_messaging_preferences CASCADE;
DROP TABLE IF EXISTS core.user_info CASCADE;
DROP TABLE IF EXISTS core.employer_info CASCADE;
DROP TABLE IF EXISTS customer.pending_customer_signup CASCADE;
DROP TABLE IF EXISTS customer.email_change_request CASCADE;
DROP TABLE IF EXISTS customer.credential_recovery CASCADE;
DROP TABLE IF EXISTS role_info CASCADE;

-- =============================================================================
-- DROP ENUM TYPES (after dropping tables that use them)
-- =============================================================================

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
DROP TYPE IF EXISTS address_type_enum CASCADE;
DROP TYPE IF EXISTS street_type_enum CASCADE;
DROP TYPE IF EXISTS favorite_entity_type_enum CASCADE;

-- =============================================================================
-- CREATE ENUM TYPES (before creating tables that use them)
-- =============================================================================

\echo 'Creating enum type: address_type_enum'
CREATE TYPE address_type_enum AS ENUM (
    'Restaurant',
    'Entity Billing',
    'Entity Address',
    'Customer Home',
    'Customer Billing',
    'Customer Employer'
);

\echo 'Creating enum type: status_enum'
CREATE TYPE status_enum AS ENUM (
    'Active',
    'Inactive',
    'Pending',
    'Arrived',
    'Completed',
    'Cancelled',
    'Processed'
);

\echo 'Creating enum type: discretionary_status_enum'
CREATE TYPE discretionary_status_enum AS ENUM (
    'Pending',
    'Cancelled',
    'Approved',
    'Rejected'
);

\echo 'Creating enum type: bill_resolution_enum'
CREATE TYPE bill_resolution_enum AS ENUM (
    'Pending',
    'Paid',
    'Rejected',
    'Failed'
);

\echo 'Creating enum type: bill_payout_status_enum'
CREATE TYPE bill_payout_status_enum AS ENUM (
    'Pending',
    'Completed',
    'Failed'
);

\echo 'Creating enum type: role_type_enum'
CREATE TYPE role_type_enum AS ENUM (
    'Internal',
    'Supplier',
    'Customer',
    'Employer'
);

\echo 'Creating enum type: institution_type_enum'
CREATE TYPE institution_type_enum AS ENUM (
    'Internal',
    'Customer',
    'Supplier',
    'Employer'
);

\echo 'Creating enum type: role_name_enum'
CREATE TYPE role_name_enum AS ENUM (
    'Admin',
    'Super Admin',
    'Manager',
    'Operator',
    'Comensal',
    'Global Manager'
);

\echo 'Creating enum type: transaction_type_enum'
CREATE TYPE transaction_type_enum AS ENUM (
    'Order',
    'Credit',
    'Debit',
    'Refund',
    'Discretionary',
    'Payment'
);

\echo 'Creating enum type: kitchen_day_enum'
CREATE TYPE kitchen_day_enum AS ENUM (
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday'
);

\echo 'Creating enum type: pickup_type_enum'
CREATE TYPE pickup_type_enum AS ENUM (
    'offer',
    'request',
    'self'
);

\echo 'Creating enum type: street_type_enum'
CREATE TYPE street_type_enum AS ENUM (
    'St',
    'Ave',
    'Blvd',
    'Rd',
    'Dr',
    'Ln',
    'Way',
    'Ct',
    'Pl',
    'Cir'
);

\echo 'Creating enum type: audit_operation_enum'
CREATE TYPE audit_operation_enum AS ENUM (
    'CREATE',
    'UPDATE',
    'ARCHIVE',
    'DELETE'
);

\echo 'Creating enum type: discretionary_reason_enum'
CREATE TYPE discretionary_reason_enum AS ENUM (
    'Marketing Campaign',
    'Credit Refund',
    'Order incorrectly marked as not collected',
    'Full Order Refund'
);

\echo 'Creating enum type: favorite_entity_type_enum'
CREATE TYPE favorite_entity_type_enum AS ENUM (
    'plate',
    'restaurant'
);

-- =============================================================================
-- CREATE TABLES (enum types now exist)
-- =============================================================================

-- National holidays table to prevent kitchen operations on these days
CREATE TABLE IF NOT EXISTS core.national_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuidv7(),
    country_code VARCHAR(3) NOT NULL CHECK (length(country_code) = 2),
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER CHECK (recurring_month IS NULL OR recurring_month BETWEEN 1 AND 12),
    recurring_day INTEGER CHECK (recurring_day IS NULL OR recurring_day BETWEEN 1 AND 31),
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - enums are now stored directly on entities (core.user_info, etc.)

\echo 'Creating table: core.institution_info'
CREATE TABLE IF NOT EXISTS core.institution_info (
    institution_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(50) NOT NULL,
    institution_type institution_type_enum NOT NULL DEFAULT 'Supplier'::institution_type_enum,
    no_show_discount INTEGER NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_institution_no_show_discount CHECK (
        (institution_type <> 'Supplier'::institution_type_enum) OR
        (no_show_discount IS NOT NULL AND no_show_discount >= 0 AND no_show_discount <= 100)
    )
);

\echo 'Creating table: core.address_info'
CREATE TABLE IF NOT EXISTS core.address_info (
    address_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    user_id UUID NULL,  -- Required only for Customer Comensal home/other; nullable for Supplier, Employee, Employer
    employer_id UUID NULL,  -- Links address to employer (nullable)
    address_type address_type_enum[] NOT NULL,
    country_code VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2 (AR, PE, CL); country_name from core.market_info via JOIN
    province VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    street_type street_type_enum NOT NULL DEFAULT 'St'::street_type_enum,
    street_name VARCHAR(100) NOT NULL,
    building_number VARCHAR(20) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT
    -- Note: user_id and modified_by foreign keys removed to resolve circular dependency
    -- with core.employer_info -> core.address_info -> core.user_info dependency chain
    -- Note: employer_id foreign key will be added after core.employer_info table is created
    -- Note: country_code foreign key will be added after core.market_info table is created
    -- Note: floor, apartment_unit, is_default moved to core.address_subpremise
);

\echo 'Creating table: audit.address_history'
-- Use case: core.address_info still has updates (address_type from linkages, is_archived, status, modified_by/date).
-- Address core (street, city, province, etc.) is immutable; subpremise edits (floor, unit, is_default) are in core.address_subpremise.
CREATE TABLE IF NOT EXISTS audit.address_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    address_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    user_id UUID NULL,
    employer_id UUID NULL,  -- Track employer_id in history
    address_type address_type_enum[],
    country_code VARCHAR(2),
    province VARCHAR(50),
    city VARCHAR(50),
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
    -- Note: modified_by foreign key removed to resolve circular dependency
    -- Note: floor, apartment_unit, is_default in core.address_subpremise
);

\echo 'Creating table: core.employer_info'
CREATE TABLE IF NOT EXISTS core.employer_info (
    employer_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(100) NOT NULL,
    address_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT
);

\echo 'Adding foreign key constraint: core.address_info.employer_id -> core.employer_info.employer_id'
ALTER TABLE core.address_info 
ADD CONSTRAINT fk_address_info_employer_id 
FOREIGN KEY (employer_id) REFERENCES core.employer_info(employer_id) ON DELETE SET NULL;

\echo 'Creating table: audit.employer_history'
CREATE TABLE IF NOT EXISTS audit.employer_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    employer_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    address_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (employer_id) REFERENCES core.employer_info(employer_id) ON DELETE RESTRICT
);

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
    employer_id UUID NULL, -- For end-customers: links to their employer
    employer_address_id UUID NULL REFERENCES core.address_info(address_id) ON DELETE SET NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES core.employer_info(employer_id) ON DELETE SET NULL
);

\echo 'Creating table: core.address_subpremise'
CREATE TABLE IF NOT EXISTS core.address_subpremise (
    subpremise_id UUID PRIMARY KEY DEFAULT uuidv7(),
    address_id UUID NOT NULL REFERENCES core.address_info(address_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE CASCADE,
    floor VARCHAR(50) NULL,
    apartment_unit VARCHAR(20) NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (address_id, user_id)
);

\echo 'Creating table: core.credit_currency_info'
CREATE TABLE IF NOT EXISTS core.credit_currency_info (
    credit_currency_id UUID PRIMARY KEY DEFAULT uuidv7(),
    currency_name VARCHAR(50) NOT NULL,
    currency_code VARCHAR(10) NOT NULL UNIQUE,
    credit_value_local_currency NUMERIC NOT NULL,
    currency_conversion_usd NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);


\echo 'Creating table: audit.credit_currency_history'
CREATE TABLE IF NOT EXISTS audit.credit_currency_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    credit_currency_id UUID NOT NULL,
    currency_name VARCHAR(50) NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    credit_value_local_currency NUMERIC NOT NULL,
    currency_conversion_usd NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

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

\echo 'Creating table: core.market_info'
CREATE TABLE IF NOT EXISTS core.market_info (
    market_id UUID PRIMARY KEY DEFAULT uuidv7(),
    country_name VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(2) NOT NULL UNIQUE,  -- ISO 3166-1 alpha-2: AR, PE, CL
    credit_currency_id UUID NOT NULL,         -- FK to core.credit_currency_info
    timezone VARCHAR(50) NOT NULL,            -- e.g., 'America/Argentina/Buenos_Aires'
    kitchen_close_time TIME NOT NULL DEFAULT '13:30',  -- Order cutoff local time (e.g. 1:30 PM); B2B manageable
    language VARCHAR(5) NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'es', 'pt')),
    phone_dial_code VARCHAR(6) NULL,   -- E.164 country prefix e.g. '+54'; NULL for pseudo-markets
    phone_local_digits SMALLINT NULL,  -- Max national digits after dial code; UI maxLength hint e.g. 10
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

-- Add foreign key constraint from core.address_info to core.market_info (deferred to avoid circular dependency)
\echo 'Adding foreign key: core.address_info.country_code -> core.market_info.country_code'
ALTER TABLE core.address_info ADD CONSTRAINT fk_address_country_code FOREIGN KEY (country_code) REFERENCES core.market_info(country_code) ON DELETE RESTRICT;

\echo 'Creating table: audit.market_history'
CREATE TABLE IF NOT EXISTS audit.market_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    credit_currency_id UUID NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    kitchen_close_time TIME NOT NULL,
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
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: core.city_info'
CREATE TABLE IF NOT EXISTS core.city_info (
    city_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(100) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    province_code VARCHAR(10),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (country_code) REFERENCES core.market_info(country_code) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Adding core.user_info.market_id (required: one market per user, v1)'
ALTER TABLE core.user_info ADD COLUMN market_id UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_user_info_market_id ON core.user_info(market_id);

\echo 'Adding core.user_info.locale (ISO 639-1: en, es, pt)'
ALTER TABLE core.user_info ADD COLUMN locale VARCHAR(5) NOT NULL DEFAULT 'en' CHECK (locale IN ('en', 'es', 'pt'));

CREATE INDEX IF NOT EXISTS idx_city_info_country_code ON core.city_info(country_code) WHERE NOT is_archived;

\echo 'Adding core.user_info.city_id (user primary city for scoping; NOT NULL, default Global for B2B)'
ALTER TABLE core.user_info ADD COLUMN city_id UUID NOT NULL DEFAULT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' REFERENCES core.city_info(city_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_user_info_city_id ON core.user_info(city_id);

\echo 'Adding core.institution_info.market_id (required: every institution has a market — Global, single, or multi; default Global for backfill)'
ALTER TABLE core.institution_info ADD COLUMN market_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES core.market_info(market_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_institution_info_market_id ON core.institution_info(market_id);

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

\echo 'Creating table: audit.institution_history'
CREATE TABLE IF NOT EXISTS audit.institution_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    name VARCHAR(50) NOT NULL,
    institution_type institution_type_enum NOT NULL,
    market_id UUID,
    no_show_discount INTEGER NULL,
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
    employer_institution_id UUID NULL, -- For end-customers: links to their employer's institution
    market_id UUID NOT NULL,
    city_id UUID NOT NULL,
    locale VARCHAR(5) NOT NULL CHECK (locale IN ('en', 'es', 'pt')),
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

\echo 'Creating table: customer.credential_recovery'
CREATE TABLE IF NOT EXISTS customer.credential_recovery (
    credential_recovery_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    recovery_code VARCHAR(10) NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_date TIMESTAMPTZ,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    city_id UUID NOT NULL REFERENCES core.city_info(city_id) ON DELETE RESTRICT
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
    place_id VARCHAR(255) NULL,
    viewport JSONB NULL,
    formatted_address_google VARCHAR(500) NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    place_id VARCHAR(255) NULL,
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
    FOREIGN KEY (geolocation_id) REFERENCES core.geolocation_info(geolocation_id) ON DELETE CASCADE
);

\echo 'Creating table: ops.institution_entity_info'
CREATE TABLE IF NOT EXISTS ops.institution_entity_info (
    institution_entity_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    address_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    tax_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    stripe_connect_account_id VARCHAR(255) NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES core.address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.institution_entity_history'
CREATE TABLE IF NOT EXISTS audit.institution_entity_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id UUID NOT NULL,
    institution_id UUID,
    address_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    tax_id VARCHAR(50),
    name VARCHAR(100),
    stripe_connect_account_id VARCHAR(255) NULL,
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

\echo 'Creating table: ops.restaurant_info'
CREATE TABLE IF NOT EXISTS ops.restaurant_info (
    restaurant_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    address_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    cuisine VARCHAR (50),
    pickup_instructions VARCHAR(500),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
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
    cuisine VARCHAR (50),
    pickup_instructions VARCHAR(500),
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

\echo 'Creating table: ops.qr_code'
CREATE TABLE IF NOT EXISTS ops.qr_code (
    qr_code_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    qr_code_payload VARCHAR(255) NOT NULL,
    qr_code_image_url VARCHAR(500) NOT NULL,
    image_storage_path VARCHAR(500) NOT NULL,
    qr_code_checksum VARCHAR(128),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    ingredients VARCHAR(255),
    dietary VARCHAR(255),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    ingredients VARCHAR(255),
    dietary VARCHAR(255),
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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

\echo 'Creating table: ops.plate_kitchen_days'
CREATE TABLE IF NOT EXISTS ops.plate_kitchen_days (
    plate_kitchen_day_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation audit_operation_enum NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);

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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_plate_selection_pickup_date_weekday CHECK (
        EXTRACT(ISODOW FROM pickup_date) = CASE kitchen_day
            WHEN 'Monday' THEN 1
            WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5
        END
    ),
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    was_collected BOOLEAN DEFAULT FALSE,
    arrival_time TIMESTAMPTZ,
    completion_time TIMESTAMPTZ,
    expected_completion_time TIMESTAMPTZ,
    confirmation_code VARCHAR(10),
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
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES ops.plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_pickup_id) REFERENCES customer.plate_pickup_live(plate_pickup_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_review_plate_id ON customer.plate_review_info(plate_id) WHERE NOT is_archived;

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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit_cost_local_currency DOUBLE PRECISION NOT NULL,
    credit_cost_usd DOUBLE PRECISION NOT NULL,
    rollover BOOLEAN NOT NULL DEFAULT TRUE,
    rollover_cap NUMERIC,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
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
    status discretionary_status_enum NOT NULL DEFAULT 'Pending'::discretionary_status_enum,
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
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE CASCADE
);

\echo 'Creating table: billing.discretionary_resolution_info'
CREATE TABLE IF NOT EXISTS billing.discretionary_resolution_info (
    approval_id UUID PRIMARY KEY DEFAULT uuidv7(),
    discretionary_id UUID NOT NULL,
    resolution discretionary_status_enum NOT NULL DEFAULT 'Pending'::discretionary_status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
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
    FOREIGN KEY (approval_id) REFERENCES billing.discretionary_resolution_info(approval_id) ON DELETE CASCADE
);

\echo 'Creating trigger function: discretionary_info_history_trigger'
CREATE OR REPLACE FUNCTION discretionary_info_history_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
    v_changed_by UUID;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        v_operation := 'CREATE'::audit_operation_enum;
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
        v_operation := 'UPDATE'::audit_operation_enum;
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
        v_operation := 'DELETE'::audit_operation_enum;
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
        v_operation := 'CREATE'::audit_operation_enum;
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
        v_operation := 'UPDATE'::audit_operation_enum;
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
        v_operation := 'DELETE'::audit_operation_enum;
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
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: customer.subscription_info'
CREATE TABLE IF NOT EXISTS customer.subscription_info (
    subscription_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    market_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    renewal_date TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    balance NUMERIC DEFAULT 0,
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'Pending',  -- 'Active', 'On Hold', 'Pending', 'Cancelled'
    hold_start_date TIMESTAMPTZ,  -- When subscription was put on hold
    hold_end_date TIMESTAMPTZ,    -- When subscription will resume (NULL = indefinite)
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,  -- Keep for backward compatibility
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
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
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
    status               status_enum NOT NULL DEFAULT 'Active'::status_enum,
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

\echo 'Creating table: billing.client_bill_info'
CREATE TABLE IF NOT EXISTS billing.client_bill_info (
    client_bill_id UUID PRIMARY KEY DEFAULT uuidv7(),
    subscription_payment_id UUID NOT NULL,
    subscription_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    amount NUMERIC NOT NULL,
    currency_code VARCHAR(10),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_id) REFERENCES customer.subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES customer.plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
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
    credit_currency_id UUID NOT NULL,
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

\echo 'Creating table: billing.restaurant_transaction'
CREATE TABLE IF NOT EXISTS billing.restaurant_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    plate_selection_id UUID,
    discretionary_id UUID,
    credit_currency_id UUID NOT NULL,
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
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    created_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES customer.plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES billing.discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: billing.restaurant_balance_info'
CREATE TABLE IF NOT EXISTS billing.restaurant_balance_info (
    restaurant_id UUID PRIMARY KEY,
    credit_currency_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.restaurant_balance_history'
CREATE TABLE IF NOT EXISTS audit.restaurant_balance_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
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

\echo 'Creating table: billing.institution_bill_info'
CREATE TABLE IF NOT EXISTS billing.institution_bill_info (
    institution_bill_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    transaction_count INTEGER,
    amount NUMERIC,
    currency_code VARCHAR(10),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    resolution bill_resolution_enum NOT NULL DEFAULT 'Pending'::bill_resolution_enum,
    tax_doc_external_id VARCHAR(255),
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: audit.institution_bill_history'
CREATE TABLE IF NOT EXISTS audit.institution_bill_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
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

\echo 'Creating table: billing.institution_bill_payout'
CREATE TABLE IF NOT EXISTS billing.institution_bill_payout (
    bill_payout_id       UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id  UUID        NOT NULL,
    provider             VARCHAR(50) NOT NULL,
    provider_transfer_id VARCHAR(255) NULL,
    amount               NUMERIC     NOT NULL,
    currency_code        VARCHAR(10) NOT NULL,
    status               bill_payout_status_enum NOT NULL DEFAULT 'Pending'::bill_payout_status_enum,
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
    credit_currency_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance_event_id UUID,
    settlement_number VARCHAR(50) NOT NULL,
    settlement_run_id UUID,
    institution_bill_id UUID,
    country_code VARCHAR(10) NOT NULL,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_entity_id) REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES core.credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
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
    credit_currency_id UUID NOT NULL,
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

-- ─────────────────────────────────────────────────────────────
-- IAM admin grants — applied when GCP IAM user exists
-- Role: viandallc@gmail.com (Cloud SQL IAM user for Cloud SQL Studio / DBeaver)
-- Safe to run locally: IF EXISTS check skips if role is absent
--
-- After a full rebuild (DROP SCHEMA / fresh objects), ALTER DEFAULT PRIVILEGES alone
-- does not grant on tables that already exist; GRANT ALL ON ALL TABLES/SEQUENCES/FUNCTIONS
-- must run after CREATE so IAM access is restored every time this script is applied.
-- GRANT USAGE ON SCHEMA public is required for Cloud SQL Studio / clients to resolve public.*.
-- ─────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM pg_roles WHERE rolname = 'viandallc@gmail.com'
    ) THEN
        GRANT USAGE ON SCHEMA core, ops, customer, billing, audit, public TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ops TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA customer TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA billing TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA audit TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA core TO "viandallc@gmail.com";
        GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA core
            GRANT ALL ON TABLES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA ops
            GRANT ALL ON TABLES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA customer
            GRANT ALL ON TABLES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA billing
            GRANT ALL ON TABLES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA audit
            GRANT ALL ON TABLES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT ALL ON TABLES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA core
            GRANT ALL ON SEQUENCES TO "viandallc@gmail.com";
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT ALL ON SEQUENCES TO "viandallc@gmail.com";
    END IF;
END
$$;
