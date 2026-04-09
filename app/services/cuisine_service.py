"""
Cuisine Service — Business logic for cuisine management and suggestion workflow.

Provides search, CRUD helpers, and the supplier suggestion -> admin review pipeline.
"""

import re
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from app.utils.db import db_read

logger = logging.getLogger(__name__)


def search_cuisines(
    db: psycopg2.extensions.connection,
    search: Optional[str] = None,
    include_archived: bool = False,
) -> List[dict]:
    """Search active cuisines by name or slug. Returns dicts for schema mapping."""
    base = "SELECT * FROM cuisine"
    conditions = []
    params: list = []

    if not include_archived:
        conditions.append("NOT is_archived AND status = 'active'")

    if search:
        conditions.append("(cuisine_name ILIKE %s OR slug ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])

    if conditions:
        base += " WHERE " + " AND ".join(conditions)

    base += " ORDER BY display_order NULLS LAST, cuisine_name"

    rows = db_read(base, tuple(params), connection=db, fetch_one=False)
    return rows or []


def create_suggestion(
    suggested_name: str,
    suggested_by: UUID,
    restaurant_id: Optional[UUID],
    modified_by: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """Create a Pending cuisine suggestion from a supplier."""
    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            INSERT INTO cuisine_suggestion (
                suggested_name, suggested_by, restaurant_id,
                suggestion_status, created_by, modified_by
            )
            VALUES (%s, %s, %s, 'pending', %s, %s)
            RETURNING *
            """,
            (
                suggested_name,
                str(suggested_by),
                str(restaurant_id) if restaurant_id else None,
                str(suggested_by),
                str(modified_by),
            ),
        )
        row = cursor.fetchone()
        db.commit()
    return dict(row) if row else None


def approve_suggestion(
    suggestion_id: UUID,
    reviewer_id: UUID,
    resolved_cuisine_id: Optional[UUID],
    review_notes: Optional[str],
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Approve a Pending suggestion.

    If resolved_cuisine_id is provided, maps to existing cuisine.
    If None, creates a new cuisine from the suggested name.
    Updates the originating restaurant's cuisine_id if present.
    """
    # Fetch suggestion (must be Pending)
    suggestion = db_read(
        "SELECT * FROM cuisine_suggestion WHERE suggestion_id = %s AND suggestion_status = 'pending'",
        (str(suggestion_id),),
        connection=db,
        fetch_one=True,
    )
    if not suggestion:
        return None

    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        # Resolve cuisine
        if resolved_cuisine_id:
            existing = db_read(
                "SELECT cuisine_id FROM cuisine WHERE cuisine_id = %s",
                (str(resolved_cuisine_id),),
                connection=db,
                fetch_one=True,
            )
            if not existing:
                return None
            final_cuisine_id = str(resolved_cuisine_id)
        else:
            slug = _generate_slug(suggestion["suggested_name"], db)
            cursor.execute(
                """
                INSERT INTO cuisine (
                    cuisine_name, slug, origin_source,
                    created_by, modified_by
                )
                VALUES (%s, %s, 'supplier', %s, %s)
                RETURNING cuisine_id
                """,
                (
                    suggestion["suggested_name"],
                    slug,
                    str(suggestion["suggested_by"]),
                    str(reviewer_id),
                ),
            )
            new_row = cursor.fetchone()
            final_cuisine_id = str(new_row["cuisine_id"])

        # Update suggestion
        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            UPDATE cuisine_suggestion
            SET suggestion_status = 'approved',
                reviewed_by = %s,
                reviewed_date = %s,
                review_notes = %s,
                resolved_cuisine_id = %s,
                modified_by = %s,
                modified_date = %s
            WHERE suggestion_id = %s AND suggestion_status = 'pending'
            RETURNING *
            """,
            (
                str(reviewer_id),
                now,
                review_notes,
                final_cuisine_id,
                str(reviewer_id),
                now,
                str(suggestion_id),
            ),
        )
        updated = cursor.fetchone()

        # Update restaurant cuisine_id if linked
        if suggestion.get("restaurant_id"):
            cursor.execute(
                "UPDATE restaurant_info SET cuisine_id = %s, modified_by = %s, modified_date = %s WHERE restaurant_id = %s",
                (final_cuisine_id, str(reviewer_id), now, str(suggestion["restaurant_id"])),
            )

        db.commit()

    return dict(updated) if updated else None


def reject_suggestion(
    suggestion_id: UUID,
    reviewer_id: UUID,
    review_notes: Optional[str],
    db: psycopg2.extensions.connection,
) -> dict:
    """Reject a Pending suggestion."""
    now = datetime.now(timezone.utc)
    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            UPDATE cuisine_suggestion
            SET suggestion_status = 'rejected',
                reviewed_by = %s,
                reviewed_date = %s,
                review_notes = %s,
                modified_by = %s,
                modified_date = %s
            WHERE suggestion_id = %s AND suggestion_status = 'pending'
            RETURNING *
            """,
            (
                str(reviewer_id),
                now,
                review_notes,
                str(reviewer_id),
                now,
                str(suggestion_id),
            ),
        )
        updated = cursor.fetchone()
        db.commit()
    return dict(updated) if updated else None


def get_pending_suggestions(db: psycopg2.extensions.connection) -> List[dict]:
    """List all Pending cuisine suggestions."""
    rows = db_read(
        "SELECT * FROM cuisine_suggestion WHERE suggestion_status = 'pending' AND NOT is_archived ORDER BY created_date",
        (),
        connection=db,
        fetch_one=False,
    )
    return rows or []


def _generate_slug(name: str, db: psycopg2.extensions.connection) -> str:
    """Generate a URL-safe slug from cuisine name, handling collisions."""
    base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = base_slug

    suffix = 1
    while True:
        existing = db_read(
            "SELECT 1 FROM cuisine WHERE slug = %s",
            (slug,),
            connection=db,
            fetch_one=True,
        )
        if not existing:
            return slug
        suffix += 1
        slug = f"{base_slug}-{suffix}"
