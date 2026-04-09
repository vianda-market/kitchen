-- Migration 0001: Restaurant Lead (vetting pipeline Phase 1)
--
-- Adds:
--   - restaurant_lead_status_enum
--   - restaurant_lead_referral_source_enum
--   - core.restaurant_lead table
--   - core.restaurant_lead_cuisine junction table
--
-- Rollback notes (manual):
--   DROP TABLE IF EXISTS core.restaurant_lead_cuisine CASCADE;
--   DROP TABLE IF EXISTS core.restaurant_lead CASCADE;
--   DROP TYPE IF EXISTS restaurant_lead_referral_source_enum CASCADE;
--   DROP TYPE IF EXISTS restaurant_lead_status_enum CASCADE;

-- Enum: lead lifecycle status
CREATE TYPE restaurant_lead_status_enum AS ENUM (
    'submitted',
    'under_review',
    'verification_pending',
    'approved',
    'rejected'
);

-- Enum: how the lead found us
CREATE TYPE restaurant_lead_referral_source_enum AS ENUM (
    'ad',
    'referral',
    'search',
    'other'
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
    reviewed_by UUID REFERENCES core.user_info(user_id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    -- Link to institution created on approval
    institution_id UUID REFERENCES core.institution_info(institution_id) ON DELETE SET NULL,
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
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_restaurant_lead_status ON core.restaurant_lead(lead_status);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_country ON core.restaurant_lead(country_code);
CREATE INDEX IF NOT EXISTS idx_restaurant_lead_email ON core.restaurant_lead(contact_email);

\echo 'Creating table: core.restaurant_lead_cuisine'
CREATE TABLE IF NOT EXISTS core.restaurant_lead_cuisine (
    restaurant_lead_id UUID NOT NULL REFERENCES core.restaurant_lead(restaurant_lead_id) ON DELETE CASCADE,
    cuisine_id UUID NOT NULL REFERENCES ops.cuisine(cuisine_id) ON DELETE CASCADE,
    PRIMARY KEY (restaurant_lead_id, cuisine_id)
);
