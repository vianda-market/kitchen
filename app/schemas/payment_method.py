from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from app.config import Status
from app.config.enums.payment_method_types import PaymentMethodProvider

# --- For creating a new payment method (aggregator-only) ---
class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=50, description="Provider: Stripe, Mercado Pago, PayU")
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_id: Optional[UUID] = Field(None, description="UUID of existing address to use")
    address_data: Optional[Dict[str, Any]] = Field(None, description="Address data for new address creation")
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
    method_type: Optional[str] = Field(None, max_length=50)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: Optional[bool] = None
    status: Optional[Status] = None
    is_default: Optional[bool] = None

# --- For returning payment method details in API responses ---
class PaymentMethodResponseSchema(BaseModel):
    payment_method_id: UUID
    user_id: UUID
    method_type: str = Field(..., max_length=50)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
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
    cellphone: Optional[str] = None
    method_type: str
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime
    provider: Optional[str] = None
    last4: Optional[str] = None
    brand: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
