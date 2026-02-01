# app/schemas/payment_methods/institution_payment_attempt.py

from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from decimal import Decimal
from app.config import Status

# --- For creating a new institution payment attempt ---
class InstitutionPaymentAttemptCreateSchema(BaseModel):
    institution_entity_id: UUID
    bank_account_id: UUID
    institution_bill_id: UUID
    credit_currency_id: UUID
    amount: Decimal = Field(..., gt=0)
    # currency_code removed - will be auto-resolved from credit_currency_id by service
    transaction_result: Optional[str] = Field(None, max_length=50)
    external_transaction_id: Optional[str] = Field(None, max_length=100)
    # Status field removed - will be automatically set to 'Pending' by base model
    # Resolution date will be set when payment is processed

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v

# --- For updating an existing institution payment attempt ---
class InstitutionPaymentAttemptUpdateSchema(BaseModel):
    transaction_result: Optional[str] = Field(None, max_length=50)
    external_transaction_id: Optional[str] = Field(None, max_length=100)
    status: Optional[Status] = None
    resolution_date: Optional[datetime] = None
    # Amount and other core fields should not be modifiable after creation
    # is_archived field removed - can only be modified via DELETE API

# --- For returning institution payment attempt details in API responses ---
class InstitutionPaymentAttemptResponseSchema(BaseModel):
    payment_id: UUID
    institution_entity_id: UUID
    bank_account_id: UUID
    institution_bill_id: Optional[UUID]
    credit_currency_id: UUID
    amount: Decimal
    currency_code: str
    transaction_result: Optional[str]
    external_transaction_id: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    resolution_date: datetime

    class Config:
        orm_mode = True

# --- For simplified payment attempt creation (minimal required fields) ---
class InstitutionPaymentAttemptMinimalCreateSchema(BaseModel):
    institution_entity_id: UUID
    bank_account_id: UUID
    institution_bill_id: Optional[UUID] = None
    credit_currency_id: UUID
    amount: Decimal = Field(..., gt=0)
    currency_code: str = Field(..., max_length=10)
    # Status field removed - will be automatically set to 'Pending' by base model
    # Resolution date will be set when payment is processed
    
    @validator('institution_bill_id', pre=True)
    def validate_institution_bill_id(cls, v):
        if v == "NO_BILLS_FOUND" or v == "null" or v == "":
            return None
        return v

# --- For payment attempt status updates ---
class InstitutionPaymentAttemptStatusUpdateSchema(BaseModel):
    transaction_result: str = Field(..., max_length=50)
    external_transaction_id: Optional[str] = Field(None, max_length=100)
    # Status will be set by the specific method (complete/failed)

# --- For payment attempt summary/listing ---
class InstitutionPaymentAttemptSummarySchema(BaseModel):
    payment_id: UUID
    institution_entity_id: UUID
    institution_bill_id: UUID
    amount: Decimal
    currency_code: str
    status: Status
    created_date: datetime
    resolution_date: Optional[datetime]
    transaction_result: Optional[str]

    class Config:
        orm_mode = True 