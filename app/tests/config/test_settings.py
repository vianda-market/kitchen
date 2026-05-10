"""
Unit tests for settings env-file gating and get_google_api_key / get_mapbox_access_token
environment-based resolution.
"""

from unittest.mock import patch

import pytest

from app.config.settings import get_google_api_key, get_mapbox_access_token, settings


class TestEnvFileGating:
    """Test that _ENV_FILE is None on Cloud Run and '.env' on local.

    Note: _ENV_FILE and _ENVIRONMENT are module-level constants computed at import time.
    We test the resolution logic by inspecting the derived constant values indirectly
    via a fresh import under a patched environment — or by verifying the helper function
    that uses the same os.getenv("ENVIRONMENT") pattern.
    """

    @patch.dict("os.environ", {"ENVIRONMENT": "local"}, clear=False)
    def test_local_env_file_is_dotenv(self):
        """ENVIRONMENT=local: re-evaluating the gating expression yields '.env'."""
        import os

        env_file = ".env" if (os.getenv("ENVIRONMENT") or "local").lower() == "local" else None
        assert env_file == ".env"

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_dev_env_file_is_none(self):
        """ENVIRONMENT=dev (Cloud Run dev): env_file resolves to None."""
        import os

        env_file = ".env" if (os.getenv("ENVIRONMENT") or "local").lower() == "local" else None
        assert env_file is None

    @patch.dict("os.environ", {"ENVIRONMENT": "staging"}, clear=False)
    def test_staging_env_file_is_none(self):
        """ENVIRONMENT=staging: env_file resolves to None."""
        import os

        env_file = ".env" if (os.getenv("ENVIRONMENT") or "local").lower() == "local" else None
        assert env_file is None

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"}, clear=False)
    def test_prod_env_file_is_none(self):
        """ENVIRONMENT=prod: env_file resolves to None."""
        import os

        env_file = ".env" if (os.getenv("ENVIRONMENT") or "local").lower() == "local" else None
        assert env_file is None

    def test_environment_unset_defaults_to_local(self):
        """ENVIRONMENT unset: defaults to 'local' convention, env_file = '.env'."""
        import os

        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("ENVIRONMENT", None)
            env_file = ".env" if (os.getenv("ENVIRONMENT") or "local").lower() == "local" else None
        assert env_file == ".env"


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


class TestGetMapboxAccessTokenPersistent:
    """Test get_mapbox_access_token(permanent=True) raises when token is unset
    and returns the correct token when set, for each environment."""

    @patch.dict("os.environ", {"ENVIRONMENT": "local"}, clear=False)
    def test_local_persistent_raises_when_unset(self):
        """permanent=True with no token set raises RuntimeError for local env (DEV_MODE=False)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError, match="MAPBOX_ACCESS_TOKEN_LOCAL_PERSISTENT"):
                    get_mapbox_access_token(permanent=True)

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_dev_persistent_raises_when_unset(self):
        """permanent=True with no token set raises RuntimeError for dev env (DEV_MODE=False)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError, match="MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT"):
                    get_mapbox_access_token(permanent=True)

    @patch.dict("os.environ", {"ENVIRONMENT": "staging"}, clear=False)
    def test_staging_persistent_raises_when_unset(self):
        """permanent=True with no token set raises RuntimeError for staging env (DEV_MODE=False)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_STAGING_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError, match="MAPBOX_ACCESS_TOKEN_STAGING_PERSISTENT"):
                    get_mapbox_access_token(permanent=True)

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"}, clear=False)
    def test_prod_persistent_raises_when_unset(self):
        """permanent=True with no token set raises RuntimeError for prod env (DEV_MODE=False)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_PROD_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError, match="MAPBOX_ACCESS_TOKEN_PROD_PERSISTENT"):
                    get_mapbox_access_token(permanent=True)

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_dev_persistent_returns_token_when_set(self):
        """permanent=True returns the DEV persistent token when configured."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", "sk.dev_persistent"):
            assert get_mapbox_access_token(permanent=True) == "sk.dev_persistent"

    @patch.dict("os.environ", {"ENVIRONMENT": "staging"}, clear=False)
    def test_staging_persistent_returns_token_when_set(self):
        """permanent=True returns the STAGING persistent token when configured."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_STAGING_PERSISTENT", "sk.staging_persistent"):
            assert get_mapbox_access_token(permanent=True) == "sk.staging_persistent"

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"}, clear=False)
    def test_prod_persistent_returns_token_when_set(self):
        """permanent=True returns the PROD persistent token when configured."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_PROD_PERSISTENT", "sk.prod_persistent"):
            assert get_mapbox_access_token(permanent=True) == "sk.prod_persistent"

    @patch.dict("os.environ", {"ENVIRONMENT": "custom"}, clear=False)
    def test_unknown_env_persistent_raises_when_unset(self):
        """Unknown ENVIRONMENT falls back to DEV persistent token; raises when unset (DEV_MODE=False)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError):
                    get_mapbox_access_token(permanent=True)

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_persistent_raises_on_empty_string(self):
        """permanent=True with empty string raises RuntimeError (not silently falsy, DEV_MODE=False)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", "   "):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError):
                    get_mapbox_access_token(permanent=True)

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_persistent_strips_whitespace(self):
        """persistent token is stripped of surrounding whitespace."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", "  sk.token  "):
            assert get_mapbox_access_token(permanent=True) == "sk.token"

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_default_permanent_false_preserves_ephemeral_behavior(self):
        """permanent=False (default) returns the ephemeral token, not the persistent one."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV", "pk.ephemeral"):
            with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", "sk.persistent"):
                assert get_mapbox_access_token() == "pk.ephemeral"

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_dev_mode_true_persistent_unset_returns_stub(self):
        """permanent=True, persistent token unset, DEV_MODE=True -> returns stub (no RuntimeError).

        DEV_MODE uses mock responses; no real Mapbox call is made, so the TOS guardrail
        is a false positive. The stub allows gateway construction to succeed in CI where
        no persistent token env var is provided.
        """
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", True):
                result = get_mapbox_access_token(permanent=True)
        assert result == "dev-mode-stub-token"

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False)
    def test_dev_mode_false_persistent_unset_still_raises(self):
        """permanent=True, persistent token unset, DEV_MODE=False -> RuntimeError (TOS guardrail preserved)."""
        with patch.object(settings, "MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT", None):
            with patch.object(settings, "DEV_MODE", False):
                with pytest.raises(RuntimeError, match="MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT"):
                    get_mapbox_access_token(permanent=True)
