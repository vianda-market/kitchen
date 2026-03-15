# app/services/supplier_payout/mock.py
"""Mock supplier payout: no external call; returns success and a fake payout id."""
from typing import Optional
from uuid import UUID
from decimal import Decimal

from app.services.supplier_payout import PayoutResult


def trigger_payout(
    institution_bill_id: UUID,
    amount: Decimal,
    currency_code: str,
    **kwargs,
) -> PayoutResult:
    """Return success and a placeholder stripe_payout_id for dev/testing."""
    short = str(institution_bill_id).replace("-", "")[:16]
    stripe_payout_id = f"po_mock_{short}"
    return {
        "stripe_payout_id": stripe_payout_id,
        "success": True,
        "error": None,
    }
