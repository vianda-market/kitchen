#!/usr/bin/env python3
"""
Cleanup script: archive duplicate QR code rows, keeping one canonical row per restaurant_id.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/qr-codes on every run without
    cleanup, accumulating many copies of QR codes for the same restaurant.
    These create ambiguity in kiosk scans and inflate the QR code table.

What this script does:
    For each restaurant_id, finds all non-archived QR code rows with no
    canonical_key.  It keeps the NEWEST row (by created_date — the most
    recently generated QR code is the active one) and soft-deletes the rest
    by setting is_archived = TRUE.

    QR codes with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_qr_codes.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_qr_codes.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/kitchen"
    python scripts/cleanup_duplicate_qr_codes.py
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
        dbname=os.environ.get("DB_NAME", "kitchen"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


# UUID of the super-admin system user used as modified_by for automated ops
SYSTEM_USER_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate QR codes (same restaurant_id, no canonical_key).

    Each group is a dict:
        {
            "restaurant_id": str,
            "qr_code_ids": [str, ...],   # newest first (keep first, archive rest)
            "keep_qr_code_id": str,
            "archive_qr_code_ids": [str, ...],
        }
    """
    cursor.execute(
        """
        SELECT
            restaurant_id::text,
            array_agg(qr_code_id::text ORDER BY created_date DESC) AS qr_code_ids
        FROM ops.qr_code
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY restaurant_id
        HAVING COUNT(*) > 1
        ORDER BY restaurant_id
        """
    )
    rows = cursor.fetchall()
    groups = []
    for restaurant_id, qr_code_ids in rows:
        # Keep newest (index 0, most recent created_date); archive the rest
        groups.append(
            {
                "restaurant_id": restaurant_id,
                "qr_code_ids": qr_code_ids,
                "keep_qr_code_id": qr_code_ids[0],
                "archive_qr_code_ids": qr_code_ids[1:],
            }
        )
    return groups


def archive_qr_codes(cursor, qr_code_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given qr_code_ids.  Returns the count archived."""
    if not qr_code_ids:
        return 0
    if dry_run:
        return len(qr_code_ids)
    cursor.execute(
        """
        UPDATE ops.qr_code
        SET is_archived = TRUE,
            status = 'inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE qr_code_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, qr_code_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate QR codes found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_qr_code_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"restaurant_id={group['restaurant_id']} "
                    f"(keeping {group['keep_qr_code_id']})"
                )
                archived = archive_qr_codes(cur, group["archive_qr_code_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} QR code(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} QR code(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate QR code rows (keep newest per restaurant_id)")
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
