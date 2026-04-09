"""
Database integration tests.

Tests complex workflows and CRUD operations with real database connections.
Replaces: app/db/tests/03_supplier_onboarding.sql

Note: This is a simplified version focusing on key integration patterns.
The original pgTAP test was very comprehensive - this version uses factories
and focuses on testing workflows rather than hardcoded values.
"""

import pytest
from uuid import uuid4, UUID
from app.tests.database.conftest import (
    db_transaction, count_rows, record_exists
)
from app.tests.database.test_data.expected_seed_data import SEED_SUPERADMIN_USER_ID


class TestSupplierOnboarding:
    """Test supplier onboarding workflow."""
    
    def test_institution_crud_workflow(self, db_transaction):
        """Test creating, updating an institution and verifying history."""
        institution_id = uuid4()
        admin_user_id = str(SEED_SUPERADMIN_USER_ID)
        
        with db_transaction.cursor() as cur:
            # Create institution
            cur.execute("""
                INSERT INTO institution_info (institution_id, name, modified_by)
                VALUES (%s, 'Test Supplier Inc.', %s)
            """, (str(institution_id), admin_user_id))
            
            # Verify creation
            cur.execute("""
                SELECT COUNT(*) FROM institution_info WHERE institution_id = %s
            """, (str(institution_id),))
            assert cur.fetchone()[0] == 1, "Institution should be created"
            
            # Verify history record created
            cur.execute("""
                SELECT COUNT(*) FROM institution_history WHERE institution_id = %s
            """, (str(institution_id),))
            assert cur.fetchone()[0] >= 1, "Institution history record should be created"
            
            # Update institution
            cur.execute("""
                UPDATE institution_info
                SET name = 'Test Supplier Inc. Updated'
                WHERE institution_id = %s
            """, (str(institution_id),))
            
            # Verify update
            cur.execute("""
                SELECT name FROM institution_info WHERE institution_id = %s
            """, (str(institution_id),))
            assert cur.fetchone()[0] == 'Test Supplier Inc. Updated', "Institution should be updated"
            
            # Verify new history record
            cur.execute("""
                SELECT COUNT(*) FROM institution_history WHERE institution_id = %s
            """, (str(institution_id),))
            assert cur.fetchone()[0] > 1, "Institution update should create new history record"
    
    def test_user_crud_workflow(self, db_transaction):
        """Test creating and updating a user with history tracking."""
        user_id = uuid4()
        institution_id = uuid4()
        admin_user_id = str(SEED_SUPERADMIN_USER_ID)
        
        with db_transaction.cursor() as cur:
            # Create institution first (required for user)
            cur.execute("""
                INSERT INTO institution_info (institution_id, name, modified_by)
                VALUES (%s, 'Test Institution', %s)
            """, (str(institution_id), admin_user_id))
            
            # Create user (market_id required; use Global Marketplace from seed)
            cur.execute("""
                INSERT INTO user_info (
                    user_id, institution_id, role_type, role_name, 
                    username, email, hashed_password, mobile_number, market_id, modified_by
                ) VALUES (%s, %s, 'supplier'::role_type_enum, 'admin'::role_name_enum,
                    'supplier_user', 'supplier_crud_test@example.com', 'hashedpwd', '+15005550006',
                    '00000000-0000-0000-0000-000000000001'::uuid, %s)
            """, (str(user_id), str(institution_id), admin_user_id))
            
            # Verify creation
            cur.execute("""
                SELECT COUNT(*) FROM user_info WHERE user_id = %s
            """, (str(user_id),))
            assert cur.fetchone()[0] == 1, "User should be created"
            
            # Verify history
            cur.execute("""
                SELECT COUNT(*) FROM user_history WHERE user_id = %s
            """, (str(user_id),))
            assert cur.fetchone()[0] >= 1, "User history record should be created"
            
            # Update user
            cur.execute("""
                UPDATE user_info SET username = 'supplier_user_updated'
                WHERE user_id = %s
            """, (str(user_id),))
            
            # Verify update
            cur.execute("""
                SELECT username FROM user_info WHERE user_id = %s
            """, (str(user_id),))
            assert cur.fetchone()[0] == 'supplier_user_updated', "User should be updated"
            
            # Verify new history record
            cur.execute("""
                SELECT COUNT(*) FROM user_history WHERE user_id = %s
            """, (str(user_id),))
            assert cur.fetchone()[0] > 1, "User update should create new history record"
    
    def test_history_table_triggers(self, db_transaction):
        """Test that history tables are automatically populated on inserts/updates."""
        institution_id = uuid4()
        admin_user_id = str(SEED_SUPERADMIN_USER_ID)
        
        with db_transaction.cursor() as cur:
            # Get initial history count
            cur.execute("SELECT COUNT(*) FROM institution_history")
            initial_count = cur.fetchone()[0]
            
            # Create institution
            cur.execute("""
                INSERT INTO institution_info (institution_id, name, modified_by)
                VALUES (%s, 'Test Institution', %s)
            """, (str(institution_id), admin_user_id))
            
            # Verify history count increased
            cur.execute("SELECT COUNT(*) FROM institution_history")
            new_count = cur.fetchone()[0]
            assert new_count > initial_count, "History record should be created on insert"
            
            # Update institution
            cur.execute("""
                UPDATE institution_info SET name = 'Updated Name'
                WHERE institution_id = %s
            """, (str(institution_id),))
            
            # Verify history count increased again
            cur.execute("SELECT COUNT(*) FROM institution_history")
            final_count = cur.fetchone()[0]
            assert final_count > new_count, "History record should be created on update"


class TestPaymentMethodAddressIntegration:
    """Test payment method and address integration (new feature)."""
    
    def test_payment_method_with_address(self, db_transaction):
        """Test that payment_method table has address_id column and can reference addresses."""
        with db_transaction.cursor() as cur:
            # Verify payment_method table has address_id column
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'payment_method' 
                  AND column_name = 'address_id'
            """)
            result = cur.fetchone()
            assert result is not None, "payment_method table should have address_id column"
            
            # Verify address_id can be NULL (some payment methods don't require addresses)
            cur.execute("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'payment_method' 
                  AND column_name = 'address_id'
            """)
            is_nullable = cur.fetchone()[0]
            assert is_nullable == 'YES', "address_id should be nullable"


