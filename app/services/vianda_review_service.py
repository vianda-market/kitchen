"""
Vianda Review Service

Business logic for customer vianda reviews (Stars 1-5, Portion Size 1-3).
One review per pickup; reviews are immutable after creation.
Only customers who have completed a pickup (was_collected=true) can submit reviews.
"""

from uuid import UUID

import psycopg2.extensions

from app.dto.models import ViandaReviewDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.db import db_insert, db_read
from app.utils.log import log_info


def create_review(
    user_id: UUID,
    vianda_pickup_id: UUID,
    stars_rating: int,
    portion_size_rating: int,
    db: psycopg2.extensions.connection,
    *,
    would_order_again: bool | None = None,
    comment: str | None = None,
    locale: str = "en",
) -> ViandaReviewDTO:
    """
    Create a vianda review. One review per pickup; immutable after creation.

    Args:
        user_id: Current user (Customer)
        vianda_pickup_id: The completed pickup being reviewed
        stars_rating: 1-5
        portion_size_rating: 1-3
        db: Database connection
        would_order_again: Optional boolean — would user order this vianda again
        comment: Optional text feedback for the restaurant (max 500 chars)
        locale: Response locale

    Returns:
        ViandaReviewDTO of the created review

    Raises:
        HTTPException: 403 if not eligible, 404 if pickup not found
    """
    # 1. Fetch pickup and validate
    pickup = db_read(
        """
        SELECT vianda_pickup_id, user_id, vianda_id, was_collected, is_archived
        FROM vianda_pickup_live
        WHERE vianda_pickup_id = %s
        """,
        (str(vianda_pickup_id),),
        connection=db,
        fetch_one=True,
    )
    if not pickup:
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_NOT_FOUND, status=404, locale=locale)

    if str(pickup["user_id"]) != str(user_id):
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_ACCESS_DENIED, status=403, locale=locale)

    if not pickup.get("was_collected"):
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_NOT_ELIGIBLE, status=403, locale=locale)

    if pickup.get("is_archived"):
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_PICKUP_ARCHIVED, status=400, locale=locale)

    # 2. Check no review exists for this pickup
    existing = db_read(
        """
        SELECT vianda_review_id FROM vianda_review_info
        WHERE vianda_pickup_id = %s AND is_archived = FALSE
        """,
        (str(vianda_pickup_id),),
        connection=db,
        fetch_one=True,
    )
    if existing:
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_ALREADY_EXISTS, status=400, locale=locale)

    # 3. Insert review
    data = {
        "user_id": str(user_id),
        "vianda_id": str(pickup["vianda_id"]),
        "vianda_pickup_id": str(vianda_pickup_id),
        "stars_rating": stars_rating,
        "portion_size_rating": portion_size_rating,
    }
    if would_order_again is not None:
        data["would_order_again"] = would_order_again
    if comment is not None:
        data["comment"] = comment.strip()[:500]
    review_id = db_insert("vianda_review_info", data, connection=db)

    # 4. Fetch and return
    row = db_read(
        """
        SELECT vianda_review_id, user_id, vianda_id, vianda_pickup_id,
               stars_rating, portion_size_rating, would_order_again, comment,
               is_archived, created_date, modified_date
        FROM vianda_review_info
        WHERE vianda_review_id = %s
        """,
        (str(review_id),),
        connection=db,
        fetch_one=True,
    )
    log_info(f"Created vianda review {review_id} for pickup {vianda_pickup_id} by user {user_id}")
    return ViandaReviewDTO(**row)


def get_reviews_by_user(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False,
) -> list[ViandaReviewDTO]:
    """List all reviews by the given user."""
    archived_clause = "" if include_archived else "AND is_archived = FALSE"
    rows = (
        db_read(
            f"""
        SELECT vianda_review_id, user_id, vianda_id, vianda_pickup_id,
               stars_rating, portion_size_rating, would_order_again, comment,
               is_archived, created_date, modified_date
        FROM vianda_review_info
        WHERE user_id = %s {archived_clause}
        ORDER BY vianda_review_id DESC
        """,
            (str(user_id),),
            connection=db,
            fetch_one=False,
        )
        or []
    )
    return [ViandaReviewDTO(**r) for r in rows]


def get_review_by_pickup(
    user_id: UUID,
    vianda_pickup_id: UUID,
    db: psycopg2.extensions.connection,
) -> ViandaReviewDTO | None:
    """Get the review for a specific pickup, if it exists and belongs to the user."""
    row = db_read(
        """
        SELECT vianda_review_id, user_id, vianda_id, vianda_pickup_id,
               stars_rating, portion_size_rating, would_order_again, comment,
               is_archived, created_date, modified_date
        FROM vianda_review_info
        WHERE vianda_pickup_id = %s AND user_id = %s AND is_archived = FALSE
        """,
        (str(vianda_pickup_id), str(user_id)),
        connection=db,
        fetch_one=True,
    )
    return ViandaReviewDTO(**row) if row else None


