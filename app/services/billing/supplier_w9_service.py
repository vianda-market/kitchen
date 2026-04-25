# app/services/billing/supplier_w9_service.py
"""
Supplier W-9 business logic — create/update, retrieve, document URL resolution.

US suppliers must submit a W-9 before payouts. One W-9 per institution entity
(UNIQUE constraint on institution_entity_id).
"""

from uuid import UUID

import psycopg2.extensions

from app.dto.models import SupplierW9DTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.crud_service import supplier_w9_service
from app.utils.db import db_read
from app.utils.gcs import get_supplier_w9_document_signed_url, upload_supplier_w9_document
from app.utils.log import log_error


def create_or_update_w9(
    data: dict,
    file_data: bytes | None,
    file_content_type: str | None,
    current_user: dict,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> SupplierW9DTO:
    """
    Create or update a W-9 record for a US supplier entity.
    If a W-9 already exists for this entity, update it (upsert behavior).
    """
    user_id = str(current_user["user_id"])
    entity_id = str(data["institution_entity_id"])
    data["modified_by"] = user_id
    data["created_by"] = user_id

    # Check if W-9 already exists for this entity
    existing = _get_w9_by_entity_id(entity_id, db)

    if existing:
        # Update existing W-9
        update_data = {k: v for k, v in data.items() if k != "institution_entity_id"}
        update_data["modified_by"] = user_id

        if file_data and file_content_type:
            try:
                blob_path = upload_supplier_w9_document(str(existing.w9_id), entity_id, file_data, file_content_type)
                update_data["document_storage_path"] = blob_path
            except Exception as e:
                log_error(f"Failed to upload W-9 document: {e}")
                raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale) from None

        updated = supplier_w9_service.update(str(existing.w9_id), update_data, db)
        if not updated:
            log_error(f"Failed to update W-9 for entity {entity_id}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
        return updated
    # Create new W-9
    w9 = supplier_w9_service.create(data, db, commit=False)
    if not w9:
        log_error(f"Failed to create W-9 for entity {entity_id}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)

    if file_data and file_content_type:
        try:
            blob_path = upload_supplier_w9_document(str(w9.w9_id), entity_id, file_data, file_content_type)
            supplier_w9_service.update(
                str(w9.w9_id),
                {"document_storage_path": blob_path, "modified_by": user_id},
                db,
                commit=False,
            )
        except Exception as e:
            log_error(f"Failed to upload W-9 document: {e}")
            db.rollback()
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale) from None

    db.commit()
    return supplier_w9_service.get_by_id(str(w9.w9_id), db)


def get_w9_by_entity(
    institution_entity_id: UUID,
    db: psycopg2.extensions.connection,
) -> SupplierW9DTO | None:
    """Fetch the W-9 record for an entity. Returns None if not collected."""
    return _get_w9_by_entity_id(str(institution_entity_id), db)


def _get_w9_by_entity_id(
    entity_id: str,
    db: psycopg2.extensions.connection,
) -> SupplierW9DTO | None:
    """Internal helper to fetch W-9 by entity_id."""
    result = db_read(
        """SELECT * FROM billing.supplier_w9
           WHERE institution_entity_id = %s AND is_archived = FALSE""",
        (entity_id,),
        connection=db,
        fetch_one=True,
    )
    return SupplierW9DTO(**result) if result else None


def resolve_w9_document_url(w9_dict: dict) -> dict:
    """Replace document_storage_path with a signed document_url in the response dict."""
    storage_path = w9_dict.pop("document_storage_path", None)
    if storage_path:
        try:
            url = get_supplier_w9_document_signed_url(
                str(w9_dict["w9_id"]),
                str(w9_dict["institution_entity_id"]),
            )
            w9_dict["document_url"] = url
        except Exception:
            w9_dict["document_url"] = None
    else:
        w9_dict["document_url"] = None
    return w9_dict
