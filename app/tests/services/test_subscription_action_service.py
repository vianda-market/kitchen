"""
Unit tests for Subscription Action Service.

Tests cancel, put on hold, resume, and reconcile_hold_subscriptions.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import Status
from app.config.enums.subscription_status import SubscriptionStatus
from app.dto.models import SubscriptionDTO
from app.services.subscription_action_service import (
    cancel_subscription,
    put_subscription_on_hold,
    reconcile_hold_subscriptions,
    resume_subscription,
)


def _make_subscription(
    subscription_id=None,
    user_id=None,
    subscription_status=SubscriptionStatus.ACTIVE.value,
    hold_start_date=None,
    hold_end_date=None,
):
    return SubscriptionDTO(
        subscription_id=subscription_id or uuid4(),
        user_id=user_id or uuid4(),
        plan_id=uuid4(),
        market_id=uuid4(),
        balance=Decimal("0"),
        renewal_date=datetime.now(UTC) + timedelta(days=30),
        is_archived=False,
        status=Status.ACTIVE,
        subscription_status=subscription_status,
        hold_start_date=hold_start_date,
        hold_end_date=hold_end_date,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


class TestCancelSubscription:
    def test_cancel_success_archives_subscription(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(subscription_id=sub_id, user_id=user_id)
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            with patch("app.services.subscription_action_service.db_update") as db_up:
                svc.get_by_id.return_value = subscription
                db_up.return_value = 1
                result = cancel_subscription(sub_id, user_id, mock_db)
        assert result.subscription_status == SubscriptionStatus.CANCELLED.value
        assert result.is_archived is True
        db_up.assert_called_once()
        call_kw = db_up.call_args[0][1]
        assert call_kw["subscription_status"] == SubscriptionStatus.CANCELLED.value
        assert call_kw["is_archived"] is True
        assert call_kw["status"] == Status.CANCELLED.value

    def test_cancel_already_cancelled_returns_400(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(
            subscription_id=sub_id,
            user_id=user_id,
            subscription_status=SubscriptionStatus.CANCELLED.value,
        )
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            with patch("app.services.subscription_action_service.db_update") as db_up:
                svc.get_by_id.return_value = subscription
                with pytest.raises(HTTPException) as exc_info:
                    cancel_subscription(sub_id, user_id, mock_db)
        assert exc_info.value.status_code == 400
        assert cast(dict[str, Any], exc_info.value.detail)["code"] == "subscription.already_cancelled"
        db_up.assert_not_called()

    def test_cancel_not_owner_returns_403(self, mock_db):
        sub_id = uuid4()
        owner_id = uuid4()
        other_id = uuid4()
        subscription = _make_subscription(subscription_id=sub_id, user_id=owner_id)
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            with patch("app.services.subscription_action_service.db_update") as db_up:
                svc.get_by_id.return_value = subscription
                with pytest.raises(HTTPException) as exc_info:
                    cancel_subscription(sub_id, other_id, mock_db)
        assert exc_info.value.status_code == 403
        db_up.assert_not_called()

    def test_cancel_not_found_returns_404(self, mock_db):
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                cancel_subscription(uuid4(), uuid4(), mock_db)
        assert exc_info.value.status_code == 404


class TestPutSubscriptionOnHold:
    def test_hold_success(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(subscription_id=sub_id, user_id=user_id)
        start = datetime.now(UTC)
        end = start + timedelta(days=30)
        updated = _make_subscription(
            subscription_id=sub_id,
            user_id=user_id,
            subscription_status=SubscriptionStatus.ON_HOLD.value,
            hold_start_date=start,
            hold_end_date=end,
        )
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            svc.update.return_value = updated
            result = put_subscription_on_hold(sub_id, user_id, start, end, mock_db)
        assert result.subscription_status == SubscriptionStatus.ON_HOLD.value
        svc.update.assert_called_once()
        call_kw = svc.update.call_args[0][1]
        assert call_kw["subscription_status"] == SubscriptionStatus.ON_HOLD.value
        assert call_kw["hold_start_date"] == start
        assert call_kw["hold_end_date"] == end

    def test_hold_duration_over_3_months_returns_400(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(subscription_id=sub_id, user_id=user_id)
        start = datetime.now(UTC)
        end = start + timedelta(days=91)
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            with pytest.raises(HTTPException) as exc_info:
                put_subscription_on_hold(sub_id, user_id, start, end, mock_db)
        assert exc_info.value.status_code == 400
        assert cast(dict[str, Any], exc_info.value.detail)["code"] == "validation.subscription.window_too_long"
        svc.update.assert_not_called()

    def test_hold_end_before_start_returns_400(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(subscription_id=sub_id, user_id=user_id)
        start = datetime.now(UTC)
        end = start - timedelta(days=1)
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            with pytest.raises(HTTPException) as exc_info:
                put_subscription_on_hold(sub_id, user_id, start, end, mock_db)
        assert exc_info.value.status_code == 400
        svc.update.assert_not_called()

    def test_hold_already_on_hold_returns_400(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(
            subscription_id=sub_id,
            user_id=user_id,
            subscription_status=SubscriptionStatus.ON_HOLD.value,
        )
        start = datetime.now(UTC)
        end = start + timedelta(days=30)
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            with pytest.raises(HTTPException) as exc_info:
                put_subscription_on_hold(sub_id, user_id, start, end, mock_db)
        assert exc_info.value.status_code == 400
        assert cast(dict[str, Any], exc_info.value.detail)["code"] == "subscription.already_on_hold"

    def test_hold_not_owner_returns_403(self, mock_db):
        sub_id = uuid4()
        owner_id = uuid4()
        other_id = uuid4()
        subscription = _make_subscription(subscription_id=sub_id, user_id=owner_id)
        start = datetime.now(UTC)
        end = start + timedelta(days=30)
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            with pytest.raises(HTTPException) as exc_info:
                put_subscription_on_hold(sub_id, other_id, start, end, mock_db)
        assert exc_info.value.status_code == 403
        svc.update.assert_not_called()


class TestResumeSubscription:
    def test_resume_success(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        start = datetime.now(UTC)
        end = start + timedelta(days=30)
        subscription = _make_subscription(
            subscription_id=sub_id,
            user_id=user_id,
            subscription_status=SubscriptionStatus.ON_HOLD.value,
            hold_start_date=start,
            hold_end_date=end,
        )
        updated = _make_subscription(
            subscription_id=sub_id,
            user_id=user_id,
            subscription_status=SubscriptionStatus.ACTIVE.value,
            hold_start_date=None,
            hold_end_date=None,
        )
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            svc.update.return_value = updated
            result = resume_subscription(sub_id, user_id, mock_db)
        assert result.subscription_status == SubscriptionStatus.ACTIVE.value
        svc.update.assert_called_once()
        call_kw = svc.update.call_args[0][1]
        assert call_kw["subscription_status"] == SubscriptionStatus.ACTIVE.value
        assert call_kw["hold_start_date"] is None
        assert call_kw["hold_end_date"] is None

    def test_resume_not_on_hold_returns_400(self, mock_db):
        sub_id = uuid4()
        user_id = uuid4()
        subscription = _make_subscription(
            subscription_id=sub_id,
            user_id=user_id,
            subscription_status=SubscriptionStatus.ACTIVE.value,
        )
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            with pytest.raises(HTTPException) as exc_info:
                resume_subscription(sub_id, user_id, mock_db)
        assert exc_info.value.status_code == 400
        assert cast(dict[str, Any], exc_info.value.detail)["code"] == "subscription.not_on_hold"
        svc.update.assert_not_called()

    def test_resume_not_owner_returns_403(self, mock_db):
        sub_id = uuid4()
        owner_id = uuid4()
        other_id = uuid4()
        subscription = _make_subscription(
            subscription_id=sub_id,
            user_id=owner_id,
            subscription_status=SubscriptionStatus.ON_HOLD.value,
        )
        with patch("app.services.subscription_action_service.subscription_service") as svc:
            svc.get_by_id.return_value = subscription
            with pytest.raises(HTTPException) as exc_info:
                resume_subscription(sub_id, other_id, mock_db)
        assert exc_info.value.status_code == 403
        svc.update.assert_not_called()


class TestReconcileHoldSubscriptions:
    def test_reconcile_no_op_when_no_due_subscriptions(self, mock_db):
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        reconcile_hold_subscriptions(mock_db)
        mock_cursor.execute.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_reconcile_updates_when_hold_end_passed(self, mock_db):
        mock_cursor = Mock()
        mock_db.cursor.return_value = mock_cursor
        reconcile_hold_subscriptions(mock_db)
        call_args = mock_cursor.execute.call_args[0]
        assert "UPDATE subscription_info" in call_args[0]
        assert "active" in call_args[1]
        assert "on_hold" in call_args[1]
        mock_db.commit.assert_called_once()
