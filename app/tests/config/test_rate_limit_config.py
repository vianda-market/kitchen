"""Tests for rate_limit_config: tier classification and rule resolution."""

import pytest
from app.config.rate_limit_config import (
    TIER_FREE,
    TIER_ONBOARDED,
    TIER_B2B,
    TIER_INTERNAL,
    WINDOW_SECONDS,
    classify_tier,
    resolve_rule,
)


# ── classify_tier ────────────────────────────────────────────────────────────

class TestClassifyTier:
    def test_internal(self):
        assert classify_tier("Internal", None) == TIER_INTERNAL

    def test_internal_ignores_onboarding(self):
        assert classify_tier("Internal", "complete") == TIER_INTERNAL

    def test_supplier(self):
        assert classify_tier("Supplier", "in_progress") == TIER_B2B

    def test_employer(self):
        assert classify_tier("Employer", "complete") == TIER_B2B

    def test_customer_free_no_status(self):
        assert classify_tier("Customer", None) == TIER_FREE

    def test_customer_free_in_progress(self):
        assert classify_tier("Customer", "in_progress") == TIER_FREE

    def test_customer_free_not_started(self):
        assert classify_tier("Customer", "not_started") == TIER_FREE

    def test_customer_onboarded(self):
        assert classify_tier("Customer", "complete") == TIER_ONBOARDED


# ── resolve_rule ─────────────────────────────────────────────────────────────

class TestResolveRule:
    def test_internal_exempt(self):
        rule = resolve_rule(TIER_INTERNAL, "/api/v1/anything", "GET")
        assert rule.exempt is True
        assert rule.max_requests == 0

    def test_onboarded_global(self):
        rule = resolve_rule(TIER_ONBOARDED, "/api/v1/addresses/suggest", "GET")
        assert rule.max_requests == 600
        assert rule.exempt is False
        assert rule.matched_prefix is None

    def test_b2b_global(self):
        rule = resolve_rule(TIER_B2B, "/api/v1/restaurants/explorer", "GET")
        assert rule.max_requests == 600
        assert rule.matched_prefix is None

    def test_free_global_no_override(self):
        rule = resolve_rule(TIER_FREE, "/api/v1/users/me", "GET")
        assert rule.max_requests == 120
        assert rule.matched_prefix is None

    def test_free_suggest_override(self):
        rule = resolve_rule(TIER_FREE, "/api/v1/addresses/suggest", "GET")
        assert rule.max_requests == 30
        assert rule.matched_prefix == "/addresses/suggest"

    def test_free_explorer_override(self):
        rule = resolve_rule(TIER_FREE, "/api/v1/restaurants/explorer", "GET")
        assert rule.max_requests == 20
        assert rule.matched_prefix == "/restaurants/explorer"

    def test_free_plate_selections_override(self):
        rule = resolve_rule(TIER_FREE, "/api/v1/plate-selections/some-id", "GET")
        assert rule.max_requests == 30
        assert rule.matched_prefix == "/plate-selections/"

    def test_free_cuisines_override(self):
        rule = resolve_rule(TIER_FREE, "/api/v1/cuisines/enriched", "GET")
        assert rule.max_requests == 60
        assert rule.matched_prefix == "/cuisines/"

    def test_free_post_ignores_overrides(self):
        """Endpoint overrides only apply to GET requests."""
        rule = resolve_rule(TIER_FREE, "/api/v1/addresses/suggest", "POST")
        assert rule.max_requests == 120
        assert rule.matched_prefix is None

    def test_free_without_version_prefix(self):
        """Paths without /api/v1 prefix should still match."""
        rule = resolve_rule(TIER_FREE, "/addresses/suggest", "GET")
        assert rule.max_requests == 30

    def test_window_seconds(self):
        rule = resolve_rule(TIER_FREE, "/api/v1/users/me", "GET")
        assert rule.window_seconds == WINDOW_SECONDS
