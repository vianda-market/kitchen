from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import Status
from app.config.enums.payment_method_types import PaymentMethodProvider


# --- For creating a new payment method (aggregator-only) ---
class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=50, description="Provider: Stripe, Mercado Pago, PayU")
    method_type_id: UUID | None = None
    is_default: bool | None = False
    address_id: UUID | None = Field(None, description="UUID of existing address to use")
    address_data: dict[str, Any] | None = Field(None, description="Address data for new address creation")
    # user_id will be set automatically from current_user
    # modified_by will be set automatically from current_user
    # status will be automatically set to 'Pending' by base model
    # is_archived will be automatically set to False by base model
    # created_date and modified_date will be automatically set by base model

    @model_validator(mode="after")
    def validate_address_fields(self):
        """Ensure either address_id or address_data is provided, not both"""
        if self.address_id and self.address_data:
            raise ValueError("Cannot provide both address_id and address_data. Provide one or the other.")
        return self

    @model_validator(mode="after")
    def validate_method_type(self):
        if self.method_type and not PaymentMethodProvider.is_valid(self.method_type):
            raise ValueError(f"method_type must be one of: {PaymentMethodProvider.values()}")
        return self


# --- For updating an existing payment method ---
class PaymentMethodUpdateSchema(BaseModel):
    method_type: str | None = Field(None, max_length=50)
    method_type_id: UUID | None = None
    address_id: UUID | None = None
    is_archived: bool | None = None
    status: Status | None = None
    is_default: bool | None = None


# --- For returning payment method details in API responses ---
class PaymentMethodResponseSchema(BaseModel):
    payment_method_id: UUID
    user_id: UUID
    method_type: str = Field(..., max_length=50)
    method_type_id: UUID | None = None
    address_id: UUID | None = None
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# --- For returning enriched payment method details with user and provider info ---
class PaymentMethodEnrichedResponseSchema(BaseModel):
    """Enriched payment method with user info and optional provider display (last4, brand)."""

    payment_method_id: UUID
    user_id: UUID
    full_name: str
    username: str
    email: str
    mobile_number: str | None = None
    method_type: str
    method_type_id: UUID | None = None
    address_id: UUID | None = None
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime
    provider: str | None = None
    last4: str | None = None
    brand: str | None = None

    model_config = ConfigDict(from_attributes=True)


# --- User payment provider (e.g. Stripe account connection) ---
class UserPaymentProviderResponseSchema(BaseModel):
    """Connected payment provider for a user (e.g. Stripe account).
    Intentionally omits provider_customer_id — internal system field, not for clients."""

    user_payment_provider_id: UUID
    provider: str
    created_date: datetime
    payment_method_count: int

    model_config = ConfigDict(from_attributes=True)


# --- Employee-facing user payment summary (Internal role only) ---
class UserPaymentSummarySchema(BaseModel):
    """Read-only summary of a customer's payment method status.
    Used by Internal employees to review which customers have Stripe cards registered.
    Intentionally omits provider_customer_id (cus_xxx) — internal Stripe identifier."""

    user_id: UUID
    username: str
    email: str
    full_name: str
    status: str
    has_stripe_provider: bool
    provider_connected_date: datetime | None = None
    payment_method_count: int
    default_last4: str | None = None
    default_brand: str | None = None

    model_config = ConfigDict(from_attributes=True)
