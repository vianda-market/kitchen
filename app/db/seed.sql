-- Prepare the database for seeding
-- This script will truncate the tables and insert initial data
-- into the user_info, institution_info, and credit_currency_info tables.
-- Note: role_info, status_info, and transaction_type_info tables have been removed.
-- Enums are now stored directly on entities (user_info.role_type, user_info.role_name, etc.).
-- It is assumed that the tables have already been created and pgTAP is available.
-- Ensure you have the necessary permissions to truncate and insert data into these tables.

-- DROP any old copies so the TRUNCATE+INSERT always works
-- DROP any old copies so the TRUNCATE+INSERT always works
ALTER TABLE institution_info
  DROP CONSTRAINT IF EXISTS fk_institution_info_modified_by;

ALTER TABLE institution_history
  DROP CONSTRAINT IF EXISTS fk_institution_history_modified_by;

ALTER TABLE user_info
  DROP CONSTRAINT IF EXISTS fk_user_info_modified_by,
  DROP CONSTRAINT IF EXISTS fk_user_info_institution_id;

ALTER TABLE client_bill_info
  DROP CONSTRAINT IF EXISTS fk_bill_info_payment_id;

ALTER TABLE institution_bill_info
  DROP CONSTRAINT IF EXISTS fk_bill_info_payment_id;

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - enums are now stored directly on entities

-- (and any other that you ADD at the bottom)

TRUNCATE user_info, institution_info, market_info, credit_currency_info CASCADE;
-- role_info, status_info, and transaction_type_info tables removed
-- Enums are now stored directly on entities (user_info, etc.)

-- Insert admin user into user_info table
INSERT INTO user_info (
  user_id, username, hashed_password, first_name, last_name, institution_id, role_type, role_name, email, cellphone, is_archived, status, created_date, modified_by, modified_date
) VALUES (
  '11111111-1111-1111-1111-111111111111',            -- user_id for admin
  'admin',                                         
  '$2b$12$6VOpXRNl38SzwpfNRsrN/.io5BbaNs1ukjx5WpXsp/IT/lOSj3XfC',                           -- hashed password for 'admin_password'
  'Admin',                                         
  'User',                                           
  '33333333-3333-3333-3333-333333333333',            -- references Vianda Enterprises
  'Employee'::role_type_enum,                        -- role_type
  'Admin'::role_name_enum,                           -- role_name
  'admin@example.com',                               -- email
  '1234567890',                                      -- cellphone
  FALSE,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (self)
  CURRENT_TIMESTAMP                                  -- modified_date
);

-- Insert bot_chef system account into user_info table
INSERT INTO user_info (
  user_id, username, hashed_password, first_name, last_name, institution_id, role_type, role_name, email, cellphone, is_archived, status, created_date, modified_by, modified_date
) VALUES (
  '22222222-2222-2222-2222-222222222222',            -- user_id for bot_chef
  'bot_chef',                                       
  '$2b$12$56afoaPKhAfLYRVgRQHFc.am3cymi7pIYkmaRovWreAiiLsxsntpK',                        -- replace with actual hashed password
  'Bot',                                            -- first name (or adjust as needed)
  'Chef',                                           -- last name (or adjust as needed)
  '33333333-3333-3333-3333-333333333333',            -- references Vianda Enterprises
  'Employee'::role_type_enum,                        -- role_type
  'Admin'::role_name_enum,                           -- role_name
  'bot_chef@example.com',                            -- email
  '0987654321',                                      -- cellphone
  FALSE,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (set to admin)
  CURRENT_TIMESTAMP                                  -- modified_date
);

