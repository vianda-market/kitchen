"""
Database tests for market-based subscription constraints

Tests the unique constraint that prevents duplicate subscriptions
per user per market. Uses minimal seed (superadmin, Global market only);
creates plan(s) in-test as needed.
"""

import pytest
import psycopg2
from uuid import uuid4
from app.tests.database.conftest import db_transaction
from app.tests.database.test_data.expected_seed_data import (
    SEED_INSTITUTION_CUSTOMERS_ID,
    SEED_SUPERADMIN_USER_ID,
)

# Argentina and Peru for plan/subscription tests (plans cannot use Global Marketplace)
ARGENTINA_MARKET_ID = "00000000-0000-0000-0000-000000000002"
PERU_MARKET_ID = "00000000-0000-0000-0000-000000000003"


def _make_subscription_user(cursor, admin_id: str) -> str:
    """Create a unique Customer user for subscription tests. Avoids idx_user_market_active collision with committed data from other tests."""
    user_id = str(uuid4())
    h = user_id[:8]
    cursor.execute(
        """
        INSERT INTO user_info (
            user_id, institution_id, role_type, role_name, username, email,
            hashed_password, market_id, modified_by
        ) VALUES (%s, %s, 'customer'::role_type_enum, 'comensal'::role_name_enum,
            %s, %s, 'hash', %s::uuid, %s)
        """,
        (
            user_id,
            str(SEED_INSTITUTION_CUSTOMERS_ID),
            f"market_test_{h}",
            f"market_test_{h}@example.com",
            ARGENTINA_MARKET_ID,
            admin_id,
        ),
    )
    return user_id


def _ensure_plan_for_market(cursor, market_id, modified_by, plan_id=None):
    """Insert one plan for the given market if none exists; return plan_id."""
    cursor.execute("SELECT plan_id FROM plan_info WHERE market_id = %s LIMIT 1", (market_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    pid = plan_id or str(uuid4())
    cursor.execute("""
        INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by, modified_date)
        VALUES (%s, %s, 'Test Plan', 10, 100.0, 0.0, 0.0, TRUE, FALSE, 'active'::status_enum, %s, CURRENT_TIMESTAMP)
    """, (pid, market_id, modified_by))
    return pid


class TestMarketSubscriptionConstraints:
    """Test market-based subscription database constraints"""
    
    def test_unique_user_market_subscription_constraint(self, db_transaction):
        """
        Test that the idx_user_market_active unique index prevents
        duplicate active subscriptions for the same user in the same market.
        
        Business Rule: A user can only have ONE active subscription per market.
        """
        cursor = db_transaction.cursor()
        modified_by = str(SEED_SUPERADMIN_USER_ID)
        user_id = _make_subscription_user(cursor, modified_by)

        try:
            plan_id = _ensure_plan_for_market(cursor, ARGENTINA_MARKET_ID, modified_by)
            market_id = ARGENTINA_MARKET_ID

            # Create first subscription (should succeed)
            subscription_id_1 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'active', FALSE, 'active', %s)
            """, (subscription_id_1, user_id, market_id, plan_id, modified_by))

            # Try to create second subscription for same user/market (should fail)
            subscription_id_2 = str(uuid4())
            with pytest.raises(psycopg2.errors.UniqueViolation) as exc_info:
                cursor.execute("""
                    INSERT INTO subscription_info (
                        subscription_id, user_id, market_id, plan_id,
                        subscription_status, is_archived, status,
                        modified_by
                    )
                    VALUES (%s, %s, %s, %s, 'active', FALSE, 'active', %s)
                """, (subscription_id_2, user_id, market_id, plan_id, modified_by))
            
            # Verify the error is about the unique constraint
            assert 'idx_user_market_active' in str(exc_info.value)
            
        except Exception as e:
            db_transaction.rollback()
            raise e
        finally:
            cursor.close()
    
    def test_user_can_subscribe_to_multiple_markets(self, db_transaction):
        """
        Test that a user CAN have multiple subscriptions across different markets.
        Uses Argentina and Peru (plans cannot use Global Marketplace).
        """
        cursor = db_transaction.cursor()
        modified_by = str(SEED_SUPERADMIN_USER_ID)
        user_id = _make_subscription_user(cursor, modified_by)

        try:
            # Use two country markets (plans cannot be for Global Marketplace)
            plan_id_1 = _ensure_plan_for_market(cursor, ARGENTINA_MARKET_ID, modified_by)
            market_id_1 = ARGENTINA_MARKET_ID
            plan_id_2 = _ensure_plan_for_market(cursor, PERU_MARKET_ID, modified_by)
            market_id_2 = PERU_MARKET_ID
            
            # Create subscription in Market 1 (should succeed)
            subscription_id_1 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'active', FALSE, 'active', %s)
            """, (subscription_id_1, user_id, market_id_1, plan_id_1, modified_by))
            
            # Create subscription in Market 2 (should also succeed)
            subscription_id_2 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'active', FALSE, 'active', %s)
            """, (subscription_id_2, user_id, market_id_2, plan_id_2, modified_by))
            
            # Verify both subscriptions exist
            cursor.execute("""
                SELECT COUNT(*) FROM subscription_info 
                WHERE user_id = %s 
                AND subscription_id IN (%s, %s)
                AND is_archived = FALSE
            """, (user_id, subscription_id_1, subscription_id_2))
            
            count = cursor.fetchone()[0]
            assert count == 2, f"Expected 2 subscriptions, found {count}"
            
        except Exception as e:
            db_transaction.rollback()
            raise e
        finally:
            cursor.close()
    
    def test_archived_subscriptions_do_not_block_new_ones(self, db_transaction):
        """
        Test that archived subscriptions do not prevent creating new ones.
        Uses unique user and Argentina market; creates plan in-test.
        """
        cursor = db_transaction.cursor()
        modified_by = str(SEED_SUPERADMIN_USER_ID)
        user_id = _make_subscription_user(cursor, modified_by)

        try:
            plan_id = _ensure_plan_for_market(cursor, ARGENTINA_MARKET_ID, modified_by)
            market_id = ARGENTINA_MARKET_ID
            
            # Create and archive first subscription
            subscription_id_1 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'cancelled', TRUE, 'inactive', %s)
            """, (subscription_id_1, user_id, market_id, plan_id, modified_by))
            
            # Create new active subscription (should succeed because first is archived)
            subscription_id_2 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'active', FALSE, 'active', %s)
            """, (subscription_id_2, user_id, market_id, plan_id, modified_by))
            
            # Verify both exist (one archived, one active)
            cursor.execute("""
                SELECT COUNT(*) FROM subscription_info 
                WHERE user_id = %s 
                AND market_id = %s
                AND subscription_id IN (%s, %s)
            """, (user_id, market_id, subscription_id_1, subscription_id_2))
            
            count = cursor.fetchone()[0]
            assert count == 2, f"Expected 2 subscriptions (1 archived, 1 active), found {count}"
            
            # Note: Cleanup not needed - fixture auto-rollbacks after test
            
        except Exception as e:
            db_transaction.rollback()
            raise e
        finally:
            cursor.close()
