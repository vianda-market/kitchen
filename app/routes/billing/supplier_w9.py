# app/routes/billing/supplier_w9.py
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import get_current_user
from app.config.enums import TaxClassification
from app.config.settings import settings
from app.dependencies.database import get_db
from app.schemas.billing.supplier_w9 import (
    SupplierW9CreateSchema,
    SupplierW9ResponseSchema,
)
from app.security.entity_scoping import ENTITY_INSTITUTION_ENTITY, EntityScopingService
from app.services.billing.supplier_w9_service import (
    create_or_update_w9,
    get_w9_by_entity,
    resolve_w9_document_url,
)
from app.services.error_handling import handle_business_operation

router = APIRouter(prefix="/supplier-w9", tags=["Supplier W-9"])

W9_ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.post("", response_model=SupplierW9ResponseSchema)
async def submit_w9(
    institution_entity_id: UUID = Form(...),
    legal_name: str = Form(...),
    tax_classification: TaxClassification = Form(...),
    ein_last_four: str = Form(...),
    address_line: str = Form(...),
    business_name: str | None = Form(None),
    document: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Submit or update a W-9 for a US supplier entity.

    If a W-9 already exists for the entity, it is updated (upsert).
    Supplier users can only submit for their own entity; Internal can submit for any entity.
    """
    # Validate via schema
    create_data = SupplierW9CreateSchema(
        institution_entity_id=institution_entity_id,
        legal_name=legal_name,
        business_name=business_name,
        tax_classification=tax_classification,
        ein_last_four=ein_last_four,
        address_line=address_line,
    )

    # Validate document if provided
    file_data = None
    file_content_type = None
    if document:
        if document.content_type not in W9_ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="W-9 document must be a PDF")
        file_data = await document.read()
        if len(file_data) > settings.MAX_INVOICE_DOCUMENT_BYTES:
            raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")
        file_content_type = document.content_type

    # Scope check
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    if not scope.is_global:
        scope.enforce(str(institution_entity_id))

    def _submit():
        data_dict = create_data.model_dump(exclude_none=True)
        data_dict["institution_entity_id"] = str(data_dict["institution_entity_id"])
        data_dict["tax_classification"] = (
            data_dict["tax_classification"].value
            if hasattr(data_dict["tax_classification"], "value")
            else data_dict["tax_classification"]
        )

        w9 = create_or_update_w9(data_dict, file_data, file_content_type, current_user, db)
        w9_dict = w9.model_dump()
        resolve_w9_document_url(w9_dict)
        return SupplierW9ResponseSchema(**w9_dict)

    return handle_business_operation(_submit, "W-9 submission")


@router.get("/{entity_id}", response_model=SupplierW9ResponseSchema)
def get_entity_w9(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get the W-9 on file for a supplier entity. Returns 404 if not collected."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    if not scope.is_global:
        scope.enforce(str(entity_id))

    def _get():
        w9 = get_w9_by_entity(entity_id, db)
        if not w9:
            raise HTTPException(status_code=404, detail="No W-9 on file for this entity")
        w9_dict = w9.model_dump()
        resolve_w9_document_url(w9_dict)
        return SupplierW9ResponseSchema(**w9_dict)

    return handle_business_operation(_get, "W-9 retrieval")
