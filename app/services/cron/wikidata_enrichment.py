"""
Wikidata Image Enrichment Cron

Processes ops.ingredient_catalog rows where image_enriched=FALSE and off_wikidata_id IS NOT NULL.
Fetches P18 (image) claims from the Wikidata REST API, constructs Wikimedia Commons URLs,
and stores them as permanent image_url values (CC licensed, permanent storage permitted).

Batch: up to ENRICHMENT_BATCH_SIZE rows per run. Wikidata supports up to 50 entity IDs
per API request, so one HTTP call serves the whole batch.

Kill switch: WIKIDATA_ENRICHMENT_ENABLED=false (default) — cron is a no-op until activated.
No API key required. No quota limits (respect Wikidata User-Agent policy).
"""

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.config.settings import settings
from app.utils.db import db_read
from app.utils.db_pool import get_db_connection_context
from app.utils.log import log_error, log_info

logger = logging.getLogger(__name__)

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
COMMONS_FILE_PATH_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/"
USER_AGENT = "vianda/1.0 (contact@vianda.market)"
P18_IMAGE = "P18"
_HTTP_TIMEOUT = 10.0


def run_wikidata_enrichment() -> dict[str, Any]:
    """
    Entry point for Cloud Run Job / Cloud Scheduler.

    Returns summary dict:
        {status, image_enriched, image_skipped, errors}
    """
    result: dict[str, Any] = {
        "status": "ok",
        "image_enriched": 0,
        "image_skipped": 0,
        "errors": 0,
    }

    if not settings.WIKIDATA_ENRICHMENT_ENABLED:
        log_info("Wikidata enrichment: WIKIDATA_ENRICHMENT_ENABLED=false — skipping run")
        result["status"] = "disabled"
        return result

    batch_size = settings.ENRICHMENT_BATCH_SIZE

    with get_db_connection_context() as db:
        rows = _fetch_pending(db, batch_size)
        if not rows:
            log_info("Wikidata enrichment: no pending rows")
            return result

        log_info("Wikidata enrichment: processing %d rows", len(rows))

        # Build wikidata_id → row mapping for batch lookup
        id_to_rows: dict[str, dict] = {}
        for row in rows:
            wid = row["off_wikidata_id"]
            if wid:
                id_to_rows[wid] = row

        if not id_to_rows:
            log_info("Wikidata enrichment: no rows with off_wikidata_id")
            return result

        # Batch fetch P18 claims from Wikidata
        image_map = _batch_fetch_p18(list(id_to_rows.keys()))

        if image_map is None:
            # HTTP error — abort
            result["status"] = "error"
            result["errors"] = len(id_to_rows)
            log_error("Wikidata enrichment: batch API call failed — aborting")
            return result

        # Process results
        for wikidata_id, row in id_to_rows.items():
            ingredient_id = row["ingredient_id"]
            image_filename = image_map.get(wikidata_id)

            if image_filename:
                image_url = COMMONS_FILE_PATH_URL + quote(image_filename, safe="")
                _mark_enriched(db, ingredient_id, image_url)
                result["image_enriched"] += 1
            else:
                _mark_skipped(db, ingredient_id)
                result["image_skipped"] += 1

    log_info(
        "Wikidata enrichment complete: image_enriched=%d image_skipped=%d errors=%d",
        result["image_enriched"],
        result["image_skipped"],
        result["errors"],
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_pending(db, limit: int) -> list[dict]:
    """Select rows pending image enrichment that have a Wikidata ID."""
    sql = """
        SELECT ingredient_id, off_wikidata_id
        FROM ops.ingredient_catalog
        WHERE image_enriched = FALSE
          AND image_skipped = FALSE
          AND off_wikidata_id IS NOT NULL
        ORDER BY created_date ASC
        LIMIT %s
    """
    rows = db_read(sql, (limit,), connection=db)
    return rows if rows else []


def _batch_fetch_p18(wikidata_ids: list[str]) -> dict[str, str] | None:
    """
    Fetch P18 (image) claims for a batch of Wikidata entity IDs.

    Returns dict: {wikidata_id: commons_filename} for entities that have P18.
    Entities without P18 are simply absent from the result.
    Returns None on HTTP error.
    """
    try:
        ids_param = "|".join(wikidata_ids[:50])  # Wikidata supports up to 50 per request
        params = {
            "action": "wbgetentities",
            "ids": ids_param,
            "props": "claims",
            "format": "json",
        }
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            response = client.get(
                WIKIDATA_API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()

        entities = data.get("entities", {})
        result: dict[str, str] = {}

        for wid, entity in entities.items():
            claims = entity.get("claims", {})
            p18_claims = claims.get(P18_IMAGE, [])
            if not p18_claims:
                continue
            # Take the first (preferred) image claim
            try:
                filename = p18_claims[0]["mainsnak"]["datavalue"]["value"]
                if filename:
                    result[wid] = filename
            except (KeyError, IndexError, TypeError):
                continue

        return result

    except Exception as exc:
        log_error("Wikidata enrichment: API call failed: %s", exc)
        return None


def _mark_enriched(db, ingredient_id, image_url: str) -> None:
    """Set image_url, image_source, image_enriched=TRUE. Commit per row."""
    sql = """
        UPDATE ops.ingredient_catalog
        SET image_url       = %s,
            image_source    = 'wikidata',
            image_enriched  = TRUE,
            modified_date   = %s
        WHERE ingredient_id = %s
    """
    try:
        cursor = db.cursor()
        cursor.execute(sql, (image_url, datetime.now(UTC), str(ingredient_id)))
        db.commit()
    except Exception as exc:
        db.rollback()
        log_error("Wikidata enrichment: failed to mark enriched for %s: %s", ingredient_id, exc)


def _mark_skipped(db, ingredient_id) -> None:
    """Set image_enriched=TRUE, image_skipped=TRUE. Commit per row."""
    sql = """
        UPDATE ops.ingredient_catalog
        SET image_enriched = TRUE,
            image_skipped  = TRUE,
            modified_date  = %s
        WHERE ingredient_id = %s
    """
    try:
        cursor = db.cursor()
        cursor.execute(sql, (datetime.now(UTC), str(ingredient_id)))
        db.commit()
    except Exception as exc:
        db.rollback()
        log_error("Wikidata enrichment: failed to mark skipped for %s: %s", ingredient_id, exc)
