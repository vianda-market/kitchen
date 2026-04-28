"""
Activation Service — lazy restaurant activation.

When a restaurant's prerequisites become satisfied, this module promotes
the restaurant from 'pending' to 'active' automatically (one-way only).

Readiness chain for a restaurant:
  1. restaurant.status = 'pending'  (precondition; already-active stays active)
  2. restaurant.is_archived = False
  3. ≥1 plate with plate_kitchen_days configured (non-archived, status='active')
  4. A QR row exists in ops.qr_code for that restaurant (non-archived, status='active')

Rule invariants (do NOT relax):
  - One-way only: active → active on prereq loss (NO auto-demotion).
  - Silent: no event log, no email, no audit row beyond the normal modified_date bump.
  - No DB CHECK constraint on activation prereqs.
  - Manual status flips by admin remain allowed.
"""

from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read
from app.utils.log import log_info


def _check_restaurant_prereqs(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Check the four readiness prerequisites for a restaurant in one query.

    Returns a dict with:
      - status: current restaurant status string (or None if not found)
      - name: restaurant name string (or None if not found)
      - is_archived: bool
      - has_plate_kitchen_days: bool — ≥1 active PKD for the restaurant
      - has_qr: bool — ≥1 active non-archived QR row for the restaurant
    """
    row = db_read(
        """
        SELECT
            r.status,
            r.name,
            r.is_archived,
            EXISTS (
                SELECT 1
                FROM ops.plate_info p
                JOIN ops.plate_kitchen_days pkd ON pkd.plate_id = p.plate_id
                WHERE p.restaurant_id = r.restaurant_id
                  AND p.is_archived = FALSE
                  AND pkd.is_archived = FALSE
                  AND pkd.status = 'active'
            ) AS has_plate_kitchen_days,
            EXISTS (
                SELECT 1
                FROM ops.qr_code qc
                WHERE qc.restaurant_id = r.restaurant_id
                  AND qc.is_archived = FALSE
                  AND qc.status = 'active'
            ) AS has_qr
        FROM ops.restaurant_info r
        WHERE r.restaurant_id = %s
        """,
        (str(restaurant_id),),
        connection=db,
        fetch_one=True,
    )
    if not row or not isinstance(row, dict):
        return {"status": None, "name": None, "is_archived": True, "has_plate_kitchen_days": False, "has_qr": False}
    return dict(row)


def compute_restaurant_missing(
    *,
    status: str | None,
    is_archived: bool,
    has_plate_kitchen_days: bool,
    has_qr: bool,
) -> list[str]:
    """
    Pure function: derive the list of unmet prerequisites.

    Returns a subset of:
      ["status_active", "not_archived", "plate_kitchen_days", "qr"]

    Empty list ⟺ all prerequisites satisfied.
    """
    missing: list[str] = []
    if status != "active":
        missing.append("status_active")
    if is_archived:
        missing.append("not_archived")
    if not has_plate_kitchen_days:
        missing.append("plate_kitchen_days")
    if not has_qr:
        missing.append("qr")
    return missing


def maybe_activate_restaurant(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """
    Promote restaurant.status from 'pending' → 'active' when all prereqs are met.

    Preconditions checked atomically:
      1. Restaurant is NOT archived
      2. Restaurant status is 'pending'  (already-active restaurants are skipped — no-op)
      3. ≥1 active plate_kitchen_days exists for the restaurant
      4. ≥1 active non-archived QR code exists for the restaurant

    Returns a dict with ``id`` and ``name`` of the promoted restaurant when promotion
    happened, or ``None`` otherwise (already active, prereqs not met, not found).
    Does NOT commit — caller owns the transaction boundary.
    """
    prereqs = _check_restaurant_prereqs(restaurant_id, db)

    if prereqs["status"] != "pending":
        # Already active (or archived, or not found) — nothing to do
        return None
    if prereqs["is_archived"]:
        return None
    if not prereqs["has_plate_kitchen_days"] or not prereqs["has_qr"]:
        # Not all prereqs met yet
        return None

    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE ops.restaurant_info
            SET status = 'active',
                modified_date = CURRENT_TIMESTAMP
            WHERE restaurant_id = %s
              AND status = 'pending'
              AND is_archived = FALSE
            """,
            (str(restaurant_id),),
        )
        promoted: bool = cur.rowcount > 0

    if promoted:
        log_info(f"Lazy activation: restaurant {restaurant_id} promoted pending → active")
        return {"id": restaurant_id, "name": prereqs["name"]}

    return None


def get_restaurant_readiness(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Return readiness fields for a single restaurant.

    Returns:
      {
        "is_ready_for_signup": bool,
        "missing": list[str],   # empty when is_ready_for_signup is True
      }
    """
    prereqs = _check_restaurant_prereqs(restaurant_id, db)
    missing = compute_restaurant_missing(
        status=prereqs["status"],
        is_archived=prereqs["is_archived"],
        has_plate_kitchen_days=prereqs["has_plate_kitchen_days"],
        has_qr=prereqs["has_qr"],
    )
    return {
        "is_ready_for_signup": len(missing) == 0,
        "missing": missing,
    }
