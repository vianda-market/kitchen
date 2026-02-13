from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID
from app.config import Status

# Use UUID (not UUID4) so IDs from seed/DB work (seed uses non-RFC-4122-v4 UUIDs e.g. aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa)


class ClientBillCreateSchema(BaseModel):
    payment_id: UUID
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    credit_currency_id: UUID
    amount: float
    # Status field removed - will be automatically set by database default


class ClientBillUpdateSchema(BaseModel):
    amount: Optional[float]
    currency_code: Optional[str]
    # is_archived field removed - can only be modified via DELETE API
    status: Optional[Status] = None


class ClientBillResponseSchema(BaseModel):
    client_bill_id: UUID
    payment_id: UUID
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    credit_currency_id: UUID
    amount: float
    currency_code: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime