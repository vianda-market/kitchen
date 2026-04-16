from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OnboardingStatusResponseSchema(BaseModel):
    institution_id: UUID | None = None
    institution_type: str
    onboarding_status: str
    completion_percentage: int
    next_step: str | None = None
    days_since_creation: int
    days_since_last_activity: int | None = None
    last_activity_date: datetime | None = None
    checklist: dict[str, bool]


class OnboardingSummaryItemSchema(BaseModel):
    institution_id: UUID
    institution_name: str
    market_name: str | None = None
    onboarding_status: str
    completion_percentage: int
    days_since_creation: int
    days_since_last_activity: int
    missing_steps: list[str]
    created_date: datetime


class OnboardingSummaryResponseSchema(BaseModel):
    total: int
    counts: dict[str, int]
    stalled_institutions: list[OnboardingSummaryItemSchema]
