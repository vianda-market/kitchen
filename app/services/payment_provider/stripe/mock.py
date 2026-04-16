# app/services/payment_provider/stripe/mock.py
"""
Stripe mock implementation. No HTTP calls; returns fixed client_secret and id for dev.
Used when PAYMENT_PROVIDER=mock. Real Stripe lives in live.py (see STRIPE_INTEGRATION_HANDOFF.md).
"""

from uuid import UUID

from app.services.payment_provider import PaymentIntentResult


def create_payment_for_subscription(
    subscription_id: UUID,
    amount_cents: int,
    currency: str,
    metadata: dict | None = None,
) -> PaymentIntentResult:
    """Return a mock payment intent id and client_secret for dev. No Stripe API call."""
    import uuid

    ext_id = f"pi_mock_{uuid.uuid4().hex[:24]}"
    return {
        "id": ext_id,
        "client_secret": f"{ext_id}_secret_{str(subscription_id).replace('-', '')}",
        "status": "requires_payment_method",
    }


def cancel_payment_intent(external_payment_id: str) -> None:
    """No-op for mock; no real payment intent to cancel."""


def get_client_secret_for_existing_payment(external_payment_id: str, subscription_id: UUID) -> str:
    """Reconstruct client_secret for an existing mock payment (same format as at create time). Used by GET payment-details."""
    return f"{external_payment_id}_secret_{str(subscription_id).replace('-', '')}"
