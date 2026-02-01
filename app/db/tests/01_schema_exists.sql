-- 01_schema_exists.sql
BEGIN;

-- 1. Ensure pgTAP is available
CREATE EXTENSION IF NOT EXISTS pgtap;
\set VERBOSITY verbose

SELECT diag('Checking existence of all expected tables in schema');

-- 2. Declare how many tests we expect
SELECT plan(50);

-- Dependent/History/Resolution Tables (18 tests)
SELECT has_table(current_schema(), 'client_bill_history',           'Dependent: client_bill_history exists');
SELECT has_table(current_schema(), 'subscription_history',          'Dependent: subscription_history exists');
SELECT has_table(current_schema(), 'institution_history',           'Dependent: institution_history exists');
SELECT has_table(current_schema(), 'institution_entity_history',    'Dependent: institution_entity_history exists');
SELECT has_table(current_schema(), 'address_history',               'Dependent: address_history exists');
SELECT has_table(current_schema(), 'institution_bill_history',      'Dependent: institution_bill_history exists');
SELECT has_table(current_schema(), 'discretionary_history',         'Dependent: discretionary_history exists');
SELECT has_table(current_schema(), 'discretionary_resolution_history', 'Dependent: discretionary_resolution_history exists');
SELECT has_table(current_schema(), 'restaurant_balance_history',    'Dependent: restaurant_balance_history exists');
SELECT has_table(current_schema(), 'restaurant_history',            'Dependent: restaurant_history exists');
SELECT has_table(current_schema(), 'plate_history',                 'Dependent: plate_history exists');
-- Removed qr_code_history test since we removed the history table
SELECT has_table(current_schema(), 'product_history',               'Dependent: product_history exists');
SELECT has_table(current_schema(), 'plan_history',                  'Dependent: plan_history exists');
SELECT has_table(current_schema(), 'user_history',                  'Dependent: user_history exists');
SELECT has_table(current_schema(), 'credit_currency_history',       'Dependent: credit_currency_history exists');
-- role_history test removed - table deprecated
SELECT has_table(current_schema(), 'geolocation_history',           'Dependent: geolocation_history exists');
SELECT has_table(current_schema(), 'plan_fintech_link_history',     'Dependent: plan_fintech_link_history exists');
SELECT has_table(current_schema(), 'restaurant_holidays',           'New: restaurant_holidays exists');
SELECT has_table(current_schema(), 'restaurant_holidays_history',   'New: restaurant_holidays_history exists');
SELECT has_table(current_schema(), 'plate_kitchen_days',            'New: plate_kitchen_days exists');
SELECT has_table(current_schema(), 'plate_kitchen_days_history',    'New: plate_kitchen_days_history exists');

-- Child Tables (10 tests)
SELECT has_table(current_schema(), 'credit_card',                    'Child: credit_card exists');
SELECT has_table(current_schema(), 'bank_account',                   'Child: bank_account exists');
SELECT has_table(current_schema(), 'appstore_account',               'Child: appstore_account exists');
SELECT has_table(current_schema(), 'fintech_wallet',                 'Child: fintech_wallet exists');
SELECT has_table(current_schema(), 'client_payment_attempt',         'Child: client_payment_attempt exists');
SELECT has_table(current_schema(), 'restaurant_transaction',         'Child: restaurant_transaction exists');
SELECT has_table(current_schema(), 'institution_payment_attempt',    'Child: institution_payment_attempt exists');
SELECT has_table(current_schema(), 'discretionary_info',            'Child: discretionary_info exists');
SELECT has_table(current_schema(), 'client_transaction',             'Child: client_transaction exists');
SELECT has_table(current_schema(), 'plate_pickup_live',              'Child: plate_pickup_live exists');

-- Base/Parent Tables (20 tests)
SELECT has_table(current_schema(), 'plate_selection',                'Base: plate_selection exists');
SELECT has_table(current_schema(), 'plate_info',                     'Base: plate_info exists');
SELECT has_table(current_schema(), 'client_bill_info',               'Base: client_bill_info exists');
SELECT has_table(current_schema(), 'subscription_info',              'Base: subscription_info exists');
SELECT has_table(current_schema(), 'payment_method',                 'Base: payment_method exists');
SELECT has_table(current_schema(), 'qr_code',                   'Base: qr_code exists');
SELECT has_table(current_schema(), 'plan_info',                      'Base: plan_info exists');
SELECT has_table(current_schema(), 'product_info',                   'Base: product_info exists');
SELECT has_table(current_schema(), 'restaurant_info',                'Base: restaurant_info exists');
SELECT has_table(current_schema(), 'institution_bill_info',          'Base: institution_bill_info exists');
SELECT has_table(current_schema(), 'institution_bank_account',       'Base: institution_bank_account exists');
SELECT has_table(current_schema(), 'geolocation_info',               'Base: geolocation_info exists');
SELECT has_table(current_schema(), 'address_info',                   'Base: address_info exists');
SELECT has_table(current_schema(), 'institution_entity_info',        'Base: institution_entity_info exists');
SELECT has_table(current_schema(), 'institution_info',               'Base: institution_info exists');
SELECT has_table(current_schema(), 'credit_currency_info',           'Base: credit_currency_info exists');
SELECT has_table(current_schema(), 'user_info',                      'Base: user_info exists');
SELECT has_table(current_schema(), 'credential_recovery',            'Base: credential_recovery exists');
-- role_info, status_info, transaction_type_info tests removed - tables deprecated, enums stored directly on entities
SELECT has_table(current_schema(), 'restaurant_balance_info',        'Base: restaurant_balance_info exists');
SELECT has_table(current_schema(), 'discretionary_resolution_info',  'Base: discretionary_resolution_info exists');

-- 3. Finish up
SELECT * FROM finish();

ROLLBACK;
