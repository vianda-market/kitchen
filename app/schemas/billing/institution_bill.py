# app/schemas/billing/institution_bill.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.config import Status
from app.config.enums import BillResolution

# --- For creating a new institution bill (one-off) ---
class InstitutionBillCreateSchema(BaseModel):
    restaurant_id: UUID
    period_start: datetime
    period_end: datetime
    status: Optional[Status] = Status.PENDING
    resolution: Optional[BillResolution] = BillResolution.PENDING

# --- For creating a new institution bill (full schema; used internally by pipeline) ---
class InstitutionBillCreateFullSchema(BaseModel):
    institution_id: UUID
    institution_entity_id: UUID
    credit_currency_id: UUID
    transaction_count: Optional[int] = 0
    amount: Optional[Decimal] = Decimal('0')
    currency_code: Optional[str] = "USD"
    period_start: datetime
    period_end: datetime
    resolution: Optional[BillResolution] = BillResolution.PENDING

class InstitutionBillUpdateSchema(BaseModel):
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    status: Optional[Status] = None
    resolution: Optional[BillResolution] = None
    # is_archived field removed - can only be modified via DELETE API

class InstitutionBillResponseSchema(BaseModel):
    institution_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    credit_currency_id: UUID
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    period_start: datetime
    period_end: datetime
    is_archived: bool
    status: Status
    resolution: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# RecordPaymentSchema removed - all institution payment goes through settlement → bill → payout pipeline (SUPPLIER_INSTITUTION_PAYMENT.md)