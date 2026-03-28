-- search_path: belt-and-suspenders (ALTER DATABASE in build_kitchen_db.sh also sets it)
SET search_path = core, ops, customer, billing, audit, public;

-- Minimal seed so the app can start after tear-down and rebuild.
--   • 6 credit currencies (USD, ARS, PEN, CLP, MXN, BRL) and 7 markets — each market has its correct credit currency (e.g. Argentina -> ARS).
--   • 2 institutions: Vianda Enterprises, Vianda Customers (both use Global market).
--   • 2 users: superadmin (human Super Admin), system bot (automated operations: signup modified_by, billing cron, etc.).
--   • user_market_assignment for super_admin only (bot is not used for login/scoping).
-- FKs are dropped so modified_by can reference superadmin before user insert; re-added at end.

ALTER TABLE institution_info
  DROP CONSTRAINT IF EXISTS fk_institution_info_modified_by,
  DROP CONSTRAINT IF EXISTS fk_institution_info_created_by;

ALTER TABLE institution_history
  DROP CONSTRAINT IF EXISTS fk_institution_history_modified_by,
  DROP CONSTRAINT IF EXISTS fk_institution_history_created_by;

ALTER TABLE user_info
  DROP CONSTRAINT IF EXISTS fk_user_info_modified_by,
  DROP CONSTRAINT IF EXISTS fk_user_info_institution_id,
  DROP CONSTRAINT IF EXISTS user_info_market_id_fkey;

ALTER TABLE credit_currency_info
  DROP CONSTRAINT IF EXISTS credit_currency_info_modified_by_fkey;
ALTER TABLE credit_currency_history
  DROP CONSTRAINT IF EXISTS credit_currency_history_modified_by_fkey;
ALTER TABLE market_info
  DROP CONSTRAINT IF EXISTS market_info_modified_by_fkey;
ALTER TABLE market_history
  DROP CONSTRAINT IF EXISTS market_history_modified_by_fkey;

-- Drop city_info modified_by FK so we can insert cities before users (circular: users need city_id, cities need modified_by)
ALTER TABLE city_info
  DROP CONSTRAINT IF EXISTS city_info_modified_by_fkey;

-- Drop user_info city_id FK so we can insert users (cities inserted first, then users with city_id)
ALTER TABLE user_info
  DROP CONSTRAINT IF EXISTS user_info_city_id_fkey;

-- client_bill_info and institution_bill_info no longer have payment_id (payment attempts deprecated)
TRUNCATE user_market_assignment, user_info, institution_info, market_info, credit_currency_info, city_info CASCADE;

