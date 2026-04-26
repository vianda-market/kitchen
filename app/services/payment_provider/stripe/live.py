# app/services/payment_provider/stripe/live.py
"""
Live Stripe implementation. Creates real PaymentIntents and handles webhook activation.
Used when PAYMENT_PROVIDER=stripe. Requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.
"""

from datetime import UTC, datetime
from uuid import UUID

import psycopg2.extensions
import stripe

from app.config.settings import settings
from app.services.payment_provider import PaymentIntentResult
from app.utils.currency import convert_currency
from app.utils.validation import validate_uuid, validate_positive_integer


def _ensure_stripe_configured() -> None:
    """Set Stripe API key from settings. Called before any Stripe API call."""
    key = (settings.STRIPE_SECRET_KEY or "").strip()
    if not key:
        raise ValueError(
            "STRIPE_SECRET_KEY is required when PAYMENT_PROVIDER=stripe. Add it to .env (use sk_test_... for sandbox)."
        )
    stripe.api_key = key


def create_payment_for_subscription(
    subscription_id: UUID,
    amount_cents: int,
    currency: str,
    metadata: dict | None = None,
) -> PaymentIntentResult:
    """Create a real Stripe PaymentIntent for the subscription. Uses idempotency key for retries."""
    _ensure_stripe_configured()
    validate_uuid(subscription_id, "subscription_id")
    validate_positive_integer(amount_cents, "amount_cents")
    validate_currency(currency, "currency")

    amount_usd_cents = convert_currency(amount_cents, currency, "usd")
    if amount_usd_cents < 50:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "payment.amount_below_stripe_minimum",
                "message": "Plan price is below Stripe's minimum charge.",
                "params": {
                    "plan_amount_minor": amount_cents,
                    "plan_currency": currency,
                    "plan_amount_usd_cents": amount_usd_cents,
                    "min_usd_cents": 50,
                },
            },
        )

    meta = metadata or {}
    meta["subscription_id"] = str(subscription_id)
    idempotency_key = str(uuid.uuid4())
    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=meta,
            idempotency_key=idempotency_key,
        )
        return PaymentIntentResult(payment_intent.id, idempotency_key)
    except stripe.error.InvalidRequestError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "payment.provider_error",
                "message": "Stripe returned an error.",
                "params": {"stripe_error": str(e)},
            },
        ) from e


def validate_currency(currency: str, field_name: str) -> None:
    """Validate that the currency is a valid 3-letter code."""
    if len(currency) != 3 or not currency.isalpha():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "payment.invalid_currency",
                "message": f"Invalid currency: {currency}.",
                "params": {"field": field_name},
            },
        )