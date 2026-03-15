# app/services/payment_provider/stripe/live.py
"""
Live Stripe implementation. Creates real PaymentIntents and handles webhook activation.
Used when PAYMENT_PROVIDER=stripe. Requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.
"""
from typing import Optional
from uuid import UUID

import stripe

from app.config.settings import settings
from app.services.payment_provider import PaymentIntentResult


def _ensure_stripe_configured() -> None:
    """Set Stripe API key from settings. Called before any Stripe API call."""
    key = (settings.STRIPE_SECRET_KEY or "").strip()
    if not key:
        raise ValueError(
            "STRIPE_SECRET_KEY is required when PAYMENT_PROVIDER=stripe. "
            "Add it to .env (use sk_test_... for sandbox)."
        )
    stripe.api_key = key


def create_payment_for_subscription(
    subscription_id: UUID,
    amount_cents: int,
    currency: str,
    metadata: Optional[dict] = None,
) -> PaymentIntentResult:
    """Create a real Stripe PaymentIntent for the subscription. Uses idempotency key for retries."""
    _ensure_stripe_configured()
    meta = metadata or {}
    meta["subscription_id"] = str(subscription_id)
    idempotency_key = f"subscription_{subscription_id}"
    pi = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=(currency or "usd").lower(),
        metadata=meta,
        idempotency_key=idempotency_key,
        automatic_payment_methods={"enabled": True},
    )
    return {
        "id": pi.id,
        "client_secret": pi.client_secret or "",
        "status": pi.status or "requires_payment_method",
    }


def cancel_payment_intent(external_payment_id: str) -> None:
    """Cancel a Stripe PaymentIntent so we do not leave orphan intents."""
    _ensure_stripe_configured()
    if not external_payment_id or external_payment_id.startswith("pi_mock_"):
        return
    try:
        stripe.PaymentIntent.cancel(external_payment_id)
    except stripe.error.InvalidRequestError:
        pass  # Already canceled or doesn't exist


def get_payment_intent_client_secret(external_payment_id: str) -> str:
    """Retrieve client_secret for an existing Stripe PaymentIntent. Used by GET payment-details."""
    _ensure_stripe_configured()
    pi = stripe.PaymentIntent.retrieve(external_payment_id)
    return pi.client_secret or ""
