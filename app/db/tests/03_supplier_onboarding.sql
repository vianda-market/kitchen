-- 03_supplier_onboarding.sql
BEGIN;

-- 1. pgTAP setup
CREATE EXTENSION IF NOT EXISTS pgtap;
\set VERBOSITY verbose

SELECT diag('Full supplier onboarding flow: registration through plate');

-- 2. Total tests = 50
SELECT plan(50);

-- 3. Clean slate
TRUNCATE
  institution_bank_account,
  institution_entity_info, institution_entity_history,
  address_info,             address_history,
  user_info,                user_history,
  institution_info,         institution_history,
  restaurant_info,          restaurant_history,
  qr_code,             -- Removed qr_code_history
  product_info,             product_history,
  plate_info,               plate_history
CASCADE;

-- 4. Re-load all the base “seed” data your other tests rely on —
\i app/db/seed.sql

------------------------------
-- Phase 1: Registration
------------------------------

-- 4 tests: institution_info insert + history + update + new history
INSERT INTO institution_info (institution_id, name, modified_by)
VALUES (gen_random_uuid(), 'Test Supplier Inc.', '22222222-2222-2222-2222-222222222222');
SELECT is(
  (SELECT COUNT(*) FROM institution_info)::integer,
  1,
  'Institution record inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM institution_history)::integer,
  1,
  'Institution history record created'
);

UPDATE institution_info
SET name = 'Test Supplier Inc. Updated';
SELECT is(
  (SELECT name FROM institution_info LIMIT 1),
  'Test Supplier Inc. Updated',
  'Institution record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM institution_history) > 1,
  'Institution update triggered new history record'
);

-- 4 tests: user_info insert + history + update + new history
INSERT INTO user_info (
  user_id, institution_id, role_type, role_name, username, email, hashed_password, cellphone, modified_by
) VALUES (
  gen_random_uuid(),
  (SELECT institution_id FROM institution_info LIMIT 1),
  'Supplier'::role_type_enum,
  'Admin'::role_name_enum,
  'supplier_user',
  'supplier@example.com',
  'hashedpwd',
  '555-1234',
  '22222222-2222-2222-2222-222222222222'
);
SELECT is(
  (SELECT COUNT(*) FROM user_info)::integer,
  1,
  'Supplier user record inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM user_history)::integer,
  1,
  'User history record created'
);

UPDATE user_info
SET username = 'supplier_user_updated'
WHERE username = 'supplier_user';
SELECT is(
  (SELECT username FROM user_info WHERE username = 'supplier_user_updated'),
  'supplier_user_updated',
  'User record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM user_history)::integer > 1,
  'User update triggered new history record'
);

-- 4 tests: address_info insert (2 rows) + history (2 rows) + update + new history
INSERT INTO address_info (
  address_id, institution_id, user_id, address_type,
  country, province, city, postal_code, street_type, street_name, building_number, timezone, modified_by
) VALUES
  (
    gen_random_uuid(),
    (SELECT institution_id FROM institution_info LIMIT 1),
    (SELECT user_id        FROM user_info       LIMIT 1),
    ARRAY['Entity Address']::address_type_enum[],
    'AR','BA','Buenos Aires','1000','Street','Main St','123',
    'America/Argentina/Buenos_Aires',
    (SELECT user_id        FROM user_info       LIMIT 1)
  ),
  (
    gen_random_uuid(),
    (SELECT institution_id FROM institution_info LIMIT 1),
    (SELECT user_id        FROM user_info       LIMIT 1),
    ARRAY['Bank Address'],
    'AR','BA','Buenos Aires','1000','Street','Second St','456',
    'America/Argentina/Buenos_Aires',
    (SELECT user_id        FROM user_info       LIMIT 1)
  );
SELECT is(
  (SELECT COUNT(*) FROM address_info)::integer,
  2,
  'Two addresses inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM address_history)::integer,
  2,
  'Address history records created'
);

UPDATE address_info
SET city = 'Updated City'
WHERE 'Entity Address' = ANY(address_type);
SELECT is(
  (SELECT city FROM address_info WHERE 'Entity Address' = ANY(address_type)),
  'Updated City',
  'Entity Address record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM address_history)::integer > 2,
  'Address update triggered new history record'
);

-- 4 tests: institution_entity_info insert + history + update + new history
INSERT INTO institution_entity_info (
  institution_entity_id, institution_id, address_id, tax_id, name, modified_by
) VALUES (
  gen_random_uuid(),
  (SELECT institution_id FROM institution_info LIMIT 1),
  (SELECT address_id      FROM address_info WHERE 'Entity Address' = ANY(address_type) LIMIT 1),
  'TAX123',
  'Supplier Legal',
  (SELECT user_id        FROM user_info LIMIT 1)
);
SELECT is(
  (SELECT COUNT(*) FROM institution_entity_info)::integer,
  1,
  'Institution entity record inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM institution_entity_history)::integer,
  1,
  'Institution entity history record created'
);

