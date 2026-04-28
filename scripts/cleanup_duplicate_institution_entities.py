#!/usr/bin/env python3
"""
Cleanup script: archive duplicate institution entity rows, keeping one canonical row per
institution+tax_id combination.

Problem context (issue #190):
    Postman collections were POSTing to /api/v1/institution-entities on every run without
    cleanup, accumulating many copies of functionally identical institution entities
    (e.g. dozens of rows for the same tax_id within the same institution).
    These clutter the supplier management UI.

What this script does:
    For each institution, finds all institution entity rows that share the same
    (institution_id, tax_id) pair.  It keeps the OLDEST row (by created_date)
    and soft-deletes the rest by setting is_archived = TRUE.

    Institution entities with a canonical_key are left untouched — they are
    managed by the upsert endpoint and do not need cleanup.

    The entities in SYSTEM_INSTITUTION_ENTITY_SKIP_LIST (seeded dev fixtures)
    are always preserved regardless of duplication.

    Running the script multiple times is a no-op once duplicates are gone
    (idempotent).

Usage:
    # Dry-run (preview what would be archived, no writes):
    python scripts/cleanup_duplicate_institution_entities.py --dry-run

    # Live run:
    python scripts/cleanup_duplicate_institution_entities.py

Prerequisites:
    DATABASE_URL env var (or the same DB env vars the app uses) must point to
    the target database.  The app's normal DB pool is NOT used here — this
    script opens a direct psycopg2 connection so it can be run without the
    FastAPI stack being up.

    export DATABASE_URL="postgresql://user:pass@localhost:5432/vianda_dev"
    python scripts/cleanup_duplicate_institution_entities.py
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

# Institution entity IDs that are seeded dev fixtures and must never be archived.
# Add new entries here when new system/sentinel entities are added to dev_fixtures.sql.
SYSTEM_INSTITUTION_ENTITY_SKIP_LIST = [
    "aaaaaaaa-aaaa-0001-0000-000000000002",  # Mercado Vianda BA Entidad (dev fixture)
]


def find_duplicate_groups(cursor) -> list[dict]:
    """
    Return groups of duplicate institution entities (same institution_id + tax_id, no canonical_key).

    Each group is a dict:
        {
            "institution_id": str,
            "tax_id": str,
            "entity_ids": [str, ...],    # oldest first
            "keep_entity_id": str,       # entity_id to retain
            "archive_entity_ids": [str, ...],  # entity_ids to soft-delete
        }
    """
    skip_placeholders = (
        ", ".join(["%s"] * len(SYSTEM_INSTITUTION_ENTITY_SKIP_LIST)) if SYSTEM_INSTITUTION_ENTITY_SKIP_LIST else "NULL"
    )
    skip_clause = (
        f"AND institution_entity_id::text NOT IN ({skip_placeholders})" if SYSTEM_INSTITUTION_ENTITY_SKIP_LIST else ""
    )

    query = f"""
        SELECT
            institution_id::text,
            tax_id,
            array_agg(institution_entity_id::text ORDER BY created_date ASC) AS entity_ids
        FROM ops.institution_entity_info
        WHERE is_archived = FALSE
          AND canonical_key IS NULL
          {skip_clause}
        GROUP BY institution_id, tax_id
        HAVING COUNT(*) > 1
        ORDER BY institution_id, tax_id
    """
    cursor.execute(query, SYSTEM_INSTITUTION_ENTITY_SKIP_LIST if SYSTEM_INSTITUTION_ENTITY_SKIP_LIST else [])
    rows = cursor.fetchall()
    groups = []
    for institution_id, tax_id, entity_ids in rows:
        groups.append(
            {
                "institution_id": institution_id,
                "tax_id": tax_id,
                "entity_ids": entity_ids,
                "keep_entity_id": entity_ids[0],
                "archive_entity_ids": entity_ids[1:],
            }
        )
    return groups


def archive_entities(cursor, entity_ids: list[str], dry_run: bool) -> int:
    """Soft-delete the given institution_entity_ids.  Returns the count archived."""
    if not entity_ids:
        return 0
    if dry_run:
        return len(entity_ids)
    cursor.execute(
        """
        UPDATE ops.institution_entity_info
        SET is_archived = TRUE,
            modified_date = CURRENT_TIMESTAMP,
            modified_by = %s::uuid
        WHERE institution_entity_id = ANY(%s::uuid[])
          AND is_archived = FALSE
        """,
        (SYSTEM_USER_ID, entity_ids),
    )
    return cursor.rowcount


def run(dry_run: bool = False) -> None:
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            groups = find_duplicate_groups(cur)

            if not groups:
                print("No duplicate institution entities found — database is clean.")
                return

            total_archived = 0
            for group in groups:
                n = len(group["archive_entity_ids"])
                verb = "Would archive" if dry_run else "Archiving"
                print(
                    f"{verb} {n} duplicate(s) for "
                    f"institution={group['institution_id']} tax_id={group['tax_id']} "
                    f"(keeping {group['keep_entity_id']})"
                )
                archived = archive_entities(cur, group["archive_entity_ids"], dry_run)
                total_archived += archived

            if dry_run:
                print(f"\nDry-run complete: {total_archived} institution entity(s) would be archived.")
                conn.rollback()
            else:
                conn.commit()
                print(f"\nDone: {total_archived} institution entity(s) archived.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive duplicate institution entity rows (keep oldest per institution+tax_id)"
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
