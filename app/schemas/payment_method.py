from pydantic import BaseModel, Field, root_validator
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from app.config import Status

# --- For creating a new payment method ---
class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_id: Optional[UUID] = Field(None, description="UUID of existing address to use")
    address_data: Optional[Dict[str, Any]] = Field(None, description="Address data for new address creation")
    # user_id will be set automatically from current_user
    # modified_by will be set automatically from current_user
    # status will be automatically set to 'Pending' by base model
    # is_archived will be automatically set to False by base model
    # created_date and modified_date will be automatically set by base model
    
    @root_validator
    def validate_address_fields(cls, values):
        """Ensure either address_id or address_data is provided, not both"""
        address_id = values.get('address_id')
        address_data = values.get('address_data')
        
        if address_id and address_data:
            raise ValueError("Cannot provide both address_id and address_data. Provide one or the other.")
        # Note: Validation for required address (credit_card/bank_account) is done in business logic
        
        return values

# --- For updating an existing payment method (payment_method_id is immutable) ---
class PaymentMethodUpdateSchema(BaseModel):
    method_type: Optional[str] = Field(None, max_length=20)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: Optional[bool] = None
    status: Optional[Status] = None
    is_default: Optional[bool] = None

# --- For returning payment method details in API responses ---
class PaymentMethodResponseSchema(BaseModel):
    payment_method_id: UUID
    user_id: UUID
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True


# --- For returning enriched payment method details with user information ---
class PaymentMethodEnrichedResponseSchema(BaseModel):
    """Schema for enriched payment method response data with user information"""
    payment_method_id: UUID
    user_id: UUID
    full_name: str
    username: str
    email: str
    cellphone: str
    method_type: str
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True
