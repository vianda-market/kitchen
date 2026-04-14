"""Resolve effective supplier terms config via three-tier cascade.

Resolution order: entity override → institution default → market_payout_aggregator → hardcoded.
See docs/plans/MULTINATIONAL_INSTITUTIONS.md for design rationale.
"""

from datetime import time
from uuid import UUID
from typing import Optional
import psycopg2.extensions

from app.utils.db import db_read

DEFAULT_KITCHEN_OPEN = time(9, 0)
DEFAULT_KITCHEN_CLOSE = time(13, 30)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_terms_row(
    institution_id: UUID,
    institution_entity_id: Optional[UUID],
    db: psycopg2.extensions.connection,
) -> Optional[dict]:
    """Fetch a specific supplier_terms row.

    If institution_entity_id is provided, fetches the entity-level override.
    If None, fetches the institution-level default (entity IS NULL).
    """
    if institution_entity_id is not None:
        return db_read(
            "SELECT * FROM supplier_terms "
            "WHERE institution_id = %s AND institution_entity_id = %s AND is_archived = FALSE",
            (str(institution_id), str(institution_entity_id)),
            connection=db,
            fetch_one=True,
        )
    return db_read(
        "SELECT * FROM supplier_terms "
        "WHERE institution_id = %s AND institution_entity_id IS NULL AND is_archived = FALSE",
        (str(institution_id),),
        connection=db,
        fetch_one=True,
    )


def _resolve_field(field: str, entity_terms: Optional[dict], institution_terms: Optional[dict]):
    """Return the first non-None value from entity → institution tiers."""
    if entity_terms and entity_terms.get(field) is not None:
        return entity_terms[field]
    if institution_terms and institution_terms.get(field) is not None:
        return institution_terms[field]
    return None


def _get_market_payout_config(institution_id: UUID, db: psycopg2.extensions.connection) -> Optional[dict]:
    """Fetch market_payout_aggregator row for the institution's primary market.

    Looks up market via institution_market junction (is_primary=TRUE first, then any).
    """
    row = db_read(
        "SELECT mpa.require_invoice, mpa.max_unmatched_bill_days, "
        "       mpa.kitchen_open_time, mpa.kitchen_close_time "
        "FROM billing.market_payout_aggregator mpa "
        "JOIN core.institution_market im ON im.market_id = mpa.market_id "
        "WHERE im.institution_id = %s AND mpa.is_archived = FALSE "
        "ORDER BY im.is_primary DESC LIMIT 1",
        (str(institution_id),),
        connection=db,
        fetch_one=True,
    )
    return row


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_terms_for_scope(
    institution_id: UUID,
    institution_entity_id: Optional[UUID],
    db: psycopg2.extensions.connection,
) -> Optional[dict]:
    """Get supplier terms row for a specific (institution, entity) scope.

    entity_id=None fetches the institution-level default (IS NULL).
    Returns raw dict or None.
    """
    return _get_terms_row(institution_id, institution_entity_id, db)


def resolve_effective_invoice_config(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    institution_entity_id: Optional[UUID] = None,
) -> dict:
    """Return resolved invoice compliance config.

    Three-tier cascade: entity → institution → market → hardcoded.

    Returns:
        {"effective_require_invoice": bool, "effective_invoice_hold_days": int}
    """
    entity_terms = _get_terms_row(institution_id, institution_entity_id, db) if institution_entity_id else None
    institution_terms = _get_terms_row(institution_id, None, db)

    market_require = False
    market_hold_days = 30
    market_row = _get_market_payout_config(institution_id, db)
    if market_row:
        market_require = market_row["require_invoice"]
        market_hold_days = market_row["max_unmatched_bill_days"]

    resolved_require = _resolve_field("require_invoice", entity_terms, institution_terms)
    resolved_hold = _resolve_field("invoice_hold_days", entity_terms, institution_terms)

    return {
        "effective_require_invoice": resolved_require if resolved_require is not None else market_require,
        "effective_invoice_hold_days": resolved_hold if resolved_hold is not None else market_hold_days,
    }


def resolve_effective_kitchen_hours(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    institution_entity_id: Optional[UUID] = None,
) -> dict:
    """Return resolved kitchen hours.

    Three-tier cascade: entity → institution → market → hardcoded.

    Returns:
        {"effective_kitchen_open_time": str (HH:MM), "effective_kitchen_close_time": str (HH:MM)}
    """
    entity_terms = _get_terms_row(institution_id, institution_entity_id, db) if institution_entity_id else None
    institution_terms = _get_terms_row(institution_id, None, db)

    market_open = DEFAULT_KITCHEN_OPEN
    market_close = DEFAULT_KITCHEN_CLOSE
    market_row = _get_market_payout_config(institution_id, db)
    if market_row:
        if market_row.get("kitchen_open_time"):
            market_open = market_row["kitchen_open_time"]
        if market_row.get("kitchen_close_time"):
            market_close = market_row["kitchen_close_time"]

    effective_open = _resolve_field("kitchen_open_time", entity_terms, institution_terms)
    effective_close = _resolve_field("kitchen_close_time", entity_terms, institution_terms)

    if effective_open is None:
        effective_open = market_open
    if effective_close is None:
        effective_close = market_close

    def _fmt(t):
        if hasattr(t, "strftime"):
            return t.strftime("%H:%M")
        return str(t)

    return {
        "effective_kitchen_open_time": _fmt(effective_open),
        "effective_kitchen_close_time": _fmt(effective_close),
    }


def get_supplier_payment_frequency(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    institution_entity_id: Optional[UUID] = None,
) -> str:
    """Return the payment frequency for a supplier. Default: 'daily'.

    Three-tier cascade: entity → institution → 'daily'.
    """
    if institution_entity_id:
        entity_terms = _get_terms_row(institution_id, institution_entity_id, db)
        freq = entity_terms.get("payment_frequency") if entity_terms else None
        if freq:
            return freq
    institution_terms = _get_terms_row(institution_id, None, db)
    if institution_terms:
        return institution_terms.get("payment_frequency") or "daily"
    return "daily"
