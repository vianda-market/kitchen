from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional
from app.config import Status

class ClientBillCreateSchema(BaseModel):
    payment_id: UUID4
    subscription_id: UUID4
    user_id: UUID4
    plan_id: UUID4
    credit_currency_id: UUID4
    amount: float
    # Status field removed - will be automatically set by database default

class ClientBillUpdateSchema(BaseModel):
    amount: Optional[float]
    currency_code: Optional[str]
    # is_archived field removed - can only be modified via DELETE API
    status: Optional[Status] = None

class ClientBillResponseSchema(BaseModel):
    client_bill_id: UUID4
    payment_id: UUID4
    subscription_id: UUID4
    user_id: UUID4
    plan_id: UUID4
    credit_currency_id: UUID4
    amount: float
    currency_code: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID4
    modified_date: datetime