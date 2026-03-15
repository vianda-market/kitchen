# app/services/payment_provider/__init__.py
"""
Payment provider abstraction. Implementations live in subfolders (e.g. stripe/).
Used for atomic subscription + payment; mock (stripe mock) or stripe (live).
"""
from typing import Optional, TypedDict
from uuid import UUID


class PaymentIntentResult(TypedDict):
    """Result of creating a payment intent (or mock equivalent)."""
    id: str
    client_secret: str
    status: str


def create_payment_for_subscription(
    subscription_id: UUID,
    amount_cents: int,
    currency: str,
    metadata: Optional[dict] = None,
) -> PaymentIntentResult:
    """
    Create a payment intent (or mock) for the given subscription.
    Called by the subscription-with-payment flow. Implementation is chosen by PAYMENT_PROVIDER (mock vs stripe).
    """
    from app.config.settings import settings
    provider = (getattr(settings, "PAYMENT_PROVIDER", None) or "mock").strip().lower()
    if provider == "mock":
        from app.services.payment_provider.stripe.mock import create_payment_for_subscription as mock_create
        return mock_create(subscription_id, amount_cents, currency, metadata or {})
    if provider == "stripe":
        try:
            from app.services.payment_provider.stripe.live import create_payment_for_subscription as live_create
            return live_create(subscription_id, amount_cents, currency, metadata or {})
        except ImportError:
            raise ValueError(
                "PAYMENT_PROVIDER=stripe but real Stripe adapter not implemented. "
                "See docs/api/internal/STRIPE_INTEGRATION_HANDOFF.md to implement live Stripe."
            )
    raise ValueError(f"Unknown PAYMENT_PROVIDER: {provider}. Use 'mock' or 'stripe'.")


def cancel_payment_intent(external_payment_id: str) -> None:
    """
    Cancel a payment intent (Stripe or mock) so we do not leave orphan intents.
    Called when reusing a Pending subscription (edit in place) to cancel the previous intent.
    Mock: no-op. Stripe: cancels via Stripe API if live module implements it.
    """
    from app.config.settings import settings
    provider = (getattr(settings, "PAYMENT_PROVIDER", None) or "mock").strip().lower()
    if provider == "mock":
        from app.services.payment_provider.stripe.mock import cancel_payment_intent as mock_cancel
        mock_cancel(external_payment_id)
        return
    if provider == "stripe":
        try:
            from app.services.payment_provider.stripe import live as stripe_live
            if hasattr(stripe_live, "cancel_payment_intent"):
                stripe_live.cancel_payment_intent(external_payment_id)
        except ImportError:
            pass  # live not implemented; avoid leaving orphan intents best-effort when live is added
        return
    # unknown provider: no-op


def get_client_secret_for_pending_payment(external_payment_id: str, subscription_id: UUID) -> str:
    """
    Get client_secret for an existing payment intent (used by GET payment-details for Pending subscriptions).
    Mock: reconstruct from external_payment_id and subscription_id. Stripe: retrieve PaymentIntent by id.
    """
    from app.config.settings import settings
    provider = (getattr(settings, "PAYMENT_PROVIDER", None) or "mock").strip().lower()
    if provider == "mock":
        from app.services.payment_provider.stripe.mock import get_client_secret_for_existing_payment as mock_get
        return mock_get(external_payment_id, subscription_id)
    if provider == "stripe":
        try:
            from app.services.payment_provider.stripe import live as stripe_live
            if hasattr(stripe_live, "get_payment_intent_client_secret"):
                return stripe_live.get_payment_intent_client_secret(external_payment_id)
        except ImportError:
            pass
        raise ValueError(
            "PAYMENT_PROVIDER=stripe but get_payment_intent_client_secret not implemented in live module. "
            "Use GET payment-details with mock, or implement Stripe retrieve PaymentIntent in live."
        )
    raise ValueError(f"Unknown PAYMENT_PROVIDER: {provider}. Use 'mock' or 'stripe'.")
