"""Resolve effective supplier terms config (supplier override > market default)."""

from uuid import UUID
from typing import Optional
import psycopg2.extensions

from app.services.crud_service import supplier_terms_service, institution_service
from app.utils.db import db_read


def resolve_effective_invoice_config(institution_id: UUID, db: psycopg2.extensions.connection) -> dict:
    """Return resolved invoice compliance config for an institution.

    Resolution: supplier_terms (if set) > market_payout_aggregator (default).

    Returns:
        {
            "effective_require_invoice": bool,
            "effective_invoice_hold_days": int,
        }
    """
    # Supplier-level overrides
    terms = supplier_terms_service.get_by_field("institution_id", institution_id, db)
    supplier_require = getattr(terms, "require_invoice", None) if terms else None
    supplier_hold_days = getattr(terms, "invoice_hold_days", None) if terms else None

    # Market-level defaults
    institution = institution_service.get_by_id(institution_id, db)
    market_id = getattr(institution, "market_id", None) if institution else None

    market_require_invoice = False
    market_max_days = 30
    if market_id:
        row = db_read(
            "SELECT require_invoice, max_unmatched_bill_days FROM market_payout_aggregator WHERE market_id = %s",
            (str(market_id),),
            connection=db,
            fetch_one=True,
        )
        if row:
            market_require_invoice = row["require_invoice"]
            market_max_days = row["max_unmatched_bill_days"]

    return {
        "effective_require_invoice": supplier_require if supplier_require is not None else market_require_invoice,
        "effective_invoice_hold_days": supplier_hold_days if supplier_hold_days is not None else market_max_days,
    }


def get_supplier_payment_frequency(institution_id: UUID, db: psycopg2.extensions.connection) -> str:
    """Return the payment frequency for a supplier institution. Default: 'daily'."""
    terms = supplier_terms_service.get_by_field("institution_id", institution_id, db)
    if terms:
        return getattr(terms, "payment_frequency", "daily") or "daily"
    return "daily"
