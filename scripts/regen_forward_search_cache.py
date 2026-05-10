#!/usr/bin/env python3
"""
Seed seeds/mapbox_geocode_cache.json with forward_search entries for the 3
demo addresses, covering the partial-query patterns a user would type during
autocomplete.

Usage (from repo root, venv activated):
    MAPBOX_CACHE_MODE=record PYTHONPATH=. python scripts/regen_forward_search_cache.py

Requires MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT to be set in .env or environment.

Cost estimate: 24 calls × $5/1000 ≈ $0.12 total.

Cache key format (from mapbox_geocode_cache.make_cache_key):
  forward_search|<normalized_q>|<country>|<language>|permanent=true

Provider parameters (from GeocodingAutocompleteProvider.suggest):
  country="AR"  (alpha-2, matching the demo addresses' region)
  language="es" (default in gateway)
  limit=5       (production default)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PREFIX = "[regen-forward-search-cache]"
_CACHE_FILE = Path(__file__).parent.parent / "seeds" / "mapbox_geocode_cache.json"

# ---------------------------------------------------------------------------
# Partial-query corpus.
# Each entry: (display_label, partial_query, country_alpha2, language)
# country and language must match what GeocodingAutocompleteProvider.suggest
# passes to MapboxGeocodingGateway.forward_search().
# ---------------------------------------------------------------------------

_QUERIES: list[tuple[str, str, str, str]] = [
    # 3200 santa fe — 8 partials
    ("3200 santa fe [1]", "3200", "AR", "es"),
    ("3200 santa fe [2]", "3200 s", "AR", "es"),
    ("3200 santa fe [3]", "3200 sa", "AR", "es"),
    ("3200 santa fe [4]", "3200 san", "AR", "es"),
    ("3200 santa fe [5]", "3200 sant", "AR", "es"),
    ("3200 santa fe [6]", "3200 santa", "AR", "es"),
    ("3200 santa fe [7]", "3200 santa f", "AR", "es"),
    ("3200 santa fe [8]", "3200 santa fe", "AR", "es"),
    # 500 defensa — 8 partials
    ("500 defensa [1]", "500", "AR", "es"),
    ("500 defensa [2]", "500 d", "AR", "es"),
    ("500 defensa [3]", "500 de", "AR", "es"),
    ("500 defensa [4]", "500 def", "AR", "es"),
    ("500 defensa [5]", "500 defe", "AR", "es"),
    ("500 defensa [6]", "500 defen", "AR", "es"),
    ("500 defensa [7]", "500 defens", "AR", "es"),
    ("500 defensa [8]", "500 defensa", "AR", "es"),
    # corrientes 1234 — 8 partials
    ("corrientes 1234 [1]", "corr", "AR", "es"),
    ("corrientes 1234 [2]", "corrie", "AR", "es"),
    ("corrientes 1234 [3]", "corrien", "AR", "es"),
    ("corrientes 1234 [4]", "corrient", "AR", "es"),
    ("corrientes 1234 [5]", "corrientes", "AR", "es"),
    ("corrientes 1234 [6]", "corrientes 1", "AR", "es"),
    ("corrientes 1234 [7]", "corrientes 12", "AR", "es"),
    ("corrientes 1234 [8]", "corrientes 1234", "AR", "es"),
    # Postman /suggest queries (002 ADDRESS_AUTOCOMPLETE_AND_VALIDATION + 000 E2E Plate Selection).
    # These are the full query strings that Newman sends to /api/v1/addresses/suggest.
    # country="" means no country filter (AddressAutocompleteService resolves alpha2=None).
    # The E2E step in collection 002 hard-asserts at least one suggestion; the others are
    # soft-checked (array shape only) but seeding them prevents MapboxCacheMiss in replay_only.
    ("postman: Av. Corrientes no country", "Av. Corrientes", "", "es"),
    ("postman: Santa Fe AR", "Santa Fe", "AR", "es"),
    ("postman: Avenida Santa Fe 2567 AR", "Avenida Santa Fe 2567", "AR", "es"),
    # Hard assertion in 002 E2E step 1 — must return at least one suggestion.
    ("postman: Avenida Santa Fe 2567 Buenos Aires AR", "Avenida Santa Fe 2567 Buenos Aires", "AR", "es"),
    # 000 E2E collection suggest step (soft check but seeds to avoid cache miss).
    ("postman: Av. Santa Fe 2567 Buenos Aires AR", "Av. Santa Fe 2567 Buenos Aires", "AR", "es"),
]


def _log(msg: str, *, err: bool = False) -> None:
    fh = sys.stderr if err else sys.stdout
    print(f"{_PREFIX} {msg}", file=fh, flush=True)


def _remove_existing_forward_search_entries(queries: list[tuple[str, str, str, str]]) -> None:
    """Remove pre-existing forward_search cache entries so record mode hits the live API."""
    from app.gateways.mapbox_geocode_cache import make_cache_key

    if not _CACHE_FILE.exists():
        return
    with _CACHE_FILE.open(encoding="utf-8") as fh:
        data = json.load(fh)

    removed = 0
    for _label, query, country, language in queries:
        key = make_cache_key(
            "forward_search",
            q=query,
            country=country.lower(),
            language=language,
            permanent=True,
        )
        if key in data:
            _log(f"Removing stale entry: {key!r}")
            del data[key]
            removed += 1

    if removed:
        with _CACHE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
        _log(f"Removed {removed} existing forward_search entries — will re-record from live API.")
    else:
        _log("No pre-existing forward_search entries found (will record fresh entries).")


def main() -> int:
    mode = os.environ.get("MAPBOX_CACHE_MODE", "replay_only")
    if mode != "record":
        _log(
            f"ERROR: MAPBOX_CACHE_MODE is {mode!r}. Must be 'record' to call the live API.",
            err=True,
        )
        _log(
            "Run with: MAPBOX_CACHE_MODE=record PYTHONPATH=. python scripts/regen_forward_search_cache.py",
            err=True,
        )
        return 1

    # Load .env before importing app modules so settings are populated.
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass  # dotenv not required; env vars may already be set

    # Confirm the persistent token is available.
    from app.config.settings import get_mapbox_access_token

    token = get_mapbox_access_token(permanent=True)
    if not token:
        _log(
            "ERROR: MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT is not set. "
            "Set it in .env or your shell before running this script.",
            err=True,
        )
        return 1

    _log("Persistent token loaded from environment.")
    _log(f"Total queries to record: {len(_QUERIES)} (≈ ${len(_QUERIES) * 0.005:.2f} estimated cost)")

    if len(_QUERIES) > 50:
        _log("ERROR: query count exceeds 50. Aborting per safety rule.", err=True)
        return 1

    # Remove stale forward_search entries so record mode hits the live API.
    _remove_existing_forward_search_entries(_QUERIES)

    from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

    # Fresh permanent gateway — not the singleton, to avoid reuse of module-level cache state.
    gw = MapboxGeocodingGateway(permanent=True)

    success = 0
    for label, query, country, language in _QUERIES:
        _log(f"Recording [{label}]: q={query!r} country={country!r} language={language!r}")
        try:
            result = gw.forward_search(query=query, country=country, language=language, limit=5)
            features = result.get("features", [])
            if features:
                top_name = (
                    features[0].get("properties", {}).get("full_address")
                    or features[0].get("properties", {}).get("name")
                    or "(no name)"
                )
                _log(f"  OK  {len(features)} feature(s), top={top_name!r}")
            else:
                _log(f"  WARNING: no features returned for {query!r}", err=True)
            success += 1
        except Exception as exc:
            _log(f"  ERROR for {query!r}: {exc}", err=True)

    _log(f"Done. Recorded {success}/{len(_QUERIES)} forward_search entries (permanent=true).")
    _log("Commit seeds/mapbox_geocode_cache.json to capture the seeded entries.")
    return 0 if success == len(_QUERIES) else 1


if __name__ == "__main__":
    sys.exit(main())
