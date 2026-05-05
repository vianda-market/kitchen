"""
Image-asset upload pipeline routes.

Two-step upload flow:
  1. POST /uploads        — client requests a signed PUT URL; kitchen inserts
                            image_asset row with pipeline_status='pending'.
  2. Client PUTs file     — directly to GCS using the signed URL (no kitchen
                            involvement).
  3. (Future) Worker      — flips pipeline_status to 'ready' after processing.

GET  /uploads/{image_asset_id} — poll status; signed read URLs returned only
                                  when pipeline_status='ready'.
DELETE /uploads/{image_asset_id} — purge GCS blobs and remove the row.

Auth: Supplier admin or Internal employee required.
Scope: Suppliers may only manage images for their own institution's products.
"""

from uuid import UUID, uuid4

import psycopg2.extensions
from fastapi import APIRouter, Depends, Response, status

from app.auth.dependencies import get_current_user, get_resolved_locale, oauth2_scheme
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    UploadCreateRequest,
    UploadCreateResponse,
    UploadStatusResponse,
)
from app.security.entity_scoping import ENTITY_PRODUCT, EntityScopingService
from app.utils.db import db_read
from app.utils.gcs import delete_image_asset_blobs, generate_image_asset_write_signed_url

router = APIRouter(prefix="/uploads", tags=["Uploads"], dependencies=[Depends(oauth2_scheme)])


def _get_product_row(product_id: UUID, db: psycopg2.extensions.connection) -> dict | None:
    """Fetch minimal product row (product_id, institution_id) or None."""
    row = db_read(
        "SELECT product_id, institution_id FROM ops.product_info WHERE product_id = %s AND is_archived = FALSE",
        (str(product_id),),
        connection=db,
        fetch_one=True,
    )
    return row  # type: ignore[return-value]


def _get_image_asset_row(image_asset_id: UUID, db: psycopg2.extensions.connection) -> dict | None:
    """Fetch an image_asset row by PK or None."""
    row = db_read(
        """
        SELECT image_asset_id, product_id, institution_id,
               original_storage_path, pipeline_status, moderation_status,
               created_date, modified_date
        FROM ops.image_asset
        WHERE image_asset_id = %s
        """,
        (str(image_asset_id),),
        connection=db,
        fetch_one=True,
    )
    return row  # type: ignore[return-value]


# ─── POST /uploads ───────────────────────────────────────────────────────────


@router.post("", response_model=UploadCreateResponse, status_code=201)
def create_upload(
    body: UploadCreateRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> UploadCreateResponse:
    """
    Request a signed PUT URL for uploading a product image.

    - Looks up the product and verifies the caller has access to its institution.
    - Replace semantics: if an image_asset row already exists for the product,
      deletes the GCS blobs and the old row before inserting a new one.
    - Inserts a new image_asset row with pipeline_status='pending'.
    - Returns image_asset_id, a signed PUT URL (valid for
      GCS_SIGNED_URL_EXPIRATION_SECONDS), and its expiry timestamp.
    """
    product_row = _get_product_row(body.product_id, db)
    if not product_row:
        raise envelope_exception(ErrorCode.UPLOAD_PRODUCT_NOT_FOUND, status=404, locale=locale)

    # Scope check: suppliers may only manage their own institution's products.
    scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
    if scope and not scope.is_global:
        if not scope.matches(product_row["institution_id"]):
            raise envelope_exception(ErrorCode.UPLOAD_ACCESS_DENIED, status=403, locale=locale)

    institution_id = str(product_row["institution_id"])
    product_id_str = str(body.product_id)

    # Replace semantics: purge prior image_asset if any.
    existing = db_read(
        "SELECT image_asset_id, institution_id FROM ops.image_asset WHERE product_id = %s",
        (product_id_str,),
        connection=db,
        fetch_one=True,
    )
    if existing:
        existing_row: dict = existing  # type: ignore[assignment]
        delete_image_asset_blobs(existing_row["institution_id"], body.product_id)
        with db.cursor() as cur:
            cur.execute(
                "DELETE FROM ops.image_asset WHERE image_asset_id = %s",
                (str(existing_row["image_asset_id"]),),
            )
        db.commit()

    # Generate signed PUT URL before inserting the row (fail fast on GCS errors).
    try:
        signed_url, expires_at = generate_image_asset_write_signed_url(institution_id, product_id_str)
    except Exception as exc:
        raise envelope_exception(ErrorCode.UPLOAD_SIGNED_URL_FAILED, status=500, locale="en") from exc

    blob_path = f"products/{institution_id}/{product_id_str}/original"
    image_asset_id = uuid4()
    modified_by = current_user.get("user_id")

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ops.image_asset (
                image_asset_id, product_id, institution_id,
                original_storage_path,
                pipeline_status, moderation_status,
                processing_version, failure_count, modified_by
            ) VALUES (%s, %s, %s, %s, 'pending', 'pending', 1, 0, %s)
            """,
            (
                str(image_asset_id),
                product_id_str,
                institution_id,
                blob_path,
                str(modified_by),
            ),
        )
    db.commit()

    return UploadCreateResponse(
        image_asset_id=image_asset_id,
        signed_write_url=signed_url,
        expires_at=expires_at,
    )


# ─── GET /uploads/{image_asset_id} ───────────────────────────────────────────


@router.get("/{image_asset_id}", response_model=UploadStatusResponse, status_code=200)
def get_upload_status(
    image_asset_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> UploadStatusResponse:
    """
    Poll the status of an image upload.

    Returns pipeline_status, moderation_status, and signed read URLs for
    derived sizes (hero, card, thumbnail) when pipeline_status='ready'.
    signed_urls is null for any other status.
    """
    row = _get_image_asset_row(image_asset_id, db)
    if not row:
        raise envelope_exception(ErrorCode.UPLOAD_NOT_FOUND, status=404, locale=locale)

    # Scope check.
    scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
    if scope and not scope.is_global:
        if not scope.matches(row["institution_id"]):
            raise envelope_exception(ErrorCode.UPLOAD_ACCESS_DENIED, status=403, locale=locale)

    signed_urls: dict[str, str] | None = None
    if row["pipeline_status"] == "ready":
        from app.utils.gcs import get_image_asset_signed_urls

        urls = get_image_asset_signed_urls(row["institution_id"], row["product_id"])
        signed_urls = urls if urls else None

    return UploadStatusResponse(
        image_asset_id=row["image_asset_id"],
        pipeline_status=row["pipeline_status"],
        moderation_status=row["moderation_status"],
        signed_urls=signed_urls,
    )


# ─── DELETE /uploads/{image_asset_id} ────────────────────────────────────────


@router.delete("/{image_asset_id}", status_code=204)
def delete_upload(
    image_asset_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Response:
    """
    Delete an image asset: purge GCS blobs then remove the DB row.

    Returns 204 No Content on success. The underlying GCS purge is best-effort
    (individual blob 404s are silently ignored).
    """
    row = _get_image_asset_row(image_asset_id, db)
    if not row:
        raise envelope_exception(ErrorCode.UPLOAD_NOT_FOUND, status=404, locale=locale)

    # Scope check.
    scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
    if scope and not scope.is_global:
        if not scope.matches(row["institution_id"]):
            raise envelope_exception(ErrorCode.UPLOAD_ACCESS_DENIED, status=403, locale=locale)

    delete_image_asset_blobs(row["institution_id"], row["product_id"])

    with db.cursor() as cur:
        cur.execute("DELETE FROM ops.image_asset WHERE image_asset_id = %s", (str(image_asset_id),))
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
