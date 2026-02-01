from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from app.config import Status

class FintechLinkAssignmentCreateSchema(BaseModel):
    payment_method_id: UUID4
    fintech_link_id: UUID4

class FintechLinkAssignmentResponseSchema(BaseModel):
    fintech_link_assignment_id: UUID4
    payment_method_id: UUID4
    fintech_link_id: UUID4
    is_archived: bool
    status: Status
    created_date: datetime

    class Config:
        orm_mode = True


class FintechLinkAssignmentEnrichedResponseSchema(BaseModel):
    """Schema for enriched fintech link assignment response data with provider, plan information, and user information"""
    fintech_link_assignment_id: UUID4
    payment_method_id: UUID4
    fintech_link_id: UUID4
    provider: str
    plan_name: str
    credit: int
    price: float
    full_name: Optional[str]
    username: Optional[str]
    email: Optional[str]
    cellphone: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime

    class Config:
        orm_mode = True

