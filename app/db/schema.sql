CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pgtap extension (optional - only needed for test files in app/db/tests/)
-- Uncomment and install pgtap if you need to run database tests:
-- CREATE EXTENSION IF NOT EXISTS pgtap;

-- Note: PostgreSQL 18+ includes native uuidv7() function
-- If using PostgreSQL 18+, use the native function instead of custom implementation
-- Custom uuid7_function.sql has been removed in favor of native PostgreSQL 18+ support

-- =============================================================================
-- DROP TABLES FIRST (with CASCADE to handle dependencies)
-- =============================================================================

-- Drop dependent/history/resolution tables first
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
DROP TABLE IF EXISTS market_info CASCADE;
DROP TABLE IF EXISTS credit_currency_history CASCADE;
DROP TABLE IF EXISTS role_history CASCADE;
DROP TABLE IF EXISTS geolocation_history CASCADE;
DROP TABLE IF EXISTS status_info CASCADE;
DROP TABLE IF EXISTS status_history CASCADE;
DROP TABLE IF EXISTS transaction_type_info CASCADE;
DROP TABLE IF EXISTS transaction_type_history CASCADE;
DROP TABLE IF EXISTS employer_history CASCADE;

-- Drop tables that are children of other base tables
DROP TABLE IF EXISTS credit_card CASCADE;
DROP TABLE IF EXISTS bank_account CASCADE;
DROP TABLE IF EXISTS appstore_account CASCADE;
DROP TABLE IF EXISTS fintech_wallet CASCADE;
DROP TABLE IF EXISTS client_payment_attempt CASCADE;
DROP TABLE IF EXISTS restaurant_transaction CASCADE;
DROP TABLE IF EXISTS institution_payment_attempt CASCADE;
DROP TABLE IF EXISTS discretionary_history CASCADE;
DROP TABLE IF EXISTS discretionary_info CASCADE;
DROP TABLE IF EXISTS client_transaction CASCADE;
DROP TABLE IF EXISTS plate_pickup_live CASCADE;
DROP TABLE IF EXISTS fintech_wallet_auth CASCADE;
DROP TABLE IF EXISTS fintech_link_assignment CASCADE;
DROP TABLE IF EXISTS fintech_link_info CASCADE;

-- Drop remaining base/parent tables
DROP TABLE IF EXISTS plate_selection CASCADE;
DROP TABLE IF EXISTS plate_info CASCADE;
DROP TABLE IF EXISTS client_bill_info CASCADE;
DROP TABLE IF EXISTS subscription_info CASCADE;
DROP TABLE IF EXISTS payment_method CASCADE;
DROP TABLE IF EXISTS product_info CASCADE;
DROP TABLE IF EXISTS plan_info CASCADE;
DROP TABLE IF EXISTS restaurant_info CASCADE;
DROP TABLE IF EXISTS credit_currency_info CASCADE;
DROP TABLE IF EXISTS institution_bill_info CASCADE;
DROP TABLE IF EXISTS restaurant_balance_info CASCADE;
DROP TABLE IF EXISTS institution_bank_account CASCADE;
DROP TABLE IF EXISTS geolocation_info CASCADE;
DROP TABLE IF EXISTS address_info CASCADE;
DROP TABLE IF EXISTS qr_code CASCADE;
DROP TABLE IF EXISTS institution_entity_info CASCADE;
DROP TABLE IF EXISTS institution_info CASCADE;
DROP TABLE IF EXISTS user_info CASCADE;
DROP TABLE IF EXISTS employer_info CASCADE;
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
DROP TYPE IF EXISTS status_enum CASCADE;
DROP TYPE IF EXISTS address_type_enum CASCADE;

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
    'Complete',
    'Cancelled',
    'Processed'
);

\echo 'Creating enum type: role_type_enum'
CREATE TYPE role_type_enum AS ENUM (
    'Employee',
    'Supplier',
    'Customer'
);

\echo 'Creating enum type: role_name_enum'
CREATE TYPE role_name_enum AS ENUM (
    'Admin',
    'Super Admin',
    'Management',
    'Operator',
    'Comensal'
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
    'self',
    'for_others',
    'by_others'
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

-- =============================================================================
-- CREATE TABLES (enum types now exist)
-- =============================================================================

-- National holidays table to prevent kitchen operations on these days
CREATE TABLE IF NOT EXISTS national_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(3) NOT NULL,
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER, -- For recurring holidays (e.g., Independence Day)
    recurring_day INTEGER,   -- For recurring holidays (e.g., Independence Day)
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ DEFAULT NOW(),
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient holiday lookups
CREATE INDEX IF NOT EXISTS idx_national_holidays_country_date ON national_holidays(country_code, holiday_date) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_national_holidays_recurring ON national_holidays(country_code, recurring_month, recurring_day) WHERE is_recurring AND NOT is_archived;

-- National holidays history table
CREATE TABLE IF NOT EXISTS national_holidays_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ DEFAULT NOW(),
    history_date TIMESTAMPTZ DEFAULT NOW()
);

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - enums are now stored directly on entities (user_info, etc.)

