-- idx_role_history_role_id removed - role_history table deprecated

CREATE INDEX IF NOT EXISTS idx_institution_history_institution_id ON audit.institution_history(institution_id);

CREATE INDEX IF NOT EXISTS idx_user_history_user_id ON audit.user_history(user_id);

CREATE INDEX IF NOT EXISTS idx_user_info_employer_address_id ON core.user_info(employer_address_id) WHERE employer_address_id IS NOT NULL;

-- Drop legacy UNIQUE constraints if present (e.g. from pre-migration DBs). Fresh schema has no UNIQUE on username/email.
ALTER TABLE core.user_info DROP CONSTRAINT IF EXISTS user_info_username_key;
ALTER TABLE core.user_info DROP CONSTRAINT IF EXISTS user_info_email_key;

-- Partial unique indexes: only non-archived users must have unique username/email.
-- Archived records do not count toward uniqueness, allowing new signup with same username after account deletion.
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_info_username_active
    ON core.user_info(username) WHERE is_archived = FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_info_email_active
    ON core.user_info(email) WHERE is_archived = FALSE;

-- customer.email_change_request: one active pending per user; unique active codes; one pending claim per new_email
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_change_request_user_active
    ON customer.email_change_request(user_id) WHERE is_used = FALSE AND is_archived = FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_change_request_code_active
    ON customer.email_change_request(verification_code) WHERE is_used = FALSE AND is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_email_change_request_user_id ON customer.email_change_request(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_change_request_email_active
    ON customer.email_change_request(new_email) WHERE is_used = FALSE AND is_archived = FALSE;

CREATE INDEX IF NOT EXISTS idx_institution_entity_history_institution_entity_id ON audit.institution_entity_history(institution_entity_id);

CREATE INDEX IF NOT EXISTS idx_address_history_address_id ON audit.address_history(address_id);

CREATE INDEX IF NOT EXISTS idx_address_location ON core.address_info(country_code, province, city);

CREATE INDEX IF NOT EXISTS idx_payment_method_address_id ON customer.payment_method(address_id);

CREATE INDEX IF NOT EXISTS idx_restaurant_id_active ON ops.restaurant_info(restaurant_id, is_archived);

CREATE INDEX IF NOT EXISTS idx_restaurant_history_restaurant_id ON audit.restaurant_history(restaurant_id);

CREATE INDEX IF NOT EXISTS idx_plate_selection_active ON customer.plate_selection_info(plate_selection_id, kitchen_day);

-- Partial unique index: one non-archived plate selection per (user_id, kitchen_day).
-- Archived records do not count; user can create new selection after cancelling.
CREATE UNIQUE INDEX IF NOT EXISTS idx_plate_selection_user_kitchen_day_active
    ON customer.plate_selection_info(user_id, kitchen_day) WHERE is_archived = FALSE;

CREATE INDEX IF NOT EXISTS idx_plate_pickup_live_active ON customer.plate_pickup_live(plate_pickup_id, is_archived);

CREATE INDEX IF NOT EXISTS idx_product_history_product_id ON audit.product_history(product_id);

CREATE INDEX IF NOT EXISTS idx_plan_history_plan_id ON audit.plan_history(plan_id);

CREATE INDEX IF NOT EXISTS idx_subscription_history_subscription_id ON audit.subscription_history(subscription_id);

CREATE INDEX IF NOT EXISTS idx_client_bill_history_client_bill_id ON audit.client_bill_history(client_bill_id);

CREATE INDEX IF NOT EXISTS idx_restaurant_balance_history_restaurant_id ON audit.restaurant_balance_history(restaurant_id);

CREATE INDEX IF NOT EXISTS idx_institution_bill_history_institution_bill_id ON audit.institution_bill_history(institution_bill_id);

CREATE INDEX IF NOT EXISTS idx_institution_settlement_history_settlement_id ON audit.institution_settlement_history(settlement_id);
CREATE INDEX IF NOT EXISTS idx_institution_settlement_history_current ON audit.institution_settlement_history(settlement_id, is_current);

CREATE INDEX IF NOT EXISTS idx_credit_currency_history_credit_currency_id ON audit.credit_currency_history(credit_currency_id);

CREATE INDEX IF NOT EXISTS idx_plate_kitchen_days_plate_id ON ops.plate_kitchen_days(plate_id);
CREATE INDEX IF NOT EXISTS idx_plate_kitchen_days_kitchen_day ON ops.plate_kitchen_days(kitchen_day);
CREATE INDEX IF NOT EXISTS idx_plate_kitchen_days_active ON ops.plate_kitchen_days(plate_id, kitchen_day, is_archived);

-- Partial unique index: only one active (non-archived) record per (plate_id, kitchen_day).
-- Archived records do not count toward uniqueness, allowing edit Friday->Tuesday when Tuesday was archived.
CREATE UNIQUE INDEX IF NOT EXISTS idx_plate_kitchen_days_plate_day_active
    ON ops.plate_kitchen_days(plate_id, kitchen_day) WHERE is_archived = FALSE;

-- Optimized indexes for ops.restaurant_holidays (as per RESTAURANT_HOLIDAY_API_PLAN.md)
-- Drop legacy UNIQUE constraint if present. Partial unique index below enforces uniqueness only for non-archived rows.
ALTER TABLE ops.restaurant_holidays DROP CONSTRAINT IF EXISTS restaurant_holidays_restaurant_id_holiday_date_key;
-- Partial unique index: only one active (non-archived) record per (restaurant_id, holiday_date).
-- Archived records do not count toward uniqueness, allowing re-add of same holiday date after archiving.
CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_holidays_restaurant_date_active
    ON ops.restaurant_holidays(restaurant_id, holiday_date) WHERE is_archived = FALSE;
DROP INDEX IF EXISTS idx_restaurant_holidays_recurring;
CREATE INDEX IF NOT EXISTS idx_restaurant_holidays_recurring
    ON ops.restaurant_holidays(restaurant_id, recurring_month, recurring_day)
    WHERE is_recurring AND NOT is_archived;

CREATE INDEX IF NOT EXISTS idx_restaurant_holidays_history_holiday_id ON audit.restaurant_holidays_history(holiday_id);
CREATE INDEX IF NOT EXISTS idx_restaurant_holidays_history_current ON audit.restaurant_holidays_history(holiday_id, is_current);

CREATE INDEX IF NOT EXISTS idx_plate_kitchen_days_history_plate_kitchen_day_id ON audit.plate_kitchen_days_history(plate_kitchen_day_id);
CREATE INDEX IF NOT EXISTS idx_plate_kitchen_days_history_current ON audit.plate_kitchen_days_history(plate_kitchen_day_id, is_current);

-- customer.plate_review_info: partial unique index so archived reviews do not block new reviews for same pickup
ALTER TABLE customer.plate_review_info DROP CONSTRAINT IF EXISTS plate_review_info_plate_pickup_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_plate_review_plate_pickup_active
    ON customer.plate_review_info(plate_pickup_id) WHERE is_archived = FALSE;

-- Indexes for status and transaction type history tables removed - tables deprecated

-- Indexes for QR code pickup flow
CREATE INDEX IF NOT EXISTS idx_plate_pickup_live_user_status ON customer.plate_pickup_live(user_id, status, is_archived) WHERE is_archived = false;
CREATE INDEX IF NOT EXISTS idx_qr_code_id ON ops.qr_code(qr_code_id);
CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_status ON billing.restaurant_transaction(status, was_collected);

-- Restaurant indexes
CREATE INDEX IF NOT EXISTS idx_restaurant_info_institution_id ON ops.restaurant_info(institution_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_info_institution_entity_id ON ops.restaurant_info(institution_entity_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_info_address_id ON ops.restaurant_info(address_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_info_status ON ops.restaurant_info(status) WHERE NOT is_archived;

-- Address indexes
-- Single column indexes for foreign keys and common filters
CREATE INDEX IF NOT EXISTS idx_address_info_institution_id ON core.address_info(institution_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_user_id ON core.address_info(user_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_status ON core.address_info(status) WHERE NOT is_archived;

-- GIN index for array containment queries on address_type (e.g., WHERE 'Restaurant' = ANY(address_type))
CREATE INDEX IF NOT EXISTS idx_address_info_address_type ON core.address_info USING GIN(address_type) WHERE NOT is_archived;

-- Location indexes for UI filtering (individual columns for dropdowns/filters)
CREATE INDEX IF NOT EXISTS idx_address_info_country_code ON core.address_info(country_code) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_province ON core.address_info(province) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_city ON core.address_info(city) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_postal_code ON core.address_info(postal_code) WHERE NOT is_archived;

-- Partial index for employer_id queries (only non-NULL, non-archived addresses)
CREATE INDEX IF NOT EXISTS idx_address_info_employer_id ON core.address_info(employer_id) WHERE employer_id IS NOT NULL AND NOT is_archived;

-- core.address_subpremise: unique (address_id, user_id) already enforced; index for lookups by address_id
CREATE INDEX IF NOT EXISTS idx_address_subpremise_address_id ON core.address_subpremise(address_id);
CREATE INDEX IF NOT EXISTS idx_address_subpremise_user_id ON core.address_subpremise(user_id);

-- Composite indexes for common query patterns
-- For location-based filtering (country_code, province, city, postal_code) - matches common UI filter patterns
CREATE INDEX IF NOT EXISTS idx_address_info_location ON core.address_info(country_code, province, city, postal_code) WHERE NOT is_archived;
-- For filtering by country_code + province (common hierarchical filter)
CREATE INDEX IF NOT EXISTS idx_address_info_country_province ON core.address_info(country_code, province) WHERE NOT is_archived;
-- For filtering by country_code + province + city (refined location filter)
CREATE INDEX IF NOT EXISTS idx_address_info_country_province_city ON core.address_info(country_code, province, city) WHERE NOT is_archived;

-- Discretionary history: look up creator (CREATE row) by discretionary_id and operation
CREATE INDEX IF NOT EXISTS idx_discretionary_history_discretionary_operation ON audit.discretionary_history(discretionary_id, operation);