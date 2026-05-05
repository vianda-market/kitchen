"""
Restaurant visibility: helper for "has active plate_kitchen_days" used by
restaurant update validation and by leads/explorer filtering (via shared SQL pattern).
"""

from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read


def restaurant_entity_has_payouts_enabled(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
) -> bool:
    """
    Return True if the institution_entity linked to this restaurant has
    payout_onboarding_status = 'complete' (Stripe Connect fully onboarded).
    Used to gate restaurant activation: a supplier may create a restaurant
    without payouts, but cannot activate it until payouts are wired.
    """
    query = """
        SELECT 1
        FROM ops.restaurant_info r
        JOIN ops.institution_entity_info e ON e.institution_entity_id = r.institution_entity_id
        WHERE r.restaurant_id = %s
          AND e.payout_onboarding_status = 'complete'
          AND NOT e.is_archived
        LIMIT 1
    """
    row = db_read(query, (str(restaurant_id),), connection=db, fetch_one=True)
    return row is not None


def restaurant_has_active_plate_kitchen_days(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
) -> bool:
    """
    Return True if the restaurant has at least one non-archived plate with
    at least one plate_kitchen_days row that is non-archived AND status = 'active'.
    Used to validate "can set restaurant to Active" and for leads/explorer visibility.
    """
    query = """
        SELECT 1
        FROM plate_info p
        INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id
          AND pkd.is_archived = FALSE
          AND pkd.status = 'active'
        WHERE p.restaurant_id = %s
          AND p.is_archived = FALSE
        LIMIT 1
    """
    row = db_read(query, (str(restaurant_id),), connection=db, fetch_one=True)
    return row is not None


def restaurant_has_active_qr_code(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
) -> bool:
    """
    Return True if the restaurant has at least one non-archived QR code with status = 'active'.
    Used to validate "can set restaurant to Active" and for leads/explorer visibility.
    """
    query = """
        SELECT 1
        FROM qr_code
        WHERE restaurant_id = %s
          AND is_archived = FALSE
          AND status = 'active'
        LIMIT 1
    """
    row = db_read(query, (str(restaurant_id),), connection=db, fetch_one=True)
    return row is not None


# SQL fragment: restaurants that have at least one plate_kitchen_day that is non-archived AND status = 'active'.
RESTAURANT_ACTIVE_WITH_PLATE_KITCHEN_DAYS_EXISTS = """
    EXISTS (
        SELECT 1
        FROM plate_info p
        INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
        WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
    )
"""

# SQL fragment: restaurants that have at least one QR code that is non-archived AND status = 'active'.
RESTAURANT_ACTIVE_WITH_QR_CODE_EXISTS = """
    EXISTS (
        SELECT 1
        FROM qr_code qc
        WHERE qc.restaurant_id = r.restaurant_id
          AND qc.is_archived = FALSE
          AND qc.status = 'active'
    )
"""