UPDATE institution_entity_info
SET name = 'Supplier Legal Updated';
SELECT is(
  (SELECT name FROM institution_entity_info LIMIT 1),
  'Supplier Legal Updated',
  'Institution entity record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM institution_entity_history)::integer > 1,
  'Institution entity update triggered new history record'
);

------------------------------
-- Phase 2: Onboarding Details
------------------------------

-- 2 tests: institution_bank_account insert + update
INSERT INTO institution_bank_account (
    bank_account_id, institution_entity_id, address_id, account_holder_name, 
    bank_name, account_type, routing_number, account_number, modified_by
) VALUES (
    gen_random_uuid(), 
    (SELECT institution_entity_id FROM institution_entity_info LIMIT 1), 
    (SELECT address_id FROM address_info LIMIT 1), 
    'Test Bank Account', 
    'Test Bank', 
    'Business', 
    '123456789', 
    '987654321', 
    (SELECT user_id FROM user_info LIMIT 1)
);
SELECT is(
  (SELECT COUNT(*) FROM institution_bank_account)::integer,
  1,
  'Institution bank account record inserted'
);

UPDATE institution_bank_account
SET account_number = '987654321';
SELECT is(
  (SELECT account_number FROM institution_bank_account LIMIT 1),
  '987654321',
  'Institution bank account record updated'
);

-- 4 tests: restaurant_info insert + history + update + history
-- Insert a currency and capture its UUID
INSERT INTO credit_currency_info (
    currency_name, currency_code, credit_value, is_archived, status, created_date, modified_by, modified_date
) VALUES (
    'Test Currency', 'TEST', 1.0, FALSE, 'Active', CURRENT_TIMESTAMP,
    (SELECT user_id FROM user_info LIMIT 1),  -- Use a real user_id here
    CURRENT_TIMESTAMP
);

-- Use the captured UUID in restaurant_info
INSERT INTO restaurant_info (
  restaurant_id, institution_id, institution_entity_id, address_id, credit_currency_id, name, cuisine, modified_by
) VALUES (
  gen_random_uuid(),
  (SELECT institution_id FROM institution_info LIMIT 1),
  (SELECT institution_entity_id FROM institution_entity_info LIMIT 1),
  (SELECT address_id FROM address_info LIMIT 1),
  (SELECT credit_currency_id FROM credit_currency_info LIMIT 1),
  'Test Restaurant',
  'Test Cuisine',
  (SELECT user_id FROM user_info LIMIT 1)
);
SELECT is(
  (SELECT COUNT(*) FROM restaurant_info)::integer,
  1,
  'Restaurant record inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM restaurant_history)::integer,
  1,
  'Restaurant history record created'
);

UPDATE restaurant_info
SET name = 'Updated Restaurant';
SELECT is(
  (SELECT name FROM restaurant_info LIMIT 1),
  'Updated Restaurant',
  'Restaurant record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM restaurant_history)::integer > 1,
  'Restaurant update triggered new history record'
);

-- 4 tests: qr_code insert + update
WITH ins_qr AS (
  INSERT INTO qr_code (
    qr_code_id, restaurant_id, qr_code_payload, qr_code_image_url, image_storage_path, modified_by
  ) VALUES (
    gen_random_uuid(),
    (SELECT restaurant_id FROM restaurant_info LIMIT 1),
    'InitialPayload',
    'http://localhost:8000/static/qr_codes/initial.png',
    'static/qr_codes/initial.png',
    (SELECT user_id      FROM user_info       LIMIT 1)
  )
  RETURNING qr_code_id
)
SELECT qr_code_id FROM ins_qr;
SELECT is(
  (SELECT COUNT(*) FROM qr_code)::integer,
  1,
  'QR Code record inserted'
);

UPDATE qr_code
SET qr_code_payload = 'NewPayload';
SELECT is(
  (SELECT qr_code_payload FROM qr_code LIMIT 1),
  'NewPayload',
  'QR Code record updated'
);

-- 4 tests: product_info insert + history + update + history
WITH ins_prod AS (
  INSERT INTO product_info (
    product_id, institution_id, name, modified_by
  ) VALUES (
    gen_random_uuid(),
    (SELECT institution_id FROM institution_info LIMIT 1),
    'Test Product',
    (SELECT user_id        FROM user_info       LIMIT 1)
  )
  RETURNING product_id
)
SELECT product_id FROM ins_prod;
SELECT is(
  (SELECT COUNT(*) FROM product_info)::integer,
  1,
  'Product record inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM product_history)::integer,
  1,
  'Product history record created'
);

UPDATE product_info
SET name = 'Updated Product';
SELECT is(
  (SELECT name FROM product_info LIMIT 1),
  'Updated Product',
  'Product record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM product_history)::integer > 1,
  'Product update triggered new history record'
);

-- 4 tests: plate_info insert + history + update + history
WITH ins_plate AS (
  INSERT INTO plate_info (
    plate_id, product_id, restaurant_id, price, credit, savings, no_show_discount, modified_by
  ) VALUES (
    gen_random_uuid(),
    (SELECT product_id    FROM product_info     LIMIT 1),
    (SELECT restaurant_id FROM restaurant_info  LIMIT 1),
    10.0,
    5,
    20,
    1,
    (SELECT user_id       FROM user_info        LIMIT 1)
  )
  RETURNING plate_id
)
SELECT plate_id FROM ins_plate;
SELECT is(
  (SELECT COUNT(*) FROM plate_info)::integer,
  1,
  'Plate record inserted'
);
SELECT is(
  (SELECT COUNT(*) FROM plate_history)::integer,
  1,
  'Plate history record created'
);

