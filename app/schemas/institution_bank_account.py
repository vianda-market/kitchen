# app/schemas/institution_bank_account.py
from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from app.dto.models import InstitutionBankAccountDTO
from app.services.crud_service import validate_routing_number, validate_account_number
from app.config import Status

# --- For creating a new institution bank account ---
class InstitutionBankAccountCreateSchema(BaseModel):
    institution_entity_id: UUID
    address_id: UUID
    account_holder_name: str = Field(..., max_length=100)
    bank_name: str = Field(..., max_length=100)
    account_type: str = Field(..., max_length=50)
    routing_number: str = Field(..., max_length=50)
    account_number: str = Field(..., max_length=50)
    is_archived: Optional[bool] = False
    # Status field removed - will be automatically set to 'Pending' by base model

    @validator('routing_number')
    def validate_routing_number(cls, v):
        if not validate_routing_number(v):
            raise ValueError('Invalid routing number format. Must be 9 digits.')
        return v

    @validator('account_number')
    def validate_account_number(cls, v):
        if not validate_account_number(v):
            raise ValueError('Invalid account number format. Must be 4-17 digits.')
        return v

    @validator('account_type')
    def validate_account_type(cls, v):
        valid_types = ['Checking', 'Savings', 'Business', 'Corporate', 'Investment']
        if v not in valid_types:
            raise ValueError(f'Invalid account type. Must be one of: {", ".join(valid_types)}')
        return v

# --- For updating an existing institution bank account (primary key is immutable) ---
class InstitutionBankAccountUpdateSchema(BaseModel):
    account_holder_name: Optional[str] = Field(None, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=100)
    account_type: Optional[str] = Field(None, max_length=50)
    routing_number: Optional[str] = Field(None, max_length=50)
    account_number: Optional[str] = Field(None, max_length=50)
    # is_archived field removed - can only be modified via DELETE API
    status: Optional[Status] = None

    @validator('routing_number')
    def validate_routing_number(cls, v):
        if v is not None and not validate_routing_number(v):
            raise ValueError('Invalid routing number format. Must be 9 digits.')
        return v

    @validator('account_number')
    def validate_account_number(cls, v):
        if v is not None and not validate_account_number(v):
            raise ValueError('Invalid account number format. Must be 4-17 digits.')
        return v

    @validator('account_type')
    def validate_account_type(cls, v):
        if v is not None:
            valid_types = ['Checking', 'Savings', 'Business', 'Corporate', 'Investment']
            if v not in valid_types:
                raise ValueError(f'Invalid account type. Must be one of: {", ".join(valid_types)}')
        return v

# --- For returning institution bank account details in API responses ---
class InstitutionBankAccountResponseSchema(BaseModel):
    bank_account_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    account_holder_name: str = Field(..., max_length=100)
    bank_name: str = Field(..., max_length=100)
    account_type: str = Field(..., max_length=50)
    routing_number: str = Field(..., max_length=50)
    account_number: str = Field(..., max_length=50)
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID

    class Config:
        orm_mode = True

# --- For simplified bank account creation (minimal required fields) ---
class InstitutionBankAccountMinimalCreateSchema(BaseModel):
    institution_entity_id: UUID
    account_holder_name: str = Field(..., max_length=100)
    bank_name: str = Field(..., max_length=100)
    account_type: str = Field(..., max_length=50)
    routing_number: str = Field(..., max_length=50)
    account_number: str = Field(..., max_length=50)
    
    # Optional fields that can be auto-populated
    address_id: Optional[UUID] = None  # Will use institution_entity's address if not provided
    # Status field removed - will be automatically set to 'Pending' by base model

    @validator('routing_number')
    def validate_routing_number(cls, v):
        if not validate_routing_number(v):
            raise ValueError('Invalid routing number format. Must be 9 digits.')
        return v

    @validator('account_number')
    def validate_account_number(cls, v):
        if not validate_account_number(v):
            raise ValueError('Invalid account number format. Must be 4-17 digits.')
        return v

    @validator('account_type')
    def validate_account_type(cls, v):
        valid_types = ['Checking', 'Savings', 'Business', 'Corporate', 'Investment']
        if v not in valid_types:
            raise ValueError(f'Invalid account type. Must be one of: {", ".join(valid_types)}')
        return v 