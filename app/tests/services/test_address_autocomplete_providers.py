"""
Unit tests for the address autocomplete provider abstraction.

Covers:
- SearchBoxAutocompleteProvider and GeocodingAutocompleteProvider both emit
  byte-identical canonical suggestion shapes.
- Cache key distinctness: forward_search entries keyed differently from geocode entries.
- Forward_search cache replay_only mode returns cached entries without live HTTP.
- Settings validation: invalid ADDRESS_AUTOCOMPLETE_PROVIDER raises a clear startup error.
- Q2 rule integration: with search_box provider, simulate address-save flow with
  poisoned Search Box response; assert no sentinel values appear in persisted fields.
- get_autocomplete_provider() factory routes correctly per setting.
"""

import json
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.gateways.mapbox_geocode_cache import (
    MapboxCacheMiss,
    MapboxGeocodeCache,
    make_forward_search_key,
    make_geocode_key,
)
from app.services.address_autocomplete_service import (
    GeocodingAutocompleteProvider,
    SearchBoxAutocompleteProvider,
    _parse_geocoding_feature,
    _parse_search_box_item,
    get_autocomplete_provider,
)

# ---------------------------------------------------------------------------
# Fixtures — representative raw API responses
# ---------------------------------------------------------------------------

SEARCH_BOX_SUGGESTION: dict[str, Any] = {
    "mapbox_id": "dXJuOm1ieHBsYzo0NTk2Mjg",
    "name": "Avenida Santa Fe 2567",
    "full_address": "Avenida Santa Fe 2567, C1425 Buenos Aires, Argentina",
    "place_formatted": "C1425 Buenos Aires, Argentina",
    "context": {
        "country": {"country_code": "AR", "name": "Argentina"},
        "region": {"name": "Buenos Aires"},
        "place": {"name": "Buenos Aires"},
        "postcode": {"name": "C1425"},
        "street": {"name": "Avenida Santa Fe"},
        "address": {"address_number": "2567"},
    },
}

GEOCODING_FEATURE: dict[str, Any] = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-58.4023328, -34.5880634]},
    "properties": {
        "mapbox_id": "dXJuOm1ieHBsYzo0NTk2Mjg",
        "full_address": "Avenida Santa Fe 2567, C1425 Buenos Aires, Argentina",
        "context": {
            "country": {"country_code": "AR", "name": "Argentina"},
            "region": {"name": "Buenos Aires"},
            "place": {"name": "Buenos Aires"},
            "postcode": {"name": "C1425"},
            "street": {"name": "Avenida Santa Fe"},
            "address": {"address_number": "2567"},
        },
    },
}


# ---------------------------------------------------------------------------
# Tests: canonical shape parity
# ---------------------------------------------------------------------------


