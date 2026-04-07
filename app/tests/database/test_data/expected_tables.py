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
    'plate_selection_info',
    'client_bill_info',
    'subscription_info',
    'institution_bill_info',
    'geolocation_info',
    'credential_recovery',
    'email_change_request',
    'pending_customer_signup',
    'restaurant_balance_info',
    'discretionary_resolution_info',
    'employer_info',
    'national_holidays',
    'cuisine',
    'cuisine_suggestion',
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
    'plate_selection_history',
    'cuisine_history',
]

# Child Tables (dependent tables)
CHILD_TABLES = [
    'address_subpremise',
    'institution_settlement',
    'external_payment_method',
    'subscription_payment',
    'restaurant_transaction',
    'discretionary_info',
    'client_transaction',
    'plate_pickup_live',
    'plate_review_info',
    'pickup_preferences',
    'restaurant_holidays',
    'plate_kitchen_days',
    'coworker_pickup_notification',
    'user_messaging_preferences',
]

# All expected tables (combined list)
ALL_EXPECTED_TABLES = BASE_TABLES + HISTORY_TABLES + CHILD_TABLES

# Tables that should have critical columns
# Format: (table_name, [column_name, ...])
TABLES_WITH_CRITICAL_COLUMNS = {
    'payment_method': ['address_id'],
    'external_payment_method': ['payment_method_id'],
    'user_info': ['locale'],
    'user_history': ['locale'],
    'user_payment_provider': ['user_payment_provider_id', 'user_id', 'provider', 'provider_customer_id'],
    'user_payment_provider_history': ['event_id', 'user_payment_provider_id', 'is_current'],
    'market_info': ['language'],
}


