from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import UUID
from app.services.crud_service import supplier_terms_service
from app.services.error_handling import handle_business_operation
from app.services.billing.supplier_terms_resolution import resolve_effective_invoice_config
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.security.field_policies import ensure_can_edit_supplier_terms
from app.schemas.consolidated_schemas import (
    SupplierTermsCreateSchema, SupplierTermsUpdateSchema, SupplierTermsResponseSchema,
)
import psycopg2.extensions

router = APIRouter(
    prefix="/supplier-terms",
    tags=["Supplier Terms"],
    dependencies=[Depends(oauth2_scheme)]
)


def _resolve_supplier_institution(current_user: dict, institution_id: UUID) -> UUID:
    """Enforce institution scoping — Suppliers can only see their own terms."""
    role_type = (current_user.get("role_type") or "").strip()
    if role_type == "supplier":
        own_id = current_user.get("institution_id")
        if not own_id or str(own_id) != str(institution_id):
            raise HTTPException(status_code=403, detail="Suppliers can only view their own terms")
        return institution_id
    if role_type == "internal":
        return institution_id
    raise HTTPException(status_code=403, detail="Only Supplier and Internal users can access supplier terms")


def _enrich_with_effective_values(terms_row: dict, db: psycopg2.extensions.connection) -> dict:
    """Add effective_require_invoice and effective_invoice_hold_days to a terms dict."""
    config = resolve_effective_invoice_config(terms_row["institution_id"], db)
    terms_row["effective_require_invoice"] = config["effective_require_invoice"]
    terms_row["effective_invoice_hold_days"] = config["effective_invoice_hold_days"]
    return terms_row


@router.get("/{institution_id}", response_model=SupplierTermsResponseSchema)
def get_supplier_terms(
    institution_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get supplier terms for an institution. Supplier sees own only, Internal sees all."""
    _resolve_supplier_institution(current_user, institution_id)

    def _get():
        terms = supplier_terms_service.get_by_field("institution_id", institution_id, db)
        if not terms:
            raise HTTPException(status_code=404, detail=f"Supplier terms not found for institution {institution_id}")
        return _enrich_with_effective_values(terms.model_dump(), db)

    return handle_business_operation(_get, "supplier terms retrieval")


@router.get("", response_model=List[SupplierTermsResponseSchema])
def list_supplier_terms(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all supplier terms. Internal only."""
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "internal":
        raise HTTPException(status_code=403, detail="Only Internal users can list all supplier terms.")

    def _list():
        all_terms = supplier_terms_service.get_all(db)
        return [_enrich_with_effective_values(t.model_dump(), db) for t in all_terms]

    return handle_business_operation(_list, "supplier terms list retrieval")


@router.put("/{institution_id}", response_model=SupplierTermsResponseSchema)
def upsert_supplier_terms(
    institution_id: UUID,
    data: SupplierTermsCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create or update supplier terms for an institution. Internal Manager/Admin/Super Admin only."""
    ensure_can_edit_supplier_terms(current_user)

    def _upsert():
        existing = supplier_terms_service.get_by_field("institution_id", institution_id, db)
        payload = data.model_dump(exclude_unset=True)
        payload["modified_by"] = current_user["user_id"]

        if existing:
            updated = supplier_terms_service.update(existing.supplier_terms_id, payload, db)
            if not updated:
                raise HTTPException(status_code=500, detail="Failed to update supplier terms")
            terms_dict = updated.model_dump()
        else:
            payload["institution_id"] = str(institution_id)
            created = supplier_terms_service.create(payload, db)
            if not created:
                raise HTTPException(status_code=500, detail="Failed to create supplier terms")
            terms_dict = created.model_dump()

        return _enrich_with_effective_values(terms_dict, db)

    return handle_business_operation(_upsert, "supplier terms upsert")
