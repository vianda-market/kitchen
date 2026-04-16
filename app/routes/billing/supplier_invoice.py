# app/routes/billing/supplier_invoice.py
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.auth.dependencies import get_current_user, get_employee_user
from app.config.enums import SupplierInvoiceType
from app.config.settings import settings
from app.dependencies.database import get_db
from app.schemas.billing.supplier_invoice import (
    ARInvoiceDetailsSchema,
    BillInvoiceMatchCreateSchema,
    BillInvoiceMatchResponseSchema,
    PEInvoiceDetailsSchema,
    SupplierInvoiceCreateSchema,
    SupplierInvoiceResponseSchema,
    SupplierInvoiceReviewSchema,
    USInvoiceDetailsSchema,
)
from app.schemas.consolidated_schemas import SupplierInvoiceEnrichedResponseSchema
from app.security.entity_scoping import ENTITY_INSTITUTION_ENTITY, EntityScopingService
from app.services.billing.supplier_invoice_service import (
    create_supplier_invoice,
    enrich_with_country_details,
    get_supplier_invoices,
    match_invoice_to_bills,
    resolve_document_url,
    review_supplier_invoice,
)
from app.services.crud_service import supplier_invoice_service
from app.services.entity_service import get_enriched_supplier_invoices
from app.services.error_handling import handle_business_operation
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(prefix="/supplier-invoices", tags=["Supplier Invoices"])

ALLOWED_CONTENT_TYPES = {"application/pdf", "text/xml", "application/xml"}


def _parse_country_details_json(country_code: str, details_json: str | None) -> dict | None:
    """Parse and validate a country_details_json string into the appropriate schema."""
    if not details_json:
        return None
    raw = json.loads(details_json)
    if country_code == "AR":
        return ARInvoiceDetailsSchema(**raw).model_dump()
    if country_code == "PE":
        return PEInvoiceDetailsSchema(**raw).model_dump()
    if country_code == "US":
        return USInvoiceDetailsSchema(**raw).model_dump()
    return raw


