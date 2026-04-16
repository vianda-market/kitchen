"""
Unit tests for get_google_api_key environment-based resolution.
"""

from unittest.mock import patch

from app.config.settings import get_google_api_key, settings


class TestGetGoogleApiKey:
    """Test get_google_api_key returns correct key per ENVIRONMENT."""

    @patch.dict("os.environ", {"ENVIRONMENT": "local"}, clear=False)
    def test_local_uses_dev_key(self):
        """ENVIRONMENT=local should use GOOGLE_API_KEY_DEV."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", "dev_key"):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", "staging_key"):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", "prod_key"):
                    assert get_google_api_key() == "dev_key"

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_dev_uses_dev_key(self):
        """ENVIRONMENT=dev should use GOOGLE_API_KEY_DEV."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", "dev_key"):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", ""):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", ""):
                    assert get_google_api_key() == "dev_key"

    @patch.dict("os.environ", {"ENVIRONMENT": "staging"}, clear=False)
    def test_staging_uses_staging_key(self):
        """ENVIRONMENT=staging should use GOOGLE_API_KEY_STAGING."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", ""):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", "staging_key"):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", ""):
                    assert get_google_api_key() == "staging_key"

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"}, clear=False)
    def test_prod_uses_prod_key(self):
        """ENVIRONMENT=prod should use GOOGLE_API_KEY_PROD."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", ""):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", ""):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", "prod_key"):
                    assert get_google_api_key() == "prod_key"

    @patch("app.config.settings.os.getenv", return_value=None)
    def test_env_unset_defaults_to_local_uses_dev_key(self, mock_getenv):
        """ENVIRONMENT unset should default to local and use GOOGLE_API_KEY_DEV."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", "dev_key"):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", ""):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", ""):
                    assert get_google_api_key() == "dev_key"

    @patch.dict("os.environ", {"ENVIRONMENT": "custom"}, clear=False)
    def test_unknown_env_fallback_to_dev_key(self):
        """Unknown ENVIRONMENT should fallback to GOOGLE_API_KEY_DEV."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", "fallback_key"):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", ""):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", ""):
                    assert get_google_api_key() == "fallback_key"

    @patch.dict("os.environ", {"ENVIRONMENT": "local"}, clear=False)
    def test_strips_whitespace(self):
        """Key should be stripped of leading/trailing whitespace."""
        with patch.object(settings, "GOOGLE_API_KEY_DEV", "  key_with_spaces  "):
            with patch.object(settings, "GOOGLE_API_KEY_STAGING", ""):
                with patch.object(settings, "GOOGLE_API_KEY_PROD", ""):
                    assert get_google_api_key() == "key_with_spaces"
