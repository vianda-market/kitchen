"""
Seed data validation tests.

Tests that seed data is correctly loaded into the database.
Replaces: app/db/tests/02_initial_seed.sql
"""

import pytest
from app.tests.database.conftest import (
    db_transaction, count_rows, count_non_archived_rows, record_exists
)
from app.tests.database.test_data.expected_seed_data import (
    SEED_SUPERADMIN_USER_ID,
    SEED_INSTITUTION_VIANDA_ID,
    get_expected_user_count,
    get_expected_institution_count,
    get_expected_currency_count,
    get_expected_market_count,
    get_expected_cuisine_count,
)


class TestSeedDataCounts:
    """Test that seed data has correct row counts."""
    
    def test_user_info_seed_count(self, db_transaction):
        """Test that user_info has the expected number of seeded rows (excludes archived test data)."""
        count = count_non_archived_rows(db_transaction, 'user_info')
        expected = get_expected_user_count()
        assert count == expected, (
            f"Expected {expected} users in user_info, found {count}"
        )
    
    def test_institution_info_seed_count(self, db_transaction):
        """Test that institution_info has the expected number of seeded rows (excludes archived test data)."""
        count = count_non_archived_rows(db_transaction, 'institution_info')
        expected = get_expected_institution_count()
        assert count >= expected, (
            f"Expected at least {expected} institutions in institution_info, found {count}"
        )
    
    def test_credit_currency_info_seed_count(self, db_transaction):
        """Test that seed has the expected number of credit currencies (6: USD, ARS, PEN, CLP, MXN, BRL; excludes archived)."""
        count = count_non_archived_rows(db_transaction, 'credit_currency_info')
        expected = get_expected_currency_count()
        assert count == expected, (
            f"Expected {expected} credit currency/currencies in seed, found {count}"
        )

    def test_market_info_seed_count(self, db_transaction):
        """Test that seed has the expected number of markets (excludes archived test data)."""
        count = count_non_archived_rows(db_transaction, 'market_info')
        expected = get_expected_market_count()
        assert count == expected, (
            f"Expected {expected} market(s) in seed, found {count}"
        )

    def test_cuisine_seed_count(self, db_transaction):
        """Test that seed has the expected number of cuisines (22 non-archived)."""
        count = count_non_archived_rows(db_transaction, 'cuisine')
        expected = get_expected_cuisine_count()
        assert count == expected, (
            f"Expected {expected} cuisine(s) in seed, found {count}"
        )


class TestSeedDataRecords:
    """Test that specific seed records exist."""
    
    def test_superadmin_user_seeded(self, db_transaction):
        """Test that Super Admin user is seeded."""
        assert record_exists(
            db_transaction,
            'user_info',
            'user_id',
            str(SEED_SUPERADMIN_USER_ID)
        ), f"Super Admin user with ID {SEED_SUPERADMIN_USER_ID} should be seeded"
    
    def test_vianda_enterprises_seeded(self, db_transaction):
        """Test that Vianda Enterprises institution is seeded."""
        assert record_exists(
            db_transaction,
            'institution_info',
            'institution_id',
            str(SEED_INSTITUTION_VIANDA_ID)
        ), f"Vianda Enterprises institution with ID {SEED_INSTITUTION_VIANDA_ID} should be seeded"
    
    def test_usd_currency_seeded(self, db_transaction):
        """Test that USD (minimal bootstrap currency) is seeded."""
        usd_currency_id = '55555555-5555-5555-5555-555555555555'
        assert record_exists(
            db_transaction,
            'credit_currency_info',
            'credit_currency_id',
            usd_currency_id
        ), "US Dollar (USD) bootstrap currency should be seeded"
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT currency_name, currency_code
                FROM credit_currency_info
                WHERE credit_currency_id = %s
            """, (usd_currency_id,))
            result = cur.fetchone()
            assert result is not None, "USD currency should exist"
            currency_name, currency_code = result
            assert currency_name == 'US Dollar', f"Expected 'US Dollar', got '{currency_name}'"
            assert currency_code == 'USD', f"Expected 'USD', got '{currency_code}'"

    def test_argentina_market_has_ars_currency(self, db_transaction):
        """Test that Argentina market resolves to ARS via credit_currency join (not USD)."""
        argentina_market_id = '00000000-0000-0000-0000-000000000002'
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT cc.currency_code
                FROM market_info m
                JOIN credit_currency_info cc ON m.credit_currency_id = cc.credit_currency_id
                WHERE m.market_id = %s
            """, (argentina_market_id,))
            result = cur.fetchone()
            assert result is not None, "Argentina market should exist with credit currency"
            currency_code = result[0]
            assert currency_code == 'ARS', f"Argentina market should have ARS, got '{currency_code}'"

    def test_global_market_seeded(self, db_transaction):
        """Test that Global Marketplace (minimal bootstrap market) is seeded."""
        global_market_id = '00000000-0000-0000-0000-000000000001'
        assert record_exists(
            db_transaction,
            'market_info',
            'market_id',
            global_market_id
        ), "Global Marketplace should be seeded"

    def test_argentina_market_language_is_spanish(self, db_transaction):
        """B2C signup derives locale from market_info.language; AR must stay es."""
        argentina_market_id = '00000000-0000-0000-0000-000000000002'
        with db_transaction.cursor() as cur:
            cur.execute(
                "SELECT language FROM market_info WHERE market_id = %s",
                (argentina_market_id,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row[0] == "es"

    def test_pending_customer_signup_has_market_id_column(self, db_transaction):
        """Signup verify flow requires market_id on pending row (no regression)."""
        with db_transaction.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'customer'
                  AND table_name = 'pending_customer_signup'
                  AND column_name = 'market_id'
                """
            )
            assert cur.fetchone() is not None
    
    def test_superadmin_user_properties(self, db_transaction):
        """Test that Super Admin user has correct properties."""
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT username, role_type, role_name, email
                FROM user_info
                WHERE user_id = %s
            """, (str(SEED_SUPERADMIN_USER_ID),))
            result = cur.fetchone()
            
            assert result is not None, "Super Admin user should exist"
            username, role_type, role_name, email = result
            
            assert username == 'superadmin', f"Super Admin username should be 'superadmin', got '{username}'"
            assert role_type == 'Internal', f"Super Admin role_type should be 'Internal', got '{role_type}'"
            assert role_name == 'Super Admin', f"Super Admin role_name should be 'Super Admin', got '{role_name}'"
            assert email == 'viandallc@gmail.com', f"Super Admin email should be 'viandallc@gmail.com', got '{email}'"
    
    def test_vianda_enterprises_name(self, db_transaction):
        """Test that Vianda Enterprises has correct name."""
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT name
                FROM institution_info
                WHERE institution_id = %s
            """, (str(SEED_INSTITUTION_VIANDA_ID),))
            result = cur.fetchone()
            
            assert result is not None, "Vianda Enterprises should exist"
            name = result[0]
            assert name == 'Vianda Enterprises', (
                f"Vianda Enterprises name should be 'Vianda Enterprises', got '{name}'"
            )

