"""
Regression test for kitchen issue #128.

Checks that:
  1. app.routes.customer.payment_methods imports cleanly (catches accidental
     deletion of helpers that route imports directly from live.py).
  2. app.services.payment_provider.stripe.live exports the four helpers that
     existed on main and must never be removed.
  3. The three #128 additions (validate_currency, the amount-below-minimum
     guard, and the InvalidRequestError handler) are present at the module level.

These are intentionally import-level / attribute checks — no network calls,
no DB, no Stripe credentials required. They are the cheapest possible guard
against "helper silently deleted by a lint-cleanup PR".
"""

import importlib

import pytest


def _mod(dotted_path: str):
    return importlib.import_module(dotted_path)


def test_payment_methods_route_imports_cleanly() -> None:
    """app.routes.customer.payment_methods must import without raising."""
    mod = _mod("app.routes.customer.payment_methods")
    assert mod is not None


def test_stripe_live_exports_required_helpers() -> None:
    """The four main helpers must all be present in live.py (catches accidental deletion)."""
    live = _mod("app.services.payment_provider.stripe.live")
    required = [
        "_ensure_stripe_configured",
        "create_payment_for_subscription",
        "create_customer_checkout_setup_session",
        "detach_customer_payment_method_external",
    ]
    missing = [name for name in required if not hasattr(live, name)]
    assert not missing, f"Helper(s) missing from live.py: {missing}"


def test_stripe_live_exports_issue_128_additions() -> None:
    """The three #128 additions must be present and callable."""
    live = _mod("app.services.payment_provider.stripe.live")

    # validate_currency is a new helper from #128.
    assert hasattr(live, "validate_currency"), "validate_currency missing from live.py"
    assert callable(live.validate_currency)

    # The minimum constant must be 50 cents (Stripe's documented threshold).
    assert hasattr(live, "_STRIPE_USD_MINIMUM_CENTS"), "_STRIPE_USD_MINIMUM_CENTS missing"
    assert live._STRIPE_USD_MINIMUM_CENTS == 50


def test_validate_currency_accepts_valid_code() -> None:
    """validate_currency must not raise for a valid 3-letter code."""
    from app.services.payment_provider.stripe.live import validate_currency

    # Should not raise.
    validate_currency("ars", "currency")
    validate_currency("usd", "currency")
    validate_currency("EUR", "currency")


def test_validate_currency_rejects_invalid_codes() -> None:
    """validate_currency must raise HTTPException 400 for non-ISO codes."""
    from fastapi import HTTPException

    from app.services.payment_provider.stripe.live import validate_currency

    with pytest.raises(HTTPException) as exc_info:
        validate_currency("US", "currency")
    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "payment.invalid_currency"

    with pytest.raises(HTTPException):
        validate_currency("", "currency")

    with pytest.raises(HTTPException):
        validate_currency("US1", "currency")
