from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID
from decimal import Decimal
from app.config import Status


class SubscriptionCreateSchema(BaseModel):
    plan_id: UUID
    # user_id will be set automatically from current_user
    # renewal_date will use database default (CURRENT_TIMESTAMP + 30 days)
    balance: Optional[Decimal] = Field(default=0, description="Initial balance")
    is_archived: Optional[bool] = False
    # Status field removed - will be automatically set to 'Pending' by base model


class SubscriptionUpdateSchema(BaseModel):
    plan_id: Optional[UUID] = Field(None, description="Foreign key to plan_info")
    renewal_date: Optional[datetime] = Field(None, description="Next renewal timestamp")
    balance: Optional[Decimal] = Field(None, description="Current balance")
    is_archived: Optional[bool] = Field(None, description="Soft-delete flag")
    status: Optional['Status'] = Field(None, description="Record status")


class SubscriptionResponseSchema(BaseModel):
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    renewal_date: datetime
    balance: Decimal
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True
