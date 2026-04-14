# app/schemas/institution_entity.py
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID
from typing import Optional
from app.config import Status

# --- For creating a new institution entity ---
class InstitutionEntityCreateSchema(BaseModel):
    institution_id: UUID
    address_id: UUID
    tax_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    email_domain: Optional[str] = Field(None, max_length=255, description="Email domain for enrollment gating (employer) or SSO (all types)")
    is_archived: Optional[bool] = False
    # Status field removed - will be automatically set to 'Pending' by base model

# --- For updating an existing institution entity (primary key is immutable) ---
class InstitutionEntityUpdateSchema(BaseModel):
    institution_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    tax_id: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    email_domain: Optional[str] = Field(None, max_length=255, description="Email domain for enrollment gating (employer) or SSO (all types)")
    is_archived: Optional[bool] = None
    status: Optional[Status] = None

# --- Base/Response Schema ---
class InstitutionEntityResponseSchema(BaseModel):
    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    currency_metadata_id: UUID
    tax_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    email_domain: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

