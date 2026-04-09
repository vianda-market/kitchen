"""
Unit tests for ads error handler (app/services/ads/error_handler.py).

Verifies error categorization for both Google and Meta platforms,
and retry logic.
"""
import pytest

from app.services.ads.error_handler import (
    AdsErrorCategory,
    categorize_google_error,
    categorize_meta_error,
    should_retry,
)


class TestCategorizeGoogleError:
    def test_rate_limited(self):
        assert categorize_google_error("RESOURCE_EXHAUSTED") == AdsErrorCategory.RATE_LIMITED

    def test_auth_expired(self):
        assert categorize_google_error("AUTHENTICATION_ERROR") == AdsErrorCategory.AUTH_EXPIRED

    def test_authorization_error(self):
        assert categorize_google_error("AUTHORIZATION_ERROR") == AdsErrorCategory.AUTH_EXPIRED

    def test_invalid_data(self):
        assert categorize_google_error("INVALID_ARGUMENT") == AdsErrorCategory.INVALID_DATA

    def test_required_field_missing(self):
        assert categorize_google_error("REQUIRED_FIELD_MISSING") == AdsErrorCategory.INVALID_DATA

    def test_transient(self):
        assert categorize_google_error("INTERNAL_ERROR") == AdsErrorCategory.TRANSIENT

    def test_unknown_error(self):
        assert categorize_google_error("SOMETHING_WEIRD") == AdsErrorCategory.PERMANENT


class TestCategorizeMetaError:
    def test_rate_limit_code_17(self):
        assert categorize_meta_error(17) == AdsErrorCategory.RATE_LIMITED

    def test_rate_limit_code_4(self):
        assert categorize_meta_error(4) == AdsErrorCategory.RATE_LIMITED

    def test_auth_expired_code_190(self):
        assert categorize_meta_error(190) == AdsErrorCategory.AUTH_EXPIRED

    def test_permission_error_code_200(self):
        assert categorize_meta_error(200) == AdsErrorCategory.AUTH_EXPIRED

    def test_invalid_param_code_100(self):
        assert categorize_meta_error(100) == AdsErrorCategory.INVALID_DATA

    def test_transient_code_1(self):
        assert categorize_meta_error(1) == AdsErrorCategory.TRANSIENT

    def test_transient_code_2(self):
        assert categorize_meta_error(2) == AdsErrorCategory.TRANSIENT

    def test_transient_code_32(self):
        assert categorize_meta_error(32) == AdsErrorCategory.TRANSIENT

    def test_unknown_code(self):
        assert categorize_meta_error(99999) == AdsErrorCategory.PERMANENT


class TestShouldRetry:
    def test_rate_limited_retries(self):
        assert should_retry(AdsErrorCategory.RATE_LIMITED)

    def test_transient_retries(self):
        assert should_retry(AdsErrorCategory.TRANSIENT)

    def test_partial_failure_retries(self):
        assert should_retry(AdsErrorCategory.PARTIAL_FAILURE)

    def test_auth_expired_no_retry(self):
        assert not should_retry(AdsErrorCategory.AUTH_EXPIRED)

    def test_invalid_data_no_retry(self):
        assert not should_retry(AdsErrorCategory.INVALID_DATA)

    def test_permanent_no_retry(self):
        assert not should_retry(AdsErrorCategory.PERMANENT)
