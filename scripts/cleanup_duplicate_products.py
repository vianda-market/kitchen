#!/usr/bin/env python3
"""
Cleanup script: archive duplicate product rows, keeping one canonical row per institution+name.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/products on every run without
    cleanup, accumulating many copies of functionally identical products
    (e.g. dozens of rows for "Big Burguer" owned by the same institution).
    These clutter the supplier's product list and the admin UI.

What this script does:
    For each institution, finds all product rows that share the same
    (institution_id, name) pair with no canonical_key.  It keeps the OLDEST
    row (by created_date) and soft-deletes the rest by setting is_archived = TRUE.

    Products with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_products.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_products.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_products.py
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
    Return groups of duplicate products (same institution_id + name, no canonical_key).

    Each group is a dict:
        {
            "institution_id": str,
            "name": str,
            "product_ids": [str, ...],   # oldest first
            "keep_product_id": str,      # product_id to retain
            "archive_product_ids": [str, ...],  # product_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            institution_id::text,
            name,
            array_agg(product_id::text ORDER BY created_date ASC) AS product_ids
        FROM ops.product_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY institution_id, name
        HAVING COUNT(*) > 1
        ORDER BY institution_id, name
        """
    )
    rows = cursor.fetchall()
    groups = []
    for institution_id, name, product_ids in rows:
        groups.append(
            {
                "institution_id": institution_id,
                "name": name,
                "product_ids": product_ids,
                "keep_product_id": product_ids[0],
                "archive_product_ids": product_ids[1:],
            }
        )
    return groups


def archive_products(cursor, product_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given product_ids.  Returns the count archived."""
    if not product_ids:
        return 0
    if dry_run:
        return len(product_ids)
    cursor.execute(
        """
        UPDATE ops.product_info
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE product_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, product_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate products found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_product_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"institution={group['institution_id']} name={group['name']!r} "
                    f"(keeping {group['keep_product_id']})"
                )
                archived = archive_products(cur, group["archive_product_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} product(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} product(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate product rows (keep oldest per institution+name)")
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
