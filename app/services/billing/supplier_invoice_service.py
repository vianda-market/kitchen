# app/services/billing/supplier_invoice_service.py
"""
Supplier invoice business logic — create, match to bills, review.

Core invoice data lives in billing.supplier_invoice. Country-specific fields
are in extension tables: supplier_invoice_ar, _pe, _us (1:1 by supplier_invoice_id).
"""

from datetime import datetime
from uuid import UUID

import psycopg2.extensions

from app.config.enums import SupplierInvoiceStatus
from app.dto.models import BillInvoiceMatchDTO, SupplierInvoiceDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.security.institution_scope import InstitutionScope
from app.services.crud_service import (
    bill_invoice_match_service,
    supplier_invoice_ar_service,
    supplier_invoice_pe_service,
    supplier_invoice_service,
    supplier_invoice_us_service,
)
from app.utils.db import db_read
from app.utils.gcs import (
    get_supplier_invoice_document_signed_url,
    upload_supplier_invoice_document,
)
from app.utils.log import log_error

# =============================================================================
# Country extension table helpers
# =============================================================================

_COUNTRY_SERVICES = {
    "AR": supplier_invoice_ar_service,
    "PE": supplier_invoice_pe_service,
    "US": supplier_invoice_us_service,
}

_COUNTRY_DETAIL_KEY = {
    "AR": "ar_details",
    "PE": "pe_details",
    "US": "us_details",
}


def _create_country_extension(
    country_code: str,
    supplier_invoice_id: str,
    details: dict,
    db: psycopg2.extensions.connection,
) -> None:
    """Insert into the appropriate country extension table."""
    service = _COUNTRY_SERVICES.get(country_code)
    if not service:
        return
    details["supplier_invoice_id"] = supplier_invoice_id
    service.create(details, db, commit=False)


def fetch_country_details(
    country_code: str,
    supplier_invoice_id: str,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """Fetch country extension record as a dict. Returns None if not found."""
    service = _COUNTRY_SERVICES.get(country_code)
    if not service:
        return None
    record = service.get_by_id(supplier_invoice_id, db)
    if not record:
        return None
    result = record.model_dump()
    result.pop("supplier_invoice_id", None)
    return result


def enrich_with_country_details(
    invoice_dict: dict,
    db: psycopg2.extensions.connection,
) -> dict:
    """Attach country-specific details to an invoice response dict."""
    country_code = invoice_dict.get("country_code", "")
    detail_key = _COUNTRY_DETAIL_KEY.get(country_code)
    if detail_key:
        details = fetch_country_details(country_code, str(invoice_dict["supplier_invoice_id"]), db)
        invoice_dict[detail_key] = details
    return invoice_dict


# =============================================================================
# Core business logic
# =============================================================================


def create_supplier_invoice(
    data: dict,
    country_details: dict | None,
    file_data: bytes | None,
    file_content_type: str | None,
    current_user: dict,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> SupplierInvoiceDTO:
    """
    Create a supplier invoice record with country extension and optional document upload.

    Internal users → status='Approved' (no review needed).
    Supplier users → status='Pending Review'.
    """
    user_id = str(current_user["user_id"])
    role_type = current_user.get("role_type", "")
    country_code = data.get("country_code", "")

    # Set status based on caller role
    if role_type == "internal":
        data["status"] = SupplierInvoiceStatus.APPROVED.value
        data["reviewed_by"] = user_id
        data["reviewed_at"] = datetime.utcnow().isoformat()
    else:
        data["status"] = SupplierInvoiceStatus.PENDING_REVIEW.value

    data["modified_by"] = user_id
    data["created_by"] = user_id

    # Create the core invoice record
    invoice = supplier_invoice_service.create(data, db, commit=False)
    if not invoice:
        log_error("Failed to create supplier invoice record")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)

    # Create country extension record
    if country_details:
        _create_country_extension(country_code, str(invoice.supplier_invoice_id), country_details, db)

    # Upload document to GCS if provided
    if file_data and file_content_type:
        try:
            blob_path = upload_supplier_invoice_document(
                str(invoice.supplier_invoice_id),
                str(invoice.institution_entity_id),
                invoice.country_code,
                file_data,
                file_content_type,
            )
            supplier_invoice_service.update(
                str(invoice.supplier_invoice_id),
                {"document_storage_path": blob_path, "modified_by": user_id},
                db,
                commit=False,
            )
        except Exception as e:
            log_error(f"Failed to upload invoice document: {e}")
            db.rollback()
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale) from None

    db.commit()
    return supplier_invoice_service.get_by_id(str(invoice.supplier_invoice_id), db)