-- Insert super-admin user into user_info table
INSERT INTO user_info (
  user_id, username, hashed_password, first_name, last_name, institution_id, role_type, role_name, email, cellphone, is_archived, status, created_date, modified_by, modified_date
) VALUES (
  'dddddddd-dddd-dddd-dddd-dddddddddddd',            -- user_id for superadmin
  'superadmin',                                     
  '$2b$12$s3rwUUe0nQ0o/6P4KFc6rOS3/Uekf6ZGqNMoa6R1L5aBgVNet6hx6',                           -- hashed password for 'super_secret'
  'Super',                                         
  'Admin',                                           
  '33333333-3333-3333-3333-333333333333',            -- references Vianda Enterprises
  'Employee'::role_type_enum,                        -- role_type
  'Super Admin'::role_name_enum,                     -- role_name
  'superadmin@example.com',                           -- email
  '5555555555',                                      -- cellphone
  FALSE,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (admin)
  CURRENT_TIMESTAMP                                  -- modified_date
);

-- Insert institution records into institution_info table
INSERT INTO institution_info (institution_id, name, is_archived, status, created_date, modified_by, modified_date)
VALUES (
  '11111111-1111-1111-1111-111111111111',           -- institution_id
  'La Parrilla Argentina',                           -- name
  False,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (admin user)
  CURRENT_TIMESTAMP                                  -- modified_date
),
(
  '22222222-2222-2222-2222-222222222222',           -- institution_id
  'Restaurante Peruano',                             -- name
  False,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (admin user)
  CURRENT_TIMESTAMP                                  -- modified_date
),
(
  '33333333-3333-3333-3333-333333333333',           -- institution_id
  'Vianda Enterprises',                              -- name
  False,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (admin user)
  CURRENT_TIMESTAMP                                  -- modified_date
),
(
  '44444444-4444-4444-4444-444444444444',           -- institution_id
  'Vianda Customers',                              -- name
  False,                                              -- is_archived
  'Active'::status_enum,                              -- status
  CURRENT_TIMESTAMP,                                 -- created_date
  '11111111-1111-1111-1111-111111111111',             -- modified_by (admin user)
  CURRENT_TIMESTAMP                                  -- modified_date
);

-- Insert Credit Currency records into credit_currency_info table
-- Removed seed data - currencies will be created via API endpoints
-- INSERT INTO credit_currency_info (credit_currency_id, currency_name, currency_code, credit_value, is_archived, status, created_date, modified_by, modified_date)
-- VALUES
-- ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Argentinean Peso', 'ARS', 1.2, FALSE, 'Active', CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
-- ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Peruvian Sol', 'PEN', 1.4, FALSE, 'Active', CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP);

-- Seed data for national holidays
INSERT INTO national_holidays (country_code, holiday_name, holiday_date, is_recurring, recurring_month, recurring_day, status, modified_by) VALUES
-- Argentina Holidays
('AR', 'New Year''s Day', '2025-01-01', TRUE, 1, 1, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),
('AR', 'Independence Day', '2025-07-09', TRUE, 7, 9, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),
('AR', 'Labor Day', '2025-05-01', TRUE, 5, 1, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),
('AR', 'Christmas Day', '2025-12-25', TRUE, 12, 25, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),

-- Peru Holidays  
('PE', 'New Year''s Day', '2025-01-01', TRUE, 1, 1, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),
('PE', 'Independence Day', '2025-07-28', TRUE, 7, 28, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),
('PE', 'Labor Day', '2025-05-01', TRUE, 5, 1, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111'),
('PE', 'Christmas Day', '2025-12-25', TRUE, 12, 25, 'Active'::status_enum, '11111111-1111-1111-1111-111111111111');

-- Sample address and institution entity data (moved to after market_info to satisfy FK constraints)

-- Restaurant data will be created via API endpoints after currencies are created
-- INSERT INTO restaurant_info (restaurant_id, institution_id, institution_entity_id, address_id, credit_currency_id, name, cuisine, modified_by) VALUES
-- ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'La Parrilla Argentina', 'Argentinean', '11111111-1111-1111-1111-111111111111'),
-- ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'La Parrilla Argentina - Sucursal', 'Argentinean', '11111111-1111-1111-1111-111111111111'),
-- ('cccccccc-cccc-cccc-cccc-cccccccccccc', '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Restaurante Peruano', 'Peruvian', '11111111-1111-1111-1111-111111111111');

