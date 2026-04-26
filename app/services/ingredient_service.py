"""
Ingredient Service

Local-first ingredient search with OFF fallback, custom ingredient creation,
and product ingredient CRUD (full-replace pattern).

Search order:
  1. Query local ingredient_catalog (verified + unverified)
  2. Count verified rows — if >= OFF_LOCAL_MIN_VERIFIED_RESULTS, return immediately
  3. Otherwise call OFF suggest + taxonomy, upsert results, re-query local DB
  4. Return image_url directly (full URL stored by Wikidata enrichment cron)
  5. Apply dialect alias per market_id if present in ingredient_alias
"""

import logging
from uuid import UUID

from fastapi import HTTPException

from app.config.settings import settings  # OFF_ENABLED, OFF_LOCAL_MIN_VERIFIED_RESULTS
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.open_food_facts_service import (
    resolve_off_taxonomy,
    search_off_suggestions,
)
from app.utils.db import db_read

logger = logging.getLogger(__name__)

# Canonical schema prefix for all ingredient tables
_SCHEMA = "ops"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_ingredients(
    query: str,
    lang: str,
    market_id: str | None,
    db,
) -> list[dict]:
    """
    Search ingredient_catalog. Falls back to OFF when verified results < threshold.

    Args:
        query: Raw search string (2–100 chars)
        lang:  Language code — 'es' | 'en' | 'pt'
        market_id: User's market_id for dialect alias lookup (may be None)
        db: psycopg2 connection

    Returns:
        List of dicts matching IngredientSearchResultSchema shape.
    """
    normalized = query.lower().strip()

    local_rows = _query_local(normalized, market_id, db)
    verified_count = sum(1 for r in local_rows if r["is_verified"])

    if not settings.OFF_ENABLED or verified_count >= settings.OFF_LOCAL_MIN_VERIFIED_RESULTS:
        return [_format_result(r) for r in local_rows]

    # Attempt OFF enrichment
    suggestions = search_off_suggestions(normalized, lang)
    if suggestions:
        resolved = resolve_off_taxonomy(suggestions, lang)
        _upsert_off_entries(resolved, db)
        local_rows = _query_local(normalized, market_id, db)

    return [_format_result(r) for r in local_rows]


def _query_local(query: str, market_id: str | None, db) -> list[dict]:
    """
    Query ingredient_catalog with optional alias join, ordered by verified/enriched.
    Applies dialect alias override when market_id is provided.
    """
    sql = """
        SELECT
            ic.ingredient_id,
            ic.name_display,
            ic.name_en,
            ic.off_taxonomy_id,
            ic.image_url,
            ic.source,
            ic.is_verified,
            ic.image_enriched,
            COALESCE(ia.alias, ic.name_display) AS display_label
        FROM ops.ingredient_catalog ic
        LEFT JOIN ops.ingredient_alias ia
            ON ia.ingredient_id = ic.ingredient_id
            AND ia.region_code = %s
        WHERE
            ic.name ILIKE %s
            OR ic.name_es ILIKE %s
            OR ic.name_en ILIKE %s
            OR ic.name_pt ILIKE %s
            OR ia.alias ILIKE %s
        ORDER BY ic.is_verified DESC, ic.image_enriched DESC
        LIMIT 10
    """
    pattern = f"%{query}%"
    params = (market_id, pattern, pattern, pattern, pattern, pattern)
    rows = db_read(sql, params, connection=db)
    return rows if rows else []


def _format_result(row: dict) -> dict:
    """Assemble IngredientSearchResultSchema-shaped dict from a DB row."""
    return {
        "ingredient_id": row["ingredient_id"],
        "name_display": row.get("display_label") or row["name_display"],
        "name_en": row.get("name_en"),
        "off_taxonomy_id": row.get("off_taxonomy_id"),
        "image_url": row.get("image_url"),
        "source": row["source"],
        "is_verified": row["is_verified"],
        "image_enriched": row["image_enriched"],
    }


def _upsert_off_entries(resolved: list[dict], db) -> None:
    """
    Insert resolved OFF entries into ingredient_catalog.
    Uses ON CONFLICT (name) DO NOTHING — never overwrites existing entries.
    modified_by is set to the system user UUID.
    """
    if not resolved:
        return

    system_user_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    sql = """
        INSERT INTO ops.ingredient_catalog
            (name, name_display, name_es, name_en, name_pt,
             off_taxonomy_id, source, modified_by)
        VALUES (%s, %s, %s, %s, %s, %s, 'off', %s)
        ON CONFLICT (name) DO NOTHING
    """
    try:
        cursor = db.cursor()
        for entry in resolved:
            cursor.execute(
                sql,
                (
                    entry["name"],
                    entry["name_display"],
                    entry.get("name_es"),
                    entry.get("name_en"),
                    entry.get("name_pt"),
                    entry.get("off_taxonomy_id"),
                    system_user_id,
                ),
            )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("OFF upsert failed: %s", exc)


# ---------------------------------------------------------------------------
# Custom ingredient creation
# ---------------------------------------------------------------------------


