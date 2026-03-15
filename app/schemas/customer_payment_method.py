"""Schemas for customer-scoped payment method management (B2C)."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CustomerPaymentMethodItemSchema(BaseModel):
    """Single payment method in list response (masked, no sensitive data)."""
    payment_method_id: UUID
    last4: Optional[str] = None
    brand: Optional[str] = None
    is_default: bool
    external_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerPaymentMethodListResponseSchema(BaseModel):
    """Response for GET /customer/payment-methods/"""
    payment_methods: List[CustomerPaymentMethodItemSchema]


class SetupSessionRequestSchema(BaseModel):
    """Optional request body for POST /customer/payment-methods/setup-session"""
    return_url: Optional[str] = Field(
        None,
        description="URL to redirect after Stripe Checkout (mode=setup) completes",
    )


class SetupSessionResponseSchema(BaseModel):
    """Response for POST /customer/payment-methods/setup-session"""
    setup_url: str = Field(..., description="URL to redirect user to add/update payment method")
    expires_at: Optional[datetime] = Field(
        None,
        description="When the setup session expires (ISO 8601)",
    )
