"""
Database tests for customer payment methods (Stripe integration Phase 2).

- Verifies user_info.stripe_customer_id and user_history.stripe_customer_id exist.
- Tests payment_method + external_payment_method flow (insert, list, archive, set default).
"""

import pytest
from uuid import uuid4, UUID
from app.tests.database.conftest import db_transaction, get_table_columns
from app.tests.database.test_data.expected_seed_data import (
    SEED_SUPERADMIN_USER_ID,
    SEED_INSTITUTION_CUSTOMERS_ID,
)

SEED_MARKET_ID = "00000000-0000-0000-0000-000000000001"


class TestStripeCustomerIdColumn:
    """Test stripe_customer_id column in user_info and user_history."""

    def test_user_info_has_stripe_customer_id(self, db_transaction):
        """user_info table has stripe_customer_id column."""
        columns = get_table_columns(db_transaction, "user_info")
        assert "stripe_customer_id" in columns

    def test_user_history_has_stripe_customer_id(self, db_transaction):
        """user_history table has stripe_customer_id column."""
        columns = get_table_columns(db_transaction, "user_history")
        assert "stripe_customer_id" in columns

    def test_user_info_stripe_customer_id_can_be_updated(self, db_transaction):
        """Can set stripe_customer_id on user_info and it propagates to history."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        cust_inst_id = str(SEED_INSTITUTION_CUSTOMERS_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_info (
                    user_id, institution_id, role_type, role_name,
                    username, email, hashed_password, market_id, modified_by
                ) VALUES (%s, %s, 'Customer'::role_type_enum, 'Comensal'::role_name_enum,
                    'stripe_test_user', 'stripe_test@example.com', 'hash', %s::uuid, %s)
                """,
                (str(user_id), cust_inst_id, SEED_MARKET_ID, admin_id),
            )
            cur.execute(
                "UPDATE user_info SET stripe_customer_id = %s WHERE user_id = %s",
                ("cus_mock_abc123", str(user_id)),
            )
            cur.execute(
                "SELECT stripe_customer_id FROM user_info WHERE user_id = %s",
                (str(user_id),),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "cus_mock_abc123"
            cur.execute(
                "SELECT stripe_customer_id FROM user_history WHERE user_id = %s AND is_current = TRUE",
                (str(user_id),),
            )
            hist = cur.fetchone()
            assert hist is not None
            assert hist[0] == "cus_mock_abc123"


class TestCustomerPaymentMethodFlow:
    """Test payment_method + external_payment_method for Stripe (Customer)."""

    def _create_customer_user(self, cur, user_id: UUID, admin_id: str) -> None:
        """Create a Customer user for testing."""
        cust_inst_id = str(SEED_INSTITUTION_CUSTOMERS_ID)
        cur.execute(
            """
            INSERT INTO user_info (
                user_id, institution_id, role_type, role_name,
                username, email, hashed_password, market_id, modified_by
            ) VALUES (%s, %s, 'Customer'::role_type_enum, 'Comensal'::role_name_enum,
                %s, %s, 'hash', %s::uuid, %s)
            """,
            (
                str(user_id),
                cust_inst_id,
                f"cust_{user_id.hex[:8]}",
                f"cust_{user_id.hex[:8]}@example.com",
                SEED_MARKET_ID,
                admin_id,
            ),
        )

    def test_payment_method_and_external_can_be_created(self, db_transaction):
        """Can insert payment_method + external_payment_method for a Customer."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, user_id, admin_id)
            pm_id = uuid4()
            ext_id = f"pm_mock_{uuid4().hex[:24]}"
            cur.execute(
                """
                INSERT INTO payment_method (payment_method_id, user_id, method_type, is_archived, status, is_default, modified_by)
                VALUES (%s, %s, 'Stripe', false, 'Active'::status_enum, true, %s)
                """,
                (str(pm_id), str(user_id), admin_id),
            )
            cur.execute(
                """
                INSERT INTO external_payment_method (payment_method_id, provider, external_id, last4, brand, provider_customer_id)
                VALUES (%s, 'stripe', %s, '4242', 'visa', 'cus_mock_test')
                """,
                (str(pm_id), ext_id),
            )
            cur.execute(
                """
                SELECT pm.payment_method_id, pm.is_default, epm.external_id, epm.last4, epm.brand
                FROM payment_method pm
                JOIN external_payment_method epm ON epm.payment_method_id = pm.payment_method_id
                WHERE pm.user_id = %s AND pm.is_archived = FALSE AND epm.provider = 'stripe'
                """,
                (str(user_id),),
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][2] == ext_id
            assert rows[0][3] == "4242"
            assert rows[0][4] == "visa"

    def test_payment_method_can_be_archived(self, db_transaction):
        """Archiving payment_method excludes it from list query."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, user_id, admin_id)
            pm_id = uuid4()
            ext_id = f"pm_mock_{uuid4().hex[:24]}"
            cur.execute(
                """
                INSERT INTO payment_method (payment_method_id, user_id, method_type, is_archived, status, is_default, modified_by)
                VALUES (%s, %s, 'Stripe', false, 'Active'::status_enum, true, %s)
                """,
                (str(pm_id), str(user_id), admin_id),
            )
            cur.execute(
                """
                INSERT INTO external_payment_method (payment_method_id, provider, external_id, last4, brand)
                VALUES (%s, 'stripe', %s, '4242', 'visa')
                """,
                (str(pm_id), ext_id),
            )
            cur.execute(
                "UPDATE payment_method SET is_archived = TRUE, modified_by = %s WHERE payment_method_id = %s",
                (str(user_id), str(pm_id)),
            )
            cur.execute(
                """
                SELECT COUNT(*) FROM payment_method pm
                JOIN external_payment_method epm ON epm.payment_method_id = pm.payment_method_id
                WHERE pm.user_id = %s AND pm.is_archived = FALSE AND epm.provider = 'stripe'
                """,
                (str(user_id),),
            )
            assert cur.fetchone()[0] == 0

    def test_payment_method_is_default_can_be_updated(self, db_transaction):
        """Can update is_default: clear others, set one."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, user_id, admin_id)
            pm1 = uuid4()
            pm2 = uuid4()
            ext1 = f"pm_mock_{uuid4().hex[:24]}"
            ext2 = f"pm_mock_{uuid4().hex[:24]}"
            cur.execute(
                """
                INSERT INTO payment_method (payment_method_id, user_id, method_type, is_archived, status, is_default, modified_by)
                VALUES (%s, %s, 'Stripe', false, 'Active'::status_enum, true, %s),
                       (%s, %s, 'Stripe', false, 'Active'::status_enum, false, %s)
                """,
                (str(pm1), str(user_id), admin_id, str(pm2), str(user_id), admin_id),
            )
            cur.execute(
                """
                INSERT INTO external_payment_method (payment_method_id, provider, external_id, last4, brand)
                VALUES (%s, 'stripe', %s, '4242', 'visa'),
                       (%s, 'stripe', %s, '5555', 'mastercard')
                """,
                (str(pm1), ext1, str(pm2), ext2),
            )
            cur.execute(
                "UPDATE payment_method SET is_default = FALSE WHERE user_id = %s",
                (str(user_id),),
            )
            cur.execute(
                "UPDATE payment_method SET is_default = TRUE WHERE payment_method_id = %s",
                (str(pm2),),
            )
            cur.execute(
                """
                SELECT payment_method_id, is_default FROM payment_method
                WHERE user_id = %s AND is_archived = FALSE ORDER BY payment_method_id
                """,
                (str(user_id),),
            )
            rows = cur.fetchall()
            assert len(rows) == 2
            defaults = {str(r[0]): r[1] for r in rows}
            assert defaults[str(pm1)] is False
            assert defaults[str(pm2)] is True