\echo 'Creating table: institution_info'
CREATE TABLE institution_info (
    institution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

\echo 'Creating table: address_info'
CREATE TABLE address_info (
    address_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    user_id UUID NOT NULL,
    employer_id UUID NULL,  -- Links address to employer (nullable)
    address_type address_type_enum[] NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    floor VARCHAR(50), -- Floor number or 'Main Floor' or null
    country_name VARCHAR(100) NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    province VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    street_type VARCHAR(50) NOT NULL,
    street_name VARCHAR(100) NOT NULL,
    building_number VARCHAR(20) NOT NULL,
    apartment_unit VARCHAR(20),
    timezone VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT
    -- Note: user_id and modified_by foreign keys removed to resolve circular dependency
    -- with employer_info -> address_info -> user_info dependency chain
    -- Note: employer_id foreign key will be added after employer_info table is created
    -- Note: country_code foreign key will be added after market_info table is created
);

\echo 'Creating table: address_history'
CREATE TABLE address_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    user_id UUID NOT NULL,
    employer_id UUID NULL,  -- Track employer_id in history
    address_type address_type_enum[],
    is_default BOOLEAN DEFAULT FALSE,
    floor VARCHAR(50),
    country_name VARCHAR(100),
    country_code VARCHAR(3),
    province VARCHAR(50),
    city VARCHAR(50),
    postal_code VARCHAR(20),
    street_type VARCHAR(50),
    street_name VARCHAR(100),
    building_number VARCHAR(20),
    apartment_unit VARCHAR(20),
    timezone VARCHAR(50),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT
    -- Note: modified_by foreign key removed to resolve circular dependency
);

\echo 'Creating table: employer_info'
CREATE TABLE employer_info (
    employer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    address_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT
);

\echo 'Adding foreign key constraint: address_info.employer_id -> employer_info.employer_id'
ALTER TABLE address_info 
ADD CONSTRAINT fk_address_info_employer_id 
FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE SET NULL;

\echo 'Creating table: employer_history'
CREATE TABLE employer_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    employer_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    address_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE RESTRICT
);

\echo 'Creating table: user_info'
CREATE TABLE user_info (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,
    role_name role_name_enum NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    cellphone VARCHAR(20) NOT NULL,
    -- Employer tracking fields (only applicable to Customer role_type)
    employer_id UUID NULL, -- For end-customers: links to their employer
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE SET NULL
);

\echo 'Creating table: credit_currency_info'
CREATE TABLE credit_currency_info (
    credit_currency_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    currency_name VARCHAR(20) NOT NULL,
    currency_code VARCHAR(10) NOT NULL UNIQUE,
    credit_value NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);


\echo 'Creating table: credit_currency_history'
CREATE TABLE credit_currency_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_currency_id UUID NOT NULL,
    currency_name VARCHAR(20) NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    credit_value NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: market_info'
CREATE TABLE market_info (
    market_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_name VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(3) NOT NULL UNIQUE,  -- ISO 3166-1 alpha-3: ARG, PER, CHL
    credit_currency_id UUID NOT NULL,         -- FK to credit_currency_info
    timezone VARCHAR(50) NOT NULL,            -- e.g., 'America/Argentina/Buenos_Aires'
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

-- Add foreign key constraint from address_info to market_info (deferred to avoid circular dependency)
\echo 'Adding foreign key: address_info.country_code -> market_info.country_code'
ALTER TABLE address_info ADD CONSTRAINT fk_address_country_code FOREIGN KEY (country_code) REFERENCES market_info(country_code) ON DELETE RESTRICT;

\echo 'Creating table: market_history'
CREATE TABLE market_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    market_id UUID NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    credit_currency_id UUID NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_history'
CREATE TABLE institution_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    name VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT
);

