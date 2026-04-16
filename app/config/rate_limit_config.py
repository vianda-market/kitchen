"""
Rate-limit tier definitions and per-endpoint override rules for authenticated users.

Tiers are resolved from JWT claims (role_type + onboarding_status).
slowapi handles anonymous/IP-based limits separately (app/utils/rate_limit.py).
"""

from dataclasses import dataclass

# ── Tier constants ───────────────────────────────────────────────────────────
TIER_FREE = "free"
TIER_ONBOARDED = "onboarded"
TIER_B2B = "b2b"
TIER_INTERNAL = "internal"

# ── Global limits (requests per window) ──────────────────────────────────────
TIER_GLOBAL_LIMITS: dict[str, int] = {
    TIER_FREE: 120,
    TIER_ONBOARDED: 600,
    TIER_B2B: 600,
    TIER_INTERNAL: 0,  # 0 = exempt
}

WINDOW_SECONDS: int = 60

# ── Per-endpoint overrides (Free tier GET only) ─────────────────────────────
# Keyed by path prefix (after stripping /api/v1). Longest prefix matched first.
FREE_TIER_ENDPOINT_OVERRIDES: dict[str, int] = {
    "/addresses/suggest": 30,
    "/restaurants/explorer": 20,
    "/plate-selections/": 30,
    "/cuisines/": 60,
}


@dataclass(frozen=True)
class RateLimitRule:
    """Resolved rate-limit rule for a single request."""

    tier: str
    max_requests: int
    window_seconds: int
    exempt: bool
    matched_prefix: str | None = None


def classify_tier(role_type: str, onboarding_status: str | None) -> str:
    """Derive rate-limit tier from JWT claims."""
    if role_type == "internal":
        return TIER_INTERNAL
    if role_type in ("supplier", "employer"):
        return TIER_B2B
    if onboarding_status == "complete":
        return TIER_ONBOARDED
    return TIER_FREE


def _strip_version_prefix(path: str) -> str:
    """Remove /api/v1 (or /api/v2) prefix for endpoint matching."""
    for prefix in ("/api/v1", "/api/v2"):
        if path.startswith(prefix):
            return path[len(prefix) :]
    return path


def resolve_rule(tier: str, path: str, method: str) -> RateLimitRule:
    """Return the applicable RateLimitRule for a given tier + request."""
    if tier == TIER_INTERNAL:
        return RateLimitRule(
            tier=tier,
            max_requests=0,
            window_seconds=WINDOW_SECONDS,
            exempt=True,
        )

    base_limit = TIER_GLOBAL_LIMITS[tier]

    # Endpoint overrides apply to Free tier GET requests only
    if tier == TIER_FREE and method == "GET":
        normalized = _strip_version_prefix(path)
        matched_prefix = None
        matched_len = 0
        for override_prefix, _limit in FREE_TIER_ENDPOINT_OVERRIDES.items():
            if normalized.startswith(override_prefix) and len(override_prefix) > matched_len:
                matched_prefix = override_prefix
                matched_len = len(override_prefix)
        if matched_prefix is not None:
            return RateLimitRule(
                tier=tier,
                max_requests=FREE_TIER_ENDPOINT_OVERRIDES[matched_prefix],
                window_seconds=WINDOW_SECONDS,
                exempt=False,
                matched_prefix=matched_prefix,
            )

    return RateLimitRule(
        tier=tier,
        max_requests=base_limit,
        window_seconds=WINDOW_SECONDS,
        exempt=False,
    )
