"""
Database tests for customer payment methods (Stripe integration Phase 2).

- Verifies user_payment_provider and user_payment_provider_history tables.
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


class TestUserPaymentProviderTable:
    """Test user_payment_provider and user_payment_provider_history tables."""

    def _create_customer_user(self, cur, user_id, admin_id, username_suffix=""):
        cust_inst_id = str(SEED_INSTITUTION_CUSTOMERS_ID)
        cur.execute(
            """
            INSERT INTO user_info (
                user_id, institution_id, role_type, role_name,
                username, email, hashed_password, market_id, modified_by
            ) VALUES (%s, %s, 'customer'::role_type_enum, 'comensal'::role_name_enum,
                %s, %s, 'hash', %s::uuid, %s)
            """,
            (
                str(user_id),
                cust_inst_id,
                f"upp_test_{user_id.hex[:8]}{username_suffix}",
                f"upp_{user_id.hex[:8]}{username_suffix}@example.com",
                SEED_MARKET_ID,
                admin_id,
            ),
        )

    def test_user_payment_provider_table_exists(self, db_transaction):
        """user_payment_provider table has expected columns."""
        columns = get_table_columns(db_transaction, "user_payment_provider")
        for col in ("user_payment_provider_id", "user_id", "provider", "provider_customer_id", "is_archived"):
            assert col in columns, f"Missing column: {col}"

    def test_user_payment_provider_history_table_exists(self, db_transaction):
        """user_payment_provider_history table has expected columns."""
        columns = get_table_columns(db_transaction, "user_payment_provider_history")
        for col in ("event_id", "user_payment_provider_id", "provider", "provider_customer_id", "is_current"):
            assert col in columns, f"Missing column: {col}"

    def test_user_info_does_not_have_stripe_customer_id(self, db_transaction):
        """stripe_customer_id column should no longer exist on user_info."""
        columns = get_table_columns(db_transaction, "user_info")
        assert "stripe_customer_id" not in columns

    def test_insert_provider_triggers_history(self, db_transaction):
        """Inserting a user_payment_provider row fires the history trigger."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, user_id, admin_id)
            upp_id = uuid4()
            cur.execute(
                """
                INSERT INTO user_payment_provider (
                    user_payment_provider_id, user_id, provider, provider_customer_id, modified_by
                ) VALUES (%s, %s, 'stripe', %s, %s)
                """,
                (str(upp_id), str(user_id), f"cus_mock_{user_id.hex[:24]}", admin_id),
            )
            cur.execute(
                """
                SELECT provider_customer_id FROM user_payment_provider_history
                WHERE user_payment_provider_id = %s AND is_current = TRUE
                """,
                (str(upp_id),),
            )
            hist = cur.fetchone()
            assert hist is not None
            assert hist[0] == f"cus_mock_{user_id.hex[:24]}"

    def test_duplicate_active_provider_per_user_rejected(self, db_transaction):
        """Partial unique index: one user cannot have two active stripe provider records."""
        import psycopg2

        admin_id = str(SEED_SUPERADMIN_USER_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, user_id, admin_id)
            cur.execute(
                """
                INSERT INTO user_payment_provider (
                    user_id, provider, provider_customer_id, modified_by
                ) VALUES (%s, 'stripe', %s, %s)
                """,
                (str(user_id), f"cus_mock_{user_id.hex[:24]}", admin_id),
            )
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cur.execute(
                    """
                    INSERT INTO user_payment_provider (
                        user_id, provider, provider_customer_id, modified_by
                    ) VALUES (%s, 'stripe', %s, %s)
                    """,
                    (str(user_id), f"cus_mock_{user_id.hex[:20]}diff", admin_id),
                )

    def test_two_users_cannot_share_same_provider_customer(self, db_transaction):
        """Partial unique index: two users cannot share the same provider+provider_customer_id."""
        import psycopg2

        admin_id = str(SEED_SUPERADMIN_USER_ID)
        u1, u2 = uuid4(), uuid4()
        shared_cus_id = f"cus_shared_{uuid4().hex[:16]}"
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, u1, admin_id, "_a")
            self._create_customer_user(cur, u2, admin_id, "_b")
            cur.execute(
                """
                INSERT INTO user_payment_provider (
                    user_id, provider, provider_customer_id, modified_by
                ) VALUES (%s, 'stripe', %s, %s)
                """,
                (str(u1), shared_cus_id, admin_id),
            )
            with pytest.raises(psycopg2.errors.UniqueViolation):
                cur.execute(
                    """
                    INSERT INTO user_payment_provider (
                        user_id, provider, provider_customer_id, modified_by
                    ) VALUES (%s, 'stripe', %s, %s)
                    """,
                    (str(u2), shared_cus_id, admin_id),
                )

    def test_archive_provider_allows_new_active_record(self, db_transaction):
        """Archiving a provider record allows a new active record for the same user+provider."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        user_id = uuid4()
        with db_transaction.cursor() as cur:
            self._create_customer_user(cur, user_id, admin_id)
            upp_id = uuid4()
            cur.execute(
                """
                INSERT INTO user_payment_provider (
                    user_payment_provider_id, user_id, provider, provider_customer_id, modified_by
                ) VALUES (%s, %s, 'stripe', %s, %s)
                """,
                (str(upp_id), str(user_id), f"cus_old_{user_id.hex[:20]}", admin_id),
            )
            # Archive the first record
            cur.execute(
                """
                UPDATE user_payment_provider SET is_archived = TRUE, modified_by = %s
                WHERE user_payment_provider_id = %s
                """,
                (admin_id, str(upp_id)),
            )
            # Should be able to insert a new active record
            cur.execute(
                """
                INSERT INTO user_payment_provider (
                    user_id, provider, provider_customer_id, modified_by
                ) VALUES (%s, 'stripe', %s, %s)
                """,
                (str(user_id), f"cus_new_{user_id.hex[:20]}", admin_id),
            )
            cur.execute(
                """
                SELECT COUNT(*) FROM user_payment_provider
                WHERE user_id = %s AND provider = 'stripe' AND is_archived = FALSE
                """,
                (str(user_id),),
            )
            assert cur.fetchone()[0] == 1


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
            ) VALUES (%s, %s, 'customer'::role_type_enum, 'comensal'::role_name_enum,
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
                VALUES (%s, %s, 'stripe', false, 'active'::status_enum, true, %s)
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
                VALUES (%s, %s, 'stripe', false, 'active'::status_enum, true, %s)
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
                VALUES (%s, %s, 'stripe', false, 'active'::status_enum, true, %s),
                       (%s, %s, 'stripe', false, 'active'::status_enum, false, %s)
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