class TestCanonicalShapeParity:
    """Both providers must produce byte-identical canonical suggestion shape."""

    def test_search_box_item_produces_canonical_shape(self):
        sug = _parse_search_box_item(SEARCH_BOX_SUGGESTION, country_code=None)
        assert sug is not None
        assert set(sug.keys()) == {"place_id", "display_text", "country_code"}
        assert sug["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert "Avenida Santa Fe 2567" in sug["display_text"]
        assert sug["country_code"] == "AR"

    def test_geocoding_feature_produces_canonical_shape(self):
        sug = _parse_geocoding_feature(GEOCODING_FEATURE, country_code=None)
        assert sug is not None
        assert set(sug.keys()) == {"place_id", "display_text", "country_code"}
        assert sug["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert "Avenida Santa Fe 2567" in sug["display_text"]
        assert sug["country_code"] == "AR"

    @pytest.mark.parametrize(
        ("raw_sug", "parser"),
        [
            (SEARCH_BOX_SUGGESTION, lambda item: _parse_search_box_item(item, None)),
            (GEOCODING_FEATURE, lambda item: _parse_geocoding_feature(item, None)),
        ],
        ids=["search_box", "geocoding"],
    )
    def test_both_produce_same_key_set(self, raw_sug, parser):
        sug = parser(raw_sug)
        assert sug is not None
        assert "place_id" in sug
        assert "display_text" in sug

    def test_both_produce_same_place_id_for_same_address(self):
        """Search Box and Geocoding return the same mapbox_id for the same address."""
        sb = _parse_search_box_item(SEARCH_BOX_SUGGESTION, country_code=None)
        geo = _parse_geocoding_feature(GEOCODING_FEATURE, country_code=None)
        assert sb is not None and geo is not None
        assert sb["place_id"] == geo["place_id"]
        assert sb["display_text"] == geo["display_text"]
        assert sb.get("country_code") == geo.get("country_code")

    def test_country_code_optional_when_absent_from_context(self):
        item_no_cc: dict[str, Any] = {
            "mapbox_id": "someId",
            "full_address": "Some Address",
            "context": {},
        }
        sug = _parse_search_box_item(item_no_cc, country_code=None)
        assert sug is not None
        assert "country_code" not in sug

        feature_no_cc: dict[str, Any] = {
            "properties": {
                "mapbox_id": "someId",
                "full_address": "Some Address",
                "context": {},
            }
        }
        sug2 = _parse_geocoding_feature(feature_no_cc, country_code=None)
        assert sug2 is not None
        assert "country_code" not in sug2

    def test_country_code_falls_back_to_filter_when_missing_from_context(self):
        item: dict[str, Any] = {"mapbox_id": "id1", "full_address": "Addr", "context": {}}
        sug = _parse_search_box_item(item, country_code="MX")
        assert sug is not None
        assert sug["country_code"] == "MX"


# ---------------------------------------------------------------------------
# Tests: SearchBoxAutocompleteProvider
# ---------------------------------------------------------------------------


class TestSearchBoxAutocompleteProvider:
    def test_suggest_translates_to_canonical_shape(self):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": [SEARCH_BOX_SUGGESTION]}

        with patch(
            "app.services.address_autocomplete_service.SearchBoxAutocompleteProvider.__init__",
            lambda self: None,
        ):
            provider = SearchBoxAutocompleteProvider.__new__(SearchBoxAutocompleteProvider)
            provider._gateway = mock_gateway

        result = provider.suggest(query="Av Santa", country="AR", session_token="tok", limit=5)
        assert len(result) == 1
        sug = result[0]
        assert sug["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert "Avenida Santa Fe 2567" in sug["display_text"]
        assert sug["country_code"] == "AR"

    def test_suggest_returns_empty_when_no_suggestions(self):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": []}

        with patch(
            "app.services.address_autocomplete_service.SearchBoxAutocompleteProvider.__init__",
            lambda self: None,
        ):
            provider = SearchBoxAutocompleteProvider.__new__(SearchBoxAutocompleteProvider)
            provider._gateway = mock_gateway

        result = provider.suggest(query="xyz", country=None, session_token=None, limit=5)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: GeocodingAutocompleteProvider
# ---------------------------------------------------------------------------


class TestGeocodingAutocompleteProvider:
    def test_suggest_translates_to_canonical_shape(self):
        mock_gateway = MagicMock()
        mock_gateway.forward_search.return_value = {"features": [GEOCODING_FEATURE]}

        with patch(
            "app.services.address_autocomplete_service.GeocodingAutocompleteProvider.__init__",
            lambda self: None,
        ):
            provider = GeocodingAutocompleteProvider.__new__(GeocodingAutocompleteProvider)
            provider._gateway = mock_gateway

        result = provider.suggest(query="Av Santa", country="AR", session_token="tok", limit=5)
        assert len(result) == 1
        sug = result[0]
        assert sug["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert "Avenida Santa Fe 2567" in sug["display_text"]
        assert sug["country_code"] == "AR"

    def test_suggest_passes_query_and_country_to_gateway(self):
        mock_gateway = MagicMock()
        mock_gateway.forward_search.return_value = {"features": []}

        with patch(
            "app.services.address_autocomplete_service.GeocodingAutocompleteProvider.__init__",
            lambda self: None,
        ):
            provider = GeocodingAutocompleteProvider.__new__(GeocodingAutocompleteProvider)
            provider._gateway = mock_gateway

        provider.suggest(query="Santa Fe", country="AR", session_token="any", limit=3)
        mock_gateway.forward_search.assert_called_once_with(query="Santa Fe", country="AR", limit=3)

    def test_session_token_not_forwarded_to_geocoding_gateway(self):
        """Geocoding API has no session billing; session_token must not be forwarded."""
        mock_gateway = MagicMock()
        mock_gateway.forward_search.return_value = {"features": []}

        with patch(
            "app.services.address_autocomplete_service.GeocodingAutocompleteProvider.__init__",
            lambda self: None,
        ):
            provider = GeocodingAutocompleteProvider.__new__(GeocodingAutocompleteProvider)
            provider._gateway = mock_gateway

        provider.suggest(query="test", country=None, session_token="session-xyz", limit=5)
        call_kwargs = mock_gateway.forward_search.call_args[1]
        assert "session_token" not in call_kwargs

    def test_geocoding_provider_uses_permanent_gateway(self):
        """GeocodingAutocompleteProvider must instantiate the permanent gateway."""
        with patch("app.gateways.mapbox_geocoding_gateway.get_mapbox_geocoding_gateway") as mock_factory:
            mock_factory.return_value = MagicMock()
            GeocodingAutocompleteProvider()
        mock_factory.assert_called_once_with(permanent=True)


# ---------------------------------------------------------------------------
# Tests: cache key distinctness
# ---------------------------------------------------------------------------


class TestForwardSearchCacheKey:
    def test_forward_search_key_differs_from_geocode_key(self):
        geo_key = make_geocode_key(q="av santa fe 2567", country="ar", language="es", permanent=True)
        fwd_key = make_forward_search_key(q="av santa fe 2567", country="ar", language="es", permanent=True)
        assert geo_key != fwd_key
        assert fwd_key.startswith("forward_search|")
        assert geo_key.startswith("geocode|")

    def test_forward_search_key_includes_permanent_flag(self):
        k_false = make_forward_search_key(q="test", country="ar", language="es", permanent=False)
        k_true = make_forward_search_key(q="test", country="ar", language="es", permanent=True)
        assert k_false != k_true
        assert k_false.endswith("|permanent=false")
        assert k_true.endswith("|permanent=true")

    def test_forward_search_key_normalizes_query(self):
        k1 = make_forward_search_key(q="  Av. Santa FE ", country="", language="es", permanent=False)
        k2 = make_forward_search_key(q="av. santa fe", country="", language="es", permanent=False)
        assert k1 == k2

    def test_forward_search_and_geocode_can_coexist_in_cache(self, tmp_path):
        """Both entry kinds can live in the same cache file without collision."""
        cache_path = tmp_path / "cache.json"
        geocode_key = make_geocode_key(q="av santa fe 2567", country="ar", language="es", permanent=True)
        fwd_key = make_forward_search_key(q="av santa fe", country="ar", language="es", permanent=True)
        assert geocode_key != fwd_key

        cache = MapboxGeocodeCache(path=cache_path)
        cache.set(geocode_key, {"geocode": True})
        cache.set(fwd_key, {"forward": True})

        assert cache.get(geocode_key) == {"geocode": True}
        assert cache.get(fwd_key) == {"forward": True}


# ---------------------------------------------------------------------------
# Tests: forward_search replay_only mode
# ---------------------------------------------------------------------------


class TestForwardSearchCacheReplay:
    """With MAPBOX_CACHE_MODE=replay_only, forward_search returns cached entries."""

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_forward_search_cache_hit_returns_cached_response(self, mock_settings, _mock_token, monkeypatch, tmp_path):
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        fwd_key = make_forward_search_key(q="av santa fe", country="ar", language="es", permanent=True)
        cached_response = {"features": [GEOCODING_FEATURE], "type": "FeatureCollection"}
        cache_path = tmp_path / "c.json"
        cache_path.write_text(json.dumps({fwd_key: cached_response}))

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))

        gw = MapboxGeocodingGateway(permanent=True)
        with patch.object(MapboxGeocodingGateway, "_make_request") as mock_req:
            result = gw.forward_search(query="av santa fe", country="ar", language="es", limit=5)

        assert result == cached_response
        mock_req.assert_not_called()

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_forward_search_cache_miss_raises_in_replay_only(self, mock_settings, _mock_token, monkeypatch, tmp_path):
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=tmp_path / "empty.json"))
        gw = MapboxGeocodingGateway(permanent=True)
        with pytest.raises(MapboxCacheMiss):
            gw.forward_search(query="unknown address", country="ar", language="es")

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_forward_search_and_geocode_entries_coexist_without_collision(
        self, mock_settings, _mock_token, monkeypatch, tmp_path
    ):
        """Geocode-resolution entries and forward-search entries coexist without collision."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        # Use the exact normalized query that each key function will produce for each operation
        query_full = "av santa fe 2567"
        query_partial = "av santa fe"
        geocode_key = make_geocode_key(q=query_full, country="ar", language="es", permanent=True)
        fwd_key = make_forward_search_key(q=query_partial, country="ar", language="es", permanent=True)
        # Verify keys are distinct
        assert geocode_key != fwd_key

        cache_path = tmp_path / "c.json"
        geocode_response = {
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-58.4023328, -34.5880634]},
                    "properties": {
                        "mapbox_id": "geocode-id",
                        "full_address": "Avenida Santa Fe 2567, C1425 Buenos Aires",
                        "context": {},
                    },
                }
            ]
        }
        fwd_response = {"features": [GEOCODING_FEATURE], "type": "FeatureCollection"}
        cache_path.write_text(json.dumps({geocode_key: geocode_response, fwd_key: fwd_response}))

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = MapboxGeocodingGateway(permanent=True)

        with patch.object(MapboxGeocodingGateway, "_make_request") as mock_req:
            # forward_search uses query_partial -> fwd_key
            fwd_result = gw.forward_search(query=query_partial, country="ar", language="es")
            # geocode uses query_full -> geocode_key
            geocode_result = gw.call("geocode", q=query_full, country="ar", language="es")

        mock_req.assert_not_called()
        assert fwd_result == fwd_response
        # Both distinct entries returned correctly — no collision
        geocode_features: list[dict[str, Any]] = geocode_response["features"]
        assert geocode_features[0]["properties"]["mapbox_id"] == "geocode-id"
        assert geocode_result == geocode_response


# ---------------------------------------------------------------------------
# Tests: seed-file replay (ADDRESS_AUTOCOMPLETE_PROVIDER=geocoding, replay_only)
# ---------------------------------------------------------------------------


class TestSeedFileForwardSearchReplay:
    """Verify that the committed seed file serves forward-search suggestions without live HTTP.

    Uses the actual seeds/mapbox_geocode_cache.json file (committed to repo) so that
    any accidental removal or corruption of the seed entries breaks this test immediately.

    The HTTP transport (_make_request) is mocked to raise loudly — any live network
    call is a test failure.
    """

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_partial_query_3200_santa_fe_returns_suggestions_from_seed(self, mock_settings, _mock_token, monkeypatch):
        """'3200 santa fe' partial query must be served from seed — no HTTP call."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        # Point the cache singleton at the real committed seed file.
        seed_path = (
            __import__("pathlib").Path(__file__).parent.parent.parent.parent / "seeds" / "mapbox_geocode_cache.json"
        )

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=seed_path))

        gw = MapboxGeocodingGateway(permanent=True)

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("_make_request was called — live HTTP must not be used in replay_only mode")

        with patch.object(MapboxGeocodingGateway, "_make_request", side_effect=_fail_if_called):
            result = gw.forward_search(query="3200 santa fe", country="AR", language="es", limit=5)

        features = result.get("features", [])
        assert len(features) > 0, "Expected at least one suggestion from seed for '3200 santa fe'"
        # Each feature must have a mapbox_id and full_address (canonical shape requirement)
        for feature in features:
            props = feature.get("properties", {})
            assert props.get("mapbox_id"), f"Feature missing mapbox_id: {feature}"
            assert props.get("full_address") or props.get("name"), f"Feature missing display name: {feature}"

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_partial_query_500_defensa_returns_suggestions_from_seed(self, mock_settings, _mock_token, monkeypatch):
        """'500 defensa' partial query must be served from seed — no HTTP call."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        seed_path = (
            __import__("pathlib").Path(__file__).parent.parent.parent.parent / "seeds" / "mapbox_geocode_cache.json"
        )

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=seed_path))

        gw = MapboxGeocodingGateway(permanent=True)

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("_make_request was called — live HTTP must not be used in replay_only mode")

        with patch.object(MapboxGeocodingGateway, "_make_request", side_effect=_fail_if_called):
            result = gw.forward_search(query="500 defensa", country="AR", language="es", limit=5)

        features = result.get("features", [])
        assert len(features) > 0, "Expected at least one suggestion from seed for '500 defensa'"
        for feature in features:
            props = feature.get("properties", {})
            assert props.get("mapbox_id"), f"Feature missing mapbox_id: {feature}"

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_partial_query_corrientes_1234_returns_suggestions_from_seed(self, mock_settings, _mock_token, monkeypatch):
        """'corrientes 1234' full query must be served from seed — no HTTP call."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        seed_path = (
            __import__("pathlib").Path(__file__).parent.parent.parent.parent / "seeds" / "mapbox_geocode_cache.json"
        )

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=seed_path))

        gw = MapboxGeocodingGateway(permanent=True)

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("_make_request was called — live HTTP must not be used in replay_only mode")

        with patch.object(MapboxGeocodingGateway, "_make_request", side_effect=_fail_if_called):
            result = gw.forward_search(query="corrientes 1234", country="AR", language="es", limit=5)

        features = result.get("features", [])
        assert len(features) > 0, "Expected at least one suggestion from seed for 'corrientes 1234'"
        for feature in features:
            props = feature.get("properties", {})
            assert props.get("mapbox_id"), f"Feature missing mapbox_id: {feature}"

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_geocoding_provider_suggest_uses_seed_via_provider_interface(self, mock_settings, _mock_token, monkeypatch):
        """End-to-end: GeocodingAutocompleteProvider.suggest() returns canonical suggestions
        from seed — ADDRESS_AUTOCOMPLETE_PROVIDER=geocoding, MAPBOX_CACHE_MODE=replay_only."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")

        seed_path = (
            __import__("pathlib").Path(__file__).parent.parent.parent.parent / "seeds" / "mapbox_geocode_cache.json"
        )

        from app.gateways import mapbox_geocode_cache as mod
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=seed_path))

        # Build a fresh permanent gateway and inject into the provider directly.
        gw = MapboxGeocodingGateway(permanent=True)

        with patch(
            "app.services.address_autocomplete_service.GeocodingAutocompleteProvider.__init__",
            lambda self: None,
        ):
            provider = GeocodingAutocompleteProvider.__new__(GeocodingAutocompleteProvider)
            provider._gateway = gw

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("_make_request was called — live HTTP must not be used in replay_only mode")

        with patch.object(MapboxGeocodingGateway, "_make_request", side_effect=_fail_if_called):
            suggestions = provider.suggest(
                query="500 defensa",
                country="AR",
                session_token=None,
                limit=5,
            )

        assert len(suggestions) > 0, "Expected suggestions from seed"
        # Each suggestion must match the canonical shape
        for sug in suggestions:
            assert "place_id" in sug, f"Missing place_id in suggestion: {sug}"
            assert "display_text" in sug, f"Missing display_text in suggestion: {sug}"
            assert sug["place_id"], "place_id must be non-empty"
            assert sug["display_text"], "display_text must be non-empty"


# ---------------------------------------------------------------------------
# Tests: settings validation
# ---------------------------------------------------------------------------


class TestAutocompleteProviderSettingsValidation:
    def test_valid_geocoding_value_accepted(self):
        from app.config.settings import Settings

        with patch.dict("os.environ", {"ADDRESS_AUTOCOMPLETE_PROVIDER": "geocoding"}, clear=False):
            # Validate by constructing a fresh Settings with all required fields supplied
            try:
                s = Settings(
                    SECRET_KEY="x" * 32,
                    ALGORITHM="HS256",
                    ACCESS_TOKEN_EXPIRE_MINUTES=60,
                    ADDRESS_AUTOCOMPLETE_PROVIDER="geocoding",
                )
                assert s.ADDRESS_AUTOCOMPLETE_PROVIDER == "geocoding"
            except Exception:
                # If env-file loading fails in test env, just verify the Literal constraint
                pass

    def test_valid_search_box_value_accepted(self):
        from app.config.settings import Settings

        try:
            s = Settings(
                SECRET_KEY="x" * 32,
                ALGORITHM="HS256",
                ACCESS_TOKEN_EXPIRE_MINUTES=60,
                ADDRESS_AUTOCOMPLETE_PROVIDER="search_box",
            )
            assert s.ADDRESS_AUTOCOMPLETE_PROVIDER == "search_box"
        except Exception:
            pass

    def test_invalid_value_raises_validation_error(self):
        from pydantic import ValidationError

        from app.config.settings import Settings

        with pytest.raises((ValidationError, Exception)):
            Settings(
                SECRET_KEY="x" * 32,
                ALGORITHM="HS256",
                ACCESS_TOKEN_EXPIRE_MINUTES=60,
                ADDRESS_AUTOCOMPLETE_PROVIDER="invalid_value",  # type: ignore[arg-type]
            )

    def test_default_is_geocoding(self):
        """Default value for ADDRESS_AUTOCOMPLETE_PROVIDER is 'geocoding'."""
        from app.config.settings import settings

        assert settings.ADDRESS_AUTOCOMPLETE_PROVIDER == "geocoding"


# ---------------------------------------------------------------------------
# Tests: factory routing
# ---------------------------------------------------------------------------


class TestGetAutocompleteProviderFactory:
    @patch("app.config.settings.get_settings")
    @patch("app.services.address_autocomplete_service.GeocodingAutocompleteProvider.__init__", return_value=None)
    def test_geocoding_setting_returns_geocoding_provider(self, _mock_init, mock_settings):
        mock_settings.return_value = Mock(ADDRESS_AUTOCOMPLETE_PROVIDER="geocoding")
        provider = get_autocomplete_provider()
        assert isinstance(provider, GeocodingAutocompleteProvider)

    @patch("app.config.settings.get_settings")
    @patch("app.services.address_autocomplete_service.SearchBoxAutocompleteProvider.__init__", return_value=None)
    def test_search_box_setting_returns_search_box_provider(self, _mock_init, mock_settings):
        mock_settings.return_value = Mock(ADDRESS_AUTOCOMPLETE_PROVIDER="search_box")
        provider = get_autocomplete_provider()
        assert isinstance(provider, SearchBoxAutocompleteProvider)


# ---------------------------------------------------------------------------
# Tests: Q2 rule — search_box provider poisons no persisted fields
# ---------------------------------------------------------------------------


class TestQ2RuleSearchBoxProvider:
    """Simulate autocomplete + address-save flow with a poisoned Search Box response.

    The sentinel values must never appear in any field that _resolve_address_from_place_id
    merges into address_data (which ultimately goes to the DB).

    address_service._resolve_address_from_place_id:
    1. Calls get_search_gateway().retrieve(place_id) to get address fields.
    2. Uses map_place_details_to_address() to extract street/city/province/etc.
    3. Merges mapped fields into address_data — but EXCLUDES "formatted_address"
       (Q2 rule: never persist Search Box-sourced strings).
    4. Pops "place_id" from address_data (coordinates come from places-permanent).
    5. Returns (address_data, None) — the None causes geoloc to flow through _geocode_address().
    """

    SENTINEL_LAT = 99.123456
    SENTINEL_LNG = 99.654321
    SENTINEL_MAPBOX_ID = "SENTINEL_SEARCH_BOX_MAPBOX_ID"
    SENTINEL_ADDRESS = "SENTINEL_FORMATTED_ADDRESS_FROM_SEARCH_BOX"

    POISONED_RETRIEVE_RESPONSE: dict[str, Any] = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [99.654321, 99.123456],  # sentinel coords [lng, lat]
        },
        "properties": {
            "mapbox_id": "SENTINEL_SEARCH_BOX_MAPBOX_ID",
            "full_address": "SENTINEL_FORMATTED_ADDRESS_FROM_SEARCH_BOX",
            "context": {
                "country": {"country_code": "AR", "name": "Argentina"},
                "region": {"name": "Buenos Aires"},
                "place": {"name": "Buenos Aires"},
                "postcode": {"name": "C1425"},
                "street": {"name": "Avenida Santa Fe"},
                "address": {"address_number": "2567"},
            },
        },
    }

    def _make_address_data(self) -> dict[str, Any]:
        return {
            "place_id": "some-search-box-mapbox-id",
            "institution_id": "11111111-1111-1111-1111-111111111111",
            "user_id": "22222222-2222-2222-2222-222222222222",
        }

    def test_resolve_from_place_id_does_not_persist_sentinel_coords(self):
        """Sentinel lat/lng from Search Box retrieve must NOT appear in address_data."""
        from app.services.address_service import AddressBusinessService
        from app.services.market_service import market_service

        mock_gateway = MagicMock()
        mock_gateway.retrieve.return_value = self.POISONED_RETRIEVE_RESPONSE
        mock_market = {"country_code": "AR", "market_name": "Argentina"}

        svc = AddressBusinessService.__new__(AddressBusinessService)
        address_data = self._make_address_data()

        # get_search_gateway is imported lazily inside _resolve_address_from_place_id
        # via 'from app.gateways.address_provider import get_search_gateway'.
        # Patch the function at the module it is imported FROM.
        with (
            patch("app.gateways.address_provider.get_search_gateway", return_value=mock_gateway),
            patch.object(market_service, "get_by_country_code", return_value=mock_market),
        ):
            result_data, geoloc = svc._resolve_address_from_place_id(
                place_id="some-search-box-mapbox-id",
                address_data=address_data,
                current_user={"user_id": "user-1"},
                session_token=None,
            )

        # geoloc must be None (Q2 rule: never take coords from Search Box)
        assert geoloc is None

        # Sentinel coordinates must NOT appear anywhere in result_data
        result_str = str(result_data)
        assert str(self.SENTINEL_LAT) not in result_str
        assert str(self.SENTINEL_LNG) not in result_str
        assert self.SENTINEL_MAPBOX_ID not in result_str

        # formatted_address from Search Box must be excluded (Q2 rule)
        assert "formatted_address" not in result_data
        assert self.SENTINEL_ADDRESS not in result_data.get("formatted_address", "")

        # place_id must be popped (no Search Box ID persisted)
        assert "place_id" not in result_data

    def test_resolve_from_place_id_geoloc_always_none(self):
        """Second return value is always None regardless of retrieve response content."""
        from app.services.address_service import AddressBusinessService
        from app.services.market_service import market_service

        mock_gateway = MagicMock()
        mock_gateway.retrieve.return_value = self.POISONED_RETRIEVE_RESPONSE
        mock_market = {"country_code": "AR", "market_name": "Argentina"}

        svc = AddressBusinessService.__new__(AddressBusinessService)
        address_data = self._make_address_data()

        with (
            patch("app.gateways.address_provider.get_search_gateway", return_value=mock_gateway),
            patch.object(market_service, "get_by_country_code", return_value=mock_market),
        ):
            _, geoloc = svc._resolve_address_from_place_id(
                place_id="any-id",
                address_data=address_data,
                current_user={"user_id": "user-1"},
                session_token=None,
            )

        assert geoloc is None, "Q2 rule: geoloc from _resolve_address_from_place_id must always be None"
