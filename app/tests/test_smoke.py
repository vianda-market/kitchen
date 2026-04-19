"""Smoke tests — cheapest sanity check that the FastAPI entry point boots cleanly.

Catches the failure modes a `python -c "from application import app"` import check
misses: silent route deletion, registration regressions, drift in the public
contract surface.

Pattern lifted from infra-kitchen-gcp/tests/test_smoke.py.
"""

import pytest
from fastapi.routing import APIRoute

from application import app

pytestmark = pytest.mark.smoke

# Baseline route count as of 2026-04-19. Allow a ±10% drift band before failing —
# the goal is to catch a router that silently failed to register (large drop) or
# an accidental duplicate registration (large jump), not to be a coverage gate.
ROUTE_COUNT_BASELINE = 406
ROUTE_COUNT_TOLERANCE = 0.10

# Routes that, if missing, indicate a broken deployment regardless of any other change.
# Keep this list very short — it is meant to prove "the major user surfaces wired up,"
# not enumerate the whole API. If a route here moves, update intentionally.
CRITICAL_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/health"),
    ("POST", "/api/v1/auth/token"),
    ("GET", "/api/v1/users/me"),
    ("GET", "/api/v1/leads/markets"),
    ("GET", "/api/v1/leads/plans"),
    ("POST", "/api/v1/webhooks/stripe"),
)


def _api_routes() -> list[APIRoute]:
    return [r for r in app.routes if isinstance(r, APIRoute)]


def test_app_boots() -> None:
    """Importing the FastAPI app must succeed and produce a non-empty router."""
    assert app is not None
    assert len(_api_routes()) > 0


def test_route_count_within_baseline() -> None:
    """Total registered API routes should not silently drop or balloon."""
    actual = len(_api_routes())
    low = int(ROUTE_COUNT_BASELINE * (1 - ROUTE_COUNT_TOLERANCE))
    high = int(ROUTE_COUNT_BASELINE * (1 + ROUTE_COUNT_TOLERANCE))
    assert low <= actual <= high, (
        f"Route count {actual} outside ±{int(ROUTE_COUNT_TOLERANCE * 100)}% of "
        f"baseline {ROUTE_COUNT_BASELINE} (allowed: {low}–{high}). "
        "If this is intentional (large feature added/removed), update ROUTE_COUNT_BASELINE."
    )


def test_critical_routes_registered() -> None:
    """Every CRITICAL_ROUTES entry must be present — proves the major surfaces are wired."""
    registered = {(method, r.path) for r in _api_routes() for method in r.methods}
    missing = [(m, p) for (m, p) in CRITICAL_ROUTES if (m, p) not in registered]
    assert not missing, f"Critical routes not registered: {missing}"
