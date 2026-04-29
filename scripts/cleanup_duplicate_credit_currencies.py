#!/usr/bin/env python3
"""
Cleanup script: archive duplicate credit currency rows, keeping one canonical row per currency_code.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/credit-currencies on every run without
    cleanup, accumulating many copies of functionally identical currencies
    (e.g. multiple rows for currency_code='ARS').
    These cause data integrity issues since currency_code has a UNIQUE constraint —
    in practice duplicates manifest as 409 errors that get silently swallowed,
    and the GET fallback in old collections left leftover rows from prior test runs.

What this script does:
    For each currency_code, finds all currency_metadata rows that share the same
    currency_code with no canonical_key.  It keeps the OLDEST row (by created_date)
    and soft-deletes the rest by setting is_archived = TRUE.

    Currencies with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    The following seeded currencies are hard-skipped and will NEVER be archived,
    regardless of duplication:

        55555555-5555-5555-5555-555555555555  (USD — seeded in reference_data.sql)
        66666666-6666-6666-6666-666666666601  (ARS — seeded in reference_data.sql)
        66666666-6666-6666-6666-666666666602  (PEN — seeded in reference_data.sql)
        66666666-6666-6666-6666-666666666603  (CLP — seeded in reference_data.sql)
        66666666-6666-6666-6666-666666666604  (MXN — seeded in reference_data.sql)
        66666666-6666-6666-6666-666666666605  (BRL — seeded in reference_data.sql)

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_credit_currencies.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_credit_currencies.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_credit_currencies.py
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

# Seeded currencies that must never be archived — these are canonical reference rows
# defined in app/db/seed/reference_data.sql.
SYSTEM_CREDIT_CURRENCY_SKIP_LIST = {
    "55555555-5555-5555-5555-555555555555",  # USD
    "66666666-6666-6666-6666-666666666601",  # ARS
    "66666666-6666-6666-6666-666666666602",  # PEN
    "66666666-6666-6666-6666-666666666603",  # CLP
    "66666666-6666-6666-6666-666666666604",  # MXN
    "66666666-6666-6666-6666-666666666605",  # BRL
}


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate credit currencies (same currency_code, no canonical_key).

    Each group is a dict:
        {
            "currency_code": str,
            "currency_ids": [str, ...],        # oldest first
            "keep_currency_id": str,           # currency_metadata_id to retain
            "archive_currency_ids": [str, ...],  # currency_metadata_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            currency_code,
            array_agg(currency_metadata_id::text ORDER BY created_date ASC) AS currency_ids
        FROM core.currency_metadata
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY currency_code
        HAVING COUNT(*) > 1
        ORDER BY currency_code
        """
    )
    rows = cursor.fetchall()
    groups = []
    for currency_code, currency_ids in rows:
        # Exclude system-seeded currencies from archival candidates
        archive_candidates = [cid for cid in currency_ids[1:] if cid not in SYSTEM_CREDIT_CURRENCY_SKIP_LIST]
        if not archive_candidates:
            continue
        groups.append(
            {
                "currency_code": currency_code,
                "currency_ids": currency_ids,
                "keep_currency_id": currency_ids[0],
                "archive_currency_ids": archive_candidates,
            }
        )
    return groups


def archive_currencies(cursor, currency_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given currency_metadata_ids. Returns the count archived."""
    if not currency_ids:
        return 0
    if dry_run:
        return len(currency_ids)
    cursor.execute(
        """
        UPDATE core.currency_metadata
        SET is_archived = TRUE,
            status = 'inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE currency_metadata_id = ANY(%s::uuid[])
          AND is_archived = FALSE
          AND currency_metadata_id != ALL(%s::uuid[])
        """,
        (SYSTEM_USER_ID, currency_ids, list(SYSTEM_CREDIT_CURRENCY_SKIP_LIST)),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate credit currencies found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_currency_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"currency_code={group['currency_code']} "
                    f"(keeping {group['keep_currency_id']})"
                )
                archived = archive_currencies(cur, group["archive_currency_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} credit currency(ies) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} credit currency(ies) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive duplicate credit currency rows (keep oldest per currency_code)"
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
