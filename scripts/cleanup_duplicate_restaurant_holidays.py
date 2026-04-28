#!/usr/bin/env python3
"""
Cleanup script: archive duplicate restaurant holiday rows, keeping one canonical row
per (restaurant_id, holiday_date) pair.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/restaurant-holidays on every run
    without cleanup, accumulating many copies of functionally identical holidays
    (e.g. multiple rows for the same restaurant_id + holiday_date).
    These cause data integrity issues since the active unique index
    idx_restaurant_holidays_restaurant_date_active enforces uniqueness only for
    non-archived rows.

What this script does:
    For each (restaurant_id, holiday_date), finds all holiday rows that share the
    same pair with no canonical_key.  It keeps the OLDEST row (by created_date)
    and soft-deletes the rest by setting is_archived = TRUE.

    Holidays with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_restaurant_holidays.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_restaurant_holidays.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_restaurant_holidays.py
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


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate restaurant holidays (same restaurant_id+holiday_date, no canonical_key).

    Each group is a dict:
        {
            "restaurant_id": str,
            "holiday_date": str,
            "holiday_ids": [str, ...],    # oldest first
            "keep_holiday_id": str,       # holiday_id to retain
            "archive_holiday_ids": [str, ...],  # holiday_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            restaurant_id::text,
            holiday_date::text,
            array_agg(holiday_id::text ORDER BY created_date ASC) AS holiday_ids
        FROM ops.restaurant_holidays
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY restaurant_id, holiday_date
        HAVING COUNT(*) > 1
        ORDER BY restaurant_id, holiday_date
        """
    )
    rows = cursor.fetchall()
    groups = []
    for restaurant_id, holiday_date, holiday_ids in rows:
        keep = holiday_ids[0]
        archive_candidates = holiday_ids[1:]
        if not archive_candidates:
            continue
        groups.append(
            {
                "restaurant_id": restaurant_id,
                "holiday_date": holiday_date,
                "holiday_ids": holiday_ids,
                "keep_holiday_id": keep,
                "archive_holiday_ids": archive_candidates,
            }
        )
    return groups


def archive_holidays(cursor, holiday_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given holiday_ids.  Returns the count archived."""
    if not holiday_ids:
        return 0
    if dry_run:
        return len(holiday_ids)
    cursor.execute(
        """
        UPDATE ops.restaurant_holidays
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE holiday_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, holiday_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate restaurant holidays found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_holiday_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"restaurant_id={group['restaurant_id']} "
                    f"holiday_date={group['holiday_date']} "
                    f"(keeping {group['keep_holiday_id']})"
                )
                archived = archive_holidays(cur, group["archive_holiday_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} restaurant holiday(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} restaurant holiday(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive duplicate restaurant holiday rows (keep oldest per restaurant_id+holiday_date)"
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
    except psycopg2.Error as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
