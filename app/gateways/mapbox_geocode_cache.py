"""
Mapbox Geocoding Cache — file-backed response cache for dev/seed workflows.

Modes (MAPBOX_CACHE_MODE env var):
  replay_only — default for tests + seed: cache miss raises MapboxCacheMiss, never calls Mapbox.
  record      — dev when adding new addresses: cache miss calls Mapbox live and writes the entry.
  bypass      — prod: never reads cache, always calls Mapbox live.

Cache file: seeds/mapbox_geocode_cache.json (committed to repo — treat as production data).
Cache key: "operation|normalized_q|country|language" (lowercase, trimmed, collapsed whitespace).
"""

import json
import logging
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_cache_file() -> Path:
    """Resolve the seed cache file path robustly.

    Resolution order:
    1. ``MAPBOX_GEOCODE_CACHE_PATH`` env var — absolute override.
    2. Relative to ``__file__`` (normal install, primary working tree).
    3. Walk up from ``Path.cwd()`` looking for ``seeds/mapbox_geocode_cache.json``
       — handles mutmut's ``mutants/`` relocation where ``__file__`` points to a
       copy directory that has no ``seeds/`` sibling.
    """
    env_override = os.getenv("MAPBOX_GEOCODE_CACHE_PATH")
    if env_override:
        return Path(env_override)

    # Primary: relative to this source file (correct in all normal layouts).
    candidate = Path(__file__).parent.parent.parent / "seeds" / "mapbox_geocode_cache.json"
    if candidate.exists():
        return candidate

    # Fallback: walk up from CWD (catches mutmut's mutants/ relocation).
    for parent in [Path.cwd(), *Path.cwd().parents]:
        fallback = parent / "seeds" / "mapbox_geocode_cache.json"
        if fallback.exists():
            return fallback

    # Nothing found — return the __file__-relative path and let callers handle the miss.
    return candidate


_CACHE_FILE = _resolve_cache_file()


class CacheMode(str, Enum):
    REPLAY_ONLY = "replay_only"
    RECORD = "record"
    BYPASS = "bypass"


class MapboxCacheMiss(Exception):
    """Raised in replay_only mode when an address has no cache entry."""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def make_geocode_key(q: str, country: str, language: str, *, permanent: bool) -> str:
    """Cache key for the ``geocode`` operation (address string → coordinates).

    No lat/lng in the signature — CodeQL can verify the return value is taint-clean
    with respect to ``py/clear-text-logging-sensitive-data``.
    """
    norm_q = _normalize(q)
    norm_country = _normalize(country)
    norm_lang = _normalize(language)
    perm_str = str(permanent).lower()
    return f"geocode|{norm_q}|{norm_country}|{norm_lang}|permanent={perm_str}"


def make_forward_search_key(q: str, country: str, language: str, *, permanent: bool) -> str:
    """Cache key for the ``forward_search`` operation (autocomplete partial input).

    Distinct from ``make_geocode_key`` so that autocomplete entries never collide
    with geocode-resolution entries that share the same normalized query string.

    No lat/lng in the signature — CodeQL can verify the return value is taint-clean.
    """
    norm_q = _normalize(q)
    norm_country = _normalize(country)
    norm_lang = _normalize(language)
    perm_str = str(permanent).lower()
    return f"forward_search|{norm_q}|{norm_country}|{norm_lang}|permanent={perm_str}"


def make_reverse_geocode_key(latitude: str, longitude: str, language: str, *, permanent: bool) -> str:
    """Cache key for the ``reverse_geocode`` operation (coordinates → address string).

    Accepts lat/lng as strings.  CodeQL will correctly flag any log line that
    interpolates the *return value* of this function as potentially tainted.
    Callers that only need to log the cache *hit* (not the key) should log
    ``"cache hit for reverse_geocode"`` without interpolating the key string.
    """
    perm_str = str(permanent).lower()
    return f"reverse_geocode|{latitude}|{longitude}|{_normalize(language)}|permanent={perm_str}"


class MapboxGeocodeCache:
    """Read-write JSON cache for raw Mapbox Geocoding API responses.

    The cache is keyed by normalized address query so the same address never
    triggers a second Mapbox call regardless of who runs the rebuild.
    """

    def __init__(self, path: Path = _CACHE_FILE):
        self._path = path
        self._data: dict[str, Any] | None = None

    @property
    def mode(self) -> CacheMode:
        raw = os.getenv("MAPBOX_CACHE_MODE", "replay_only").strip().lower()
        try:
            return CacheMode(raw)
        except ValueError:
            logger.warning("Unknown MAPBOX_CACHE_MODE %r — defaulting to replay_only", raw)
            return CacheMode.REPLAY_ONLY

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            if self._path.exists():
                with self._path.open(encoding="utf-8") as fh:
                    self._data = json.load(fh)
            else:
                self._data = {}
        return self._data

    def get(self, key: str) -> Any | None:
        return self._load().get(key)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
        logger.info("mapbox_geocode_cache: wrote key %r to %s", key, self._path)


_cache = MapboxGeocodeCache()


def get_geocode_cache() -> MapboxGeocodeCache:
    return _cache
