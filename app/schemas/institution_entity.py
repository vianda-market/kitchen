# app/schemas/institution_entity.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.config import Status


# --- For creating a new institution entity ---
class InstitutionEntityCreateSchema(BaseModel):
    institution_id: UUID
    address_id: UUID
    tax_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    email_domain: str | None = Field(
        None, max_length=255, description="Email domain for enrollment gating (employer) or SSO (all types)"
    )
    is_archived: bool | None = False
    # Status field removed - will be automatically set to 'Pending' by base model


# --- For updating an existing institution entity (primary key is immutable) ---
class InstitutionEntityUpdateSchema(BaseModel):
    institution_id: UUID | None = None
    address_id: UUID | None = None
    tax_id: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=100)
    email_domain: str | None = Field(
        None, max_length=255, description="Email domain for enrollment gating (employer) or SSO (all types)"
    )
    is_archived: bool | None = None
    status: Status | None = None


# --- Base/Response Schema ---
class InstitutionEntityResponseSchema(BaseModel):
    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    currency_metadata_id: UUID
    tax_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    email_domain: str | None = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)