@router.post("", response_model=SupplierInvoiceResponseSchema)
async def create_invoice(
    institution_entity_id: UUID = Form(...),
    country_code: str = Form(...),
    invoice_type: SupplierInvoiceType = Form(...),
    issued_date: date = Form(...),
    amount: Decimal = Form(...),
    currency_code: str = Form(...),
    external_invoice_number: str | None = Form(None),
    tax_amount: Decimal | None = Form(None),
    tax_rate: Decimal | None = Form(None),
    document_format: str | None = Form(None),
    country_details_json: str | None = Form(None),
    bill_matches_json: str | None = Form(None),
    document: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a supplier invoice with optional document upload and bill matches.

    Internal users → auto-approved. Supplier users → Pending Review.
    country_details_json: JSON object with country-specific fields (AR: cae_code, etc; PE: sunat_serie, etc; US: tax_year).
    bill_matches_json: JSON array of {institution_bill_id, matched_amount} objects.
    """
    # Parse and validate country details
    country_details = _parse_country_details_json(country_code, country_details_json)

    # Build the nested schema for validation
    ar_details = (
        ARInvoiceDetailsSchema(**json.loads(country_details_json))
        if country_code == "AR" and country_details_json
        else None
    )
    pe_details = (
        PEInvoiceDetailsSchema(**json.loads(country_details_json))
        if country_code == "PE" and country_details_json
        else None
    )
    us_details = (
        USInvoiceDetailsSchema(**json.loads(country_details_json))
        if country_code == "US" and country_details_json
        else None
    )

    create_data = SupplierInvoiceCreateSchema(
        institution_entity_id=institution_entity_id,
        country_code=country_code,
        invoice_type=invoice_type,
        issued_date=issued_date,
        amount=amount,
        currency_code=currency_code,
        external_invoice_number=external_invoice_number,
        tax_amount=tax_amount,
        tax_rate=tax_rate,
        document_format=document_format,
        ar_details=ar_details,
        pe_details=pe_details,
        us_details=us_details,
    )

    # Validate document if provided
    file_data = None
    file_content_type = None
    if document:
        if document.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}",
            )
        file_data = await document.read()
        if len(file_data) > settings.MAX_INVOICE_DOCUMENT_BYTES:
            raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")
        file_content_type = document.content_type

    # Scope check
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    if not scope.is_global:
        scope.enforce(str(institution_entity_id))

    def _create():
        data_dict = create_data.model_dump(
            exclude_none=True, exclude={"bill_matches", "ar_details", "pe_details", "us_details"}
        )
        data_dict["institution_entity_id"] = str(data_dict["institution_entity_id"])
        data_dict["invoice_type"] = (
            data_dict["invoice_type"].value
            if hasattr(data_dict["invoice_type"], "value")
            else data_dict["invoice_type"]
        )

        invoice = create_supplier_invoice(data_dict, country_details, file_data, file_content_type, current_user, db)

        # Create bill matches if provided
        if bill_matches_json:
            matches_raw = json.loads(bill_matches_json)
            bill_matches = [
                {"institution_bill_id": m["institution_bill_id"], "matched_amount": Decimal(str(m["matched_amount"]))}
                for m in matches_raw
            ]
            match_invoice_to_bills(invoice.supplier_invoice_id, bill_matches, current_user, db)

        # Build response with country details and document URL
        invoice_dict = invoice.model_dump()
        resolve_document_url(invoice_dict)
        enrich_with_country_details(invoice_dict, db)
        return SupplierInvoiceResponseSchema(**invoice_dict)

    return handle_business_operation(_create, "supplier invoice creation")


@router.get("", response_model=list[SupplierInvoiceResponseSchema])
def list_invoices(
    institution_entity_id: UUID | None = None,
    status: str | None = None,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List supplier invoices with optional filtering. Scoped to institution."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _list():
        invoices = get_supplier_invoices(db, scope=scope, entity_id=institution_entity_id, status_filter=status)
        result = []
        for inv in invoices:
            inv_dict = inv.model_dump()
            resolve_document_url(inv_dict)
            enrich_with_country_details(inv_dict, db)
            result.append(SupplierInvoiceResponseSchema(**inv_dict))
        return result

    return handle_business_operation(_list, "supplier invoices listing")


@router.get("/enriched", response_model=list[SupplierInvoiceEnrichedResponseSchema])
def list_enriched_invoices(
    response: Response,
    institution_entity_id: UUID | None = None,
    status: str | None = None,
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get supplier invoices with enriched data (entity name, institution name, created-by name).

    Scoping:
    - Internal: See all invoices
    - Suppliers: See invoices for their institution's entities only"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _list_enriched():
        invoices = get_enriched_supplier_invoices(
            db,
            scope=scope,
            institution_entity_id=institution_entity_id,
            status_filter=status,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )
        result = []
        for inv in invoices:
            inv_dict = inv.model_dump()
            resolve_document_url(inv_dict)
            enrich_with_country_details(inv_dict, db)
            result.append(SupplierInvoiceEnrichedResponseSchema(**inv_dict))
        return result

    result = handle_business_operation(_list_enriched, "enriched supplier invoices listing")
    set_pagination_headers(response, result)
    return result


@router.get("/{invoice_id}", response_model=SupplierInvoiceResponseSchema)
def get_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single supplier invoice by ID. Scoped to institution."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _get():
        invoice = supplier_invoice_service.get_by_id(str(invoice_id), db, scope=scope)
        if not invoice:
            raise HTTPException(status_code=404, detail="Supplier invoice not found")
        inv_dict = invoice.model_dump()
        resolve_document_url(inv_dict)
        enrich_with_country_details(inv_dict, db)
        return SupplierInvoiceResponseSchema(**inv_dict)

    return handle_business_operation(_get, "supplier invoice retrieval")


@router.patch("/{invoice_id}/review", response_model=SupplierInvoiceResponseSchema)
def review_invoice(
    invoice_id: UUID,
    review_data: SupplierInvoiceReviewSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Approve or reject a supplier invoice. Internal Admin only."""

    def _review():
        invoice = review_supplier_invoice(
            invoice_id,
            review_data.status.value,
            review_data.rejection_reason,
            current_user["user_id"],
            db,
        )
        inv_dict = invoice.model_dump()
        resolve_document_url(inv_dict)
        enrich_with_country_details(inv_dict, db)
        return SupplierInvoiceResponseSchema(**inv_dict)

    return handle_business_operation(_review, "supplier invoice review")


@router.post("/{invoice_id}/match", response_model=list[BillInvoiceMatchResponseSchema])
def add_bill_matches(
    invoice_id: UUID,
    bill_matches: list[BillInvoiceMatchCreateSchema],
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Add bill matches to an existing supplier invoice."""
    EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _match():
        matches_data = [m.model_dump() for m in bill_matches]
        for m in matches_data:
            m["institution_bill_id"] = str(m["institution_bill_id"])
            m["matched_amount"] = str(m["matched_amount"])
        created = match_invoice_to_bills(invoice_id, matches_data, current_user, db)
        return [BillInvoiceMatchResponseSchema.model_validate(m) for m in created]

    return handle_business_operation(_match, "bill invoice matching")
