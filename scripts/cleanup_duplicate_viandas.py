#!/usr/bin/env python3
"""
Cleanup script: archive duplicate vianda rows, keeping one canonical row per restaurant+product.

Problem context (issue #166):
    Postman collections were POSTing to /api/v1/viandas on every run without
    cleanup, accumulating many copies of functionally identical viandas
    (e.g. dozens of rows for the same product at the same restaurant).
    These clutter the admin UI and the supplier's vianda list.

What this script does:
    For each restaurant, finds all vianda rows that share the same
    (restaurant_id, product_id) pair.  It keeps the OLDEST row (by
    created_date) and soft-deletes the rest by setting is_archived = TRUE.

    Viandas with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_viandas.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_viandas.py

    # Or via make (if you add a target):
    make cleanup-viandas

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_viandas.py
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
    Return groups of duplicate viandas (same restaurant_id + product_id, no canonical_key).

    Each group is a dict:
        {
            "restaurant_id": str,
            "product_id": str,
            "vianda_ids": [str, ...],   # oldest first
            "keep_vianda_id": str,      # vianda_id to retain
            "archive_vianda_ids": [str, ...],  # vianda_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            restaurant_id::text,
            product_id::text,
            array_agg(vianda_id::text ORDER BY created_date ASC) AS vianda_ids
        FROM ops.vianda_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY restaurant_id, product_id
        HAVING COUNT(*) > 1
        ORDER BY restaurant_id, product_id
        """
    )
    rows = cursor.fetchall()
    groups = []
    for restaurant_id, product_id, vianda_ids in rows:
        groups.append(
            {
                "restaurant_id": restaurant_id,
                "product_id": product_id,
                "vianda_ids": vianda_ids,
                "keep_vianda_id": vianda_ids[0],
                "archive_vianda_ids": vianda_ids[1:],
            }
        )
    return groups


def archive_viandas(cursor, vianda_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given vianda_ids.  Returns the count archived."""
    if not vianda_ids:
        return 0
    if dry_run:
        return len(vianda_ids)
    cursor.execute(
        """
        UPDATE ops.vianda_info
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE vianda_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, vianda_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate viandas found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_vianda_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"restaurant={group['restaurant_id']} product={group['product_id']} "
                    f"(keeping {group['keep_vianda_id']})"
                )
                archived = archive_viandas(cur, group["archive_vianda_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} vianda(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} vianda(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate vianda rows (keep oldest per restaurant+product)")
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
