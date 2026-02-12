"""
Database tests for market-based subscription constraints

Tests the unique constraint that prevents duplicate subscriptions
per user per market.
"""

import pytest
import psycopg2
from uuid import uuid4
from app.tests.database.conftest import db_transaction


class TestMarketSubscriptionConstraints:
    """Test market-based subscription database constraints"""
    
    def test_unique_user_market_subscription_constraint(self, db_transaction):
        """
        Test that the idx_user_market_active unique index prevents
        duplicate active subscriptions for the same user in the same market.
        
        Business Rule: A user can only have ONE active subscription per market.
        """
        cursor = db_transaction.cursor()
        
        try:
            # Use admin user for test (we'll only insert into this transaction, no conflict with seed data)
            cursor.execute("""
                SELECT user_id FROM user_info 
                WHERE username = 'admin' 
                LIMIT 1
            """)
            user_id = cursor.fetchone()[0]
            
            # Use Chile market (admin doesn't have a subscription there yet)
            cursor.execute("""
                SELECT market_id FROM market_info 
                WHERE country_code = 'CHL' 
                LIMIT 1
            """)
            market_result = cursor.fetchone()
            market_id = market_result[0]
            
            # Get a plan for this market
            cursor.execute("""
                SELECT plan_id FROM plan_info 
                WHERE market_id = %s 
                LIMIT 1
            """, (market_id,))
            plan_id = cursor.fetchone()[0]
            
            # Get modified_by user (use admin)
            cursor.execute("""
                SELECT user_id FROM user_info 
                WHERE username = 'admin' 
                LIMIT 1
            """)
            modified_by = cursor.fetchone()[0]
            
            # Create first subscription (should succeed)
            subscription_id_1 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'Active', FALSE, 'Active', %s)
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
                    VALUES (%s, %s, %s, %s, 'Active', FALSE, 'Active', %s)
                """, (subscription_id_2, user_id, market_id, plan_id, modified_by))
            
            # Verify the error is about the unique constraint
            assert 'idx_user_market_active' in str(exc_info.value)
            
            # Note: Cleanup not needed - fixture auto-rollbacks after test
            
        except Exception as e:
            db_transaction.rollback()
            raise e
        finally:
            cursor.close()
    
    def test_user_can_subscribe_to_multiple_markets(self, db_transaction):
        """
        Test that a user CAN have multiple subscriptions across different markets.
        
        Business Rule: Users can subscribe to multiple markets simultaneously.
        """
        cursor = db_transaction.cursor()
        
        try:
            # Use admin user for test
            cursor.execute("""
                SELECT user_id FROM user_info 
                WHERE username = 'admin' 
                LIMIT 1
            """)
            user_id = cursor.fetchone()[0]
            
            # Get two different markets (use Peru and Chile, admin only has Argentina)
            cursor.execute("""
                SELECT market_id FROM market_info 
                WHERE country_code IN ('PER', 'CHL')
                ORDER BY country_code
            """)
            markets = cursor.fetchall()
            market_id_1 = markets[1][0]  # Chile
            market_id_2 = markets[0][0]  # Peru
            
            # Get plans for each market
            cursor.execute("""
                SELECT plan_id FROM plan_info 
                WHERE market_id = %s 
                LIMIT 1
            """, (market_id_1,))
            plan_id_1 = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT plan_id FROM plan_info 
                WHERE market_id = %s 
                LIMIT 1
            """, (market_id_2,))
            plan_id_2 = cursor.fetchone()[0]
            
            # Get modified_by user
            cursor.execute("""
                SELECT user_id FROM user_info 
                WHERE username = 'admin' 
                LIMIT 1
            """)
            modified_by = cursor.fetchone()[0]
            
            # Create subscription in Market 1 (should succeed)
            subscription_id_1 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'Active', FALSE, 'Active', %s)
            """, (subscription_id_1, user_id, market_id_1, plan_id_1, modified_by))
            
            # Create subscription in Market 2 (should also succeed)
            subscription_id_2 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'Active', FALSE, 'Active', %s)
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
            
            # Note: Cleanup not needed - fixture auto-rollbacks after test
            
        except Exception as e:
            db_transaction.rollback()
            raise e
        finally:
            cursor.close()
    
    def test_archived_subscriptions_do_not_block_new_ones(self, db_transaction):
        """
        Test that archived subscriptions do not prevent creating new ones.
        
        Business Rule: The unique constraint only applies to non-archived subscriptions.
        """
        cursor = db_transaction.cursor()
        
        try:
            # Use superadmin user for test (has Peru subscription, but not Argentina)
            cursor.execute("""
                SELECT user_id FROM user_info 
                WHERE username = 'superadmin' 
                LIMIT 1
            """)
            user_id = cursor.fetchone()[0]
            
            # Use Argentina market (superadmin doesn't have a subscription there)
            cursor.execute("""
                SELECT market_id FROM market_info 
                WHERE country_code = 'ARG' 
                LIMIT 1
            """)
            market_id = cursor.fetchone()[0]
            
            # Get a plan
            cursor.execute("""
                SELECT plan_id FROM plan_info 
                WHERE market_id = %s 
                LIMIT 1
            """, (market_id,))
            plan_id = cursor.fetchone()[0]
            
            # Get modified_by user
            cursor.execute("""
                SELECT user_id FROM user_info 
                WHERE username = 'admin' 
                LIMIT 1
            """)
            modified_by = cursor.fetchone()[0]
            
            # Create and archive first subscription
            subscription_id_1 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'Cancelled', TRUE, 'Inactive', %s)
            """, (subscription_id_1, user_id, market_id, plan_id, modified_by))
            
            # Create new active subscription (should succeed because first is archived)
            subscription_id_2 = str(uuid4())
            cursor.execute("""
                INSERT INTO subscription_info (
                    subscription_id, user_id, market_id, plan_id,
                    subscription_status, is_archived, status,
                    modified_by
                )
                VALUES (%s, %s, %s, %s, 'Active', FALSE, 'Active', %s)
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
