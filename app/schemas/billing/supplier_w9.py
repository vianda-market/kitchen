# app/schemas/billing/supplier_w9.py
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.config.enums import TaxClassification
from app.i18n.envelope import I18nValueError


class SupplierW9CreateSchema(BaseModel):
    institution_entity_id: UUID
    legal_name: str
    business_name: str | None = None
    tax_classification: TaxClassification
    ein_last_four: str
    address_line: str

    @field_validator("ein_last_four")
    @classmethod
    def validate_ein_last_four(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise I18nValueError("validation.supplier_invoice.w9_ein_format")
        return v


class SupplierW9UpdateSchema(BaseModel):
    legal_name: str | None = None
    business_name: str | None = None
    tax_classification: TaxClassification | None = None
    ein_last_four: str | None = None
    address_line: str | None = None

    @field_validator("ein_last_four")
    @classmethod
    def validate_ein_last_four(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\d{4}", v):
            raise I18nValueError("validation.supplier_invoice.w9_ein_format")
        return v


class SupplierW9ResponseSchema(BaseModel):
    w9_id: UUID
    institution_entity_id: UUID
    legal_name: str
    business_name: str | None = None
    tax_classification: str
    ein_last_four: str
    address_line: str
    document_url: str | None = None
    is_archived: bool
    collected_at: datetime
    created_by: UUID | None = None
    modified_date: datetime
    modified_by: UUID

    model_config = ConfigDict(from_attributes=True)
