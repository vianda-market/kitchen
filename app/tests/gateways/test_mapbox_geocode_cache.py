"""Unit tests for MapboxGeocodeCache and the gateway cache-aware call() override."""

import json
from unittest.mock import Mock, patch

import pytest

from app.gateways.mapbox_geocode_cache import (
    CacheMode,
    MapboxCacheMiss,
    MapboxGeocodeCache,
    make_forward_search_key,
    make_geocode_key,
    make_reverse_geocode_key,
)
from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway


class TestMakeGeocodeKey:
    def test_normalizes_query(self):
        key = make_geocode_key(q="  Av. Santa FE  2567 ", country="AR", language="ES", permanent=False)
        assert key == "geocode|av. santa fe 2567|ar|es|permanent=false"

    def test_missing_optional_fields(self):
        key = make_geocode_key(q="Test", country="", language="", permanent=False)
        assert key == "geocode|test|||permanent=false"

    def test_permanent_true_has_distinct_key(self):
        ephemeral = make_geocode_key(q="Test addr", country="AR", language="es", permanent=False)
        permanent = make_geocode_key(q="Test addr", country="AR", language="es", permanent=True)
        assert ephemeral != permanent
        assert ephemeral.endswith("|permanent=false")
        assert permanent.endswith("|permanent=true")


class TestMakeForwardSearchKey:
    def test_normalizes_query(self):
        key = make_forward_search_key(q="  Av. Santa FE  ", country="AR", language="ES", permanent=False)
        assert key == "forward_search|av. santa fe|ar|es|permanent=false"

    def test_missing_optional_fields(self):
        key = make_forward_search_key(q="Test", country="", language="", permanent=False)
        assert key == "forward_search|test|||permanent=false"

    def test_permanent_true_has_distinct_key(self):
        ephemeral = make_forward_search_key(q="Test addr", country="AR", language="es", permanent=False)
        permanent = make_forward_search_key(q="Test addr", country="AR", language="es", permanent=True)
        assert ephemeral != permanent
        assert ephemeral.endswith("|permanent=false")
        assert permanent.endswith("|permanent=true")

    def test_distinct_from_geocode_key(self):
        """forward_search and geocode keys must never collide for the same query."""
        fwd = make_forward_search_key(q="Santa Fe", country="AR", language="es", permanent=False)
        geo = make_geocode_key(q="Santa Fe", country="AR", language="es", permanent=False)
        assert fwd != geo
        assert fwd.startswith("forward_search|")
        assert geo.startswith("geocode|")


class TestMakeReverseGeocodeKey:
    def test_uses_coordinates(self):
        key = make_reverse_geocode_key(latitude="-34.5", longitude="-58.4", language="es", permanent=False)
        assert key == "reverse_geocode|-34.5|-58.4|es|permanent=false"

    def test_permanent_flag_in_key(self):
        k = make_reverse_geocode_key(latitude="-34.5", longitude="-58.4", language="es", permanent=True)
        assert k.endswith("|permanent=true")


class TestMapboxGeocodeCache:
    def test_mode_defaults_to_replay_only(self, monkeypatch):
        monkeypatch.delenv("MAPBOX_CACHE_MODE", raising=False)
        assert MapboxGeocodeCache().mode == CacheMode.REPLAY_ONLY

    def test_mode_reads_env(self, monkeypatch):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "record")
        assert MapboxGeocodeCache().mode == CacheMode.RECORD

    def test_mode_unknown_value_falls_back_to_replay_only(self, monkeypatch):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "garbage")
        assert MapboxGeocodeCache().mode == CacheMode.REPLAY_ONLY

    def test_get_returns_none_when_file_missing(self, tmp_path):
        cache = MapboxGeocodeCache(path=tmp_path / "missing.json")
        assert cache.get("anything") is None

    def test_set_creates_file_and_get_reads_it(self, tmp_path):
        path = tmp_path / "cache.json"
        cache = MapboxGeocodeCache(path=path)
        cache.set("key1", {"value": 1})
        assert path.exists()
        on_disk = json.loads(path.read_text())
        assert on_disk == {"key1": {"value": 1}}
        assert cache.get("key1") == {"value": 1}

    def test_set_round_trip_via_fresh_instance(self, tmp_path):
        path = tmp_path / "cache.json"
        MapboxGeocodeCache(path=path).set("k", "v")
        assert MapboxGeocodeCache(path=path).get("k") == "v"


