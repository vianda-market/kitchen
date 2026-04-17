"""
Expected seed data for database validation tests.

This module contains constants and utilities for validating seed data.
All UUIDs and expected values are defined here to avoid hardcoding in tests.
"""

from uuid import UUID

# Seed users: Super Admin (human), system bot (automated operations only)
SEED_SUPERADMIN_USER_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SEED_SYSTEM_BOT_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# Seed Institution UUIDs: Vianda Enterprises = 11111111, Vianda Customers = 22222222 (no supplier institutions in seed)
SEED_INSTITUTION_VIANDA_ID = UUID("11111111-1111-1111-1111-111111111111")
SEED_INSTITUTION_CUSTOMERS_ID = UUID("22222222-2222-2222-2222-222222222222")

# Expected seed data counts (6 currencies: USD, ARS, PEN, CLP, MXN, BRL; 7 markets)
EXPECTED_SEED_COUNTS = {
    "user_info": 2,
    "institution_info": 2,
    "currency_metadata": 6,  # USD, ARS, PEN, CLP, MXN, BRL
    "market_info": 7,  # Global + AR, PE, US, CL, MX, BR (for city_info)
    "cuisine": 22,  # 22 seeded cuisines
}

# Expected seed record properties
EXPECTED_SEED_RECORDS = {
    "user_info": {
        SEED_SUPERADMIN_USER_ID: {
            "username": "superadmin",
            "role_type": "Employee",
            "role_name": "Super Admin",
            "email": "superadmin@example.com",
        }
    },
    "institution_info": {
        SEED_INSTITUTION_VIANDA_ID: {
            "name": "Vianda Enterprises",
        }
    },
    "currency_metadata": {
        "USD": {"currency_code": "USD"},
        "ARS": {"currency_code": "ARS"},
    },
}


def get_expected_user_count():
    """Get expected number of seeded users."""
    return EXPECTED_SEED_COUNTS["user_info"]


def get_expected_institution_count():
    """Get expected number of seeded institutions."""
    return EXPECTED_SEED_COUNTS["institution_info"]


def get_expected_currency_count():
    """Get expected number of seeded currencies."""
    return EXPECTED_SEED_COUNTS["currency_metadata"]


def get_expected_market_count():
    """Get expected number of seeded markets."""
    return EXPECTED_SEED_COUNTS["market_info"]


def get_expected_cuisine_count():
    """Get expected number of seeded cuisines."""
    return EXPECTED_SEED_COUNTS["cuisine"]
