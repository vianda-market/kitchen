from pydantic import BaseModel, validator
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional
from app.config import Status

class ClientPaymentAttemptCreateSchema(BaseModel):
    payment_method_id: UUID
    credit_currency_id: UUID
    amount: Decimal 
    transaction_result: str
    external_transaction_id: Optional[str] = None
    resolution_date: Optional[datetime] = None

    @validator("amount", pre=True)
    def parse_amount(cls, v):
        if isinstance(v, (float, int, str)):
            return Decimal(str(v))
        raise ValueError("amount must be a valid number")

class ClientPaymentAttemptUpdateSchema(BaseModel):
    """Schema for updating client payment attempt - only allows status and resolution_date updates"""
    status: Optional[Status] = None
    resolution_date: Optional[datetime] = None

class ClientPaymentAttemptResponseSchema(BaseModel):
    payment_id: UUID
    payment_method_id: UUID
    credit_currency_id: UUID
    currency_code: str
    amount: Decimal 
    transaction_result: str
    external_transaction_id: Optional[str] = None
    created_date: datetime
    resolution_date: Optional[datetime] = None
    is_archived: bool
    status: Status
