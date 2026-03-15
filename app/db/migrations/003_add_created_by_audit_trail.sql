-- Migration: Add created_by to all mutable tables (Phase B audit trail)
-- Run on existing databases. Adds created_by column to tables that have modified_by.
-- Fresh builds use schema.sql which already includes these columns.

\echo 'Adding created_by to audit tables...'
ALTER TABLE national_holidays ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE national_holidays_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE address_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE address_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE employer_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE employer_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE user_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE user_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE credit_currency_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE credit_currency_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE market_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE market_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE city_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE geolocation_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE geolocation_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE institution_entity_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE institution_entity_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE qr_code ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE product_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE product_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_holidays ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_holidays_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_kitchen_days ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_kitchen_days_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_selection_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_selection_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plate_pickup_live ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE pickup_preferences ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plan_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE plan_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE discretionary_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE discretionary_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE client_transaction ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE subscription_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE subscription_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE payment_method ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE client_bill_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE client_bill_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_transaction ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_balance_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE restaurant_balance_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE institution_bill_info ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE institution_bill_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE institution_settlement ADD COLUMN IF NOT EXISTS created_by UUID NULL;
ALTER TABLE institution_settlement_history ADD COLUMN IF NOT EXISTS created_by UUID NULL;
