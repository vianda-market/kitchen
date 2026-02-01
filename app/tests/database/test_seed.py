"""
Seed data validation tests.

Tests that seed data is correctly loaded into the database.
Replaces: app/db/tests/02_initial_seed.sql
"""

import pytest
from app.tests.database.conftest import (
    db_transaction, count_rows, record_exists
)
from app.tests.database.test_data.expected_seed_data import (
    SEED_ADMIN_USER_ID,
    SEED_INSTITUTION_VIANDA_ID,
    EXPECTED_SEED_COUNTS,
    get_expected_user_count,
    get_expected_institution_count,
    get_expected_currency_count
)


class TestSeedDataCounts:
    """Test that seed data has correct row counts."""
    
    def test_user_info_seed_count(self, db_transaction):
        """Test that user_info has the expected number of seeded rows."""
        count = count_rows(db_transaction, 'user_info')
        expected = get_expected_user_count()
        assert count == expected, (
            f"Expected {expected} users in user_info, found {count}"
        )
    
    def test_institution_info_seed_count(self, db_transaction):
        """Test that institution_info has the expected number of seeded rows."""
        count = count_rows(db_transaction, 'institution_info')
        expected = get_expected_institution_count()
        assert count >= expected, (
            f"Expected at least {expected} institutions in institution_info, found {count}"
        )
    
    def test_credit_currency_info_seed_count(self, db_transaction):
        """Test that credit_currency_info table exists (currencies created via API, not seeded)."""
        # Currencies are no longer seeded - they're created via API endpoints
        # Just verify the table exists and is accessible
        count = count_rows(db_transaction, 'credit_currency_info')
        # Table should exist (count can be 0 or more)
        assert count >= 0, "credit_currency_info table should be accessible"


class TestSeedDataRecords:
    """Test that specific seed records exist."""
    
    def test_admin_user_seeded(self, db_transaction):
        """Test that admin user is seeded."""
        assert record_exists(
            db_transaction, 
            'user_info', 
            'user_id', 
            str(SEED_ADMIN_USER_ID)
        ), f"Admin user with ID {SEED_ADMIN_USER_ID} should be seeded"
    
    def test_vianda_enterprises_seeded(self, db_transaction):
        """Test that Vianda Enterprises institution is seeded."""
        assert record_exists(
            db_transaction,
            'institution_info',
            'institution_id',
            str(SEED_INSTITUTION_VIANDA_ID)
        ), f"Vianda Enterprises institution with ID {SEED_INSTITUTION_VIANDA_ID} should be seeded"
    
    @pytest.mark.skip(reason="Currencies are no longer seeded - created via API")
    def test_usd_currency_seeded(self, db_transaction):
        """Test that USD currency is seeded (skipped - currencies created via API)."""
        # This test is skipped because currencies are now created via API endpoints
        # rather than being seeded into the database
        pass
    
    def test_admin_user_properties(self, db_transaction):
        """Test that admin user has correct properties."""
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT username, role_type, role_name, email
                FROM user_info
                WHERE user_id = %s
            """, (str(SEED_ADMIN_USER_ID),))
            result = cur.fetchone()
            
            assert result is not None, "Admin user should exist"
            username, role_type, role_name, email = result
            
            assert username == 'admin', f"Admin username should be 'admin', got '{username}'"
            assert role_type == 'Employee', f"Admin role_type should be 'Employee', got '{role_type}'"
            assert role_name == 'Admin', f"Admin role_name should be 'Admin', got '{role_name}'"
            assert email == 'admin@example.com', f"Admin email should be 'admin@example.com', got '{email}'"
    
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

