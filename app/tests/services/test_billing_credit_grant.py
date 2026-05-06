"""
Regression tests for billing.py credit-grant logic.

Covers the billing.py:43 bug where credits were derived from
    math.ceil(bill.amount / credit_value_supplier_local)
instead of using plan.credit directly.

The fix: process_client_bill_internal now grants plan.credit per period,
decoupled from credit_value_supplier_local.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.config import Status
from app.dto.models import PlanDTO, SubscriptionDTO


def _make_subscription(plan_id=None, balance=Decimal("0"), renewal_date=None):
    return SubscriptionDTO(
        subscription_id=uuid4(),
        user_id=uuid4(),
        plan_id=plan_id or uuid4(),
        market_id=uuid4(),
        balance=balance,
        renewal_date=renewal_date or datetime.now(UTC),
        is_archived=False,
        status=Status.ACTIVE,
        subscription_status="Active",
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


def _make_plan(credits: int = 10, price: Decimal = Decimal("9.99")):
    return PlanDTO(
        plan_id=uuid4(),
        market_id=uuid4(),
        name="Test Plan",
        credit=credits,
        price=price,
        credit_cost_local_currency=price / credits,
        credit_cost_usd=Decimal("0.01"),
        rollover=True,
        rollover_cap=None,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


def _make_bill(subscription_id=None, currency_metadata_id=None, amount=Decimal("9.99"), plan_id=None, user_id=None):
    from app.dto.models import ClientBillDTO

    return ClientBillDTO(
        client_bill_id=uuid4(),
        subscription_payment_id=uuid4(),
        subscription_id=subscription_id or uuid4(),
        user_id=user_id or uuid4(),
        plan_id=plan_id or uuid4(),
        currency_metadata_id=currency_metadata_id or uuid4(),
        amount=amount,
        currency_code="ARS",
        status=Status.COMPLETED,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


class TestProcessClientBillInternalCreditGrant:
    """
    process_client_bill_internal must grant plan.credit regardless of the
    supplier credit value — NOT derive credits from bill.amount / supplier_value.
    """

    def test_grants_plan_credits_not_derived_from_supplier_value(self):
        """
        Regression test: credits granted == plan.credit, independent of
        credit_value_supplier_local.

        Scenario: plan has 10 credits. bill amount is 9.99.
        Old (buggy) logic: ceil(9.99 / supplier_value) — varies with supplier value.
        New (correct) logic: 10 credits always.
        """
        bill_id = uuid4()
        subscription_id = uuid4()
        plan_id = uuid4()
        modified_by = uuid4()

        plan = _make_plan(credits=10)
        plan = PlanDTO(
            plan_id=plan_id,
            market_id=uuid4(),
            name="Test Plan",
            credit=10,
            price=Decimal("9.99"),
            credit_cost_local_currency=Decimal("0.999"),
            credit_cost_usd=Decimal("0.01"),
            rollover=True,
            rollover_cap=None,
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        sub = _make_subscription(plan_id=plan_id)
        sub = SubscriptionDTO(
            subscription_id=subscription_id,
            user_id=uuid4(),
            plan_id=plan_id,
            market_id=uuid4(),
            balance=Decimal("0"),
            renewal_date=datetime.now(UTC),
            is_archived=False,
            status=Status.ACTIVE,
            subscription_status="Active",
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        bill = _make_bill(
            subscription_id=subscription_id,
            amount=Decimal("9.99"),
        )
        # Bill is COMPLETED (not yet PROCESSED) so it gets processed.
        from app.dto.models import ClientBillDTO

        bill = ClientBillDTO(
            client_bill_id=bill_id,
            subscription_payment_id=uuid4(),
            subscription_id=subscription_id,
            user_id=uuid4(),
            plan_id=plan_id,
            currency_metadata_id=uuid4(),
            amount=Decimal("9.99"),
            currency_code="ARS",
            status=Status.COMPLETED,
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        mock_db = MagicMock()

        with (
            patch("app.services.billing.client_bill.client_bill_service") as mock_bill_svc,
            patch("app.services.billing.client_bill.subscription_service") as mock_sub_svc,
            patch("app.services.billing.client_bill.plan_service") as mock_plan_svc,
            patch("app.services.billing.client_bill.update_balance") as mock_update_balance,
            patch("app.services.billing.client_bill.credit_currency_service") as mock_cc_svc,
        ):
            mock_bill_svc.get_by_id.return_value = bill
            mock_sub_svc.get_by_id.return_value = sub
            mock_plan_svc.get_by_id.return_value = plan
            mock_cc_svc.get_by_id.return_value = MagicMock()
            mock_sub_svc.update.return_value = None
            mock_bill_svc.update.return_value = None
            mock_update_balance.return_value = True

            from app.services.billing.client_bill import process_client_bill_internal

            result = process_client_bill_internal(bill_id, mock_db, modified_by)

        assert result is True
        # Critical: update_balance called with plan.credit (10), not derived from supplier value
        mock_update_balance.assert_called_once()
        call_args = mock_update_balance.call_args
        credits_passed = call_args[0][1]  # second positional arg
        assert credits_passed == float(10), (
            f"Expected credits_passed=10 (plan.credit), got {credits_passed}. "
            "The billing.py:43 bug: credits must come from plan.credit, not bill.amount/supplier_value."
        )

    def test_credits_independent_of_supplier_value(self):
        """
        Even if credit_value_supplier_local changes, the credits granted stay at plan.credit.

        This is the core invariant: customer-side credits are plan-defined,
        supplier-side payout is market-currency-defined. They must never cross.
        """
        bill_id = uuid4()
        subscription_id = uuid4()
        plan_id = uuid4()
        modified_by = uuid4()

        # Plan with 50 credits
        plan = PlanDTO(
            plan_id=plan_id,
            market_id=uuid4(),
            name="Premium Plan",
            credit=50,
            price=Decimal("49.99"),
            credit_cost_local_currency=Decimal("0.9998"),
            credit_cost_usd=Decimal("0.01"),
            rollover=True,
            rollover_cap=None,
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        sub = SubscriptionDTO(
            subscription_id=subscription_id,
            user_id=uuid4(),
            plan_id=plan_id,
            market_id=uuid4(),
            balance=Decimal("0"),
            renewal_date=datetime.now(UTC),
            is_archived=False,
            status=Status.ACTIVE,
            subscription_status="Active",
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        from app.dto.models import ClientBillDTO

        bill = ClientBillDTO(
            client_bill_id=bill_id,
            subscription_payment_id=uuid4(),
            subscription_id=subscription_id,
            user_id=uuid4(),
            plan_id=plan_id,
            currency_metadata_id=uuid4(),
            amount=Decimal("49.99"),
            currency_code="ARS",
            status=Status.COMPLETED,
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        mock_db = MagicMock()

        with (
            patch("app.services.billing.client_bill.client_bill_service") as mock_bill_svc,
            patch("app.services.billing.client_bill.subscription_service") as mock_sub_svc,
            patch("app.services.billing.client_bill.plan_service") as mock_plan_svc,
            patch("app.services.billing.client_bill.update_balance") as mock_update_balance,
            patch("app.services.billing.client_bill.credit_currency_service") as mock_cc_svc,
        ):
            mock_bill_svc.get_by_id.return_value = bill
            mock_sub_svc.get_by_id.return_value = sub
            mock_plan_svc.get_by_id.return_value = plan
            mock_cc_svc.get_by_id.return_value = MagicMock()
            mock_sub_svc.update.return_value = None
            mock_bill_svc.update.return_value = None
            mock_update_balance.return_value = True

            from app.services.billing.client_bill import process_client_bill_internal

            result = process_client_bill_internal(bill_id, mock_db, modified_by)

        assert result is True
        call_args = mock_update_balance.call_args
        credits_passed = call_args[0][1]
        # Should be exactly 50 (plan.credit), not something derived from 49.99 / supplier_value
        assert credits_passed == float(50), f"Expected 50 credits (plan.credit), got {credits_passed}."

    def test_already_processed_bill_is_skipped(self):
        """Idempotency: a PROCESSED bill returns True without re-granting credits."""
        bill_id = uuid4()
        modified_by = uuid4()
        mock_db = MagicMock()

        from app.dto.models import ClientBillDTO

        bill = ClientBillDTO(
            client_bill_id=bill_id,
            subscription_payment_id=uuid4(),
            subscription_id=uuid4(),
            user_id=uuid4(),
            plan_id=uuid4(),
            currency_metadata_id=uuid4(),
            amount=Decimal("9.99"),
            currency_code="ARS",
            status=Status.PROCESSED,
            created_date=datetime.now(UTC),
            modified_by=uuid4(),
            modified_date=datetime.now(UTC),
        )

        with (
            patch("app.services.billing.client_bill.client_bill_service") as mock_bill_svc,
            patch("app.services.billing.client_bill.update_balance") as mock_update_balance,
        ):
            mock_bill_svc.get_by_id.return_value = bill

            from app.services.billing.client_bill import process_client_bill_internal

            result = process_client_bill_internal(bill_id, mock_db, modified_by)

        assert result is True
        mock_update_balance.assert_not_called()

    def test_missing_bill_returns_false(self):
        """If the bill row does not exist, return False (not an exception)."""
        bill_id = uuid4()
        mock_db = MagicMock()

        with patch("app.services.billing.client_bill.client_bill_service") as mock_bill_svc:
            mock_bill_svc.get_by_id.return_value = None

            from app.services.billing.client_bill import process_client_bill_internal

            result = process_client_bill_internal(bill_id, mock_db, uuid4())

        assert result is False