def get_enriched_reviews_by_institution(
    institution_id: UUID | None,
    db: psycopg2.extensions.connection,
    *,
    vianda_id: UUID | None = None,
    restaurant_id: UUID | None = None,
) -> list[dict]:
    """
    Return enriched vianda reviews scoped to an institution (supplier).
    No customer PII (user_id, vianda_pickup_id excluded).

    Args:
        institution_id: Supplier institution UUID. None = global (Internal users).
        db: Database connection
        vianda_id: Optional filter by vianda
        restaurant_id: Optional filter by restaurant

    Returns:
        List of dicts matching ViandaReviewEnrichedResponseSchema fields
    """
    conditions = ["pr.is_archived = FALSE"]
    params: list = []

    if institution_id is not None:
        conditions.append("ie.institution_id = %s")
        params.append(str(institution_id))

    if vianda_id is not None:
        conditions.append("pr.vianda_id = %s")
        params.append(str(vianda_id))

    if restaurant_id is not None:
        conditions.append("pl.restaurant_id = %s")
        params.append(str(restaurant_id))

    where_clause = " AND ".join(conditions)

    rows = (
        db_read(
            f"""
        SELECT pr.vianda_review_id, pr.vianda_id, prod.name AS vianda_name,
               r.name AS restaurant_name,
               pr.stars_rating, pr.portion_size_rating,
               pr.would_order_again, pr.comment, pr.created_date
        FROM vianda_review_info pr
        JOIN vianda_info pl ON pr.vianda_id = pl.vianda_id
        JOIN product_info prod ON pl.product_id = prod.product_id
        JOIN restaurant_info r ON pl.restaurant_id = r.restaurant_id
        JOIN institution_entity_info ie ON r.restaurant_id = ie.entity_id
        WHERE {where_clause}
        ORDER BY pr.created_date DESC
        """,
            tuple(params),
            connection=db,
            fetch_one=False,
        )
        or []
    )
    return rows


def get_vianda_review_aggregates(
    vianda_ids: list[UUID],
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Return aggregates per vianda_id: average_stars, average_portion_size, review_count.
    Only non-archived reviews.
    """
    if not vianda_ids:
        return {}
    ids_placeholder = ",".join("%s" for _ in vianda_ids)
    rows = (
        db_read(
            f"""
        SELECT vianda_id,
               ROUND(AVG(stars_rating)::numeric, 1) as average_stars,
               ROUND(AVG(portion_size_rating)::numeric, 1) as average_portion_size,
               COUNT(*)::int as review_count
        FROM vianda_review_info
        WHERE vianda_id IN ({ids_placeholder}) AND is_archived = FALSE
        GROUP BY vianda_id
        """,
            tuple(str(pid) for pid in vianda_ids),
            connection=db,
            fetch_one=False,
        )
        or []
    )
    return {
        str(r["vianda_id"]): {
            "average_stars": float(r["average_stars"]) if r["average_stars"] is not None else None,
            "average_portion_size": float(r["average_portion_size"]) if r["average_portion_size"] is not None else None,
            "review_count": r["review_count"],
        }
        for r in rows
    }


def file_portion_complaint(
    vianda_review_id: UUID,
    user_id: UUID,
    complaint_text: str | None,
    photo_storage_path: str | None,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> dict:
    """
    File a portion complaint for a review with portion_size_rating == 1.

    Args:
        vianda_review_id: The review this complaint is for
        user_id: Current customer user
        complaint_text: Optional details about the portion issue
        photo_storage_path: Optional GCS path to complaint photo
        db: Database connection
        locale: Response locale

    Returns:
        Dict with complaint details

    Raises:
        HTTPException: 404 if review not found, 403 if not owned, 400 if portion rating != 1
    """
    # Validate review exists, belongs to user, and has portion_size_rating == 1
    review = db_read(
        """
        SELECT vianda_review_id, user_id, vianda_id, vianda_pickup_id, portion_size_rating
        FROM vianda_review_info
        WHERE vianda_review_id = %s AND is_archived = FALSE
        """,
        (str(vianda_review_id),),
        connection=db,
        fetch_one=True,
    )
    if not review:
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_NOT_FOUND, status=404, locale=locale)
    if str(review["user_id"]) != str(user_id):
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_ACCESS_DENIED, status=403, locale=locale)
    if review["portion_size_rating"] != 1:
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_INVALID_PORTION_RATING, status=400, locale=locale)

    # Check no existing complaint for this review
    existing = db_read(
        "SELECT complaint_id FROM portion_complaint WHERE vianda_review_id = %s",
        (str(vianda_review_id),),
        connection=db,
        fetch_one=True,
    )
    if existing:
        raise envelope_exception(ErrorCode.VIANDA_REVIEW_COMPLAINT_EXISTS, status=400, locale=locale)

    # Get restaurant_id from the pickup
    pickup = db_read(
        "SELECT restaurant_id FROM vianda_pickup_live WHERE vianda_pickup_id = %s",
        (str(review["vianda_pickup_id"]),),
        connection=db,
        fetch_one=True,
    )
    restaurant_id = pickup["restaurant_id"] if pickup else None

    # Insert complaint
    data = {
        "vianda_pickup_id": str(review["vianda_pickup_id"]),
        "vianda_review_id": str(vianda_review_id),
        "user_id": str(user_id),
        "restaurant_id": str(restaurant_id) if restaurant_id else None,
    }
    if complaint_text:
        data["complaint_text"] = complaint_text.strip()[:1000]
    if photo_storage_path:
        data["photo_storage_path"] = photo_storage_path

    complaint_id = db_insert("portion_complaint", data, connection=db)

    # Fetch and return
    row = db_read(
        """
        SELECT complaint_id, vianda_pickup_id, vianda_review_id, restaurant_id,
               photo_storage_path, complaint_text, resolution_status, created_date
        FROM portion_complaint WHERE complaint_id = %s
        """,
        (str(complaint_id),),
        connection=db,
        fetch_one=True,
    )
    log_info(f"Portion complaint filed: {complaint_id} for review {vianda_review_id} by user {user_id}")
    return row
