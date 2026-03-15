# app/services/supplier_payout/__init__.py
"""
Supplier (institution) payout abstraction. Used after settlement → bill to trigger
actual payout (e.g. Stripe Connect). Mock returns success; live implementation
calls Stripe (or other provider) and returns payout id.
"""
from typing import Optional, TypedDict
from uuid import UUID
from decimal import Decimal


class PayoutResult(TypedDict):
    """Result of triggering a payout for an institution bill."""
    stripe_payout_id: Optional[str]
    success: bool
    error: Optional[str]


def trigger_payout(
    institution_bill_id: UUID,
    amount: Decimal,
    currency_code: str,
    **kwargs,
) -> PayoutResult:
    """
    Trigger payout for an institution bill. Implementation is chosen by config
    (e.g. SUPPLIER_PAYOUT_PROVIDER=mock | stripe). Returns stripe_payout_id and success.
    """
    from app.config.settings import settings
    provider = (getattr(settings, "SUPPLIER_PAYOUT_PROVIDER", None) or "mock").strip().lower()
    if provider == "mock":
        from app.services.supplier_payout.mock import trigger_payout as mock_trigger
        return mock_trigger(institution_bill_id, amount, currency_code, **kwargs)
    if provider == "stripe":
        try:
            from app.services.supplier_payout.stripe_payout import trigger_payout as live_trigger
            return live_trigger(institution_bill_id, amount, currency_code, **kwargs)
        except ImportError:
            return {
                "stripe_payout_id": None,
                "success": False,
                "error": "Stripe supplier payout adapter not implemented.",
            }
    return {
        "stripe_payout_id": None,
        "success": False,
        "error": f"Unknown SUPPLIER_PAYOUT_PROVIDER: {provider}. Use 'mock' or 'stripe'.",
    }
