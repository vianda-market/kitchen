# app/schemas/billing/supplier_w9.py
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
import re

from app.config.enums import TaxClassification


class SupplierW9CreateSchema(BaseModel):
    institution_entity_id: UUID
    legal_name: str
    business_name: Optional[str] = None
    tax_classification: TaxClassification
    ein_last_four: str
    address_line: str

    @field_validator("ein_last_four")
    @classmethod
    def validate_ein_last_four(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("ein_last_four must be exactly 4 digits")
        return v


class SupplierW9UpdateSchema(BaseModel):
    legal_name: Optional[str] = None
    business_name: Optional[str] = None
    tax_classification: Optional[TaxClassification] = None
    ein_last_four: Optional[str] = None
    address_line: Optional[str] = None

    @field_validator("ein_last_four")
    @classmethod
    def validate_ein_last_four(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"\d{4}", v):
            raise ValueError("ein_last_four must be exactly 4 digits")
        return v


class SupplierW9ResponseSchema(BaseModel):
    w9_id: UUID
    institution_entity_id: UUID
    legal_name: str
    business_name: Optional[str] = None
    tax_classification: str
    ein_last_four: str
    address_line: str
    document_url: Optional[str] = None
    is_archived: bool
    collected_at: datetime
    created_by: Optional[UUID] = None
    modified_date: datetime
    modified_by: UUID

    model_config = ConfigDict(from_attributes=True)
