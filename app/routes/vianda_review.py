# app/routes/vianda_review.py
"""
Vianda Review API routes.

Customer endpoints: submit and view vianda reviews (Stars 1-5, Portion Size 1-3).
Supplier endpoint: enriched institution-scoped reviews for feedback dashboard.
One review per pickup; reviews are immutable after creation.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth.dependencies import get_client_user, get_current_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    PortionComplaintResponseSchema,
    ViandaReviewCreateSchema,
    ViandaReviewEnrichedResponseSchema,
    ViandaReviewResponseSchema,
)
from app.services.vianda_review_service import (
    create_review,
    file_portion_complaint,
    get_enriched_reviews_by_institution,
    get_review_by_pickup,
    get_reviews_by_user,
)
from app.utils.log import log_error

router = APIRouter(
    prefix="/vianda-reviews",
    tags=["Vianda Reviews"],
)


# --- Supplier / Internal: enriched institution-scoped reviews ---


@router.get("/by-institution/enriched", response_model=list[ViandaReviewEnrichedResponseSchema])
def get_institution_reviews_enriched(
    vianda_id: UUID | None = Query(None, description="Filter by vianda"),
    restaurant_id: UUID | None = Query(None, description="Filter by restaurant"),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Enriched vianda reviews scoped to the supplier's institution. No customer PII.

    Auth: Supplier (Admin/Manager/Operator) or Internal. Customers are rejected.
    """
    role_type = current_user.get("role_type")
    if role_type == "customer":
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_CUSTOMER_ONLY, status=403, locale=locale)

    # Suppliers are scoped to their institution; Internal sees all
    institution_id = None
    if role_type == "supplier":
        inst = current_user.get("institution_id")
        if not inst:
            raise envelope_exception(ErrorCode.VIANDA_REVIEW_NO_INSTITUTION, status=403, locale=locale)
        institution_id = UUID(str(inst))

    rows = get_enriched_reviews_by_institution(institution_id, db, vianda_id=vianda_id, restaurant_id=restaurant_id)
    return [ViandaReviewEnrichedResponseSchema(**r) for r in rows]


# --- Customer-only endpoints ---


@router.post("", response_model=ViandaReviewResponseSchema, status_code=201)
def create_vianda_review(
    payload: ViandaReviewCreateSchema,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a vianda review for a completed pickup. Customer-only. One review per pickup; immutable."""
    try:
        user_id = current_user["user_id"]
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        dto = create_review(
            user_id=user_id,
            vianda_pickup_id=payload.vianda_pickup_id,
            stars_rating=payload.stars_rating,
            portion_size_rating=payload.portion_size_rating,
            db=db,
            would_order_again=payload.would_order_again,
            comment=payload.comment,
        )
        return ViandaReviewResponseSchema(
            vianda_review_id=dto.vianda_review_id,
            user_id=dto.user_id,
            vianda_id=dto.vianda_id,
            vianda_pickup_id=dto.vianda_pickup_id,
            stars_rating=dto.stars_rating,
            portion_size_rating=dto.portion_size_rating,
            would_order_again=dto.would_order_again,
            comment=dto.comment,
            is_archived=dto.is_archived,
            created_date=dto.created_date,
            modified_date=dto.modified_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating vianda review: {e}")
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_CREATION_FAILED, status=500, locale="en") from None


@router.get("/me", response_model=list[ViandaReviewResponseSchema])
def list_my_reviews(
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List current user's vianda reviews. Customer-only. Non-archived only."""
    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    dtos = get_reviews_by_user(user_id, db, include_archived=False)
    return [
        ViandaReviewResponseSchema(
            vianda_review_id=d.vianda_review_id,
            user_id=d.user_id,
            vianda_id=d.vianda_id,
            vianda_pickup_id=d.vianda_pickup_id,
            stars_rating=d.stars_rating,
            portion_size_rating=d.portion_size_rating,
            would_order_again=d.would_order_again,
            comment=d.comment,
            is_archived=d.is_archived,
            created_date=d.created_date,
            modified_date=d.modified_date,
        )
        for d in dtos
    ]


@router.get("/me/by-pickup/{vianda_pickup_id}", response_model=ViandaReviewResponseSchema)
def get_my_review_by_pickup(
    vianda_pickup_id: UUID,
    current_user: dict = Depends(get_client_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get current user's review for a specific pickup, if it exists. Customer-only."""
    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    dto = get_review_by_pickup(user_id, vianda_pickup_id, db)
    if not dto:
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_BY_PICKUP_NOT_FOUND, status=404, locale=locale)
    return ViandaReviewResponseSchema(
        vianda_review_id=dto.vianda_review_id,
        user_id=dto.user_id,
        vianda_id=dto.vianda_id,
        vianda_pickup_id=dto.vianda_pickup_id,
        stars_rating=dto.stars_rating,
        portion_size_rating=dto.portion_size_rating,
        would_order_again=dto.would_order_again,
        comment=dto.comment,
        is_archived=dto.is_archived,
        created_date=dto.created_date,
        modified_date=dto.modified_date,
    )


@router.post("/{vianda_review_id}/portion-complaint", response_model=PortionComplaintResponseSchema, status_code=201)
def create_portion_complaint(
    vianda_review_id: UUID,
    complaint_text: str | None = Form(None),
    photo: UploadFile | None = File(None),
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """File a portion complaint for a review with portion size rating of 1 (small).

    Customer-only. Accepts optional photo (multipart) and text details.
    Routes to support queue for SLA review.
    """
    try:
        user_id = current_user["user_id"]
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        # Upload photo to GCS if provided
        photo_storage_path = None
        if photo and photo.filename:
            from app.config.settings import settings

            if settings.GCS_CUSTOMER_BUCKET:
                from app.utils.gcs import upload_customer_bucket_blob

                photo_bytes = photo.file.read()
                blob_path = f"complaints/{vianda_review_id}/photo"
                upload_customer_bucket_blob(blob_path, photo_bytes, content_type=photo.content_type or "image/jpeg")
                photo_storage_path = blob_path

        row = file_portion_complaint(
            vianda_review_id=vianda_review_id,
            user_id=user_id,
            complaint_text=complaint_text,
            photo_storage_path=photo_storage_path,
            db=db,
        )
        return PortionComplaintResponseSchema(**row)
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error filing portion complaint: {e}")
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_COMPLAINT_FAILED, status=500, locale="en") from None
