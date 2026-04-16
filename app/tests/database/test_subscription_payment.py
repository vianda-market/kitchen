"""
Database tests for the new subscription payment flow (Stripe atomic flow).

- Verifies subscription_payment table exists and has required columns.
- Verifies payment provider mock returns expected shape.
- Integration: create subscription (Pending), record subscription_payment, activate subscription.
"""

from datetime import UTC
from uuid import UUID, uuid4

import pytest

from app.tests.database.conftest import (
    get_table_columns,
)
from app.tests.database.test_data.expected_seed_data import (
    SEED_INSTITUTION_CUSTOMERS_ID,
    SEED_SUPERADMIN_USER_ID,
)

# Argentina market for plan/subscription inserts (plans cannot use Global Marketplace)
ARGENTINA_MARKET_ID = UUID("00000000-0000-0000-0000-000000000002")


def _make_subscription_user(cur, admin_id: UUID) -> UUID:
    """Create a unique Customer user for subscription tests. Avoids idx_user_market_active collision when tests commit."""
    user_id = uuid4()
    h = user_id.hex[:8]
    cur.execute(
        """
        INSERT INTO user_info (
            user_id, institution_id, role_type, role_name, username, email,
            hashed_password, market_id, modified_by
        ) VALUES (%s, %s, 'customer'::role_type_enum, 'comensal'::role_name_enum,
            %s, %s, 'hash', %s::uuid, %s)
        """,
        (
            str(user_id),
            str(SEED_INSTITUTION_CUSTOMERS_ID),
            f"sub_test_{h}",
            f"sub_test_{h}@example.com",
            str(ARGENTINA_MARKET_ID),
            str(admin_id),
        ),
    )
    return user_id


