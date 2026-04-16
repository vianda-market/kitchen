"""Schemas for customer-scoped payment method management (B2C)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerPaymentMethodItemSchema(BaseModel):
    """Single payment method in list response (masked, no sensitive data)."""

    payment_method_id: UUID
    last4: str | None = None
    brand: str | None = None
    is_default: bool
    external_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CustomerPaymentMethodListResponseSchema(BaseModel):
    """Response for GET /customer/payment-methods/"""

    payment_methods: list[CustomerPaymentMethodItemSchema]


class SetupSessionRequestSchema(BaseModel):
    """Optional request body for POST /customer/payment-methods/setup-session"""

    success_url: str | None = Field(
        None,
        description="Stripe Checkout success_url after setup completes",
    )
    cancel_url: str | None = Field(
        None,
        description="Stripe Checkout cancel_url; defaults to success_url when omitted",
    )
    return_url: str | None = Field(
        None,
        description="Deprecated alias for success_url",
    )


class SetupSessionResponseSchema(BaseModel):
    """Response for POST /customer/payment-methods/setup-session"""

    setup_url: str = Field(..., description="URL to redirect user to add/update payment method")
    expires_at: datetime | None = Field(
        None,
        description="When the setup session expires (ISO 8601)",
    )
