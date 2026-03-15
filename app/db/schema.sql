CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pgtap extension (optional - only needed for test files in app/db/tests/)
-- Uncomment and install pgtap if you need to run database tests:
-- CREATE EXTENSION IF NOT EXISTS pgtap;

-- UUID7: All new rows use uuidv7() for time-ordered IDs.
-- PostgreSQL 18+: uuidv7() is built-in. No action needed.
-- PostgreSQL < 18: run docs/archived/db_migrations/uuid7_function.sql before this schema.

-- =============================================================================
-- DROP TABLES FIRST (with CASCADE to handle dependencies)
-- =============================================================================

-- Drop dependent/history/resolution tables first
DROP TABLE IF EXISTS archival_config_history CASCADE;
DROP TABLE IF EXISTS archival_config CASCADE;
DROP TABLE IF EXISTS client_bill_history CASCADE;
DROP TABLE IF EXISTS subscription_history CASCADE;
DROP TABLE IF EXISTS user_history CASCADE;
DROP TABLE IF EXISTS institution_history CASCADE;
DROP TABLE IF EXISTS institution_entity_history CASCADE;
DROP TABLE IF EXISTS address_history CASCADE;
DROP TABLE IF EXISTS restaurant_history CASCADE;
DROP TABLE IF EXISTS qr_code CASCADE;  -- Removed qr_code_history and qr_code_info
DROP TABLE IF EXISTS product_history CASCADE;
DROP TABLE IF EXISTS plan_history CASCADE;
DROP TABLE IF EXISTS institution_bill_history CASCADE;
DROP TABLE IF EXISTS discretionary_resolution_history CASCADE;
DROP TABLE IF EXISTS discretionary_resolution_info CASCADE;
DROP TABLE IF EXISTS restaurant_balance_history CASCADE;
DROP TABLE IF EXISTS plate_history CASCADE;
DROP TABLE IF EXISTS market_history CASCADE;
DROP TABLE IF EXISTS city_info CASCADE;
DROP TABLE IF EXISTS market_info CASCADE;
DROP TABLE IF EXISTS credit_currency_history CASCADE;
DROP TABLE IF EXISTS role_history CASCADE;
DROP TABLE IF EXISTS geolocation_history CASCADE;
DROP TABLE IF EXISTS status_info CASCADE;
DROP TABLE IF EXISTS status_history CASCADE;
DROP TABLE IF EXISTS transaction_type_info CASCADE;
DROP TABLE IF EXISTS transaction_type_history CASCADE;
DROP TABLE IF EXISTS employer_history CASCADE;
DROP TABLE IF EXISTS national_holidays_history CASCADE;
DROP TABLE IF EXISTS national_holidays CASCADE;
DROP TABLE IF EXISTS restaurant_holidays_history CASCADE;
DROP TABLE IF EXISTS restaurant_holidays CASCADE;
DROP TABLE IF EXISTS plate_kitchen_days_history CASCADE;
DROP TABLE IF EXISTS plate_kitchen_days CASCADE;
DROP TABLE IF EXISTS pickup_preferences CASCADE;

-- Drop tables that are children of other base tables
-- credit_card, bank_account, fintech_wallet, fintech_wallet_auth, appstore_account removed (Stripe/aggregator-only)
DROP TABLE IF EXISTS client_payment_attempt CASCADE;
DROP TABLE IF EXISTS restaurant_transaction CASCADE;
DROP TABLE IF EXISTS institution_payment_attempt CASCADE;
DROP TABLE IF EXISTS discretionary_history CASCADE;
DROP TABLE IF EXISTS discretionary_info CASCADE;
DROP TABLE IF EXISTS client_transaction CASCADE;
DROP TABLE IF EXISTS user_favorite_info CASCADE;
DROP TABLE IF EXISTS plate_review_info CASCADE;
DROP TABLE IF EXISTS plate_pickup_live CASCADE;
DROP TABLE IF EXISTS fintech_wallet_auth CASCADE;

