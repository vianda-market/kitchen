"""
Plate Review Service

Business logic for customer plate reviews (Stars 1-5, Portion Size 1-3).
One review per pickup; reviews are immutable after creation.
Only customers who have completed a pickup (was_collected=true) can submit reviews.
"""

from uuid import UUID
from typing import Optional, List
import psycopg2.extensions

from app.dto.models import PlateReviewDTO
from app.utils.db import db_read, db_insert
from app.utils.log import log_info, log_error
from fastapi import HTTPException


def create_review(
    user_id: UUID,
    plate_pickup_id: UUID,
    stars_rating: int,
    portion_size_rating: int,
    db: psycopg2.extensions.connection,
) -> PlateReviewDTO:
    """
    Create a plate review. One review per pickup; immutable after creation.

    Eligibility: The pickup must belong to the user, have was_collected=true,
    and must not already have a review.

    Args:
        user_id: Current user (Customer)
        plate_pickup_id: The completed pickup being reviewed
        stars_rating: 1-5
        portion_size_rating: 1-3
        db: Database connection

    Returns:
        PlateReviewDTO of the created review

    Raises:
        HTTPException: 403 if not eligible, 404 if pickup not found
    """
    # 1. Fetch pickup and validate
    pickup = db_read(
        """
        SELECT plate_pickup_id, user_id, plate_id, was_collected, is_archived
        FROM plate_pickup_live
        WHERE plate_pickup_id = %s
        """,
        (str(plate_pickup_id),),
        connection=db,
        fetch_one=True,
    )
    if not pickup:
        raise HTTPException(status_code=404, detail="Pickup not found")

    if str(pickup["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Pickup does not belong to you")

    if not pickup.get("was_collected"):
        raise HTTPException(
            status_code=403,
            detail="You can only review plates you have picked up. Complete the pickup first.",
        )

    if pickup.get("is_archived"):
        raise HTTPException(status_code=400, detail="Cannot review an archived pickup")

    # 2. Check no review exists for this pickup
    existing = db_read(
        """
        SELECT plate_review_id FROM plate_review_info
        WHERE plate_pickup_id = %s AND is_archived = FALSE
        """,
        (str(plate_pickup_id),),
        connection=db,
        fetch_one=True,
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="This pickup has already been reviewed. Reviews are immutable.",
        )

    # 3. Insert review
    data = {
        "user_id": str(user_id),
        "plate_id": str(pickup["plate_id"]),
        "plate_pickup_id": str(plate_pickup_id),
        "stars_rating": stars_rating,
        "portion_size_rating": portion_size_rating,
    }
    review_id = db_insert("plate_review_info", data, connection=db)

    # 4. Fetch and return
    row = db_read(
        """
        SELECT plate_review_id, user_id, plate_id, plate_pickup_id,
               stars_rating, portion_size_rating, is_archived, created_date, modified_date
        FROM plate_review_info
        WHERE plate_review_id = %s
        """,
        (str(review_id),),
        connection=db,
        fetch_one=True,
    )
    log_info(f"Created plate review {review_id} for pickup {plate_pickup_id} by user {user_id}")
    return PlateReviewDTO(**row)


def get_reviews_by_user(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False,
) -> List[PlateReviewDTO]:
    """List all reviews by the given user."""
    archived_clause = "" if include_archived else "AND is_archived = FALSE"
    rows = db_read(
        f"""
        SELECT plate_review_id, user_id, plate_id, plate_pickup_id,
               stars_rating, portion_size_rating, is_archived, created_date, modified_date
        FROM plate_review_info
        WHERE user_id = %s {archived_clause}
        ORDER BY plate_review_id DESC
        """,
        (str(user_id),),
        connection=db,
        fetch_one=False,
    ) or []
    return [PlateReviewDTO(**r) for r in rows]


def get_review_by_pickup(
    user_id: UUID,
    plate_pickup_id: UUID,
    db: psycopg2.extensions.connection,
) -> Optional[PlateReviewDTO]:
    """Get the review for a specific pickup, if it exists and belongs to the user."""
    row = db_read(
        """
        SELECT plate_review_id, user_id, plate_id, plate_pickup_id,
               stars_rating, portion_size_rating, is_archived, created_date, modified_date
        FROM plate_review_info
        WHERE plate_pickup_id = %s AND user_id = %s AND is_archived = FALSE
        """,
        (str(plate_pickup_id), str(user_id)),
        connection=db,
        fetch_one=True,
    )
    return PlateReviewDTO(**row) if row else None


def get_plate_review_aggregates(
    plate_ids: List[UUID],
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Return aggregates per plate_id: average_stars, average_portion_size, review_count.
    Only non-archived reviews.
    """
    if not plate_ids:
        return {}
    ids_placeholder = ",".join("%s" for _ in plate_ids)
    rows = db_read(
        f"""
        SELECT plate_id,
               ROUND(AVG(stars_rating)::numeric, 1) as average_stars,
               ROUND(AVG(portion_size_rating)::numeric, 1) as average_portion_size,
               COUNT(*)::int as review_count
        FROM plate_review_info
        WHERE plate_id IN ({ids_placeholder}) AND is_archived = FALSE
        GROUP BY plate_id
        """,
        tuple(str(pid) for pid in plate_ids),
        connection=db,
        fetch_one=False,
    ) or []
    return {
        str(r["plate_id"]): {
            "average_stars": float(r["average_stars"]) if r["average_stars"] is not None else None,
            "average_portion_size": float(r["average_portion_size"]) if r["average_portion_size"] is not None else None,
            "review_count": r["review_count"],
        }
        for r in rows
    }