UPDATE plate_info
SET price = 99.99;
SELECT is(
  (SELECT price FROM plate_info LIMIT 1),
  99.99::double precision,
  'Plate record updated'
);
SELECT ok(
  (SELECT COUNT(*) FROM plate_history)::integer > 1,
  'Plate update triggered new history record'
);

-- Test institution_payment_attempt table
-- First create an institution bill record
INSERT INTO institution_bill_info (
    institution_id, institution_entity_id, restaurant_id, credit_currency_id,
    amount, currency_code, period_start, period_end, resolution, modified_by
) VALUES (
    (SELECT institution_id FROM institution_info LIMIT 1),
    (SELECT institution_entity_id FROM institution_entity_info LIMIT 1),
    (SELECT restaurant_id FROM restaurant_info LIMIT 1),
    (SELECT credit_currency_id FROM credit_currency_info LIMIT 1),
    150.75,
    'USD',
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    CURRENT_TIMESTAMP,
    'Unresolved',
    (SELECT user_id FROM user_info LIMIT 1)
);

-- Now create the payment attempt
INSERT INTO institution_payment_attempt (
    payment_id, institution_entity_id, bank_account_id, institution_bill_id,
    credit_currency_id, amount, currency_code, transaction_result,
    external_transaction_id, status, created_date, resolution_date
) VALUES (
    gen_random_uuid(),
    (SELECT institution_entity_id FROM institution_entity_info LIMIT 1),
    (SELECT bank_account_id FROM institution_bank_account LIMIT 1),
    (SELECT institution_bill_id FROM institution_bill_info LIMIT 1),
    (SELECT credit_currency_id FROM credit_currency_info LIMIT 1),
    150.75,
    'USD',
    'Success',
    'ext_txn_12345',
    'Complete',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt)::integer,
    1,
    'Institution payment attempt record inserted'
);

SELECT is(
    (SELECT amount FROM institution_payment_attempt LIMIT 1),
    150.75,
    'Payment attempt amount is correct'
);

SELECT is(
    (SELECT currency_code FROM institution_payment_attempt LIMIT 1),
    'USD',
    'Payment attempt currency code is correct'
);

SELECT is(
    (SELECT status FROM institution_payment_attempt LIMIT 1),
    'Complete',
    'Payment attempt status is correct'
);

-- Test institution_payment_attempt with pending status
INSERT INTO institution_payment_attempt (
    payment_id, institution_entity_id, bank_account_id, institution_bill_id,
    credit_currency_id, amount, currency_code, transaction_result,
    external_transaction_id, status, created_date, resolution_date
) VALUES (
    gen_random_uuid(),
    (SELECT institution_entity_id FROM institution_entity_info LIMIT 1),
    (SELECT bank_account_id FROM institution_bank_account LIMIT 1),
    (SELECT institution_bill_id FROM institution_bill_info LIMIT 1),
    (SELECT credit_currency_id FROM credit_currency_info LIMIT 1),
    200.00,
    'USD',
    NULL,
    NULL,
    'Pending',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt)::integer,
    2,
    'Second institution payment attempt record inserted'
);

SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt WHERE status = 'Pending')::integer,
    1,
    'One payment attempt has pending status'
);

SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt WHERE status = 'Complete')::integer,
    1,
    'One payment attempt has complete status'
);

-- Test institution_payment_attempt with failed status
INSERT INTO institution_payment_attempt (
    payment_id, institution_entity_id, bank_account_id, institution_bill_id,
    credit_currency_id, amount, currency_code, transaction_result,
    external_transaction_id, status, created_date, resolution_date
) VALUES (
    gen_random_uuid(),
    (SELECT institution_entity_id FROM institution_entity_info LIMIT 1),
    (SELECT bank_account_id FROM institution_bank_account LIMIT 1),
    (SELECT institution_bill_id FROM institution_bill_info LIMIT 1),
    (SELECT credit_currency_id FROM credit_currency_info LIMIT 1),
    75.50,
    'USD',
    'Insufficient Funds',
    'ext_txn_failed',
    'Failed',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt)::integer,
    3,
    'Third institution payment attempt record inserted'
);

SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt WHERE status = 'Failed')::integer,
    1,
    'One payment attempt has failed status'
);

-- Test total amount calculation
SELECT is(
    (SELECT SUM(amount) FROM institution_payment_attempt)::numeric,
    426.25,
    'Total amount of all payment attempts is correct'
);

-- Test currency distribution
SELECT is(
    (SELECT COUNT(*) FROM institution_payment_attempt WHERE currency_code = 'USD')::integer,
    3,
    'All payment attempts use USD currency'
);

-- 5. Wrap up
SELECT * FROM finish();

ROLLBACK;