class TestGatewayCacheIntegration:
    """Integration tests between MapboxGeocodingGateway and the geocode cache."""

    @patch("app.config.settings.get_mapbox_access_token", return_value="pk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def _gateway_ephemeral(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=False)
        return MapboxGeocodingGateway(permanent=False)

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def _gateway_permanent(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=False)
        return MapboxGeocodingGateway(permanent=True)

    def test_bypass_mode_skips_cache(self, monkeypatch):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        gw = self._gateway_ephemeral()
        with patch.object(MapboxGeocodingGateway, "_make_request", return_value={"ok": True}) as mock_req:
            result = gw.call("geocode", q="x", language="es")
        assert result == {"ok": True}
        assert mock_req.called

    def test_replay_only_cache_hit_returns_cached_ephemeral(self, monkeypatch, tmp_path):
        """Ephemeral gateway finds its own key (permanent=false)."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        cache_path = tmp_path / "c.json"
        cache_path.write_text(json.dumps({"geocode|x||es|permanent=false": {"hit": True}}))
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = self._gateway_ephemeral()
        with patch.object(MapboxGeocodingGateway, "_make_request") as mock_req:
            result = gw.call("geocode", q="x", language="es")
        assert result == {"hit": True}
        assert not mock_req.called

    def test_replay_only_cache_hit_returns_cached_permanent(self, monkeypatch, tmp_path):
        """Permanent gateway finds its own key (permanent=true), not the ephemeral key."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        cache_path = tmp_path / "c.json"
        cache_path.write_text(
            json.dumps(
                {
                    "geocode|x||es|permanent=false": {"ephemeral": True},
                    "geocode|x||es|permanent=true": {"permanent": True},
                }
            )
        )
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = self._gateway_permanent()
        with patch.object(MapboxGeocodingGateway, "_make_request") as mock_req:
            result = gw.call("geocode", q="x", language="es")
        assert result == {"permanent": True}
        assert not mock_req.called

    def test_ephemeral_and_permanent_gateways_dont_share_cache_entries(self, monkeypatch, tmp_path):
        """Cache keys must differ between the two gateway modes."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        cache_path = tmp_path / "c.json"
        # Only ephemeral key present
        cache_path.write_text(json.dumps({"geocode|x||es|permanent=false": {"hit": True}}))
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        perm_gw = self._gateway_permanent()
        # Permanent gateway must NOT find the ephemeral entry
        with pytest.raises(MapboxCacheMiss):
            perm_gw.call("geocode", q="x", language="es")

    def test_replay_only_cache_miss_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=tmp_path / "empty.json"))
        gw = self._gateway_ephemeral()
        with pytest.raises(MapboxCacheMiss):
            gw.call("geocode", q="missing", language="es")

    def test_record_mode_calls_live_and_writes_cache_ephemeral(self, monkeypatch, tmp_path):
        """Record mode writes under the permanent=false key for an ephemeral gateway."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "record")
        cache_path = tmp_path / "c.json"
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = self._gateway_ephemeral()
        with patch.object(MapboxGeocodingGateway, "_make_request", return_value={"fresh": True}) as mock_req:
            result = gw.call("geocode", q="newaddr", language="es")
        assert result == {"fresh": True}
        assert mock_req.called
        on_disk = json.loads(cache_path.read_text())
        assert on_disk["geocode|newaddr||es|permanent=false"] == {"fresh": True}

    def test_record_mode_calls_live_and_writes_cache_permanent(self, monkeypatch, tmp_path):
        """Record mode writes under the permanent=true key for a permanent gateway."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "record")
        cache_path = tmp_path / "c.json"
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = self._gateway_permanent()
        with patch.object(MapboxGeocodingGateway, "_make_request", return_value={"perm": True}) as mock_req:
            result = gw.call("geocode", q="newaddr", language="es")
        assert result == {"perm": True}
        assert mock_req.called
        on_disk = json.loads(cache_path.read_text())
        assert on_disk["geocode|newaddr||es|permanent=true"] == {"perm": True}

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_bypasses_cache_layer(self, mock_settings, _mock_token, monkeypatch):
        """When no token is set, gateway uses canned mock responses and skips the cache entirely."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway(permanent=False)
        # Should NOT raise MapboxCacheMiss — dev_mode short-circuits before cache check.
        lat, lng = gw.geocode("Av. Santa Fe 2567, Buenos Aires")
        assert isinstance(lat, float) and isinstance(lng, float)


class TestGatewayPermanentMode:
    """Tests for the permanent=True gateway path (Step 2)."""

    @patch("app.config.settings.get_mapbox_access_token")
    @patch("app.gateways.base_gateway.get_settings")
    def test_permanent_gateway_uses_persistent_token(self, mock_settings, mock_token):
        """Permanent gateway calls get_mapbox_access_token(permanent=True)."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        mock_token.return_value = "sk.test"
        MapboxGeocodingGateway(permanent=True)
        mock_token.assert_called_once_with(permanent=True)

    @patch("app.config.settings.get_mapbox_access_token")
    @patch("app.gateways.base_gateway.get_settings")
    def test_ephemeral_gateway_uses_ephemeral_token(self, mock_settings, mock_token):
        """Ephemeral gateway calls get_mapbox_access_token(permanent=False)."""
        mock_settings.return_value = Mock(DEV_MODE=False)
        mock_token.return_value = "pk.test"
        MapboxGeocodingGateway(permanent=False)
        mock_token.assert_called_once_with(permanent=False)

    def test_permanent_gateway_sends_permanent_param(self, monkeypatch):
        """Permanent gateway includes permanent=true in the Mapbox API request."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        captured_params: list = []

        def fake_make_request(self_gw, operation, **kwargs):
            # Record the params that _make_request would build, without actually making a request.
            # We do this by inspecting self_gw._permanent.
            captured_params.append(self_gw._permanent)
            return {
                "features": [
                    {
                        "geometry": {"coordinates": [-58.4, -34.6]},
                        "properties": {"mapbox_id": "id1", "full_address": "Addr", "context": {}},
                    }
                ]
            }

        with (
            patch("app.config.settings.get_mapbox_access_token", return_value="sk.test"),
            patch("app.gateways.base_gateway.get_settings") as mock_settings,
            patch.object(MapboxGeocodingGateway, "_make_request", fake_make_request),
        ):
            mock_settings.return_value = Mock(DEV_MODE=False)
            gw = MapboxGeocodingGateway(permanent=True)
            gw.geocode("test addr")

        assert captured_params == [True], "Expected _permanent=True to be forwarded"

    def test_ephemeral_gateway_does_not_send_permanent_param(self, monkeypatch):
        """Ephemeral gateway does NOT include permanent=true in the Mapbox API request."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        captured_params: list = []

        def fake_make_request(self_gw, operation, **kwargs):
            captured_params.append(self_gw._permanent)
            return {
                "features": [
                    {
                        "geometry": {"coordinates": [-58.4, -34.6]},
                        "properties": {"mapbox_id": "id1", "full_address": "Addr", "context": {}},
                    }
                ]
            }

        with (
            patch("app.config.settings.get_mapbox_access_token", return_value="pk.test"),
            patch("app.gateways.base_gateway.get_settings") as mock_settings,
            patch.object(MapboxGeocodingGateway, "_make_request", fake_make_request),
        ):
            mock_settings.return_value = Mock(DEV_MODE=False)
            gw = MapboxGeocodingGateway(permanent=False)
            gw.geocode("test addr")

        assert captured_params == [False], "Expected _permanent=False for ephemeral gateway"

    def test_missing_persistent_token_raises_runtime_error(self, monkeypatch):
        """If the persistent token is not configured, constructing a permanent gateway raises RuntimeError."""
        monkeypatch.setenv("ENVIRONMENT", "local")

        def raise_runtime(*args, **kwargs):
            if kwargs.get("permanent"):
                raise RuntimeError("MAPBOX_ACCESS_TOKEN_LOCAL_PERSISTENT is not set.")
            return "pk.test"

        with (
            patch("app.config.settings.get_mapbox_access_token", side_effect=raise_runtime),
            patch("app.gateways.base_gateway.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Mock(DEV_MODE=False)
            with pytest.raises(RuntimeError, match="PERSISTENT"):
                MapboxGeocodingGateway(permanent=True)


class TestGetMapboxGeocodingGatewaySingleton:
    """Tests for the two-mode singleton factory."""

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_ephemeral_singleton_returns_same_instance(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        import app.gateways.mapbox_geocoding_gateway as mod

        mod._mapbox_geocoding_gateway_ephemeral = None
        from app.gateways.mapbox_geocoding_gateway import get_mapbox_geocoding_gateway

        gw1 = get_mapbox_geocoding_gateway(permanent=False)
        gw2 = get_mapbox_geocoding_gateway(permanent=False)
        assert gw1 is gw2
        mod._mapbox_geocoding_gateway_ephemeral = None

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_permanent_singleton_returns_same_instance(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=False)
        import app.gateways.mapbox_geocoding_gateway as mod

        mod._mapbox_geocoding_gateway_permanent = None
        from app.gateways.mapbox_geocoding_gateway import get_mapbox_geocoding_gateway

        gw1 = get_mapbox_geocoding_gateway(permanent=True)
        gw2 = get_mapbox_geocoding_gateway(permanent=True)
        assert gw1 is gw2
        mod._mapbox_geocoding_gateway_permanent = None

    @patch(
        "app.config.settings.get_mapbox_access_token",
        side_effect=lambda permanent=False: "sk.test" if permanent else "pk.test",
    )
    @patch("app.gateways.base_gateway.get_settings")
    def test_ephemeral_and_permanent_singletons_are_distinct(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=False)
        import app.gateways.mapbox_geocoding_gateway as mod

        mod._mapbox_geocoding_gateway_ephemeral = None
        mod._mapbox_geocoding_gateway_permanent = None
        from app.gateways.mapbox_geocoding_gateway import get_mapbox_geocoding_gateway

        eph = get_mapbox_geocoding_gateway(permanent=False)
        perm = get_mapbox_geocoding_gateway(permanent=True)
        assert eph is not perm
        assert eph._permanent is False
        assert perm._permanent is True
        mod._mapbox_geocoding_gateway_ephemeral = None
        mod._mapbox_geocoding_gateway_permanent = None
