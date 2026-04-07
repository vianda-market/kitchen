from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class OnboardingStatusResponseSchema(BaseModel):
    institution_id: Optional[UUID] = None
    institution_type: str
    onboarding_status: str
    completion_percentage: int
    next_step: Optional[str] = None
    days_since_creation: int
    days_since_last_activity: Optional[int] = None
    last_activity_date: Optional[datetime] = None
    checklist: Dict[str, bool]


class OnboardingSummaryItemSchema(BaseModel):
    institution_id: UUID
    institution_name: str
    market_name: Optional[str] = None
    onboarding_status: str
    completion_percentage: int
    days_since_creation: int
    days_since_last_activity: int
    missing_steps: List[str]
    created_date: datetime


class OnboardingSummaryResponseSchema(BaseModel):
    total: int
    counts: Dict[str, int]
    stalled_institutions: List[OnboardingSummaryItemSchema]