-- Drop remaining base/parent tables
DROP TABLE IF EXISTS coworker_pickup_notification CASCADE;
DROP TABLE IF EXISTS plate_selection_history CASCADE;
DROP TABLE IF EXISTS plate_selection_info CASCADE;
DROP TABLE IF EXISTS plate_selection CASCADE;
DROP TABLE IF EXISTS plate_info CASCADE;
DROP TABLE IF EXISTS client_bill_info CASCADE;
DROP TABLE IF EXISTS subscription_payment CASCADE;
DROP TABLE IF EXISTS subscription_info CASCADE;
DROP TABLE IF EXISTS external_payment_method CASCADE;
DROP TABLE IF EXISTS payment_method CASCADE;
DROP TABLE IF EXISTS product_info CASCADE;
DROP TABLE IF EXISTS plan_info CASCADE;
DROP TABLE IF EXISTS restaurant_info CASCADE;
DROP TABLE IF EXISTS credit_currency_info CASCADE;
DROP TABLE IF EXISTS institution_settlement_history CASCADE;
DROP TABLE IF EXISTS institution_settlement CASCADE;
DROP TABLE IF EXISTS institution_bill_info CASCADE;
DROP TABLE IF EXISTS restaurant_balance_info CASCADE;
DROP TABLE IF EXISTS geolocation_info CASCADE;
DROP TABLE IF EXISTS address_subpremise CASCADE;
DROP TABLE IF EXISTS address_info CASCADE;
DROP TABLE IF EXISTS qr_code CASCADE;
DROP TABLE IF EXISTS institution_entity_info CASCADE;
DROP TABLE IF EXISTS institution_info CASCADE;
DROP TABLE IF EXISTS user_market_assignment CASCADE;
DROP TABLE IF EXISTS user_messaging_preferences CASCADE;
DROP TABLE IF EXISTS user_info CASCADE;
DROP TABLE IF EXISTS employer_info CASCADE;
DROP TABLE IF EXISTS pending_customer_signup CASCADE;
DROP TABLE IF EXISTS credential_recovery CASCADE;
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
    'Rejected'
);

\echo 'Creating enum type: role_type_enum'
CREATE TYPE role_type_enum AS ENUM (
    'Employee',
    'Supplier',
    'Customer'
);

