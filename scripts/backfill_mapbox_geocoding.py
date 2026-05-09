#!/usr/bin/env python3
"""
Backfill Mapbox geocoding for records missing coordinates.

Walks ops.restaurant_info rows where location IS NULL and geocodes each via the
cache-aware Mapbox gateway. Reads the mode from MAPBOX_CACHE_MODE (default: replay_only).

  replay_only (default) — only reads from seeds/mapbox_geocode_cache.json.
                          Cache miss → warning logged, row skipped. No Mapbox calls.
  record                — cache miss calls live Mapbox API and writes the entry.
  bypass                — always calls live Mapbox API (skips cache).

Usage (from repo root, venv activated):
    # Dry-run — preview what would be updated, no writes:
    PYTHONPATH=. python scripts/backfill_mapbox_geocoding.py --dry-run

    # Replay from committed cache (default — safe for CI/rebuild):
    PYTHONPATH=. python scripts/backfill_mapbox_geocoding.py

    # Record new addresses (requires a live Mapbox token):
    MAPBOX_CACHE_MODE=record PYTHONPATH=. python scripts/backfill_mapbox_geocoding.py

Prerequisites:
    DATABASE_URL or individual DB_HOST/DB_PORT/DB_NAME/DB_USER env vars.
    PYTHONPATH=. must be set so app.* imports resolve.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import psycopg2
import psycopg2.extras

# System super-admin UUID used as modified_by for automated operations.
_SYSTEM_USER = "dddddddd-dddd-dddd-dddd-dddddddddddd"

_PREFIX = "[backfill-mapbox]"


def _log(msg: str, *, err: bool = False) -> None:
    fh = sys.stderr if err else sys.stdout
    print(f"{_PREFIX} {msg}", file=fh, flush=True)


def _get_connection() -> psycopg2.extensions.connection:
    """Direct psycopg2 connection — no FastAPI stack required."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("KITCHEN_DB_NAME") or os.environ.get("DB_NAME", "kitchen"),
        user=os.environ.get("DB_USER", os.environ.get("USER", "postgres")),
        password=os.environ.get("DB_PASSWORD") or os.environ.get("PGPASSWORD", ""),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def _build_address_string(row: dict[str, Any]) -> str:
    """Replicate AddressBusinessService._build_full_address_string() logic."""
    return f"{row['building_number']} {row['street_name']}, {row['city']}, {row['province']}, {row['country_code']}"


def _backfill_restaurants(cur: Any, *, dry_run: bool) -> dict[str, int]:
    """Geocode restaurant_info rows where location IS NULL."""
    from app.gateways.mapbox_geocode_cache import MapboxCacheMiss
    from app.gateways.mapbox_geocoding_gateway import get_mapbox_geocoding_gateway

    gateway = get_mapbox_geocoding_gateway()

    cur.execute(
        """
        SELECT
            r.restaurant_id,
            r.address_id,
            a.building_number,
            a.street_name,
            a.city,
            a.province,
            a.country_code
        FROM ops.restaurant_info r
        JOIN core.address_info a ON a.address_id = r.address_id
        WHERE r.location IS NULL
          AND r.is_archived = FALSE
          AND a.building_number IS NOT NULL
          AND a.street_name    IS NOT NULL
        ORDER BY r.restaurant_id
        """
    )
    rows = list(cur.fetchall())

    stats: dict[str, int] = {"total": len(rows), "updated": 0, "skipped": 0, "errors": 0}

    for row in rows:
        address = _build_address_string(row)
        restaurant_id = str(row["restaurant_id"])

        try:
            lat, lng = gateway.geocode(address)
        except MapboxCacheMiss as exc:
            _log(
                f"SKIP restaurant {restaurant_id}: {exc}",
                err=True,
            )
            stats["skipped"] += 1
            continue
        except Exception as exc:
            _log(f"ERROR geocoding restaurant {restaurant_id} ({address!r}): {exc}", err=True)
            stats["errors"] += 1
            continue

        _log(f"restaurant {restaurant_id}: {address!r} → ({lat}, {lng})")

        if not dry_run:
            cur.execute(
                """
                UPDATE ops.restaurant_info
                SET location     = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    modified_by  = %s,
                    modified_date = NOW()
                WHERE restaurant_id = %s
                """,
                (lng, lat, _SYSTEM_USER, restaurant_id),
            )
        stats["updated"] += 1

    return stats


def _backfill_geolocation_timestamps(cur: Any, *, dry_run: bool) -> dict[str, int]:
    """Stamp mapbox_geocoded_at on geolocation_info rows that are missing it."""
    cur.execute(
        """
        SELECT g.geolocation_id, g.address_id,
               a.building_number, a.street_name, a.city, a.province, a.country_code
        FROM core.geolocation_info g
        JOIN core.address_info a ON a.address_id = g.address_id
        WHERE g.mapbox_geocoded_at IS NULL
          AND g.latitude  <> 0
          AND g.longitude <> 0
        ORDER BY g.geolocation_id
        """
    )
    rows = list(cur.fetchall())
    stats: dict[str, int] = {"total": len(rows), "stamped": 0}

    for row in rows:
        geo_id = str(row["geolocation_id"])
        address = _build_address_string(row)
        normalized = address.strip().lower()
        import re

        normalized = re.sub(r"\s+", " ", normalized)

        _log(f"stamp geolocation {geo_id}: set mapbox_geocoded_at + normalized_address")

        if not dry_run:
            cur.execute(
                """
                UPDATE core.geolocation_info
                SET mapbox_geocoded_at        = NOW(),
                    mapbox_normalized_address = %s,
                    modified_by               = %s,
                    modified_date             = NOW()
                WHERE geolocation_id = %s
                """,
                (normalized, _SYSTEM_USER, geo_id),
            )
        stats["stamped"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Mapbox geocoding for missing coordinates.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB.")
    args = parser.parse_args()

    mode = os.environ.get("MAPBOX_CACHE_MODE", "replay_only")
    _log(f"starting — MAPBOX_CACHE_MODE={mode} dry_run={args.dry_run}")

    if "PGPASSWORD" in os.environ and "DB_PASSWORD" not in os.environ:
        os.environ["DB_PASSWORD"] = os.environ["PGPASSWORD"]

    try:
        conn = _get_connection()
    except Exception as exc:
        _log(f"ERROR: cannot connect to database: {exc}", err=True)
        return 1

    try:
        with conn:
            with conn.cursor() as cur:
                restaurant_stats = _backfill_restaurants(cur, dry_run=args.dry_run)
                geo_stats = _backfill_geolocation_timestamps(cur, dry_run=args.dry_run)

        _log(
            f"restaurants: total={restaurant_stats['total']} "
            f"updated={restaurant_stats['updated']} "
            f"skipped={restaurant_stats['skipped']} "
            f"errors={restaurant_stats['errors']}"
        )
        _log(f"geolocation timestamps: total={geo_stats['total']} stamped={geo_stats['stamped']}")
        if args.dry_run:
            _log("dry-run complete — no changes written")
        else:
            _log("done")
    except Exception as exc:
        _log(f"ERROR: {exc}", err=True)
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
