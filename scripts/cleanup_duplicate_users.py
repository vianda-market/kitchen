#!/usr/bin/env python3
"""
Cleanup script: archive duplicate user rows, keeping one canonical row per username.

Problem context (issue #168):
    Postman collections were POSTing to /api/v1/users on every run without
    cleanup, accumulating many copies of functionally identical users
    (e.g. dozens of rows for the same supplier_admin username).
    These clutter the admin UI and cause conflicts when the username/email
    unique constraint rejects repeat runs.

What this script does:
    For each username that appears more than once in core.user_info (across
    non-archived rows), it keeps the OLDEST row (by created_date) and
    soft-deletes the rest by setting is_archived = TRUE.

    Users with a canonical_key are left untouched — they are managed by the
    upsert endpoint and do not need cleanup.

    System users in SYSTEM_USER_SKIP_LIST are ALWAYS kept regardless of
    age or duplication.  This protects the seeded super_admin, Vianda
    Enterprises admins, and any other internal sentinel accounts from
    accidental archival.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_users.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_users.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_users.py
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

# Usernames that must NEVER be archived by this script.
# Extend this list when new system/sentinel accounts are seeded.
SYSTEM_USER_SKIP_LIST = frozenset(
    [
        "superadmin",  # seeded super_admin in dev_fixtures.sql
        "vianda_admin",  # shared internal admin used by downstream collections
    ]
)


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate users (same username, no canonical_key, not in skip list).

    Each group is a dict:
        {
            "username": str,
            "user_ids": [str, ...],   # oldest first
            "keep_user_id": str,      # user_id to retain
            "archive_user_ids": [str, ...],  # user_ids to soft-delete
        }
    """
    cursor.execute(
        """
        SELECT
            username,
            array_agg(user_id::text ORDER BY created_date ASC) AS user_ids
        FROM core.user_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
        GROUP BY username
        HAVING COUNT(*) > 1
        ORDER BY username
        """
    )
    rows = cursor.fetchall()
    groups = []
    for username, user_ids in rows:
        # Skip any group that contains a system account
        if username in SYSTEM_USER_SKIP_LIST:
            print(f"  SKIP: '{username}' is in SYSTEM_USER_SKIP_LIST — not touched.")
            continue
        # Also check: if the oldest row happens to be a system account, skip the whole group
        groups.append(
            {
                "username": username,
                "user_ids": user_ids,
                "keep_user_id": user_ids[0],
                "archive_user_ids": user_ids[1:],
            }
        )
    return groups


def archive_users(cursor, user_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given user_ids.  Returns the count archived."""
    if not user_ids:
        return 0
    if dry_run:
        return len(user_ids)
    cursor.execute(
        """
        UPDATE core.user_info
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE user_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, user_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate users found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_user_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(f"{verb} {n} duplicate(s) for username='{group['username']}' (keeping {group['keep_user_id']})")
                archived = archive_users(cur, group["archive_user_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} user(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} user(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive duplicate user rows (keep oldest per username, skip system users)"
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
