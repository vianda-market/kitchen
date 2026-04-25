from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import Status
from app.i18n.envelope import I18nValueError


class SubscriptionCreateSchema(BaseModel):
    plan_id: UUID
    # user_id will be set automatically from current_user
    # renewal_date will use database default (CURRENT_TIMESTAMP + 30 days)
    balance: Decimal | None = Field(default=0, description="Initial balance")
    is_archived: bool | None = False
    # Status field removed - will be automatically set to 'Pending' by base model


class SubscriptionWithPaymentRequestSchema(BaseModel):
    """Request body for POST /subscriptions/with-payment (atomic subscription + payment)."""

    plan_id: UUID
    return_url: str | None = Field(None, description="URL to redirect after payment (e.g. Stripe Checkout)")


class SubscriptionWithPaymentResponseSchema(BaseModel):
    """Response of POST /subscriptions/with-payment. Client uses client_secret for payment UI, then confirm-payment or poll GET subscription."""

    subscription_id: UUID
    payment_id: UUID
    external_payment_id: str
    client_secret: str
    amount_cents: int
    currency: str


class SubscriptionUpdateSchema(BaseModel):
    plan_id: UUID | None = Field(None, description="Foreign key to plan_info")
    renewal_date: datetime | None = Field(None, description="Next renewal timestamp")
    balance: Decimal | None = Field(None, description="Current balance")
    is_archived: bool | None = Field(None, description="Soft-delete flag")
    status: Optional["Status"] = Field(None, description="Record status")


class SubscriptionResponseSchema(BaseModel):
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    renewal_date: datetime
    balance: Decimal
    is_archived: bool
    status: Status
    subscription_status: str | None = None
    hold_start_date: datetime | None = None
    hold_end_date: datetime | None = None
    early_renewal_threshold: int | None = 10
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionHoldRequestSchema(BaseModel):
    """Request body for PUT subscription on hold. hold_start_date = today; hold_end_date = user-selected resume date (max 3 months)."""

    hold_start_date: datetime
    hold_end_date: datetime

    @model_validator(mode="after")
    def validate_hold_dates(self):
        start = self.hold_start_date
        end = self.hold_end_date
        if start and end:
            if end <= start:
                raise I18nValueError("validation.subscription.window_invalid")
            delta = end - start
            if delta.days > 90:
                raise I18nValueError("validation.subscription.window_too_long")
        return self


class RenewalPreferencesSchema(BaseModel):
    """Request body for PATCH /subscriptions/me/renewal-preferences.
    Send an integer (>= 1) to set the early renewal credit threshold.
    Send null to disable early renewal (period-end only)."""

    early_renewal_threshold: int | None = Field(
        None,
        ge=1,
        description="Min credits before early renewal triggers. Send null to disable early renewal (period-end only).",
    )
