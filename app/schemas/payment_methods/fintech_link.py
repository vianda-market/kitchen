from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from app.config import Status

class FintechLinkCreateSchema(BaseModel):
    plan_id: UUID4
    provider: str
    fintech_link: str

class FintechLinkUpdateSchema(BaseModel):
    plan_id: Optional[UUID4] = None
    provider: Optional[str] = None
    fintech_link: Optional[str] = None

class FintechLinkResponseSchema(BaseModel):
    fintech_link_id: UUID4
    plan_id: UUID4
    provider: str
    fintech_link: str
    is_archived: bool
    status: Status
    created_date: datetime

class FintechLinkEnrichedResponseSchema(BaseModel):
    """Schema for enriched fintech link response data with plan name, price, currency code, credit, and plan status"""
    fintech_link_id: UUID4
    plan_id: UUID4
    plan_name: str
    price: float
    credit: int
    plan_status: Status
    currency_code: str
    provider: str
    fintech_link: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True
