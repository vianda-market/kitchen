#!/usr/bin/env python3
"""
Cleanup script: archive duplicate market rows, keeping one canonical row per country_code.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/markets on every run without
    cleanup, accumulating many copies of functionally identical markets
    (e.g. multiple rows for country_code='AR').
    These cause data integrity issues since country_code has a UNIQUE constraint —
    in practice duplicates manifest as 409 errors that get silently swallowed,
    and the GET fallback in old collections left leftover rows from prior test runs.

What this script does:
    For each country_code, finds all market rows that share the same country_code
    with no canonical_key.  It keeps the OLDEST row (by created_date) and
    soft-deletes the rest by setting is_archived = TRUE.

    Markets with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    The following seeded markets are hard-skipped and will NEVER be archived,
    regardless of duplication:

        00000000-0000-0000-0000-000000000001  (Global / XG)
        00000000-0000-0000-0000-000000000002  (Argentina / AR)
        00000000-0000-0000-0000-000000000003  (Peru / PE)
        00000000-0000-0000-0000-000000000004  (US)
        00000000-0000-0000-0000-000000000005  (Chile / CL)
        00000000-0000-0000-0000-000000000006  (Mexico / MX)
        00000000-0000-0000-0000-000000000007  (Brazil / BR)

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_markets.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_markets.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_markets.py
"""

import argparse
import os
import sys

import psycopg2


def get_connection() -> psycopg2.extensions.connection:
    """Open a direct psycopg2 connection from DATABASE_URL or individual env vars."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    # Fall back to individual env vars matching the app's config
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "vianda_dev"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


# UUID of the super-admin system user used as modified_by for automated ops
SYSTEM_USER_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"

# Seeded markets that must never be archived — these are canonical reference rows
# defined in app/db/seed/reference_data.sql.
SYSTEM_MARKET_SKIP_LIST = {
    "00000000-0000-0000-0000-000000000001",  # Global (XG)
    "00000000-0000-0000-0000-000000000002",  # Argentina (AR)
    "00000000-0000-0000-0000-000000000003",  # Peru (PE)
    "00000000-0000-0000-0000-000000000004",  # US
    "00000000-0000-0000-0000-000000000005",  # Chile (CL)
    "00000000-0000-0000-0000-000000000006",  # Mexico (MX)
    "00000000-0000-0000-0000-000000000007",  # Brazil (BR)
}


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate markets (same country_code, no canonical_key).

    Each group is a dict:
        {
            "country_code": str,
            "market_ids": [str, ...],   # oldest first
            "keep_market_id": str,      # market_id to retain
            "archive_market_ids": [str, ...],  # market_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            country_code,
            array_agg(market_id::text ORDER BY created_date ASC) AS market_ids
        FROM core.market_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY country_code
        HAVING COUNT(*) > 1
        ORDER BY country_code
        """
    )
    rows = cursor.fetchall()
    groups = []
    for country_code, market_ids in rows:
        # Exclude system-seeded markets from archival candidates
        archive_candidates = [mid for mid in market_ids[1:] if mid not in SYSTEM_MARKET_SKIP_LIST]
        if not archive_candidates:
            continue
        groups.append(
            {
                "country_code": country_code,
                "market_ids": market_ids,
                "keep_market_id": market_ids[0],
                "archive_market_ids": archive_candidates,
            }
        )
    return groups


def archive_markets(cursor, market_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given market_ids.  Returns the count archived."""
    if not market_ids:
        return 0
    if dry_run:
        return len(market_ids)
    cursor.execute(
        """
        UPDATE core.market_info
        SET is_archived = TRUE,
            status = 'inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE market_id = ANY(%s::uuid[])
          AND is_archived = FALSE
          AND market_id != ALL(%s::uuid[])
        """,
        (SYSTEM_USER_ID, market_ids, list(SYSTEM_MARKET_SKIP_LIST)),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate markets found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_market_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"country_code={group['country_code']} "
                    f"(keeping {group['keep_market_id']})"
                )
                archived = archive_markets(cur, group["archive_market_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} market(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} market(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate market rows (keep oldest per country_code)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without writing to the database.",
    )
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Could not connect to database: {exc}", file=sys.stderr)
        print("Set DATABASE_URL or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD env vars.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