-- Restaurant balance data will be created via API endpoints after currencies are created
-- INSERT INTO restaurant_balance_info (restaurant_id, credit_currency_id, transaction_count, balance, currency_code, modified_by) VALUES
-- ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 15, 500.00, 'ARS', '11111111-1111-1111-1111-111111111111'),
-- ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 8, 300.00, 'ARS', '11111111-1111-1111-1111-111111111111'),
-- ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 12, 400.00, 'PEN', '11111111-1111-1111-1111-111111111111');

-- ============================================================================
-- MARKET-BASED SUBSCRIPTION SYSTEM SEED DATA
-- ============================================================================

-- Insert credit currency data FIRST (required by market_info FK)
INSERT INTO credit_currency_info (credit_currency_id, currency_name, currency_code, credit_value, is_archived, status, created_date, modified_by, modified_date) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Argentine Peso', 'ARS', 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Peruvian Sol', 'PEN', 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Chilean Peso', 'CLP', 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP);

-- Insert market data (country-based markets with FK to credit_currency_info)
INSERT INTO market_info (market_id, country_name, country_code, credit_currency_id, timezone, is_archived, status, created_date, modified_by, modified_date) VALUES
('11111111-1111-1111-1111-111111111111', 'Argentina', 'ARG', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'America/Argentina/Buenos_Aires', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('22222222-2222-2222-2222-222222222222', 'Peru', 'PER', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'America/Lima', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('33333333-3333-3333-3333-333333333333', 'Chile', 'CHL', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'America/Santiago', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP);

-- Insert address data (after market_info to satisfy FK constraint on country_code)
INSERT INTO address_info (address_id, institution_id, user_id, address_type, country_name, country_code, province, city, postal_code, street_type, street_name, building_number, timezone, modified_by) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', ARRAY['Entity Billing', 'Restaurant']::address_type_enum[], 'Argentina', 'ARG', 'Buenos Aires', 'Buenos Aires', '1001', 'Street', 'Av. 9 de Julio', '123', 'America/Argentina/Buenos_Aires', '11111111-1111-1111-1111-111111111111'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', ARRAY['Restaurant']::address_type_enum[], 'Argentina', 'ARG', 'Buenos Aires', 'Buenos Aires', '1002', 'Street', 'Av. Corrientes', '456', 'America/Argentina/Buenos_Aires', '11111111-1111-1111-1111-111111111111'),
('cccccccc-cccc-cccc-cccc-cccccccccccc', '22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', ARRAY['Entity Billing', 'Restaurant']::address_type_enum[], 'Peru', 'PER', 'Lima', 'Lima', '15001', 'Street', 'Av. Arequipa', '789', 'America/Lima', '11111111-1111-1111-1111-111111111111'),
('dddddddd-dddd-dddd-dddd-dddddddddddd', '33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', ARRAY['Customer Home']::address_type_enum[], 'Argentina', 'ARG', 'Buenos Aires', 'Buenos Aires', '1003', 'Street', 'Av. Santa Fe', '321', 'America/Argentina/Buenos_Aires', '11111111-1111-1111-1111-111111111111'),
('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', ARRAY['Customer Billing']::address_type_enum[], 'Argentina', 'ARG', 'Buenos Aires', 'Buenos Aires', '1004', 'Street', 'Av. Callao', '654', 'America/Argentina/Buenos_Aires', '11111111-1111-1111-1111-111111111111');

-- Insert institution entity data (after address_info to satisfy FK constraint)
INSERT INTO institution_entity_info (institution_entity_id, institution_id, address_id, tax_id, name, modified_by) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'AR-12345678-9', 'La Parrilla Argentina S.A.', '11111111-1111-1111-1111-111111111111'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'PE-87654321-0', 'Restaurante Peruano E.I.R.L.', '11111111-1111-1111-1111-111111111111');

