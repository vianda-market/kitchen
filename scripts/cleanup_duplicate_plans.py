#!/usr/bin/env python3
"""
Cleanup script: archive duplicate plan rows, keeping one canonical row per market.

Problem context (issue #130):
    Postman collections were POSTing to /api/v1/plans on every run without
    cleanup, accumulating many copies of functionally identical plans
    (e.g. dozens of "Argentina Plan A" rows at 10 ARS).  These clutter the
    admin UI and the 10 ARS price violates Stripe's minimum-charge requirement.

What this script does:
    For each market, finds all plan rows that share the same (market_id, name)
    pair.  It keeps the OLDEST row (by created_date) and soft-deletes the rest
    by setting is_archived = TRUE.

    Plans with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_plans.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_plans.py

    # Or via make (if you add a target):
    make cleanup-plans

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_plans.py
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
    Return groups of duplicate plans (same market_id + name, no canonical_key).

    Each group is a dict:
        {
            "market_id": str,
            "name": str,
            "plan_ids": [str, ...],   # oldest first
            "keep_plan_id": str,      # plan_id to retain
            "archive_plan_ids": [str, ...],  # plan_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            market_id::text,
            name,
            array_agg(plan_id::text ORDER BY created_date ASC) AS plan_ids
        FROM customer.plan_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY market_id, name
        HAVING COUNT(*) > 1
        ORDER BY market_id, name
        """
    )
    rows = cursor.fetchall()
    groups = []
    for market_id, name, plan_ids in rows:
        groups.append(
            {
                "market_id": market_id,
                "name": name,
                "plan_ids": plan_ids,
                "keep_plan_id": plan_ids[0],
                "archive_plan_ids": plan_ids[1:],
            }
        )
    return groups


def archive_plans(cursor, plan_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given plan_ids.  Returns the count archived."""
    if not plan_ids:
        return 0
    if dry_run:
        return len(plan_ids)
    cursor.execute(
        """
        UPDATE customer.plan_info
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE plan_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, plan_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate plans found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_plan_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"market={group['market_id']} name='{group['name']}' "
                    f"(keeping {group['keep_plan_id']})"
                )
                archived = archive_plans(cur, group["archive_plan_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} plan(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} plan(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive duplicate plan rows (keep oldest per market+name)")
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