\echo 'Creating table: user_history'
CREATE TABLE user_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: credential_recovery'
CREATE TABLE credential_recovery (
    token UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    creation_timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expiration_timestamp TIMESTAMPTZ,
    used BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: geolocation_info'
CREATE TABLE geolocation_info (
    geolocation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address_id UUID NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: geolocation_history'
CREATE TABLE geolocation_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    geolocation_id UUID NOT NULL,
    address_id UUID NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMP DEFAULT 'infinity',
    FOREIGN KEY (geolocation_id) REFERENCES geolocation_info(geolocation_id) ON DELETE CASCADE
);

\echo 'Creating table: institution_entity_info'
CREATE TABLE institution_entity_info (
    institution_entity_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    address_id UUID NOT NULL,
    tax_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_entity_history'
CREATE TABLE institution_entity_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_entity_id UUID NOT NULL,
    institution_id UUID,
    address_id UUID NOT NULL,
    tax_id VARCHAR(50),
    name VARCHAR(100),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_info'
CREATE TABLE restaurant_info (
    restaurant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    address_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    cuisine VARCHAR (50),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_history'
CREATE TABLE restaurant_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    address_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    name VARCHAR(100),
    cuisine VARCHAR (50),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: qr_code'
CREATE TABLE qr_code (
    qr_code_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant_id UUID NOT NULL,
    qr_code_payload VARCHAR(255) NOT NULL,
    qr_code_image_url VARCHAR(500) NOT NULL,
    image_storage_path VARCHAR(500) NOT NULL,
    qr_code_checksum VARCHAR(128),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: product_info'
CREATE TABLE product_info (
    product_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    ingredients VARCHAR(255),
    dietary VARCHAR(255),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    image_storage_path VARCHAR(500) NOT NULL DEFAULT 'static/placeholders/product_default.png',
    image_checksum VARCHAR(128) NOT NULL DEFAULT '7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c',
    image_url VARCHAR(500) NOT NULL DEFAULT 'http://localhost:8000/static/placeholders/product_default.png',
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: product_history'
CREATE TABLE product_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_info'
CREATE TABLE plate_info (
    plate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit INTEGER NOT NULL,
    savings INTEGER CHECK (savings BETWEEN 0 AND 100) NOT NULL,
    no_show_discount INTEGER NOT NULL,
    delivery_time_minutes INTEGER NOT NULL DEFAULT 15,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_holidays'
CREATE TABLE restaurant_holidays (
    holiday_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant_id UUID NOT NULL,
    country VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(100),
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month_day VARCHAR(10), -- e.g., "12-25" for Christmas, "01-01" for New Year
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    UNIQUE(restaurant_id, holiday_date)
);

\echo 'Creating table: restaurant_holidays_history'
CREATE TABLE restaurant_holidays_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation audit_operation_enum NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);

\echo 'Creating table: plate_kitchen_days'
CREATE TABLE plate_kitchen_days (
    plate_kitchen_day_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE CASCADE,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    UNIQUE(plate_id, kitchen_day)
);

\echo 'Creating table: plate_kitchen_days_history'
CREATE TABLE plate_kitchen_days_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plate_kitchen_day_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation audit_operation_enum NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);

\echo 'Creating table: plate_history'
CREATE TABLE plate_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plate_id UUID NOT NULL,
    product_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    credit INTEGER NOT NULL,
    savings INTEGER CHECK (savings BETWEEN 0 AND 100) NOT NULL,
    no_show_discount INTEGER NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_selection'
CREATE TABLE plate_selection (
    plate_selection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    plate_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    product_id UUID NOT NULL,
    qr_code_id UUID NOT NULL,
    credit INTEGER NOT NULL,
    kitchen_day kitchen_day_enum NOT NULL,
    pickup_time_range VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (qr_code_id) REFERENCES qr_code(qr_code_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plate_pickup_live'
CREATE TABLE plate_pickup_live (
    plate_pickup_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_id) REFERENCES plate_info(plate_id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES product_info(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (qr_code_id) REFERENCES qr_code(qr_code_id) ON DELETE RESTRICT
);

\echo 'Creating table: pickup_preferences'
CREATE TABLE pickup_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (matched_with_preference_id) REFERENCES pickup_preferences(preference_id) ON DELETE SET NULL,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: plan_info'
CREATE TABLE plan_info (
    plan_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    market_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    rollover BOOLEAN NOT NULL DEFAULT TRUE,
    rollover_cap NUMERIC,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT
);

\echo 'Creating table: plan_history'
CREATE TABLE plan_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id UUID NOT NULL,
    market_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    name VARCHAR(100),
    credit INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    rollover BOOLEAN NOT NULL,
    rollover_cap NUMERIC,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: fintech_link_info'
CREATE TABLE fintech_link_info (
    fintech_link_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id UUID NOT NULL,
    provider VARCHAR(50) NOT NULL, -- e.g., "MercadoPago"
    fintech_link VARCHAR(100) NOT NULL, -- the link to MercadoPago for the plan
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: fintech_link_history'
CREATE TABLE fintech_link_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fintech_link_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    provider VARCHAR(50) NOT NULL,
    fintech_link VARCHAR(100) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    operation audit_operation_enum NOT NULL,
    FOREIGN KEY (fintech_link_id) REFERENCES fintech_link_info(fintech_link_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);


\echo 'Creating table: discretionary_info'
CREATE TABLE discretionary_info (
    discretionary_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,  -- NULL for Supplier requests, required for Client requests
    restaurant_id UUID,  -- NULL for Client requests, required for Supplier requests
    approval_id UUID,
    category VARCHAR(50),
    reason discretionary_reason_enum NOT NULL,
    amount NUMERIC,
    comment TEXT,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    -- Ensure either user_id (Client) or restaurant_id (Supplier) is provided
    CHECK ((user_id IS NOT NULL AND restaurant_id IS NULL) OR (user_id IS NULL AND restaurant_id IS NOT NULL))
);

\echo 'Creating table: discretionary_history'
CREATE TABLE discretionary_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discretionary_id UUID NOT NULL,
    user_id UUID,  -- NULL for Supplier requests, required for Client requests
    restaurant_id UUID,  -- NULL for Client requests, required for Supplier requests
    approval_id UUID,
    category VARCHAR(50),
    reason discretionary_reason_enum NOT NULL,
    amount NUMERIC,
    comment TEXT,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_date TIMESTAMPTZ,
    modified_by UUID,
    operation audit_operation_enum NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID,
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE CASCADE
);

\echo 'Creating table: discretionary_resolution_info'
CREATE TABLE discretionary_resolution_info (
    approval_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discretionary_id UUID NOT NULL,
    resolution VARCHAR(20) NOT NULL DEFAULT 'Pending',
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
CREATE TABLE discretionary_resolution_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    approval_id UUID NOT NULL,
    discretionary_id UUID NOT NULL,
    resolution VARCHAR(20) NOT NULL,
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

CREATE TRIGGER discretionary_resolution_info_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON discretionary_resolution_info
FOR EACH ROW EXECUTE FUNCTION discretionary_resolution_info_history_trigger();

\echo 'Creating table: client_transaction'
CREATE TABLE client_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    source VARCHAR(50) NOT NULL,  -- e.g., 'plate_selection' or 'discretionary_promotion'
    plate_selection_id UUID, -- references a plate_selection record when source = 'order'
    discretionary_id UUID, -- references a discretionary record when source = 'discretionary'
    credit NUMERIC NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: subscription_info'
CREATE TABLE subscription_info (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    market_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    renewal_date TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    balance NUMERIC DEFAULT 0,
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'Pending',  -- 'Active', 'On Hold', 'Pending', 'Expired', 'Cancelled'
    hold_start_date TIMESTAMPTZ,  -- When subscription was put on hold
    hold_end_date TIMESTAMPTZ,    -- When subscription will resume (NULL = indefinite)
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,  -- Keep for backward compatibility
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

-- Ensure one active subscription per user per market
CREATE UNIQUE INDEX idx_user_market_active 
    ON subscription_info(user_id, market_id) 
    WHERE is_archived = FALSE;

-- Index for querying subscriptions by market
CREATE INDEX idx_subscription_market 
    ON subscription_info(market_id) 
    WHERE is_archived = FALSE;

\echo 'Creating table: subscription_history'
CREATE TABLE subscription_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (subscription_id) REFERENCES subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: payment_method'
CREATE TABLE payment_method (
    payment_method_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    method_type VARCHAR(20) NOT NULL,
    method_type_id UUID,
    address_id UUID,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT
);

\echo 'Creating table: credit_Card'
CREATE TABLE credit_card (
    credit_card_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    card_holder_name VARCHAR(100),
    card_number_last_4 VARCHAR(4),
    card_brand VARCHAR(50),
    expiry_date VARCHAR(5),
    credit_card_token VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
);

\echo 'Creating table: bank_account'
CREATE TABLE bank_account (
    bank_account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    account_holder_name VARCHAR(100),
    account_number_last_4 VARCHAR(4),
    bank_name VARCHAR(100),
    routing_number VARCHAR(50),
    account_type VARCHAR(50),
    bank_account_token VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
);

\echo 'Creating table: appstore_account'
CREATE TABLE appstore_account (
    appstore_account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    platform VARCHAR(50),
    account_identifier VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
);

\echo 'Creating table: fintech_link_assignment'
CREATE TABLE fintech_link_assignment (
    fintech_link_assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    fintech_link_id UUID NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT,
    FOREIGN KEY (fintech_link_id) REFERENCES fintech_link_info(fintech_link_id) ON DELETE RESTRICT
);

\echo 'Creating table: fintech_wallet'
CREATE TABLE fintech_wallet (
    fintech_wallet_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    provider VARCHAR(50),
    username VARCHAR(50),
    wallet_id VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
);

\echo 'Creating table: fintech_wallet_auth'
CREATE TABLE fintech_wallet_auth (
    fintech_wallet_auth_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fintech_wallet_id UUID NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL, -- when access_token expires
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fintech_wallet_id) REFERENCES fintech_wallet(fintech_wallet_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: client_payment_attempt'
CREATE TABLE client_payment_attempt (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    amount NUMERIC NOT NULL,
    transaction_result VARCHAR(50) NOT NULL,
    external_transaction_id VARCHAR(255),
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolution_date TIMESTAMPTZ,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT
);

\echo 'Creating table: client_bill_info'
CREATE TABLE client_bill_info (
    client_bill_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id UUID NOT NULL,
    subscription_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    amount NUMERIC NOT NULL,
    currency_code VARCHAR(10),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_id) REFERENCES subscription_info(subscription_id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plan_info(plan_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (payment_id) REFERENCES client_payment_attempt(payment_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: client_bill_history'
CREATE TABLE client_bill_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_bill_id UUID NOT NULL,
    payment_id UUID NOT NULL,
    subscription_id UUID NOT NULL,
    user_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    amount NUMERIC,
    currency_code VARCHAR(10),
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (client_bill_id) REFERENCES client_bill_info(client_bill_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_transaction'
CREATE TABLE restaurant_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (plate_selection_id) REFERENCES plate_selection(plate_selection_id) ON DELETE RESTRICT,
    FOREIGN KEY (discretionary_id) REFERENCES discretionary_info(discretionary_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_balance_info'
CREATE TABLE restaurant_balance_info (
    restaurant_id UUID PRIMARY KEY,
    credit_currency_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT
);

\echo 'Creating table: restaurant_balance_history'
CREATE TABLE restaurant_balance_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    transaction_count INTEGER NOT NULL,
    balance NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_balance_info(restaurant_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_bill_info'
CREATE TABLE institution_bill_info (
    institution_bill_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    payment_id UUID,
    transaction_count INTEGER,
    amount NUMERIC,
    currency_code VARCHAR(10),
    balance_event_id UUID,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    resolution VARCHAR(20) NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurant_info(restaurant_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_event_id) REFERENCES restaurant_balance_history(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_bill_history'
CREATE TABLE institution_bill_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_bill_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    institution_entity_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    credit_currency_id UUID NOT NULL,
    payment_id UUID,
    transaction_count INTEGER,
    amount NUMERIC,
    currency_code VARCHAR(10),
    balance_event_id UUID,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    resolution VARCHAR(20) NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (institution_bill_id) REFERENCES institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_event_id) REFERENCES restaurant_balance_history(event_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_bank_account'
CREATE TABLE institution_bank_account (
    bank_account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_entity_id UUID NOT NULL,
    address_id UUID NOT NULL,
    account_holder_name VARCHAR(100) NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    routing_number VARCHAR(50) NOT NULL,
    account_number VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

\echo 'Creating table: institution_payment_attempt'
CREATE TABLE institution_payment_attempt (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_entity_id UUID NOT NULL,
    bank_account_id UUID NOT NULL,
    institution_bill_id UUID,
    credit_currency_id UUID NOT NULL,
    amount NUMERIC NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    transaction_result VARCHAR(50),
    external_transaction_id VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolution_date TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (institution_entity_id) REFERENCES institution_entity_info(institution_entity_id) ON DELETE RESTRICT,
    FOREIGN KEY (institution_bill_id) REFERENCES institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT,
    FOREIGN KEY (bank_account_id) REFERENCES institution_bank_account(bank_account_id) ON DELETE RESTRICT
);

-- Create indexes for balance_event_id foreign keys
CREATE INDEX idx_institution_bill_balance_event_id ON institution_bill_info(balance_event_id);
CREATE INDEX idx_institution_bill_history_balance_event_id ON institution_bill_history(balance_event_id);