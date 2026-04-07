"""Tests for rate_limit_middleware helper functions."""

import time
import pytest
from collections import deque
from unittest.mock import Mock, patch

from app.auth.middleware.rate_limit_middleware import (
    _extract_bearer_token,
    _check_rate_limit,
    _evict_stale_buckets,
    _buckets,
)


# ── _extract_bearer_token ────────────────────────────────────────────────────

class TestExtractBearerToken:
    def test_valid_bearer(self):
        request = Mock()
        request.headers = {"Authorization": "Bearer abc123"}
        assert _extract_bearer_token(request) == "abc123"

    def test_missing_header(self):
        request = Mock()
        request.headers = {}
        assert _extract_bearer_token(request) is None

    def test_empty_bearer(self):
        request = Mock()
        request.headers = {"Authorization": "Bearer "}
        assert _extract_bearer_token(request) is None

    def test_wrong_scheme(self):
        request = Mock()
        request.headers = {"Authorization": "Basic abc123"}
        assert _extract_bearer_token(request) is None


# ── _check_rate_limit ────────────────────────────────────────────────────────

class TestCheckRateLimit:
    def setup_method(self):
        _buckets.clear()

    def test_allows_under_limit(self):
        now = time.monotonic()
        allowed, remaining = _check_rate_limit("user1", 5, 60, now)
        assert allowed is True
        assert remaining == 4

    def test_blocks_at_limit(self):
        now = time.monotonic()
        for _ in range(5):
            _check_rate_limit("user2", 5, 60, now)
        allowed, remaining = _check_rate_limit("user2", 5, 60, now)
        assert allowed is False
        assert remaining == 0

    def test_prunes_expired_entries(self):
        now = time.monotonic()
        # Fill bucket in the past
        _buckets["user3"] = deque([now - 120, now - 100, now - 80])
        # All are older than 60s window, should be pruned
        allowed, remaining = _check_rate_limit("user3", 3, 60, now)
        assert allowed is True
        assert remaining == 2

    def test_creates_bucket_for_new_key(self):
        now = time.monotonic()
        assert "new_user" not in _buckets
        _check_rate_limit("new_user", 10, 60, now)
        assert "new_user" in _buckets

    def test_does_not_append_when_blocked(self):
        now = time.monotonic()
        _buckets["user4"] = deque([now] * 3)
        _check_rate_limit("user4", 3, 60, now)
        assert len(_buckets["user4"]) == 3  # no new entry added


# ── _evict_stale_buckets ────────────────────────────────────────────────────

class TestEvictStaleBuckets:
    def setup_method(self):
        _buckets.clear()

    @patch("app.auth.middleware.rate_limit_middleware.settings")
    def test_no_eviction_under_threshold(self, mock_settings):
        mock_settings.RATE_LIMIT_MAX_TRACKED_USERS = 100
        now = time.monotonic()
        _buckets["user1"] = deque([now - 200])
        _evict_stale_buckets(now)
        assert "user1" in _buckets  # not evicted, under threshold

    @patch("app.auth.middleware.rate_limit_middleware.settings")
    def test_evicts_stale_over_threshold(self, mock_settings):
        mock_settings.RATE_LIMIT_MAX_TRACKED_USERS = 2
        mock_settings.RATE_LIMIT_EVICTION_AGE_SECONDS = 60
        now = time.monotonic()
        _buckets["stale"] = deque([now - 120])
        _buckets["fresh"] = deque([now - 10])
        _buckets["also_stale"] = deque([now - 200])
        _evict_stale_buckets(now)
        assert "fresh" in _buckets
        assert "stale" not in _buckets
        assert "also_stale" not in _buckets

    @patch("app.auth.middleware.rate_limit_middleware.settings")
    def test_evicts_empty_buckets(self, mock_settings):
        mock_settings.RATE_LIMIT_MAX_TRACKED_USERS = 1
        mock_settings.RATE_LIMIT_EVICTION_AGE_SECONDS = 60
        now = time.monotonic()
        _buckets["empty"] = deque()
        _buckets["fresh"] = deque([now])
        _evict_stale_buckets(now)
        assert "empty" not in _buckets
        assert "fresh" in _buckets
