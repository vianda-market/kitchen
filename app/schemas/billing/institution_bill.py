# app/schemas/billing/institution_bill.py
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.config import Status
from app.config.enums import BillResolution
from app.schemas.types import NullableMoneyDecimal


# --- For creating a new institution bill (one-off) ---
class InstitutionBillCreateSchema(BaseModel):
    restaurant_id: UUID
    period_start: datetime
    period_end: datetime
    status: Status | None = Status.PENDING
    resolution: BillResolution | None = BillResolution.PENDING


# --- For creating a new institution bill (full schema; used internally by pipeline) ---
class InstitutionBillCreateFullSchema(BaseModel):
    institution_id: UUID
    institution_entity_id: UUID
    currency_metadata_id: UUID
    transaction_count: int | None = 0
    amount: Decimal | None = Decimal("0")
    currency_code: str | None = "USD"
    period_start: datetime
    period_end: datetime
    resolution: BillResolution | None = BillResolution.PENDING


class InstitutionBillUpdateSchema(BaseModel):
    transaction_count: int | None = None
    amount: Decimal | None = None
    currency_code: str | None = None
    status: Status | None = None
    resolution: BillResolution | None = None
    # is_archived field removed - can only be modified via DELETE API


class InstitutionBillResponseSchema(BaseModel):
    institution_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    currency_metadata_id: UUID
    transaction_count: int | None = None
    amount: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    currency_code: str | None = None
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
