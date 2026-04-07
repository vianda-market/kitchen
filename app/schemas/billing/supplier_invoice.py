# app/schemas/billing/supplier_invoice.py
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
import re

from app.config.enums import SupplierInvoiceStatus, SupplierInvoiceType


# =============================================================================
# Country-specific detail schemas (validated per-country)
# =============================================================================

class ARInvoiceDetailsSchema(BaseModel):
    """Argentina AFIP Factura Electronica fields."""
    cae_code: str
    cae_expiry_date: date
    afip_point_of_sale: str
    supplier_cuit: str
    recipient_cuit: Optional[str] = None
    afip_document_type: Optional[str] = None

    @field_validator("cae_code")
    @classmethod
    def validate_cae_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{14}", v):
            raise ValueError("CAE code must be exactly 14 digits")
        return v

    @field_validator("supplier_cuit", "recipient_cuit")
    @classmethod
    def validate_cuit(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"\d{2}-\d{8}-\d{1}", v):
            raise ValueError("CUIT must match format XX-XXXXXXXX-X")
        return v

    @field_validator("afip_document_type")
    @classmethod
    def validate_afip_document_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("A", "B", "C"):
            raise ValueError("AFIP document type must be one of: A, B, C")
        return v


class PEInvoiceDetailsSchema(BaseModel):
    """Peru SUNAT CPE fields."""
    sunat_serie: str
    sunat_correlativo: str
    supplier_ruc: str
    recipient_ruc: Optional[str] = None
    cdr_status: Optional[str] = None

    @field_validator("sunat_serie")
    @classmethod
    def validate_sunat_serie(cls, v: str) -> str:
        if not re.fullmatch(r"F\d{3}", v):
            raise ValueError("SUNAT serie must match format F + 3 digits (e.g. F001)")
        return v

    @field_validator("sunat_correlativo")
    @classmethod
    def validate_sunat_correlativo(cls, v: str) -> str:
        if not re.fullmatch(r"\d{1,8}", v):
            raise ValueError("SUNAT correlativo must be 1-8 digits")
        return v

    @field_validator("supplier_ruc", "recipient_ruc")
    @classmethod
    def validate_ruc(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"\d{11}", v):
            raise ValueError("RUC must be exactly 11 digits")
        return v

    @field_validator("cdr_status")
    @classmethod
    def validate_cdr_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("accepted", "rejected", "pending"):
            raise ValueError("CDR status must be one of: accepted, rejected, pending")
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
    external_invoice_number: Optional[str] = None
    issued_date: date
    amount: Decimal
    currency_code: str
    tax_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    document_format: Optional[str] = None
    # Country-specific details (one required, based on country_code)
    ar_details: Optional[ARInvoiceDetailsSchema] = None
    pe_details: Optional[PEInvoiceDetailsSchema] = None
    us_details: Optional[USInvoiceDetailsSchema] = None
    # Bill matches (submitted alongside invoice)
    bill_matches: Optional[List["BillInvoiceMatchCreateSchema"]] = None

    @model_validator(mode="after")
    def validate_country_details(self):
        if self.country_code == "AR" and not self.ar_details:
            raise ValueError("AR invoices require ar_details")
        if self.country_code == "PE" and not self.pe_details:
            raise ValueError("PE invoices require pe_details")
        if self.country_code == "US" and not self.us_details:
            raise ValueError("US invoices require us_details")
        return self


class SupplierInvoiceResponseSchema(BaseModel):
    """Response schema with nested country details."""
    supplier_invoice_id: UUID
    institution_entity_id: UUID
    country_code: str
    invoice_type: str
    external_invoice_number: Optional[str] = None
    issued_date: date
    amount: Decimal
    currency_code: str
    tax_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    # Document (signed URL, not storage path)
    document_url: Optional[str] = None
    document_format: Optional[str] = None
    # Country-specific details (populated based on country_code)
    ar_details: Optional[ARInvoiceDetailsSchema] = None
    pe_details: Optional[PEInvoiceDetailsSchema] = None
    us_details: Optional[USInvoiceDetailsSchema] = None
    # Review
    status: str
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    # Audit
    is_archived: bool
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Review schema (PATCH /review) ---
class SupplierInvoiceReviewSchema(BaseModel):
    status: SupplierInvoiceStatus
    rejection_reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_rejection_reason(self):
        if self.status == SupplierInvoiceStatus.REJECTED and not self.rejection_reason:
            raise ValueError("rejection_reason is required when rejecting an invoice")
        if self.status == SupplierInvoiceStatus.PENDING_REVIEW:
            raise ValueError("Cannot set status back to Pending Review")
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
    matched_amount: Decimal
    matched_by: UUID
    matched_at: datetime

    model_config = ConfigDict(from_attributes=True)
