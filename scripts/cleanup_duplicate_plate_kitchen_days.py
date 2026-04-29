#!/usr/bin/env python3
"""
Cleanup script: archive duplicate plate kitchen day rows, keeping one canonical
row per (plate_id, kitchen_day) combination.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/plate-kitchen-days on every run
    without cleanup, accumulating many copies of functionally identical scheduling
    rows (e.g. multiple active rows for the same plate on Monday).
    The unique constraint only covers non-archived rows, so archived duplicates
    cannot be re-activated without colliding, and the accumulation pollutes
    the explore / selection flows.

What this script does:
    For each (plate_id, kitchen_day) combination, finds all non-archived rows
    with no canonical_key.  It keeps the OLDEST row (by created_date) and
    soft-deletes the rest by setting is_archived = TRUE.

    Rows with a canonical_key are left untouched — they are managed by the
    PUT /plate-kitchen-days/by-key upsert endpoint and do not need cleanup.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_plate_kitchen_days.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_plate_kitchen_days.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_plate_kitchen_days.py
"""

import argparse
import os
import sys

import psycopg2
import psycopg2.extras


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


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate plate kitchen days (same plate_id + kitchen_day,
    no canonical_key, not archived).

    Each group is a dict:
        {
            "plate_id": str,
            "kitchen_day": str,
            "pkd_ids": [str, ...],           # oldest first
            "keep_pkd_id": str,              # plate_kitchen_day_id to retain
            "archive_pkd_ids": [str, ...],   # plate_kitchen_day_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            plate_id::text,
            kitchen_day,
            array_agg(plate_kitchen_day_id::text ORDER BY created_date ASC) AS pkd_ids
        FROM ops.plate_kitchen_days
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY plate_id, kitchen_day
        HAVING COUNT(*) > 1
        ORDER BY plate_id, kitchen_day
        """
    )
    rows = cursor.fetchall()
    groups = []
    for plate_id, kitchen_day, pkd_ids in rows:
        groups.append(
            {
                "plate_id": plate_id,
                "kitchen_day": kitchen_day,
                "pkd_ids": pkd_ids,
                "keep_pkd_id": pkd_ids[0],
                "archive_pkd_ids": pkd_ids[1:],
            }
        )
    return groups


def archive_plate_kitchen_days(cursor, pkd_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given plate_kitchen_day_ids.  Returns the count archived."""
    if not pkd_ids:
        return 0
    if dry_run:
        return len(pkd_ids)
    cursor.execute(
        """
        UPDATE ops.plate_kitchen_days
        SET is_archived = TRUE,
            status = 'inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE plate_kitchen_day_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, pkd_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    psycopg2.extras.register_uuid()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate plate kitchen days found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_pkd_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"plate_id={group['plate_id']} "
                    f"kitchen_day={group['kitchen_day']} "
                    f"(keeping {group['keep_pkd_id']})"
                )
                archived = archive_plate_kitchen_days(cur, group["archive_pkd_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} plate kitchen day(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} plate kitchen day(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive duplicate plate kitchen day rows (keep oldest per plate_id+kitchen_day)"
    )
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
