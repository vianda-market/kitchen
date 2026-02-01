"""
Expected table lists for schema validation tests.

These lists are used to verify that all expected tables exist in the database schema.
Tables are organized by category for easier maintenance and testing.
"""

# Base/Parent Tables (core entities)
BASE_TABLES = [
    'user_info',
    'institution_info',
    'credit_currency_info',
    'address_info',
    'institution_entity_info',
    'restaurant_info',
    'product_info',
    'plate_info',
    'plan_info',
    'payment_method',
    'qr_code',
    'plate_selection',
    'client_bill_info',
    'subscription_info',
    'institution_bill_info',
    'institution_bank_account',
    'geolocation_info',
    'credential_recovery',
    'restaurant_balance_info',
    'discretionary_resolution_info',
    'employer_info',
    'national_holidays',
]

# History Tables (audit trail tables)
HISTORY_TABLES = [
    'user_history',
    'institution_history',
    'institution_entity_history',
    'address_history',
    'restaurant_history',
    'product_history',
    'plate_history',
    'plan_history',
    'credit_currency_history',
    'geolocation_history',
    'subscription_history',
    'client_bill_history',
    'institution_bill_history',
    'restaurant_balance_history',
    'discretionary_history',
    'discretionary_resolution_history',
    'employer_history',
    'national_holidays_history',
    'restaurant_holidays_history',
    'plate_kitchen_days_history',
]

# Child Tables (dependent tables)
CHILD_TABLES = [
    'credit_card',
    'bank_account',
    'appstore_account',
    'fintech_wallet',
    'fintech_wallet_auth',
    'fintech_link_info',
    'fintech_link_assignment',
    'fintech_link_history',
    'client_payment_attempt',
    'restaurant_transaction',
    'institution_payment_attempt',
    'discretionary_info',
    'client_transaction',
    'plate_pickup_live',
    'pickup_preferences',
    'restaurant_holidays',
    'plate_kitchen_days',
]

# All expected tables (combined list)
ALL_EXPECTED_TABLES = BASE_TABLES + HISTORY_TABLES + CHILD_TABLES

# Tables that should have critical columns
# Format: (table_name, [column_name, ...])
TABLES_WITH_CRITICAL_COLUMNS = {
    'payment_method': ['address_id'],  # Payment methods can have addresses
    'credit_card': ['payment_method_id'],  # Credit cards belong to payment methods
    'bank_account': ['payment_method_id'],  # Bank accounts belong to payment methods
}


