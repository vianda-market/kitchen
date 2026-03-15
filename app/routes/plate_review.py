# app/routes/plate_review.py
"""
Plate Review API routes.

Customer-only: submit and view plate reviews (Stars 1-5, Portion Size 1-3).
One review per pickup; reviews are immutable after creation.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
import psycopg2.extensions

from app.auth.dependencies import get_client_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import PlateReviewCreateSchema, PlateReviewResponseSchema
from app.services.plate_review_service import (
    create_review,
    get_reviews_by_user,
    get_review_by_pickup,
)
from app.utils.log import log_error

router = APIRouter(
    prefix="/plate-reviews",
    tags=["Plate Reviews"],
)

# Customer-only: use get_client_user


@router.post("", response_model=PlateReviewResponseSchema, status_code=201)
def create_plate_review(
    payload: PlateReviewCreateSchema,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a plate review for a completed pickup. Customer-only. One review per pickup; immutable."""
    try:
        user_id = current_user["user_id"]
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        dto = create_review(
            user_id=user_id,
            plate_pickup_id=payload.plate_pickup_id,
            stars_rating=payload.stars_rating,
            portion_size_rating=payload.portion_size_rating,
            db=db,
        )
        return PlateReviewResponseSchema(
            plate_review_id=dto.plate_review_id,
            user_id=dto.user_id,
            plate_id=dto.plate_id,
            plate_pickup_id=dto.plate_pickup_id,
            stars_rating=dto.stars_rating,
            portion_size_rating=dto.portion_size_rating,
            is_archived=dto.is_archived,
            created_date=dto.created_date,
            modified_date=dto.modified_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating plate review: {e}")
        raise HTTPException(status_code=500, detail="Failed to create plate review")


@router.get("/me", response_model=list[PlateReviewResponseSchema])
def list_my_reviews(
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List current user's plate reviews. Customer-only. Non-archived only."""
    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    dtos = get_reviews_by_user(user_id, db, include_archived=False)
    return [
        PlateReviewResponseSchema(
            plate_review_id=d.plate_review_id,
            user_id=d.user_id,
            plate_id=d.plate_id,
            plate_pickup_id=d.plate_pickup_id,
            stars_rating=d.stars_rating,
            portion_size_rating=d.portion_size_rating,
            is_archived=d.is_archived,
            created_date=d.created_date,
            modified_date=d.modified_date,
        )
        for d in dtos
    ]


@router.get("/me/by-pickup/{plate_pickup_id}", response_model=PlateReviewResponseSchema)
def get_my_review_by_pickup(
    plate_pickup_id: UUID,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get current user's review for a specific pickup, if it exists. Customer-only."""
    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    dto = get_review_by_pickup(user_id, plate_pickup_id, db)
    if not dto:
        raise HTTPException(status_code=404, detail="Review not found for this pickup")
    return PlateReviewResponseSchema(
        plate_review_id=dto.plate_review_id,
        user_id=dto.user_id,
        plate_id=dto.plate_id,
        plate_pickup_id=dto.plate_pickup_id,
        stars_rating=dto.stars_rating,
        portion_size_rating=dto.portion_size_rating,
        is_archived=dto.is_archived,
        created_date=dto.created_date,
        modified_date=dto.modified_date,
    )
