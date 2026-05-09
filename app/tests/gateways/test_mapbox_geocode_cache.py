"""Unit tests for MapboxGeocodeCache and the gateway cache-aware call() override."""

import json
from unittest.mock import Mock, patch

import pytest

from app.gateways.mapbox_geocode_cache import (
    CacheMode,
    MapboxCacheMiss,
    MapboxGeocodeCache,
    make_cache_key,
)
from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway


class TestMakeCacheKey:
    def test_geocode_normalizes_query(self):
        key = make_cache_key("geocode", q="  Av. Santa FE  2567 ", country="AR", language="ES")
        assert key == "geocode|av. santa fe 2567|ar|es"

    def test_geocode_with_missing_optional_fields(self):
        key = make_cache_key("geocode", q="Test")
        assert key == "geocode|test||"

    def test_reverse_geocode_uses_coordinates(self):
        key = make_cache_key("reverse_geocode", latitude=-34.5, longitude=-58.4, language="es")
        assert key == "reverse_geocode|-34.5|-58.4|es"

    def test_unknown_operation_falls_back_to_sorted_kwargs(self):
        key = make_cache_key("custom_op", b=2, a=1)
        assert key == "custom_op|a=1|b=2"


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
    @patch("app.config.settings.get_mapbox_access_token", return_value="pk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def _gateway_with_token(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=False)
        return MapboxGeocodingGateway()

    def test_bypass_mode_skips_cache(self, monkeypatch):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        gw = self._gateway_with_token()
        with patch.object(MapboxGeocodingGateway, "_make_request", return_value={"ok": True}) as mock_req:
            result = gw.call("geocode", q="x", language="es")
        assert result == {"ok": True}
        assert mock_req.called

    def test_replay_only_cache_hit_returns_cached(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        cache_path = tmp_path / "c.json"
        cache_path.write_text(json.dumps({"geocode|x||es": {"hit": True}}))
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = self._gateway_with_token()
        with patch.object(MapboxGeocodingGateway, "_make_request") as mock_req:
            result = gw.call("geocode", q="x", language="es")
        assert result == {"hit": True}
        assert not mock_req.called

    def test_replay_only_cache_miss_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=tmp_path / "empty.json"))
        gw = self._gateway_with_token()
        with pytest.raises(MapboxCacheMiss):
            gw.call("geocode", q="missing", language="es")

    def test_record_mode_calls_live_and_writes_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "record")
        cache_path = tmp_path / "c.json"
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))
        gw = self._gateway_with_token()
        with patch.object(MapboxGeocodingGateway, "_make_request", return_value={"fresh": True}) as mock_req:
            result = gw.call("geocode", q="newaddr", language="es")
        assert result == {"fresh": True}
        assert mock_req.called
        on_disk = json.loads(cache_path.read_text())
        assert on_disk["geocode|newaddr||es"] == {"fresh": True}

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_bypasses_cache_layer(self, mock_settings, _mock_token, monkeypatch):
        """When no token is set, gateway uses canned mock responses and skips the cache entirely."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway()
        # Should NOT raise MapboxCacheMiss — dev_mode short-circuits before cache check.
        lat, lng = gw.geocode("Av. Santa Fe 2567, Buenos Aires")
        assert isinstance(lat, float) and isinstance(lng, float)