def create_custom_ingredient(name: str, lang: str, user_id: UUID, db) -> dict:
    """
    Create a custom ingredient (source='custom', is_verified=False).
    Returns existing entry if name already exists (case-insensitive).
    """
    normalized = name.lower().strip()

    # Check for existing entry
    existing_sql = """
        SELECT ingredient_id, name_display, name_en, off_taxonomy_id,
               image_url, source, is_verified, image_enriched
        FROM ops.ingredient_catalog
        WHERE name = %s
    """
    existing = db_read(existing_sql, (normalized,), connection=db, fetch_one=True)
    if existing:
        return _format_result({**existing, "display_label": existing["name_display"]})

    # Insert new custom entry, populating the appropriate language column
    name_es = normalized if lang == "es" else None
    name_en = normalized if lang == "en" else None
    name_pt = normalized if lang == "pt" else None

    insert_sql = """
        INSERT INTO ops.ingredient_catalog
            (name, name_display, name_es, name_en, name_pt,
             source, is_verified, image_enriched, image_skipped, modified_by)
        VALUES (%s, %s, %s, %s, %s, 'custom', FALSE, FALSE, FALSE, %s)
        RETURNING ingredient_id, name_display, name_en, off_taxonomy_id,
                  image_url, source, is_verified, image_enriched
    """
    try:
        cursor = db.cursor()
        cursor.execute(
            insert_sql,
            (
                normalized,
                name,
                name_es,
                name_en,
                name_pt,
                str(user_id),
            ),
        )
        row = cursor.fetchone()
        db.commit()
        if row is None:
            raise HTTPException(status_code=500, detail="Failed to create ingredient")
        # Build dict from RETURNING columns
        columns = [
            "ingredient_id",
            "name_display",
            "name_en",
            "off_taxonomy_id",
            "image_url",
            "source",
            "is_verified",
            "image_enriched",
        ]
        result_row = dict(zip(columns, row, strict=False))
        return _format_result({**result_row, "display_label": result_row["name_display"]})
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Custom ingredient creation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create ingredient") from None


# ---------------------------------------------------------------------------
# Product ingredient CRUD
# ---------------------------------------------------------------------------


def get_product_ingredients(
    product_id: UUID,
    market_id: str | None,
    db,
) -> list[dict]:
    """
    Return ordered list of ingredients for a product, with dialect alias applied.
    """
    sql = """
        SELECT
            pi.product_ingredient_id,
            pi.ingredient_id,
            COALESCE(ia.alias, ic.name_display) AS name_display,
            ic.name_en,
            ic.image_url,
            pi.sort_order
        FROM ops.product_ingredient pi
        JOIN ops.ingredient_catalog ic
            ON ic.ingredient_id = pi.ingredient_id
        LEFT JOIN ops.ingredient_alias ia
            ON ia.ingredient_id = ic.ingredient_id
            AND ia.region_code = %s
        WHERE pi.product_id = %s
        ORDER BY pi.sort_order ASC
    """
    rows = db_read(sql, (market_id, str(product_id)), connection=db)
    return [_format_product_ingredient(r) for r in (rows or [])]


def set_product_ingredients(
    product_id: UUID,
    ingredient_ids: list[UUID],
    user_id: UUID,
    market_id: str | None,
    db,
    *,
    commit: bool = True,
) -> list[dict]:
    """
    Full-replace: delete existing product ingredients, then insert provided list.
    Verifies each ingredient_id exists (404 on first missing).
    Returns updated ingredient list ordered by sort_order.

    Args:
        commit: Whether to commit immediately (default: True).
                Set to False for atomic multi-operation transactions.
    """
    # Verify all ingredient_ids exist
    for iid in ingredient_ids:
        check_sql = """
            SELECT 1 FROM ops.ingredient_catalog WHERE ingredient_id = %s
        """
        row = db_read(check_sql, (str(iid),), connection=db, fetch_one=True)
        if not row:
            raise envelope_exception(
                ErrorCode.INGREDIENT_NOT_FOUND,
                status=404,
                locale="en",
                ingredient_id=str(iid),
            )

    try:
        cursor = db.cursor()

        # Delete existing
        cursor.execute(
            "DELETE FROM ops.product_ingredient WHERE product_id = %s",
            (str(product_id),),
        )

        # Insert new with sort_order = list index
        insert_sql = """
            INSERT INTO ops.product_ingredient
                (product_id, ingredient_id, sort_order, modified_by)
            VALUES (%s, %s, %s, %s)
        """
        for idx, iid in enumerate(ingredient_ids):
            cursor.execute(
                insert_sql,
                (
                    str(product_id),
                    str(iid),
                    idx,
                    str(user_id),
                ),
            )

        if commit:
            db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("set_product_ingredients failed for product %s: %s", product_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update product ingredients") from None

    return get_product_ingredients(product_id, market_id, db)


def _format_product_ingredient(row: dict) -> dict:
    """Assemble ProductIngredientResponseSchema-shaped dict from a DB row."""
    return {
        "product_ingredient_id": row["product_ingredient_id"],
        "ingredient_id": row["ingredient_id"],
        "name_display": row["name_display"],
        "name_en": row.get("name_en"),
        "image_url": row.get("image_url"),
        "sort_order": row["sort_order"],
    }
