"""
Unit tests for AddressAutocompleteService (suggest — autocomplete only).

Tests inject a mock provider via the constructor to remain provider-agnostic.
Provider-specific parsing is tested in test_address_autocomplete_providers.py.
"""

from typing import Any
from unittest.mock import Mock

from app.services.address_autocomplete_service import AddressAutocompleteService


def _make_mock_provider(suggestions: list[dict[str, Any]]) -> Mock:
    """Return a mock AutocompleteProvider whose suggest() returns the given list."""
    provider = Mock()
    provider.suggest.return_value = suggestions
    return provider


class TestAddressAutocompleteServiceSuggest:
    def test_suggest_returns_empty_for_empty_input(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        assert svc.suggest(q="") == []
        assert svc.suggest(q="   ") == []
        provider.suggest.assert_not_called()

    def test_suggest_returns_suggestions_from_provider(self):
        canonical = [
            {"place_id": "dXJuOm1ieHBsYzo0NTk2Mjg", "display_text": "Avenida Santa Fe 2567", "country_code": "AR"}
        ]
        provider = _make_mock_provider(canonical)
        svc = AddressAutocompleteService(provider=provider)
        result = svc.suggest(q="Av. Santa Fe", limit=5)
        assert len(result) == 1
        assert result[0]["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert result[0]["display_text"] == "Avenida Santa Fe 2567"
        assert result[0]["country_code"] == "AR"
        provider.suggest.assert_called_once()

    def test_suggest_respects_limit(self):
        many = [{"place_id": f"id_{i}", "display_text": f"Address {i}"} for i in range(5)]
        provider = _make_mock_provider(many)
        svc = AddressAutocompleteService(provider=provider)
        # The service passes limit to the provider; provider is responsible for truncation.
        # Here provider returns all 5 — verify service passes limit correctly.
        call_kw = None

        def capture_suggest(**kwargs):
            nonlocal call_kw
            call_kw = kwargs
            return many[: kwargs.get("limit", 5)]

        provider.suggest.side_effect = capture_suggest
        svc.suggest(q="Main", limit=2)
        assert call_kw is not None
        assert call_kw["limit"] == 2

    def test_suggest_passes_country_alpha2(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        svc.suggest(q="test", country="AR")
        provider.suggest.assert_called_once()
        call_kw = provider.suggest.call_args[1]
        assert call_kw["country"] == "AR"

    def test_suggest_resolves_alpha3_to_alpha2(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        svc.suggest(q="test", country="ARG")
        call_kw = provider.suggest.call_args[1]
        assert call_kw["country"] == "AR"

    def test_suggest_resolves_country_name(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        svc.suggest(q="test", country="Argentina")
        call_kw = provider.suggest.call_args[1]
        assert call_kw["country"] == "AR"

    def test_suggest_passes_session_token(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        svc.suggest(q="test", session_token="my-token-123")
        call_kw = provider.suggest.call_args[1]
        assert call_kw["session_token"] == "my-token-123"

    def test_suggest_generates_session_token_when_not_provided(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        svc.suggest(q="test")
        call_kw = provider.suggest.call_args[1]
        assert call_kw["session_token"] is not None
        assert len(call_kw["session_token"]) == 36  # UUID format

    def test_suggest_returns_empty_on_provider_exception(self):
        provider = Mock()
        provider.suggest.side_effect = RuntimeError("network error")
        svc = AddressAutocompleteService(provider=provider)
        result = svc.suggest(q="test")
        assert result == []

    def test_suggest_prefixes_city_province_when_all_provided(self):
        provider = _make_mock_provider([])
        svc = AddressAutocompleteService(provider=provider)
        svc.suggest(q="Av Santa Fe", country="AR", province="Buenos Aires", city="Buenos Aires")
        call_kw = provider.suggest.call_args[1]
        assert "Buenos Aires" in call_kw["query"]
        assert "Av Santa Fe" in call_kw["query"]
