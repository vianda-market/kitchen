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


def make_cache_key(operation: str, **kwargs: Any) -> str:
    """Build a normalized cache key for a geocoding operation.

    The ``permanent`` flag is included in the key so that ephemeral and
    permanent responses never cross-contaminate the cache.  Existing entries
    keyed without the flag (i.e. ``permanent=False``) are preserved — the
    default ``permanent`` value is ``False``, so the key segment reads
    ``permanent=false`` for all previously-recorded ephemeral entries.

    The ``forward_search`` operation adds an ``op=forward_search`` segment so
    that autocomplete cache entries never collide with geocode-resolution entries
    that share the same normalized query string.
    """
    if operation == "geocode":
        q = _normalize(kwargs.get("q", ""))
        country = _normalize(kwargs.get("country") or "")
        lang = _normalize(kwargs.get("language") or "")
        permanent = str(kwargs.get("permanent", False)).lower()
        return f"geocode|{q}|{country}|{lang}|permanent={permanent}"
    if operation == "forward_search":
        q = _normalize(kwargs.get("q", ""))
        country = _normalize(kwargs.get("country") or "")
        lang = _normalize(kwargs.get("language") or "")
        permanent = str(kwargs.get("permanent", False)).lower()
        return f"forward_search|{q}|{country}|{lang}|permanent={permanent}"
    if operation == "reverse_geocode":
        lat = str(kwargs.get("latitude", ""))
        lng = str(kwargs.get("longitude", ""))
        lang = _normalize(kwargs.get("language") or "")
        permanent = str(kwargs.get("permanent", False)).lower()
        return f"reverse_geocode|{lat}|{lng}|{lang}|permanent={permanent}"
    # Fallback: include all kwargs sorted for determinism
    tail = "|".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return f"{operation}|{tail}"


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
