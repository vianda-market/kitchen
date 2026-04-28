#!/usr/bin/env python3
"""
Cleanup script: archive duplicate institution rows, keeping one canonical row per name.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/institutions on every run without
    cleanup, accumulating many copies of functionally identical institutions
    (e.g. dozens of rows named "Postman Test" as supplier institutions).
    These clutter the admin UI and the supplier list.

What this script does:
    For each institution type, finds all institution rows that share the same
    name.  It keeps the OLDEST row (by created_date) and soft-deletes the rest
    by setting is_archived = TRUE.

    Institutions with a canonical_key are left untouched — they are managed by
    the upsert endpoint and do not need cleanup.

    The following system institutions are always preserved regardless of any
    duplication check:
      - 11111111-1111-1111-1111-111111111111 (Vianda Enterprises)
      - 22222222-2222-2222-2222-222222222222 (Vianda Customers)
      - aaaaaaaa-aaaa-0001-0000-000000000001 (dev fixture: Mercado Vianda BA)

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_institutions.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_institutions.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_institutions.py
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

# Institutions that must never be archived, regardless of duplication.
# These are seeded system institutions critical to the platform's operation.
SYSTEM_INSTITUTION_SKIP_LIST = frozenset(
    {
        "11111111-1111-1111-1111-111111111111",  # Vianda Enterprises (internal)
        "22222222-2222-2222-2222-222222222222",  # Vianda Customers (customer group)
        "aaaaaaaa-aaaa-0001-0000-000000000001",  # Dev fixture: Mercado Vianda BA (supplier)
    }
)


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate institutions (same name, no canonical_key).

    Each group is a dict:
        {
            "name": str,
            "institution_ids": [str, ...],   # oldest first
            "keep_institution_id": str,      # institution_id to retain
            "archive_institution_ids": [str, ...],  # institution_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            name,
            array_agg(institution_id::text ORDER BY created_date ASC) AS institution_ids
        FROM core.institution_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY name
        HAVING COUNT(*) > 1
        ORDER BY name
        """
    )
    rows = cursor.fetchall()
    groups = []
    for name, institution_ids in rows:
        # Filter out system institutions from all positions
        safe_ids = [iid for iid in institution_ids if iid not in SYSTEM_INSTITUTION_SKIP_LIST]
        if len(safe_ids) <= 1:
            continue
        groups.append(
            {
                "name": name,
                "institution_ids": safe_ids,
                "keep_institution_id": safe_ids[0],
                "archive_institution_ids": safe_ids[1:],
            }
        )
    return groups


def archive_institutions(cursor, institution_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given institution_ids.  Returns the count archived."""
    if not institution_ids:
        return 0
    if dry_run:
        return len(institution_ids)
    cursor.execute(
        """
        UPDATE core.institution_info
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE institution_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, institution_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate institutions found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_institution_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(f"{verb} {n} duplicate(s) for name={group['name']!r} (keeping {group['keep_institution_id']})")
                archived = archive_institutions(cur, group["archive_institution_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} institution(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} institution(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate institution rows (keep oldest per name)")
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
