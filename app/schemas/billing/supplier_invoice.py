# app/schemas/billing/supplier_invoice.py
import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.config.enums import SupplierInvoiceStatus, SupplierInvoiceType
from app.i18n.envelope import I18nValueError
from app.schemas.types import MoneyDecimal, NullableMoneyDecimal

# =============================================================================
# Country-specific detail schemas (validated per-country)
# =============================================================================


class ARInvoiceDetailsSchema(BaseModel):
    """Argentina AFIP Factura Electronica fields."""

    cae_code: str
    cae_expiry_date: date
    afip_point_of_sale: str
    supplier_cuit: str
    recipient_cuit: str | None = None
    afip_document_type: str | None = None

    @field_validator("cae_code")
    @classmethod
    def validate_cae_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{14}", v):
            raise I18nValueError("validation.supplier_invoice.cae_format")
        return v

    @field_validator("supplier_cuit", "recipient_cuit")
    @classmethod
    def validate_cuit(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\d{2}-\d{8}-\d{1}", v):
            raise I18nValueError("validation.supplier_invoice.cuit_format")
        return v

    @field_validator("afip_document_type")
    @classmethod
    def validate_afip_document_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("A", "B", "C"):
            raise I18nValueError("validation.supplier_invoice.afip_doc_type")
        return v


class PEInvoiceDetailsSchema(BaseModel):
    """Peru SUNAT CPE fields."""

    sunat_serie: str
    sunat_correlativo: str
    supplier_ruc: str
    recipient_ruc: str | None = None
    cdr_status: str | None = None

    @field_validator("sunat_serie")
    @classmethod
    def validate_sunat_serie(cls, v: str) -> str:
        if not re.fullmatch(r"F\d{3}", v):
            raise I18nValueError("validation.supplier_invoice.sunat_serie_format")
        return v

    @field_validator("sunat_correlativo")
    @classmethod
    def validate_sunat_correlativo(cls, v: str) -> str:
        if not re.fullmatch(r"\d{1,8}", v):
            raise I18nValueError("validation.supplier_invoice.sunat_correlativo_format")
        return v

    @field_validator("supplier_ruc", "recipient_ruc")
    @classmethod
    def validate_ruc(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\d{11}", v):
            raise I18nValueError("validation.supplier_invoice.ruc_format")
        return v

    @field_validator("cdr_status")
    @classmethod
    def validate_cdr_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("accepted", "rejected", "pending"):
            raise I18nValueError("validation.supplier_invoice.cdr_status")
        return v


class USInvoiceDetailsSchema(BaseModel):
    """US IRS 1099-NEC fields."""

    tax_year: int


# =============================================================================
# Core invoice schemas
# =============================================================================


class SupplierInvoiceCreateSchema(BaseModel):
    """Create schema with nested country details."""

    institution_entity_id: UUID
    country_code: str
    invoice_type: SupplierInvoiceType
    external_invoice_number: str | None = None
    issued_date: date
    amount: Decimal
    currency_code: str
    tax_amount: Decimal | None = None
    tax_rate: Decimal | None = None
    document_format: str | None = None
    # Country-specific details (one required, based on country_code)
    ar_details: ARInvoiceDetailsSchema | None = None
    pe_details: PEInvoiceDetailsSchema | None = None
    us_details: USInvoiceDetailsSchema | None = None
    # Bill matches (submitted alongside invoice)
    bill_matches: list["BillInvoiceMatchCreateSchema"] | None = None

    @model_validator(mode="after")
    def validate_country_details(self):
        if self.country_code == "AR" and not self.ar_details:
            raise I18nValueError("validation.supplier_invoice.ar_details_required")
        if self.country_code == "PE" and not self.pe_details:
            raise I18nValueError("validation.supplier_invoice.pe_details_required")
        if self.country_code == "US" and not self.us_details:
            raise I18nValueError("validation.supplier_invoice.us_details_required")
        return self


class SupplierInvoiceResponseSchema(BaseModel):
    """Response schema with nested country details."""

    supplier_invoice_id: UUID
    institution_entity_id: UUID
    country_code: str
    invoice_type: str
    external_invoice_number: str | None = None
    issued_date: date
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_code: str
    tax_amount: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    tax_rate: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    # Document (signed URL, not storage path)
    document_url: str | None = None
    document_format: str | None = None
    # Country-specific details (populated based on country_code)
    ar_details: ARInvoiceDetailsSchema | None = None
    pe_details: PEInvoiceDetailsSchema | None = None
    us_details: USInvoiceDetailsSchema | None = None
    # Review
    status: str
    rejection_reason: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    # Audit
    is_archived: bool
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Review schema (PATCH /review) ---
class SupplierInvoiceReviewSchema(BaseModel):
    status: SupplierInvoiceStatus
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def validate_rejection_reason(self):
        if self.status == SupplierInvoiceStatus.REJECTED and not self.rejection_reason:
            raise I18nValueError("validation.supplier_invoice.rejection_reason_required")
        if self.status == SupplierInvoiceStatus.PENDING_REVIEW:
            raise I18nValueError("validation.supplier_invoice.status_cannot_reset")
        return self


# --- Bill match create schema ---
class BillInvoiceMatchCreateSchema(BaseModel):
    institution_bill_id: UUID
    matched_amount: Decimal


# --- Bill match response schema ---
class BillInvoiceMatchResponseSchema(BaseModel):
    match_id: UUID
    institution_bill_id: UUID
    supplier_invoice_id: UUID
    matched_amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    matched_by: UUID
    matched_at: datetime

    model_config = ConfigDict(from_attributes=True)
