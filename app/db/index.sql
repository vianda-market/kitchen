-- idx_role_history_role_id removed - role_history table deprecated

CREATE INDEX idx_institution_history_institution_id ON institution_history(institution_id);

CREATE INDEX idx_user_history_user_id ON user_history(user_id);

CREATE INDEX idx_institution_entity_history_institution_entity_id ON institution_entity_history(institution_entity_id);

CREATE INDEX idx_address_history_address_id ON address_history(address_id);

CREATE INDEX idx_address_location ON address_info(country_code, province, city);

CREATE INDEX idx_payment_method_address_id ON payment_method(address_id);

CREATE INDEX idx_restaurant_id_active ON restaurant_info(restaurant_id, is_archived);

CREATE INDEX idx_restaurant_history_restaurant_id ON restaurant_history(restaurant_id);

CREATE INDEX idx_plate_selection_active ON plate_selection(plate_selection_id, kitchen_day);

CREATE INDEX idx_plate_pickup_live_active ON plate_pickup_live(plate_pickup_id, is_archived);

CREATE INDEX idx_product_history_product_id ON product_history(product_id);

CREATE INDEX idx_plan_history_plan_id ON plan_history(plan_id);

CREATE INDEX idx_subscription_history_subscription_id ON subscription_history(subscription_id);

CREATE INDEX idx_client_bill_history_client_bill_id ON client_bill_history(client_bill_id);

CREATE INDEX idx_restaurant_balance_history_restaurant_id ON restaurant_balance_history(restaurant_id);

CREATE INDEX idx_institution_bill_history_institution_bill_id ON institution_bill_history(institution_bill_id);

CREATE INDEX idx_credit_currency_history_credit_currency_id ON credit_currency_history(credit_currency_id);

CREATE INDEX idx_plate_kitchen_days_plate_id ON plate_kitchen_days(plate_id);
CREATE INDEX idx_plate_kitchen_days_kitchen_day ON plate_kitchen_days(kitchen_day);
CREATE INDEX idx_plate_kitchen_days_active ON plate_kitchen_days(plate_id, kitchen_day, is_archived);

-- Optimized indexes for restaurant_holidays (as per RESTAURANT_HOLIDAY_API_PLAN.md)
CREATE INDEX IF NOT EXISTS idx_restaurant_holidays_restaurant_date ON restaurant_holidays(restaurant_id, holiday_date) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_holidays_recurring ON restaurant_holidays(restaurant_id, recurring_month_day) WHERE is_recurring AND NOT is_archived;

CREATE INDEX idx_restaurant_holidays_history_holiday_id ON restaurant_holidays_history(holiday_id);
CREATE INDEX idx_restaurant_holidays_history_current ON restaurant_holidays_history(holiday_id, is_current);

CREATE INDEX idx_plate_kitchen_days_history_plate_kitchen_day_id ON plate_kitchen_days_history(plate_kitchen_day_id);
CREATE INDEX idx_plate_kitchen_days_history_current ON plate_kitchen_days_history(plate_kitchen_day_id, is_current);

-- Indexes for status and transaction type history tables removed - tables deprecated

-- Indexes for QR code pickup flow
CREATE INDEX idx_plate_pickup_live_user_status ON plate_pickup_live(user_id, status, is_archived) WHERE is_archived = false;
CREATE INDEX idx_qr_code_id ON qr_code(qr_code_id);
CREATE INDEX idx_restaurant_transaction_status ON restaurant_transaction(status, was_collected);

-- Restaurant indexes
CREATE INDEX IF NOT EXISTS idx_restaurant_info_institution_id ON restaurant_info(institution_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_info_institution_entity_id ON restaurant_info(institution_entity_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_info_address_id ON restaurant_info(address_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_restaurant_info_status ON restaurant_info(status) WHERE NOT is_archived;

-- Address indexes
-- Single column indexes for foreign keys and common filters
CREATE INDEX IF NOT EXISTS idx_address_info_institution_id ON address_info(institution_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_user_id ON address_info(user_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_status ON address_info(status) WHERE NOT is_archived;

-- GIN index for array containment queries on address_type (e.g., WHERE 'Restaurant' = ANY(address_type))
CREATE INDEX IF NOT EXISTS idx_address_info_address_type ON address_info USING GIN(address_type) WHERE NOT is_archived;

-- Location indexes for UI filtering (individual columns for dropdowns/filters)
CREATE INDEX IF NOT EXISTS idx_address_info_country_code ON address_info(country_code) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_province ON address_info(province) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_city ON address_info(city) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_address_info_postal_code ON address_info(postal_code) WHERE NOT is_archived;

-- Partial index for employer_id queries (only non-NULL, non-archived addresses)
CREATE INDEX IF NOT EXISTS idx_address_info_employer_id ON address_info(employer_id) WHERE employer_id IS NOT NULL AND NOT is_archived;

-- Composite indexes for common query patterns
-- For location-based filtering (country_code, province, city, postal_code) - matches common UI filter patterns
CREATE INDEX IF NOT EXISTS idx_address_info_location ON address_info(country_code, province, city, postal_code) WHERE NOT is_archived;
-- For filtering by country_code + province (common hierarchical filter)
CREATE INDEX IF NOT EXISTS idx_address_info_country_province ON address_info(country_code, province) WHERE NOT is_archived;
-- For filtering by country_code + province + city (refined location filter)
CREATE INDEX IF NOT EXISTS idx_address_info_country_province_city ON address_info(country_code, province, city) WHERE NOT is_archived;