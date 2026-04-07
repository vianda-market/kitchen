# app/services/payment_provider/stripe/live.py
"""
Live Stripe implementation. Creates real PaymentIntents and handles webhook activation.
Used when PAYMENT_PROVIDER=stripe. Requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

import psycopg2.extensions
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


def create_customer_checkout_setup_session(
    user_id: UUID,
    success_url: str,
    cancel_url: str,
    db: psycopg2.extensions.connection,
) -> Tuple[str, datetime]:
    """
    Lock user row for email, ensure Stripe Customer exists in user_payment_provider, create Checkout Session mode=setup.
    Commits after provider insert so the record survives Session.create failures (return 502 to client).

    TODO: Stripe may deprecate payment_method_types=['card'] in favor of automatic_payment_methods or
    payment_method_configuration — see docs/plans/STRIPE_CUSTOMER_INTEGRATION_FOLLOWUPS.md
    """
    _ensure_stripe_configured()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT email FROM user_info
            WHERE user_id = %s::uuid
            FOR UPDATE
            """,
            (str(user_id),),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("User not found.")
        email = row[0]

        cursor.execute(
            """
            SELECT provider_customer_id FROM user_payment_provider
            WHERE user_id = %s::uuid AND provider = 'stripe' AND is_archived = FALSE
            LIMIT 1
            """,
            (str(user_id),),
        )
        provider_row = cursor.fetchone()
        stripe_cus: Optional[str] = provider_row[0] if provider_row else None

        if not stripe_cus:
            customer = stripe.Customer.create(
                email=email,
                metadata={"user_id": str(user_id)},
            )
            stripe_cus = customer.id
            cursor.execute(
                """
                INSERT INTO user_payment_provider (
                    user_id, provider, provider_customer_id,
                    modified_by, modified_date
                ) VALUES (
                    %s::uuid, 'stripe', %s,
                    %s::uuid, CURRENT_TIMESTAMP
                )
                """,
                (str(user_id), stripe_cus, str(user_id)),
            )
        db.commit()
    finally:
        cursor.close()

    session = stripe.checkout.Session.create(
        mode="setup",
        customer=stripe_cus,
        success_url=success_url,
        cancel_url=cancel_url,
        payment_method_types=["card"],
    )
    if not session.url:
        raise RuntimeError("Stripe Checkout Session returned no URL.")
    exp = session.expires_at
    if exp is None:
        expires_at = datetime.now(timezone.utc)
    else:
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
    return session.url, expires_at


def detach_customer_payment_method_external(external_id: Optional[str]) -> None:
    """Detach PM in Stripe; resource_missing = already detached (no-op). Re-raises other Stripe errors."""
    _ensure_stripe_configured()
    if not external_id or str(external_id).startswith("pm_mock_"):
        return
    try:
        stripe.PaymentMethod.detach(str(external_id))
    except stripe.error.InvalidRequestError as e:
        if getattr(e, "code", None) == "resource_missing":
            return
        raise