-- 6 credit currencies (USD, ARS, PEN, CLP, MXN, BRL) for seeded markets. Insert first; market_info FK references these.
INSERT INTO credit_currency_info (credit_currency_id, currency_name, currency_code, credit_value_local_currency, currency_conversion_usd, is_archived, status, created_date, created_by, modified_by, modified_date) VALUES
('55555555-5555-5555-5555-555555555555', 'US Dollar', 'USD', 1.0, 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('66666666-6666-6666-6666-666666666601', 'Argentine Peso', 'ARS', 1.0, 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('66666666-6666-6666-6666-666666666602', 'Peruvian Sol', 'PEN', 1.0, 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('66666666-6666-6666-6666-666666666603', 'Chilean Peso', 'CLP', 1.0, 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('66666666-6666-6666-6666-666666666604', 'Mexican Peso', 'MXN', 1.0, 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('66666666-6666-6666-6666-666666666605', 'Brazilian Real', 'BRL', 1.0, 1.0, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP);

-- Markets: each references its country's credit currency so JOINs return correct currency_code (e.g. Argentina -> ARS)
INSERT INTO market_info (market_id, country_name, country_code, credit_currency_id, timezone, kitchen_close_time, language, phone_dial_code, phone_local_digits, is_archived, status, created_date, created_by, modified_by, modified_date) VALUES
('00000000-0000-0000-0000-000000000001', 'Global Marketplace', 'GL', '55555555-5555-5555-5555-555555555555', 'UTC',                           '13:30'::TIME, 'en', NULL,   NULL, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('00000000-0000-0000-0000-000000000002', 'Argentina',          'AR', '66666666-6666-6666-6666-666666666601', 'America/Argentina/Buenos_Aires', '13:30'::TIME, 'es', '+54',  10,   FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('00000000-0000-0000-0000-000000000003', 'Peru',               'PE', '66666666-6666-6666-6666-666666666602', 'America/Lima',                  '13:30'::TIME, 'es', '+51',  9,    FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('00000000-0000-0000-0000-000000000004', 'United States',      'US', '55555555-5555-5555-5555-555555555555', 'America/New_York',              '13:30'::TIME, 'en', '+1',   10,   FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('00000000-0000-0000-0000-000000000005', 'Chile',              'CL', '66666666-6666-6666-6666-666666666603', 'America/Santiago',              '13:30'::TIME, 'es', '+56',  9,    FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('00000000-0000-0000-0000-000000000006', 'Mexico',             'MX', '66666666-6666-6666-6666-666666666604', 'America/Mexico_City',           '13:30'::TIME, 'es', '+52',  10,   FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('00000000-0000-0000-0000-000000000007', 'Brazil',             'BR', '66666666-6666-6666-6666-666666666605', 'America/Sao_Paulo',             '13:30'::TIME, 'pt', '+55',  11,   FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP);

-- Institutions: only Vianda Enterprises (employees) and Vianda Customers (B2C). Suppliers created via API.
-- no_show_discount: NULL for Internal/Customer (not applicable); Supplier requires it at create time.
-- created_by: dddddddd (superadmin) — FK dropped before insert, re-added after users exist.
INSERT INTO institution_info (institution_id, name, institution_type, market_id, no_show_discount, is_archived, status, created_date, created_by, modified_by, modified_date)
VALUES (
  '11111111-1111-1111-1111-111111111111',           -- Vianda Enterprises (employees)
  'Vianda Enterprises',
  'Internal'::institution_type_enum,
  '00000000-0000-0000-0000-000000000001',           -- Global Marketplace
  NULL,                                              -- no_show_discount not applicable for Internal
  False,
  'Active'::status_enum,
  CURRENT_TIMESTAMP,
  'dddddddd-dddd-dddd-dddd-dddddddddddd',           -- created_by (superadmin)
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  CURRENT_TIMESTAMP
),
(
  '22222222-2222-2222-2222-222222222222',           -- Vianda Customers (B2C)
  'Vianda Customers',
  'Customer'::institution_type_enum,
  '00000000-0000-0000-0000-000000000001',           -- Global Marketplace
  NULL,                                              -- no_show_discount not applicable for Customer
  False,
  'Active'::status_enum,
  CURRENT_TIMESTAMP,
  'dddddddd-dddd-dddd-dddd-dddddddddddd',           -- created_by (superadmin)
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  CURRENT_TIMESTAMP
);

-- Cities from supported_cities config (insert BEFORE users so user_info.city_id FK can reference them).
-- Global city first (B2B users get this; country_code GL matches Global Marketplace).
INSERT INTO city_info (city_id, name, country_code, province_code, is_archived, status, created_date, created_by, modified_by, modified_date) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Global', 'GL', NULL, FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP);

INSERT INTO city_info (name, country_code, province_code, is_archived, status, created_date, created_by, modified_by, modified_date) VALUES
('Buenos Aires', 'AR', 'CABA', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Cordoba', 'AR', 'CO', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('La Plata', 'AR', 'BA', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Mendoza', 'AR', 'MN', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Misiones', 'AR', 'MI', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Rosario', 'AR', 'SF', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Tierra del Fuego', 'AR', 'TF', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Rio de Janeiro', 'BR', 'RJ', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Sao Paulo', 'BR', 'SP', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Santiago', 'CL', 'RM', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Mexico DF', 'MX', 'CDMX', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Monterrey', 'MX', 'NL', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Arequipa', 'PE', 'ARE', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Lima', 'PE', 'LIM', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Trujillo', 'PE', 'LAL', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Austin', 'US', 'TX', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Chicago', 'US', 'IL', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Los Angeles', 'US', 'CA', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Miami', 'US', 'FL', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('New York', 'US', 'NY', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('San Francisco', 'US', 'CA', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP),
('Seattle', 'US', 'WA', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP);

-- Seeded users: Super Admin (human), system bot (automated operations only; do not use for login).
-- Both get Global city (aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa).
INSERT INTO user_info (
  user_id, username, hashed_password, first_name, last_name, institution_id, role_type, role_name, email, mobile_number, email_verified, email_verified_at, market_id, city_id, locale, is_archived, status, created_date, created_by, modified_by, modified_date
) VALUES (
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  'superadmin',
  '$2b$12$H7UZ/eImB4SmjzNybAqKl.rL2JYyGZRlJhcHjivhNAz7qRIfAZLUq',   -- SuperAdmin1 (no special chars)
  'Super',
  'Admin',
  '11111111-1111-1111-1111-111111111111',            -- Vianda Enterprises
  'Internal'::role_type_enum,
  'Super Admin'::role_name_enum,
  'viandallc@gmail.com',
  '+14155552671',
  TRUE,
  CURRENT_TIMESTAMP,
  '00000000-0000-0000-0000-000000000001',            -- Global Marketplace
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',            -- Global city (B2B)
  'en',
  FALSE,
  'Active'::status_enum,
  CURRENT_TIMESTAMP,
  'dddddddd-dddd-dddd-dddd-dddddddddddd',            -- created_by (self for superadmin)
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  CURRENT_TIMESTAMP
),
(
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',           -- System bot: customer signup modified_by, billing cron, etc. Do not use for login.
  'system_bot',
  '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3VjGgaSTlF.K',   -- bcrypt for "secret"; not for login
  'System',
  'Bot',
  '11111111-1111-1111-1111-111111111111',            -- Vianda Enterprises
  'Internal'::role_type_enum,
  'Admin'::role_name_enum,
  'admin@vianda.market',
  NULL,
  TRUE,
  CURRENT_TIMESTAMP,
  '00000000-0000-0000-0000-000000000001',            -- Global Marketplace
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',            -- Global city (B2B)
  'en',
  FALSE,
  'Active'::status_enum,
  CURRENT_TIMESTAMP,
  'dddddddd-dddd-dddd-dddd-dddddddddddd',            -- created_by (superadmin created system bot)
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  CURRENT_TIMESTAMP
);

-- Populate user_market_assignment so the Super Admin has market scope (e.g. get_assigned_market_ids). Bot is not assigned; automated only.
INSERT INTO user_market_assignment (user_id, market_id, is_primary)
SELECT user_id, market_id, true FROM user_info WHERE user_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd';

-- No address_info, plan_info, subscription_info, national_holidays in seed; create via API.

ALTER TABLE institution_info
  ADD CONSTRAINT fk_institution_info_modified_by FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_institution_info_created_by FOREIGN KEY (created_by) REFERENCES user_info(user_id) ON DELETE SET NULL;

ALTER TABLE institution_history
  ADD CONSTRAINT fk_institution_history_modified_by FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_institution_history_created_by FOREIGN KEY (created_by) REFERENCES user_info(user_id) ON DELETE SET NULL;

ALTER TABLE user_info
  ADD CONSTRAINT fk_user_info_modified_by FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_user_info_institution_id FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
  ADD CONSTRAINT user_info_market_id_fkey FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT;

ALTER TABLE credit_currency_info
  ADD CONSTRAINT credit_currency_info_modified_by_fkey FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;
ALTER TABLE credit_currency_history
  ADD CONSTRAINT credit_currency_history_modified_by_fkey FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;
ALTER TABLE market_info
  ADD CONSTRAINT market_info_modified_by_fkey FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;
ALTER TABLE market_history
  ADD CONSTRAINT market_history_modified_by_fkey FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;

ALTER TABLE city_info
  ADD CONSTRAINT city_info_modified_by_fkey FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT;

ALTER TABLE user_info
  ADD CONSTRAINT user_info_city_id_fkey FOREIGN KEY (city_id) REFERENCES city_info(city_id) ON DELETE RESTRICT;

-- role_info, role_history, status_info, status_history, transaction_type_info, transaction_type_history
-- tables removed - no foreign key constraints needed