-- Insert plan data (market-specific plans)
-- Argentina Market Plans
INSERT INTO plan_info (plan_id, market_id, credit_currency_id, name, credit, price, rollover, rollover_cap, is_archived, status, created_date, modified_by, modified_date) VALUES
('11111111-aaaa-aaaa-aaaa-111111111111', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Argentina Basic', 20, 5000.00, TRUE, 5, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('11111111-bbbb-bbbb-bbbb-111111111111', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Argentina Standard', 40, 9000.00, TRUE, 10, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('11111111-cccc-cccc-cccc-111111111111', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Argentina Premium', 60, 12000.00, TRUE, 15, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),

-- Peru Market Plans
('22222222-aaaa-aaaa-aaaa-222222222222', '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Peru Basic', 20, 150.00, TRUE, 5, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('22222222-bbbb-bbbb-bbbb-222222222222', '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Peru Standard', 40, 270.00, TRUE, 10, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('22222222-cccc-cccc-cccc-222222222222', '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Peru Premium', 60, 360.00, TRUE, 15, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),

-- Chile Market Plans
('33333333-aaaa-aaaa-aaaa-333333333333', '33333333-3333-3333-3333-333333333333', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'Chile Basic', 20, 15000.00, TRUE, 5, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('33333333-bbbb-bbbb-bbbb-333333333333', '33333333-3333-3333-3333-333333333333', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'Chile Standard', 40, 27000.00, TRUE, 10, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),
('33333333-cccc-cccc-cccc-333333333333', '33333333-3333-3333-3333-333333333333', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'Chile Premium', 60, 36000.00, TRUE, 15, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP);

-- Sample subscription data (admin has subscriptions in Argentina and Peru)
-- Note: subscription_status values: 'Active', 'On Hold', 'Pending', 'Expired', 'Cancelled'
INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, renewal_date, balance, subscription_status, hold_start_date, hold_end_date, is_archived, status, created_date, modified_by, modified_date) VALUES
-- Admin user active subscription in Argentina
('aaaaaaaa-0001-0001-0001-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', '11111111-bbbb-bbbb-bbbb-111111111111', CURRENT_TIMESTAMP + INTERVAL '30 days', 40, 'Active', NULL, NULL, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP),

-- Superadmin active subscription in Peru  
('bbbbbbbb-0002-0002-0002-bbbbbbbbbbbb', 'dddddddd-dddd-dddd-dddd-dddddddddddd', '22222222-2222-2222-2222-222222222222', '22222222-aaaa-aaaa-aaaa-222222222222', CURRENT_TIMESTAMP + INTERVAL '30 days', 20, 'Active', NULL, NULL, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, '11111111-1111-1111-1111-111111111111', CURRENT_TIMESTAMP);

-- ============================================================================
-- END MARKET-BASED SUBSCRIPTION SYSTEM SEED DATA
-- ============================================================================

ALTER TABLE institution_info
ADD CONSTRAINT fk_institution_info_modified_by
FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;

ALTER TABLE institution_history
ADD CONSTRAINT fk_institution_history_modified_by
FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;

ALTER TABLE user_info
  ADD CONSTRAINT fk_user_info_modified_by FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_user_info_institution_id FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT;

ALTER TABLE client_bill_info
  ADD CONSTRAINT fk_bill_info_payment_id FOREIGN KEY (payment_id) REFERENCES client_payment_attempt(payment_id) ON DELETE RESTRICT;

ALTER TABLE institution_bill_info
  ADD CONSTRAINT fk_bill_info_payment_id FOREIGN KEY (payment_id) REFERENCES institution_payment_attempt(payment_id) ON DELETE RESTRICT;

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - no foreign key constraints needed