\echo 'Creating enum type: institution_type_enum'
CREATE TYPE institution_type_enum AS ENUM (
    'Employee',
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
    'Employer',
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
CREATE TABLE IF NOT EXISTS national_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuidv7(),
    country_code VARCHAR(3) NOT NULL,
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER, -- For recurring holidays (e.g., Independence Day)
    recurring_day INTEGER,   -- For recurring holidays (e.g., Independence Day)
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient holiday lookups
CREATE INDEX IF NOT EXISTS idx_national_holidays_country_date ON national_holidays(country_code, holiday_date) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_national_holidays_recurring ON national_holidays(country_code, recurring_month, recurring_day) WHERE is_recurring AND NOT is_archived;

-- National holidays history table
CREATE TABLE IF NOT EXISTS national_holidays_history (
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
    history_date TIMESTAMPTZ DEFAULT NOW()
);

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - enums are now stored directly on entities (user_info, etc.)

\echo 'Creating table: institution_info'
CREATE TABLE IF NOT EXISTS institution_info (
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

\echo 'Creating table: address_info'
CREATE TABLE IF NOT EXISTS address_info (
    address_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    user_id UUID NULL,  -- Required only for Customer Comensal home/other; nullable for Supplier, Employee, Employer
    employer_id UUID NULL,  -- Links address to employer (nullable)
    address_type address_type_enum[] NOT NULL,
    country_code VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2 (AR, PE, CL); country_name from market_info via JOIN
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
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT
    -- Note: user_id and modified_by foreign keys removed to resolve circular dependency
    -- with employer_info -> address_info -> user_info dependency chain
    -- Note: employer_id foreign key will be added after employer_info table is created
    -- Note: country_code foreign key will be added after market_info table is created
    -- Note: floor, apartment_unit, is_default moved to address_subpremise
);

\echo 'Creating table: address_history'
-- Use case: address_info still has updates (address_type from linkages, is_archived, status, modified_by/date).
-- Address core (street, city, province, etc.) is immutable; subpremise edits (floor, unit, is_default) are in address_subpremise.
CREATE TABLE IF NOT EXISTS address_history (
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
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT
    -- Note: modified_by foreign key removed to resolve circular dependency
    -- Note: floor, apartment_unit, is_default in address_subpremise
);

\echo 'Creating table: employer_info'
CREATE TABLE IF NOT EXISTS employer_info (
    employer_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(100) NOT NULL,
    address_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT
);

\echo 'Adding foreign key constraint: address_info.employer_id -> employer_info.employer_id'
ALTER TABLE address_info 
ADD CONSTRAINT fk_address_info_employer_id 
FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE SET NULL;

\echo 'Creating table: employer_history'
CREATE TABLE IF NOT EXISTS employer_history (
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
    FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE RESTRICT
);

\echo 'Creating table: user_info'
CREATE TABLE IF NOT EXISTS user_info (
    user_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,
    role_name role_name_enum NOT NULL,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    cellphone VARCHAR(20),
    -- Employer tracking fields (only applicable to Customer role_type)
    employer_id UUID NULL, -- For end-customers: links to their employer
    employer_address_id UUID NULL REFERENCES address_info(address_id) ON DELETE SET NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE SET NULL
);

\echo 'Creating table: address_subpremise'
CREATE TABLE IF NOT EXISTS address_subpremise (
    subpremise_id UUID PRIMARY KEY DEFAULT uuidv7(),
    address_id UUID NOT NULL REFERENCES address_info(address_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES user_info(user_id) ON DELETE CASCADE,
    floor VARCHAR(50) NULL,
    apartment_unit VARCHAR(20) NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (address_id, user_id)
);

\echo 'Creating table: credit_currency_info'
CREATE TABLE IF NOT EXISTS credit_currency_info (
    credit_currency_id UUID PRIMARY KEY DEFAULT uuidv7(),
    currency_name VARCHAR(50) NOT NULL,
    currency_code VARCHAR(10) NOT NULL UNIQUE,
    credit_value NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);


\echo 'Creating table: credit_currency_history'
CREATE TABLE IF NOT EXISTS credit_currency_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    credit_currency_id UUID NOT NULL,
    currency_name VARCHAR(50) NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    credit_value NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: market_info'
CREATE TABLE IF NOT EXISTS market_info (
    market_id UUID PRIMARY KEY DEFAULT uuidv7(),
    country_name VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(2) NOT NULL UNIQUE,  -- ISO 3166-1 alpha-2: AR, PE, CL
    credit_currency_id UUID NOT NULL,         -- FK to credit_currency_info
    timezone VARCHAR(50) NOT NULL,            -- e.g., 'America/Argentina/Buenos_Aires'
    kitchen_close_time TIME NOT NULL DEFAULT '13:30',  -- Order cutoff local time (e.g. 1:30 PM); B2B manageable
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

-- Add foreign key constraint from address_info to market_info (deferred to avoid circular dependency)
\echo 'Adding foreign key: address_info.country_code -> market_info.country_code'
ALTER TABLE address_info ADD CONSTRAINT fk_address_country_code FOREIGN KEY (country_code) REFERENCES market_info(country_code) ON DELETE RESTRICT;

\echo 'Creating table: market_history'
CREATE TABLE IF NOT EXISTS market_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    credit_currency_id UUID NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    kitchen_close_time TIME NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: city_info'
CREATE TABLE IF NOT EXISTS city_info (
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
    FOREIGN KEY (country_code) REFERENCES market_info(country_code) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Adding user_info.market_id (required: one market per user, v1)'
ALTER TABLE user_info ADD COLUMN market_id UUID NOT NULL REFERENCES market_info(market_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_user_info_market_id ON user_info(market_id);

\echo 'Adding user_info.stripe_customer_id (Stripe Customer for saved payment methods)'
ALTER TABLE user_info ADD COLUMN stripe_customer_id VARCHAR(255) NULL;

CREATE INDEX IF NOT EXISTS idx_city_info_country_code ON city_info(country_code) WHERE NOT is_archived;

\echo 'Adding user_info.city_id (user primary city for scoping; NOT NULL, default Global for B2B)'
ALTER TABLE user_info ADD COLUMN city_id UUID NOT NULL DEFAULT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' REFERENCES city_info(city_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_user_info_city_id ON user_info(city_id);

\echo 'Adding institution_info.market_id (required: every institution has a market — Global, single, or multi; default Global for backfill)'
ALTER TABLE institution_info ADD COLUMN market_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES market_info(market_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_institution_info_market_id ON institution_info(market_id);

\echo 'Creating table: user_market_assignment (v2: multi-market per user)'
CREATE TABLE IF NOT EXISTS user_market_assignment (
    assignment_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL REFERENCES user_info(user_id) ON DELETE CASCADE,
    market_id UUID NOT NULL REFERENCES market_info(market_id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, market_id)
);
CREATE INDEX IF NOT EXISTS idx_user_market_assignment_user_id ON user_market_assignment(user_id);
CREATE INDEX IF NOT EXISTS idx_user_market_assignment_market_id ON user_market_assignment(market_id);

\echo 'Creating table: user_messaging_preferences'
CREATE TABLE IF NOT EXISTS user_messaging_preferences (
    user_id UUID PRIMARY KEY REFERENCES user_info(user_id) ON DELETE CASCADE,
    notify_coworker_pickup_alert BOOLEAN NOT NULL DEFAULT TRUE,
    notify_plate_readiness_alert BOOLEAN NOT NULL DEFAULT TRUE,
    notify_promotions_push BOOLEAN NOT NULL DEFAULT TRUE,
    notify_promotions_email BOOLEAN NOT NULL DEFAULT TRUE,
    coworkers_can_see_my_orders BOOLEAN NOT NULL DEFAULT TRUE,
    can_participate_in_plate_pickups BOOLEAN NOT NULL DEFAULT TRUE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

\echo 'Creating table: institution_history'
CREATE TABLE IF NOT EXISTS institution_history (
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
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT
);

\echo 'Creating table: user_history'
CREATE TABLE IF NOT EXISTS user_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,
    role_name role_name_enum NOT NULL,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    cellphone VARCHAR(20),
    employer_institution_id UUID NULL, -- For end-customers: links to their employer's institution
    market_id UUID NOT NULL,
    city_id UUID NOT NULL,
    stripe_customer_id VARCHAR(255) NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: credential_recovery'
CREATE TABLE IF NOT EXISTS credential_recovery (
    credential_recovery_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    recovery_code VARCHAR(10) NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_date TIMESTAMPTZ,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_credential_recovery_code ON credential_recovery(recovery_code);
CREATE INDEX IF NOT EXISTS idx_credential_recovery_user_id ON credential_recovery(user_id);

\echo 'Creating table: pending_customer_signup'
CREATE TABLE IF NOT EXISTS pending_customer_signup (
    pending_id UUID PRIMARY KEY DEFAULT uuidv7(),
    email VARCHAR(100) NOT NULL,
    verification_code VARCHAR(10) NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    username VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    cellphone VARCHAR(20),
    market_id UUID NOT NULL REFERENCES market_info(market_id) ON DELETE RESTRICT,
    city_id UUID NOT NULL REFERENCES city_info(city_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_customer_signup_code ON pending_customer_signup(verification_code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_customer_signup_email_active ON pending_customer_signup(email) WHERE used = FALSE;
CREATE INDEX IF NOT EXISTS idx_pending_customer_signup_expiry ON pending_customer_signup(token_expiry);

\echo 'Creating table: geolocation_info'
CREATE TABLE IF NOT EXISTS geolocation_info (
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
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: geolocation_history'
CREATE TABLE IF NOT EXISTS geolocation_history (
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
    FOREIGN KEY (geolocation_id) REFERENCES geolocation_info(geolocation_id) ON DELETE CASCADE
);

\echo 'Creating table: institution_entity_info'
CREATE TABLE IF NOT EXISTS institution_entity_info (
    institution_entity_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_id UUID NOT NULL,
    address_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    tax_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_entity_history'
CREATE TABLE IF NOT EXISTS institution_entity_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id UUID NOT NULL,
    institution_id UUID,
    address_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    tax_id VARCHAR(50),
    name VARCHAR(100),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_info'
CREATE TABLE IF NOT EXISTS restaurant_info (
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
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_history'
CREATE TABLE IF NOT EXISTS restaurant_history (
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
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: qr_code'
CREATE TABLE IF NOT EXISTS qr_code (
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
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: product_info'
CREATE TABLE IF NOT EXISTS product_info (
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
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: product_history'
CREATE TABLE IF NOT EXISTS product_history (
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
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_info'
CREATE TABLE IF NOT EXISTS plate_info (
    plate_id UUID PRIMARY KEY DEFAULT uuidv7(),
    product_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit INTEGER NOT NULL,
    delivery_time_minutes INTEGER NOT NULL DEFAULT 15,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_holidays'
CREATE TABLE IF NOT EXISTS restaurant_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuidv7(),
    restaurant_id UUID NOT NULL,
    country VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(100),
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month_day VARCHAR(10), -- e.g., "12-25" for Christmas, "01-01" for New Year
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
    -- Uniqueness (restaurant_id, holiday_date) enforced only for non-archived rows via partial unique index in index.sql
);

\echo 'Creating table: restaurant_holidays_history'
CREATE TABLE IF NOT EXISTS restaurant_holidays_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    holiday_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    country VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(100),
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month_day VARCHAR(10),
    status status_enum NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation audit_operation_enum NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);

\echo 'Creating table: plate_kitchen_days'
CREATE TABLE IF NOT EXISTS plate_kitchen_days (
    plate_kitchen_day_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
    -- Uniqueness (plate_id, kitchen_day) enforced only for non-archived rows via partial unique index in index.sql
);

\echo 'Creating table: plate_kitchen_days_history'
CREATE TABLE IF NOT EXISTS plate_kitchen_days_history (
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

\echo 'Creating table: plate_history'
CREATE TABLE IF NOT EXISTS plate_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_id UUID NOT NULL,
    product_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit INTEGER NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_selection_info'
CREATE TABLE IF NOT EXISTS plate_selection_info (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (qr_code_id) REFERENCES qr_code(qr_code_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_selection_history'
CREATE TABLE IF NOT EXISTS plate_selection_history (
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
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_selection_history_plate_selection ON plate_selection_history(plate_selection_id) WHERE is_current = TRUE;

\echo 'Creating table: coworker_pickup_notification'
CREATE TABLE IF NOT EXISTS coworker_pickup_notification (
    notification_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plate_selection_id UUID NOT NULL,
    notifier_user_id UUID NOT NULL,
    notified_user_id UUID NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (notifier_user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (notified_user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_coworker_pickup_notification_plate_selection ON coworker_pickup_notification(plate_selection_id);

\echo 'Creating table: plate_pickup_live'
CREATE TABLE IF NOT EXISTS plate_pickup_live (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (qr_code_id) REFERENCES qr_code(qr_code_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_review_info'
CREATE TABLE IF NOT EXISTS plate_review_info (
    plate_review_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    plate_pickup_id UUID NOT NULL,
    stars_rating INTEGER NOT NULL CHECK (stars_rating >= 1 AND stars_rating <= 5),
    portion_size_rating INTEGER NOT NULL CHECK (portion_size_rating >= 1 AND portion_size_rating <= 3),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_pickup_id) REFERENCES plate_pickup_live(plate_pickup_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_plate_review_plate_id ON plate_review_info(plate_id) WHERE NOT is_archived;

\echo 'Creating table: user_favorite_info'
CREATE TABLE IF NOT EXISTS user_favorite_info (
    favorite_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL,
    entity_type favorite_entity_type_enum NOT NULL,
    entity_id UUID NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, entity_type, entity_id),
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_user_favorite_user_entity ON user_favorite_info(user_id, entity_type);

\echo 'Creating table: pickup_preferences'
CREATE TABLE IF NOT EXISTS pickup_preferences (
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
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (matched_with_preference_id) REFERENCES pickup_preferences(preference_id) ON DELETE SET NULL,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plan_info'
CREATE TABLE IF NOT EXISTS plan_info (
    plan_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit_worth DOUBLE PRECISION NOT NULL,
    rollover BOOLEAN NOT NULL DEFAULT TRUE,
    rollover_cap NUMERIC,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_plan_info_not_global_market CHECK (market_id != '00000000-0000-0000-0000-000000000001'::uuid)
);

\echo 'Creating table: plan_history'
CREATE TABLE IF NOT EXISTS plan_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    plan_id UUID NOT NULL,
    market_id UUID NOT NULL,
    name VARCHAR(100),
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit_worth DOUBLE PRECISION NOT NULL,
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
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: discretionary_info'
CREATE TABLE IF NOT EXISTS discretionary_info (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    -- Ensure either user_id (Client) or restaurant_id (Supplier) is provided
    CHECK ((user_id IS NOT NULL AND restaurant_id IS NULL) OR (user_id IS NULL AND restaurant_id IS NOT NULL))
);

\echo 'Creating table: discretionary_history'
CREATE TABLE IF NOT EXISTS discretionary_history (
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
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE CASCADE
);

\echo 'Creating table: discretionary_resolution_info'
CREATE TABLE IF NOT EXISTS discretionary_resolution_info (
    approval_id UUID PRIMARY KEY DEFAULT uuidv7(),
    discretionary_id UUID NOT NULL,
    resolution discretionary_status_enum NOT NULL DEFAULT 'Pending'::discretionary_status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    resolved_by UUID NOT NULL,
    resolved_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolution_comment TEXT,
    FOREIGN KEY (resolved_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE RESTRICT
);

\echo 'Creating table: discretionary_resolution_history'
CREATE TABLE IF NOT EXISTS discretionary_resolution_history (
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
    FOREIGN KEY (approval_id) REFERENCES discretionary_resolution_info(approval_id) ON DELETE CASCADE
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
        INSERT INTO discretionary_history (
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
        INSERT INTO discretionary_history (
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
        INSERT INTO discretionary_history (
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

DROP TRIGGER IF EXISTS discretionary_info_history_trigger ON discretionary_info;
CREATE TRIGGER discretionary_info_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON discretionary_info
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
        INSERT INTO discretionary_resolution_history (
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
        INSERT INTO discretionary_resolution_history (
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
        INSERT INTO discretionary_resolution_history (
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

DROP TRIGGER IF EXISTS discretionary_resolution_info_history_trigger ON discretionary_resolution_info;
CREATE TRIGGER discretionary_resolution_info_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON discretionary_resolution_info
FOR EACH ROW EXECUTE FUNCTION discretionary_resolution_info_history_trigger();

\echo 'Creating table: client_transaction'
CREATE TABLE IF NOT EXISTS client_transaction (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: subscription_info'
CREATE TABLE IF NOT EXISTS subscription_info (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

-- Ensure one active subscription per user per market
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_market_active 
    ON subscription_info(user_id, market_id) 
    WHERE is_archived = FALSE;

-- Index for querying subscriptions by market
CREATE INDEX IF NOT EXISTS idx_subscription_market 
    ON subscription_info(market_id) 
    WHERE is_archived = FALSE;

\echo 'Creating table: subscription_history'
CREATE TABLE IF NOT EXISTS subscription_history (
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
    FOREIGN KEY (subscription_id) REFERENCES subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: subscription_payment'
CREATE TABLE IF NOT EXISTS subscription_payment (
    subscription_payment_id UUID PRIMARY KEY DEFAULT uuidv7(),
    subscription_id UUID NOT NULL,
    payment_provider VARCHAR(50) NOT NULL DEFAULT 'stripe',
    external_payment_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES subscription_info(subscription_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_subscription_id ON subscription_payment(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_external_id ON subscription_payment(external_payment_id);

\echo 'Creating table: payment_method'
CREATE TABLE IF NOT EXISTS payment_method (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT
);

\echo 'Creating table: external_payment_method'
CREATE TABLE IF NOT EXISTS external_payment_method (
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
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_external_payment_method_payment_method_id ON external_payment_method(payment_method_id);
CREATE INDEX IF NOT EXISTS idx_external_payment_method_provider ON external_payment_method(provider);

\echo 'Creating table: client_bill_info'
CREATE TABLE IF NOT EXISTS client_bill_info (
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
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_id) REFERENCES subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_payment_id) REFERENCES subscription_payment(subscription_payment_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: client_bill_history'
CREATE TABLE IF NOT EXISTS client_bill_history (
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
    FOREIGN KEY (client_bill_id) REFERENCES client_bill_info(client_bill_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_transaction'
CREATE TABLE IF NOT EXISTS restaurant_transaction (
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
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection_info(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_balance_info'
CREATE TABLE IF NOT EXISTS restaurant_balance_info (
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
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_balance_history'
CREATE TABLE IF NOT EXISTS restaurant_balance_history (
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
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_balance_info(restaurant_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_bill_info'
CREATE TABLE IF NOT EXISTS institution_bill_info (
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
    stripe_payout_id VARCHAR(255),
    payout_completed_at TIMESTAMPTZ,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_bill_history'
CREATE TABLE IF NOT EXISTS institution_bill_history (
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
    stripe_payout_id VARCHAR(255),
    payout_completed_at TIMESTAMPTZ,
    created_date TIMESTAMPTZ NOT NULL,
    created_by UUID NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_bill_id) REFERENCES institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_settlement'
CREATE TABLE IF NOT EXISTS institution_settlement (
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
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_event_id) REFERENCES restaurant_balance_history(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_bill_id) REFERENCES institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_entity_period ON institution_settlement(institution_entity_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_restaurant_period ON institution_settlement(restaurant_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_bill ON institution_settlement(institution_bill_id);

\echo 'Creating table: institution_settlement_history'
CREATE TABLE IF NOT EXISTS institution_settlement_history (
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
    FOREIGN KEY (settlement_id) REFERENCES institution_settlement(settlement_id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_event_id) REFERENCES restaurant_balance_history(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);
