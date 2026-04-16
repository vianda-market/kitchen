"""
Open Food Facts Service

Plain functions for querying the OFF suggest and taxonomy APIs.
No API key or DEV_MODE concern — OFF is a free, open dataset.
Graceful degradation: any error logs a warning and returns an empty list.

Pattern: matches app/services/cron/currency_refresh.py (no class wrapper needed).
"""

import logging

import httpx

logger = logging.getLogger(__name__)

OFF_SUGGEST_URL = "https://world.openfoodfacts.org/cgi/suggest.pl"
OFF_TAXONOMY_URL = "https://world.openfoodfacts.org/api/v2/taxonomy"
OFF_USER_AGENT = "vianda/1.0 (contact@vianda.market)"
_TIMEOUT = 5.0  # seconds


def search_off_suggestions(query: str, lang: str) -> list[str]:
    """
    Call OFF suggest.pl for ingredient autocomplete.
    Returns list of suggestion strings. Empty list on any error.
    """
    try:
        params = {
            "tagtype": "ingredients",
            "term": query,
            "lc": lang,
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(
                OFF_SUGGEST_URL,
                params=params,
                headers={"User-Agent": OFF_USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return [str(s) for s in data if s]
            return []
    except Exception as exc:
        logger.warning("OFF suggest failed for query=%r lang=%r: %s", query, lang, exc)
        return []


def resolve_off_taxonomy(suggestions: list[str], lang: str) -> list[dict]:
    """
    Batch-resolve suggestion strings to taxonomy entries via OFF taxonomy API.

    Prepends lang code: 'zanahoria' → tags='es:zanahoria'.
    Returns list of dicts with keys:
        off_taxonomy_id, name_display, name, name_es, name_en, name_pt
    Empty list on any error.
    """
    if not suggestions:
        return []
    try:
        # Build comma-separated tag list prefixed with lang code
        tags = ",".join(f"{lang}:{s}" for s in suggestions[:20])
        params = {
            "tagtype": "ingredients",
            "tags": tags,
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.get(
                OFF_TAXONOMY_URL,
                params=params,
                headers={"User-Agent": OFF_USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        tags_data = data.get("tags", {})
        if not isinstance(tags_data, dict):
            return []

        for off_id, entry in tags_data.items():
            name_map = entry.get("name", {})
            if not isinstance(name_map, dict):
                continue

            name_display = _pick_name(name_map, lang)
            if not name_display:
                continue

            results.append(
                {
                    "off_taxonomy_id": off_id,
                    "name_display": name_display,
                    "name": name_display.lower().strip(),
                    "name_es": name_map.get("es") or None,
                    "name_en": name_map.get("en") or None,
                    "name_pt": name_map.get("pt") or name_map.get("pt-BR") or None,
                }
            )

        return results
    except Exception as exc:
        logger.warning(
            "OFF taxonomy resolution failed for lang=%r (%d suggestions): %s",
            lang,
            len(suggestions),
            exc,
        )
        return []


def _pick_name(name_map: dict, preferred_lang: str) -> str | None:
    """Return the best display name from an OFF name map, preferring preferred_lang."""
    for key in (preferred_lang, "en", "es", "pt", "pt-BR"):
        val = name_map.get(key)
        if val:
            return val
    # fallback: first non-empty value
    for val in name_map.values():
        if val:
            return val
    return None
