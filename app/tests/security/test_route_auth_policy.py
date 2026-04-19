"""Every API route must require authentication, except an explicit allowlist.

Pattern lifted from infra-kitchen-gcp/tests/test_policy.py: allowlist over denylist.
A new public route is a security-relevant decision that must be made deliberately —
adding a route here forces a code review on the allowlist edit.
"""

import pytest
from application import app
from fastapi.routing import APIRoute

pytestmark = pytest.mark.policy

# Names of dependency callables that establish an authenticated user.
# Includes oauth2_scheme because /auth/users/me consumes the raw token directly
# and validates it inline rather than via a get_*_user helper.
AUTH_DEPENDENCIES: frozenset[str] = frozenset(
    {
        "get_current_user",
        "get_admin_user",
        "get_super_admin_user",
        "get_employee_user",
        "get_client_user",
        "get_client_or_employee_user",
        "get_client_employee_or_supplier_user",
        "get_employee_or_customer_user",
        "get_employee_or_supplier_user",
        "get_optional_user",
        "oauth2_scheme",
    }
)

# Public routes — explicit allowlist. Format: "METHOD path".
# Each entry should have a known reason (marketing site, webhook signature auth,
# pre-login auth, public health probe, etc.). When adding, comment why.
PUBLIC_ROUTE_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Health / metadata
        "GET /",
        "GET /api",
        "GET /health",
        "GET /api/v1/locales",
        "GET /api/v1/admin/archival/health",  # health probe used by infra; no PII
        # Pre-login auth
        "POST /api/v1/auth/token",
        "POST /api/v1/auth/forgot-password",
        "POST /api/v1/auth/forgot-username",
        "POST /api/v1/auth/reset-password",
        "GET /api/v1/auth/users/me",  # consumes oauth2_scheme directly; auth enforced inline
        # Customer signup (account does not exist yet)
        "POST /api/v1/customers/signup/request",
        "POST /api/v1/customers/signup/verify",
        "GET /api/v1/customers/signup/dev-pending-token",  # dev-only convenience; gated by ENVIRONMENT
        # Marketing site (vianda-home) — gated by recaptcha at router level, not user auth
        "GET /api/v1/leads/cities",
        "GET /api/v1/leads/city-metrics",
        "GET /api/v1/leads/countries",
        "GET /api/v1/leads/cuisines",
        "GET /api/v1/leads/email-registered",
        "GET /api/v1/leads/employee-count-ranges",
        "GET /api/v1/leads/featured-restaurant",
        "GET /api/v1/leads/markets",
        "GET /api/v1/leads/plans",
        "GET /api/v1/leads/restaurants",
        "GET /api/v1/leads/supplier-countries",
        "GET /api/v1/leads/zipcode-metrics",
        "POST /api/v1/leads/interest",
        "POST /api/v1/leads/restaurant-interest",
        # Referral codes — assigned/claimed pre-account; identity by code, not user
        "POST /api/v1/referrals/assign-code",
        "GET /api/v1/referrals/assigned-code",
        # Webhooks — authenticated by provider signature, not by JWT
        "POST /api/v1/webhooks/stripe",
        "POST /api/v1/webhooks/stripe-connect",
        "GET /api/v1/mercado-pago/mercadopago/callback",
    }
)


def _route_has_auth(route: APIRoute) -> bool:
    """Return True if any dependency in the route's tree is an auth dependency."""

    def walk(deps) -> bool:
        for d in deps:
            name = getattr(d.call, "__name__", None) or type(d.call).__name__
            if name in AUTH_DEPENDENCIES:
                return True
            if walk(d.dependencies):
                return True
        return False

    return walk(route.dependant.dependencies)


def _enumerate_public_routes() -> set[str]:
    public: set[str] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if _route_has_auth(route):
            continue
        for method in route.methods:
            if method == "HEAD":
                continue
            public.add(f"{method} {route.path}")
    return public


def test_no_unexpected_public_routes() -> None:
    """Every public route must be on the allowlist; new public surfaces are a deliberate decision."""
    public = _enumerate_public_routes()
    unexpected = sorted(public - PUBLIC_ROUTE_ALLOWLIST)
    assert not unexpected, (
        "New routes are publicly accessible without auth. Either add an auth dependency "
        "or, if intentionally public, add to PUBLIC_ROUTE_ALLOWLIST with a comment "
        f"explaining why. Unexpected public routes: {unexpected}"
    )


def test_allowlist_has_no_dead_entries() -> None:
    """Allowlist entries must correspond to real public routes — keeps the list honest as routes evolve."""
    public = _enumerate_public_routes()
    dead = sorted(PUBLIC_ROUTE_ALLOWLIST - public)
    assert not dead, (
        "Allowlist contains entries that are no longer public (route removed or now requires auth). "
        f"Remove from PUBLIC_ROUTE_ALLOWLIST: {dead}"
    )
