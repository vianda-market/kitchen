# app/services/supplier_payout/stripe_payout.py
"""
Live Stripe payout for institution bills (e.g. Stripe Connect payouts).
Implement when going live; for now raises ImportError so __init__ falls back to error result.
"""
from decimal import Decimal
from uuid import UUID

from app.services.supplier_payout import PayoutResult


def trigger_payout(
    institution_bill_id: UUID,
    amount: Decimal,
    currency_code: str,
    **kwargs,
) -> PayoutResult:
    """Trigger real Stripe payout. Not implemented yet."""
    raise ImportError("Stripe supplier payout not implemented; use SUPPLIER_PAYOUT_PROVIDER=mock.")
