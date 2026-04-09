"""
Unit tests for PII hasher (app/services/ads/pii_hasher.py).

Verifies SHA256 hashing normalization per Google/Meta requirements:
- Lowercase before hashing
- Strip whitespace before hashing
- Consistent output for equivalent inputs
"""
import hashlib

import pytest

from app.services.ads.pii_hasher import build_hashed_user_data, normalize_and_hash


class TestNormalizeAndHash:
    def test_basic_hash(self):
        result = normalize_and_hash("test@example.com")
        expected = hashlib.sha256(b"test@example.com").hexdigest()
        assert result == expected

    def test_lowercase_normalization(self):
        assert normalize_and_hash("Test@Example.COM") == normalize_and_hash("test@example.com")

    def test_whitespace_stripping(self):
        assert normalize_and_hash("  test@example.com  ") == normalize_and_hash("test@example.com")

    def test_combined_normalization(self):
        assert normalize_and_hash("  TEST@Example.COM  ") == normalize_and_hash("test@example.com")

    def test_phone_e164(self):
        result = normalize_and_hash("+5491155550001")
        expected = hashlib.sha256(b"+5491155550001").hexdigest()
        assert result == expected

    def test_deterministic(self):
        r1 = normalize_and_hash("user@vianda.market")
        r2 = normalize_and_hash("user@vianda.market")
        assert r1 == r2

    def test_different_inputs_different_hashes(self):
        assert normalize_and_hash("a@b.com") != normalize_and_hash("c@d.com")


class TestBuildHashedUserData:
    def test_email_only(self):
        data = build_hashed_user_data("test@example.com")
        assert "hashed_email" in data
        assert "hashed_phone" not in data
        assert "hashed_external_id" not in data

    def test_email_and_phone(self):
        data = build_hashed_user_data("test@example.com", phone="+1234567890")
        assert "hashed_email" in data
        assert "hashed_phone" in data
        assert "hashed_external_id" not in data

    def test_all_fields(self):
        data = build_hashed_user_data("test@example.com", phone="+1234567890", user_id="user-uuid-123")
        assert "hashed_email" in data
        assert "hashed_phone" in data
        assert "hashed_external_id" in data

    def test_hashes_are_hex_strings(self):
        data = build_hashed_user_data("test@example.com", phone="+1", user_id="uid")
        for key, val in data.items():
            assert len(val) == 64, f"{key} should be 64-char hex"
            assert all(c in "0123456789abcdef" for c in val), f"{key} should be hex"
