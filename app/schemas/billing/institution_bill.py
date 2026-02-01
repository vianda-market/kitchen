# app/schemas/billing/institution_bill.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from app.config import Status

# --- For creating a new institution bill (one-off) ---
class InstitutionBillCreateSchema(BaseModel):
    restaurant_id: UUID
    period_start: datetime
    period_end: datetime
    status: Optional[Status] = Status.PENDING
    resolution: Optional[str] = "Pending"

# --- For creating a new institution bill (full schema) ---
class InstitutionBillCreateFullSchema(BaseModel):
    institution_id: UUID
    institution_entity_id: UUID
    restaurant_id: UUID
    credit_currency_id: UUID
    payment_id: Optional[UUID] = None
    transaction_count: Optional[int] = 0
    amount: Optional[Decimal] = Decimal('0')
    currency_code: Optional[str] = "USD"
    balance_event_id: Optional[UUID] = None
    period_start: datetime
    period_end: datetime
    resolution: Optional[str] = "Pending"
    # Status field removed - will be automatically set to 'Pending' by base model

class InstitutionBillUpdateSchema(BaseModel):
    payment_id: Optional[UUID] = None
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    status: Optional[Status] = None
    resolution: Optional[str] = Field(None, max_length=20)
    # is_archived field removed - can only be modified via DELETE API

class InstitutionBillResponseSchema(BaseModel):
    institution_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    restaurant_id: UUID
    credit_currency_id: UUID
    payment_id: Optional[UUID] = None
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    balance_event_id: Optional[UUID] = None
    period_start: datetime
    period_end: datetime
    is_archived: bool
    status: Status
    resolution: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

# --- For recording manual payments (MVP) ---
class RecordPaymentSchema(BaseModel):
    """Schema for recording a manual payment for a bill"""
    bank_account_id: UUID = Field(..., description="Bank account used for payment")
    external_transaction_id: str = Field(..., max_length=100, description="Transaction ID from bank")
    transaction_result: Optional[str] = Field("Approved", max_length=50, description="Result of transaction")
    
    @validator('external_transaction_id')
    def validate_external_transaction_id(cls, v):
        if not v or not v.strip():
            raise ValueError('External transaction ID cannot be empty')
        return v.strip()