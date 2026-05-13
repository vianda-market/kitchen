# app/utils/cursor_pagination.py
"""
Cursor-based pagination for the explore endpoint (restaurants-by-city).

Pagination unit is **viandas**, not restaurants. A restaurant is never split
across pages — if any of its viandas fit in the current page, all of them are
included (the page may slightly exceed `limit`).

Cursors are opaque base64-encoded JSON. The frontend must never parse or
construct them; the backend is free to change the encoding at any time.
"""

import base64
import json

# Defaults and bounds for the `limit` query param (vianda count per page).
DEFAULT_LIMIT = 20
MIN_LIMIT = 10
MAX_LIMIT = 50


def encode_cursor(restaurant_index: int) -> str:
    """Encode a restaurant-list position into an opaque cursor string."""
    payload = json.dumps({"ri": restaurant_index}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> int:
    """Decode an opaque cursor to a restaurant-list index.

    Raises ``ValueError`` on any malformed or out-of-range cursor so the
    caller can return HTTP 400.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(raw)
        index = int(data["ri"])
        if index < 0:
            raise ValueError("cursor index must be non-negative")
        return index
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


def clamp_limit(limit: int | None) -> int:
    """Return *limit* clamped to [MIN_LIMIT, MAX_LIMIT], defaulting when None."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(MIN_LIMIT, min(limit, MAX_LIMIT))


def slice_restaurants_by_cursor(
    restaurants: list[dict],
    cursor: str | None,
    limit: int | None,
) -> tuple[list[dict], str | None, bool]:
    """Slice a **sorted** restaurant list using cursor-based pagination.

    Parameters
    ----------
    restaurants:
        The full, already-sorted list of restaurant dicts (each with a
        ``viandas`` list or ``None``).
    cursor:
        Opaque cursor from a previous response, or ``None`` for page 1.
    limit:
        Maximum number of **viandas** to include.  Clamped to
        [MIN_LIMIT, MAX_LIMIT]; ``None`` → DEFAULT_LIMIT.

    Returns
    -------
    (page_restaurants, next_cursor, has_more)
        *page_restaurants* is the subset for this page.
        *next_cursor* is ``None`` when there are no more results.
        *has_more* mirrors ``next_cursor is not None``.

    Raises
    ------
    ValueError
        If *cursor* is present but malformed / out of range.
    """
    start = 0
    if cursor is not None:
        start = decode_cursor(cursor)
        if start >= len(restaurants):
            raise ValueError("Cursor points beyond available results")

    effective_limit = clamp_limit(limit)

    page: list[dict] = []
    vianda_count = 0
    idx = start

    while idx < len(restaurants):
        r = restaurants[idx]
        r_viandas = len(r.get("viandas") or [])

        # Always include at least one restaurant per page (even if it alone
        # exceeds the limit) so pagination always makes progress.
        if vianda_count > 0 and vianda_count + r_viandas > effective_limit:
            break

        page.append(r)
        vianda_count += r_viandas
        idx += 1

        # Stop once we've met or exceeded the limit.
        if vianda_count >= effective_limit:
            break

    has_more = idx < len(restaurants)
    next_cursor = encode_cursor(idx) if has_more else None

    return page, next_cursor, has_more