def match_invoice_to_bills(
    supplier_invoice_id: UUID,
    bill_matches: list[dict],
    current_user: dict,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> list[BillInvoiceMatchDTO]:
    """
    Create bill_invoice_match records linking an invoice to one or more bills.
    Validates that each bill belongs to the same entity as the invoice.
    """
    user_id = str(current_user["user_id"])

    invoice = supplier_invoice_service.get_by_id(str(supplier_invoice_id), db)
    if not invoice:
        raise envelope_exception(ErrorCode.SUPPLIER_INVOICE_NOT_FOUND, status=404, locale=locale)

    entity_id = str(invoice.institution_entity_id)
    created_matches = []

    for match_data in bill_matches:
        bill_id = str(match_data["institution_bill_id"])

        bill_row = db_read(
            """SELECT institution_entity_id FROM billing.institution_bill_info
               WHERE institution_bill_id = %s AND is_archived = FALSE""",
            (bill_id,),
            connection=db,
            fetch_one=True,
        )
        if not bill_row:
            raise envelope_exception(ErrorCode.BILLING_BILL_NOT_FOUND, status=404, locale=locale)
        if str(bill_row["institution_entity_id"]) != entity_id:
            raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=400, locale=locale)

        match_record = bill_invoice_match_service.create(
            {
                "institution_bill_id": bill_id,
                "supplier_invoice_id": str(supplier_invoice_id),
                "matched_amount": str(match_data["matched_amount"]),
                "matched_by": user_id,
            },
            db,
        )
        if match_record:
            created_matches.append(match_record)

    return created_matches


def review_supplier_invoice(
    invoice_id: UUID,
    review_status: str,
    rejection_reason: str | None,
    reviewer_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> SupplierInvoiceDTO:
    """Approve or reject a supplier invoice. Only valid from 'pending_review' status."""
    invoice = supplier_invoice_service.get_by_id(str(invoice_id), db)
    if not invoice:
        raise envelope_exception(ErrorCode.SUPPLIER_INVOICE_NOT_FOUND, status=404, locale=locale)

    if invoice.status != SupplierInvoiceStatus.PENDING_REVIEW:
        raise envelope_exception(
            ErrorCode.SUPPLIER_INVOICE_INVALID_STATUS,
            status=400,
            locale=locale,
            invoice_status=invoice.status.value,
        )

    update_data = {
        "status": review_status,
        "reviewed_by": str(reviewer_id),
        "reviewed_at": datetime.utcnow().isoformat(),
        "modified_by": str(reviewer_id),
    }
    if rejection_reason:
        update_data["rejection_reason"] = rejection_reason

    updated = supplier_invoice_service.update(str(invoice_id), update_data, db)
    if not updated:
        log_error(f"Failed to update invoice status for {invoice_id}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
    return updated


def get_supplier_invoices(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    entity_id: UUID | None = None,
    status_filter: str | None = None,
) -> list[SupplierInvoiceDTO]:
    """Get supplier invoices with optional filtering. Scoped to institution."""
    invoices = supplier_invoice_service.get_all(db, scope=scope)

    if entity_id:
        invoices = [i for i in invoices if str(i.institution_entity_id) == str(entity_id)]
    if status_filter:
        invoices = [i for i in invoices if i.status.value == status_filter]

    return invoices


def resolve_document_url(invoice_dict: dict) -> dict:
    """Replace document_storage_path with a signed document_url in the response dict."""
    storage_path = invoice_dict.pop("document_storage_path", None)
    if storage_path:
        try:
            url = get_supplier_invoice_document_signed_url(
                str(invoice_dict["supplier_invoice_id"]),
                str(invoice_dict["institution_entity_id"]),
                invoice_dict.get("country_code", ""),
            )
            invoice_dict["document_url"] = url
        except Exception:
            invoice_dict["document_url"] = None
    else:
        invoice_dict["document_url"] = None
    return invoice_dict