class TestSubscriptionPaymentTable:
    """Subscription payment table structure and presence."""

    def test_subscription_payment_table_exists(self, db_transaction):
        """subscription_payment table exists and has required columns."""
        columns = get_table_columns(db_transaction, "subscription_payment")
        required = {
            "subscription_payment_id",
            "subscription_id",
            "payment_provider",
            "external_payment_id",
            "status",
            "amount_cents",
            "currency",
            "created_at",
        }
        missing = required - columns
        assert not missing, f"subscription_payment missing columns: {missing}"

    def test_subscription_payment_can_insert_and_select(self, db_transaction):
        """Can insert a row into subscription_payment (requires subscription_info)."""
        admin_id = str(SEED_SUPERADMIN_USER_ID)
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, SEED_SUPERADMIN_USER_ID)
            # Need a plan and subscription first (minimal)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Test Plan', 10, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), admin_id),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'pending', 'pending'::status_enum, 0, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), admin_id),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_mock_test123', 'pending', 10000, 'usd')
                RETURNING subscription_payment_id
                """,
                (str(sub_id),),
            )
            row = cur.fetchone()
            assert row is not None
            payment_id = row[0]
            cur.execute(
                "SELECT subscription_id, external_payment_id, status FROM subscription_payment WHERE subscription_payment_id = %s",
                (str(payment_id),),
            )
            r = cur.fetchone()
            assert r is not None
            assert str(r[0]) == str(sub_id)
            assert r[1] == "pi_mock_test123"
            assert r[2] == "pending"


class TestPaymentProviderMock:
    """Payment provider mock (no DB required)."""

    def test_mock_returns_id_client_secret_status(self):
        """create_payment_for_subscription (mock) returns id, client_secret, status."""
        from app.services.payment_provider.stripe.mock import create_payment_for_subscription as mock_create

        sub_id = uuid4()
        result = mock_create(sub_id, 1000, "usd", {})
        assert "id" in result
        assert "client_secret" in result
        assert "status" in result
        assert result["id"].startswith("pi_mock_") or "pi_mock" in result["id"]
        assert len(result["client_secret"]) > 0


class TestSubscriptionPaymentFlow:
    """Integration: activate subscription after payment (same logic as confirm-payment)."""

    def test_activate_subscription_after_payment_sets_active(self, db_transaction):
        """Create Pending subscription + subscription_payment, then activate; subscription becomes Active."""
        from app.services.crud_service import subscription_service
        from app.services.subscription_action_service import activate_subscription_after_payment

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Test Plan', 10, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'pending', 'pending'::status_enum, 0, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), str(admin_id)),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_mock_flow', 'pending', 10000, 'usd')
                """,
                (str(sub_id),),
            )
        subscription = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert subscription is not None
        assert subscription.subscription_status == "pending"
        activate_subscription_after_payment(sub_id, modified_by=admin_id, db=db_transaction)
        updated = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert updated is not None
        assert updated.subscription_status == "active"

    def test_create_and_process_bill_for_subscription_payment(self, db_transaction):
        """Confirm-payment path: create client_bill for subscription_payment and process (credits + Processed)."""
        from app.services.crud_service import (
            get_client_bill_by_subscription_payment,
            subscription_service,
        )
        from app.services.subscription_action_service import create_and_process_bill_for_subscription_payment

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Test Plan', 10, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'active', 'active'::status_enum, 0, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), str(user_id)),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_mock_bill', 'succeeded', 10000, 'usd')
                RETURNING subscription_payment_id
                """,
                (str(sub_id),),
            )
            sp_id = cur.fetchone()[0]
        create_and_process_bill_for_subscription_payment(sub_id, UUID(str(sp_id)), user_id, db_transaction)
        bill = get_client_bill_by_subscription_payment(UUID(str(sp_id)), db_transaction)
        assert bill is not None
        assert bill.status.value == "processed"
        sub = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert sub is not None
        assert float(sub.balance) >= 1

    def test_first_period_bill_grants_plan_credit_and_renewal_30_days(self, db_transaction):
        """First bill (balance 0): balance = plan.credit, renewal_date = activation + 30 days."""
        from datetime import datetime, timedelta

        from app.services.crud_service import (
            get_client_bill_by_subscription_payment,
            subscription_service,
        )
        from app.services.subscription_action_service import create_and_process_bill_for_subscription_payment

        admin_id = SEED_SUPERADMIN_USER_ID
        plan_credits = 70
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Entry Level', %s, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), plan_credits, str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'pending', 'pending'::status_enum, 0, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), str(user_id)),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_mock_first', 'succeeded', 10000, 'usd')
                RETURNING subscription_payment_id
                """,
                (str(sub_id),),
            )
            sp_id = cur.fetchone()[0]
        before = datetime.now(UTC)
        create_and_process_bill_for_subscription_payment(sub_id, UUID(str(sp_id)), user_id, db_transaction)
        after = datetime.now(UTC)
        bill = get_client_bill_by_subscription_payment(UUID(str(sp_id)), db_transaction)
        assert bill is not None
        assert bill.status.value == "processed"
        sub = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert sub is not None
        assert float(sub.balance) == plan_credits, "First period should grant plan.credit"
        expected_renewal_min = before + timedelta(days=29)
        expected_renewal_max = after + timedelta(days=31)
        renewal = sub.renewal_date
        if renewal.tzinfo is None:
            renewal = renewal.replace(tzinfo=UTC)
        else:
            renewal = renewal.astimezone(UTC)
        assert expected_renewal_min <= renewal <= expected_renewal_max, (
            "First period renewal_date should be activation + 30 days"
        )

    def test_renewal_period_bill_uses_plan_credit_and_extends_renewal(self, db_transaction):
        """Later bill (balance > 0): credits = plan.credit (same as first period), renewal_date = previous + 30 days."""
        from datetime import datetime, timedelta

        from app.services.billing.client_bill import process_client_bill_internal
        from app.services.crud_service import subscription_service

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            cur.execute(
                "SELECT currency_metadata_id FROM market_info WHERE market_id = %s", (str(ARGENTINA_MARKET_ID),)
            )
            row = cur.fetchone()
            assert row is not None
            currency_metadata_id = row[0]
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Plan', 70, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            old_renewal = datetime.now(UTC) + timedelta(days=5)
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, renewal_date, modified_by)
                VALUES (%s, %s, %s, %s, 'active', 'active'::status_enum, 50, %s, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), old_renewal, str(user_id)),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_renewal', 'succeeded', 20000, 'usd')
                RETURNING subscription_payment_id
                """,
                (str(sub_id),),
            )
            sp_id = cur.fetchone()[0]
            bill_id = uuid4()
            cur.execute(
                """
                INSERT INTO client_bill_info (client_bill_id, subscription_payment_id, subscription_id, user_id, plan_id, currency_metadata_id, amount, currency_code, status, modified_by)
                VALUES (%s, %s, %s, %s, %s, %s, 200.0, 'USD', 'active'::status_enum, %s)
                """,
                (
                    str(bill_id),
                    str(sp_id),
                    str(sub_id),
                    str(user_id),
                    str(plan_id),
                    str(currency_metadata_id),
                    str(user_id),
                ),
            )
        process_client_bill_internal(bill_id, db_transaction, user_id, commit=True)
        sub = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert sub is not None
        assert float(sub.balance) == 50 + 70, "Renewal: credits = plan.credit (70), balance 50+70=120"
        renewal = sub.renewal_date
        if renewal.tzinfo is None:
            renewal = renewal.replace(tzinfo=UTC)
        else:
            renewal = renewal.astimezone(UTC)
        expected_renewal = (
            old_renewal.replace(tzinfo=UTC) if old_renewal.tzinfo is None else old_renewal.astimezone(UTC)
        ) + timedelta(days=30)
        assert abs((renewal - expected_renewal).total_seconds()) < 2, (
            "Renewal date should be previous renewal_date + 30 days"
        )

    def test_zero_plan_credit_raises_400(self, db_transaction):
        """Processing a bill for a plan with credit=0 raises HTTPException 400 (no fallback)."""
        from fastapi import HTTPException

        from app.services.subscription_action_service import create_and_process_bill_for_subscription_payment

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Zero Credit Plan', 0, 0, 0.0, 0.0, false, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'pending', 'pending'::status_enum, 0, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), str(user_id)),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_zero_credit', 'succeeded', 0, 'usd')
                RETURNING subscription_payment_id
                """,
                (str(sub_id),),
            )
            sp_id = cur.fetchone()[0]
        with pytest.raises(HTTPException) as exc_info:
            create_and_process_bill_for_subscription_payment(sub_id, UUID(str(sp_id)), user_id, db_transaction)
        assert exc_info.value.status_code == 400
        assert "credit" in str(exc_info.value.detail).lower() or "credits" in str(exc_info.value.detail).lower()

    def test_renewal_with_rollover_cap_sets_balance_rolled_plus_plan_credit(self, db_transaction):
        """Renewal with rollover_cap: balance 50, cap 20, plan.credit 70 -> new balance = 20 + 70 = 90."""
        from datetime import datetime, timedelta

        from app.services.billing.client_bill import process_client_bill_internal
        from app.services.crud_service import subscription_service

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            cur.execute(
                "SELECT currency_metadata_id FROM market_info WHERE market_id = %s", (str(ARGENTINA_MARKET_ID),)
            )
            row = cur.fetchone()
            assert row is not None
            currency_metadata_id = row[0]
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, rollover_cap, is_archived, status, modified_by)
                VALUES (%s, %s, 'Plan With Cap', 70, 100.0, 0.0, 0.0, true, 20, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            old_renewal = datetime.now(UTC) + timedelta(days=5)
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, renewal_date, modified_by)
                VALUES (%s, %s, %s, %s, 'active', 'active'::status_enum, 50, %s, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), old_renewal, str(user_id)),
            )
            cur.execute(
                """
                INSERT INTO subscription_payment (subscription_id, payment_provider, external_payment_id, status, amount_cents, currency)
                VALUES (%s, 'stripe', 'pi_cap', 'succeeded', 20000, 'usd')
                RETURNING subscription_payment_id
                """,
                (str(sub_id),),
            )
            sp_id = cur.fetchone()[0]
            bill_id = uuid4()
            cur.execute(
                """
                INSERT INTO client_bill_info (client_bill_id, subscription_payment_id, subscription_id, user_id, plan_id, currency_metadata_id, amount, currency_code, status, modified_by)
                VALUES (%s, %s, %s, %s, %s, %s, 200.0, 'USD', 'active'::status_enum, %s)
                """,
                (
                    str(bill_id),
                    str(sp_id),
                    str(sub_id),
                    str(user_id),
                    str(plan_id),
                    str(currency_metadata_id),
                    str(user_id),
                ),
            )
        process_client_bill_internal(bill_id, db_transaction, user_id, commit=True)
        sub = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert sub is not None
        assert float(sub.balance) == 90, "Renewal with rollover_cap=20: rolled=20, plan.credit=70 -> 90"

    def test_apply_subscription_renewal_sets_rolled_plus_plan_credit(self, db_transaction):
        """apply_subscription_renewal (used by cron and renewal bill): balance = rolled + plan.credit, renewal_date += 30."""
        from datetime import datetime, timedelta

        from app.services.billing.client_bill import apply_subscription_renewal
        from app.services.crud_service import subscription_service

        admin_id = SEED_SUPERADMIN_USER_ID
        past_renewal = datetime.now(UTC) - timedelta(days=1)
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Cron Plan', 30, 50.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, renewal_date, modified_by)
                VALUES (%s, %s, %s, %s, 'active', 'active'::status_enum, 5, %s, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), past_renewal, str(user_id)),
            )
        apply_subscription_renewal(sub_id, db_transaction, modified_by=user_id, commit=True)
        sub = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert sub is not None
        assert float(sub.balance) == 35, "Rolled 5 + plan.credit 30 = 35"
        renewal = sub.renewal_date
        if renewal.tzinfo is None:
            renewal = renewal.replace(tzinfo=UTC)
        else:
            renewal = renewal.astimezone(UTC)
        expected_min = (past_renewal if past_renewal.tzinfo else past_renewal.replace(tzinfo=UTC)) + timedelta(days=29)
        assert renewal >= expected_min, "renewal_date should be previous + 30 days"

    def test_cancel_active_subscription_archives(self, db_transaction):
        """Cancel Active subscription archives it; get_by_id and get_by_user exclude it."""
        from app.services.crud_service import get_subscription_by_user_and_market, subscription_service
        from app.services.subscription_action_service import cancel_subscription

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Cancel Test Plan', 10, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'active', 'active'::status_enum, 50, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id), str(user_id)),
            )
        db_transaction.commit()

        sub = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert sub is not None
        assert sub.subscription_status == "active"
        assert sub.is_archived is False

        result = cancel_subscription(sub_id, user_id, db_transaction)
        assert result.subscription_status == "cancelled"
        assert result.is_archived is True

        # Archived subscriptions are excluded from get_by_id and get_by_user
        after_cancel = subscription_service.get_by_id(sub_id, db_transaction, scope=None)
        assert after_cancel is None
        get_by_user = subscription_service.get_by_user(user_id, db_transaction)
        assert get_by_user is None
        by_market = get_subscription_by_user_and_market(user_id, ARGENTINA_MARKET_ID, db_transaction)
        assert by_market is None

    def test_resubscribe_after_cancel(self, db_transaction):
        """After cancelling Active subscription, user can create new subscription in same market."""
        from app.services.crud_service import (
            get_subscription_by_user_and_market,
            subscription_service,
        )
        from app.services.subscription_action_service import cancel_subscription

        admin_id = SEED_SUPERADMIN_USER_ID
        with db_transaction.cursor() as cur:
            user_id = _make_subscription_user(cur, admin_id)
            plan_id_1 = uuid4()
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Plan A', 10, 100.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id_1), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
            sub_id = uuid4()
            cur.execute(
                """
                INSERT INTO subscription_info (subscription_id, user_id, market_id, plan_id, subscription_status, status, balance, modified_by)
                VALUES (%s, %s, %s, %s, 'active', 'active'::status_enum, 10, %s)
                """,
                (str(sub_id), str(user_id), str(ARGENTINA_MARKET_ID), str(plan_id_1), str(user_id)),
            )
        db_transaction.commit()

        cancel_subscription(sub_id, user_id, db_transaction)

        # Slot is free: no non-archived subscription for user+market
        by_market = get_subscription_by_user_and_market(user_id, ARGENTINA_MARKET_ID, db_transaction)
        assert by_market is None

        # Create new subscription in same market (would succeed; unique index allows it)
        plan_id_2 = uuid4()
        with db_transaction.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plan_info (plan_id, market_id, name, credit, price, credit_cost_local_currency, credit_cost_usd, rollover, is_archived, status, modified_by)
                VALUES (%s, %s, 'Plan B', 20, 200.0, 0.0, 0.0, true, false, 'active'::status_enum, %s)
                """,
                (str(plan_id_2), str(ARGENTINA_MARKET_ID), str(admin_id)),
            )
        new_sub = subscription_service.create(
            {
                "plan_id": plan_id_2,
                "user_id": user_id,
                "status": "active",
                "subscription_status": "active",
                "modified_by": user_id,
            },
            db_transaction,
            scope=None,
        )
        assert new_sub is not None
        assert new_sub.plan_id == plan_id_2
        assert new_sub.subscription_status == "active"
