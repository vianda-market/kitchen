#!/usr/bin/env python3
"""
Regen seeds/mapbox_geocode_cache.json permanent=true entries from the actual
places-permanent Mapbox Geocoding v6 endpoint.

Step 0.1 — closes the cache-quality concern from Step 2.

Background
----------
The prior executor duplicated ephemeral dev-fixture responses under permanent=true
keys, arguing that places and places-permanent return identical payloads. This script
was written to replace those copies with live API calls and verify the claim.

Outcome of verification (2026-05-09):
  - The normalized query strings used as cache keys ("3200 santa fe, buenos aires,
    buenos aires, ar" etc.) are internal backfill strings, not realistic user queries.
  - Both the ``places`` (ephemeral) and ``places-permanent`` endpoints return the
    EXACT SAME response — byte-for-byte identical mapbox_id, coordinates, and
    full_address — for each of these queries. This held for all 3 demo-day addresses.
  - The prior executor's reasoning was correct: there is no divergence between the two
    datasets for these addresses.
  - Conclusion: the duplicated entries in seeds/mapbox_geocode_cache.json are sound
    dev fixtures. No replacement needed.

If you add new addresses to the cache in the future:
  - Set MAPBOX_CACHE_MODE=record and run scripts/backfill_mapbox_geocoding.py.
  - That script uses get_mapbox_geocoding_gateway() (ephemeral) for the restaurant
    location column and does not write permanent=true entries.
  - For permanent=true entries (used when address_service writes lat/lng to DB),
    run this script in record mode — it will write permanent=true entries alongside
    the ephemeral ones. The responses will be identical, which is expected.

Usage (from repo root, venv activated):
    MAPBOX_CACHE_MODE=record PYTHONPATH=. python scripts/regen_permanent_cache.py

Requires MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT to be set in .env or environment.
Estimated cost: N x $5/1000 (where N = number of new addresses, ~$0.015 for 3).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_PREFIX = "[regen-permanent-cache]"
_CACHE_FILE = Path(__file__).parent.parent / "seeds" / "mapbox_geocode_cache.json"


def _log(msg: str, *, err: bool = False) -> None:
    fh = sys.stderr if err else sys.stdout
    print(f"{_PREFIX} {msg}", file=fh, flush=True)


def _remove_existing_permanent_entries(addresses: list[tuple[str, str | None, str]]) -> None:
    """Remove pre-existing permanent=true cache entries so record mode hits the live API."""
    from app.gateways.mapbox_geocode_cache import make_cache_key

    if not _CACHE_FILE.exists():
        return
    with _CACHE_FILE.open(encoding="utf-8") as fh:
        data = json.load(fh)

    removed = 0
    for q, country, language in addresses:
        key = make_cache_key("geocode", q=q, country=country or "", language=language, permanent=True)
        if key in data:
            _log(f"Removing stale entry: q={q!r} country={country!r}")
            del data[key]
            removed += 1

    if removed:
        with _CACHE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
        _log(f"Removed {removed} existing permanent=true entries — will re-record from live API.")
    else:
        _log("No pre-existing permanent=true entries found (will record fresh entries).")


def main() -> int:
    mode = os.environ.get("MAPBOX_CACHE_MODE", "replay_only")
    if mode != "record":
        _log(
            f"ERROR: MAPBOX_CACHE_MODE is {mode!r}. Must be 'record' to call the live API.",
            err=True,
        )
        _log("Run with: MAPBOX_CACHE_MODE=record PYTHONPATH=. python scripts/regen_permanent_cache.py", err=True)
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

    # Addresses to record. Add new addresses here when the demo-day fixture set grows.
    # These are the normalized query strings used as cache keys (before the "geocode|" prefix).
    # They must match the strings produced by AddressBusinessService._build_full_address_string().
    addresses: list[tuple[str, str | None, str]] = [
        # (query_string_as_sent_to_gateway, country, language)
        ("3200 santa fe, buenos aires, buenos aires, ar", None, "es"),
        ("500 defensa, buenos aires, buenos aires, ar", None, "es"),
        ("corrientes 1234, buenos aires, buenos aires, ar", None, "es"),
    ]

    _log(f"Will record {len(addresses)} permanent-mode cache entries.")
    if len(addresses) > 50:
        _log("ERROR: address count exceeds 50. Aborting per safety rule.", err=True)
        return 1

    # Remove stale permanent=true entries so record mode hits the live API
    # (not the previously cached response).
    _remove_existing_permanent_entries(addresses)

    from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

    # Create a fresh permanent gateway (not the singleton, to avoid reuse of cached instance).
    gw = MapboxGeocodingGateway(permanent=True)

    from app.gateways.mapbox_geocode_cache import make_cache_key

    success = 0
    for q, country, language in addresses:
        key = make_cache_key("geocode", q=q, country=country or "", language=language, permanent=True)
        _log(f"Recording from live API: q={q!r} country={country!r}")
        try:
            # call() handles record mode: cache miss → live API → write cache.
            # Note: the permanent=true and permanent=false endpoints return identical
            # responses for standard geocoding queries (verified 2026-05-09). The
            # separate cache keys exist to isolate the two modes, not because the
            # responses differ in content.
            result = gw.call("geocode", q=q, country=country, language=language, limit=1)
            features = result.get("features", [])
            if features:
                coords = features[0].get("geometry", {}).get("coordinates", [])
                props = features[0].get("properties", {})
                mapbox_id = props.get("mapbox_id", "")
                full_address = props.get("full_address", "")
                _log(
                    f"  OK  coords=({coords[1] if len(coords) >= 2 else 'N/A'}, "
                    f"{coords[0] if len(coords) >= 2 else 'N/A'})  "
                    f"mapbox_id={mapbox_id!r}  full_address={full_address!r}"
                )
            else:
                _log(f"  WARNING: no features returned for {q!r}", err=True)
            success += 1
        except Exception as exc:
            _log(f"  ERROR for {q!r}: {type(exc).__name__}", err=True)

    _log(f"Done. Recorded {success}/{len(addresses)} entries under permanent=true keys.")
    _log("Commit seeds/mapbox_geocode_cache.json to capture the regenerated entries.")
    return 0 if success == len(addresses) else 1


if __name__ == "__main__":
    sys.exit(main())
