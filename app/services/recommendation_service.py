"""
Recommendation layer for explore results.

Consumes signals (favorites today; ML, promoted post-MVP) and computes is_recommended
plus sort keys. Viandas and restaurants surpassing the threshold are sorted to the top.
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.config.recommendation_config import (
    RECOMMENDATION_THRESHOLD,
    WEIGHT_RESTAURANT_FAVORITED,
    WEIGHT_VIANDA_FAVORITED,
)
from app.services.favorite_service import get_favorite_ids


def _compute_vianda_score(
    vianda: dict,
    fav_vianda_ids: set,
    fav_restaurant_ids: set,
    restaurant_id: Any,
) -> int:
    """Return recommendation score for one vianda. MVP: vianda favorited or restaurant favorited."""
    vianda_id_str = str(vianda.get("vianda_id", ""))
    restaurant_id_str = str(restaurant_id) if restaurant_id else ""
    if vianda_id_str in fav_vianda_ids:
        return WEIGHT_VIANDA_FAVORITED
    if restaurant_id_str in fav_restaurant_ids:
        return WEIGHT_RESTAURANT_FAVORITED
    return 0


def _compute_restaurant_score(
    restaurant: dict,
    fav_restaurant_ids: set,
    viandas: list[dict],
    fav_vianda_ids: set,
) -> int:
    """Return recommendation score for one restaurant. MVP: restaurant favorited or any vianda favorited."""
    restaurant_id_str = str(restaurant.get("restaurant_id", ""))
    if restaurant_id_str in fav_restaurant_ids:
        return WEIGHT_RESTAURANT_FAVORITED
    if any(str(p.get("vianda_id", "")) in fav_vianda_ids for p in viandas):
        return WEIGHT_RESTAURANT_FAVORITED
    return 0


def apply_recommendation(
    restaurants: list[dict],
    user_id: UUID | None,
    db: psycopg2.extensions.connection,
    *,
    favorite_ids: dict[str, list[UUID]] | None = None,
) -> None:
    """
    Mutates restaurants and viandas in-place: sets is_recommended and _recommendation_score.
    Uses favorite_ids if provided; otherwise fetches via get_favorite_ids(user_id, db).
    """
    if user_id is None:
        for r in restaurants:
            r["is_recommended"] = False
            r["_recommendation_score"] = 0
            for p in r.get("viandas") or []:
                p["is_recommended"] = False
                p["_recommendation_score"] = 0
        return

    fav = favorite_ids if favorite_ids is not None else get_favorite_ids(user_id, db)
    fav_vianda_ids = {str(pid) for pid in fav.get("vianda_ids", [])}
    fav_restaurant_ids = {str(rid) for rid in fav.get("restaurant_ids", [])}

    for r in restaurants:
        viandas = r.get("viandas") or []
        rest_score = _compute_restaurant_score(r, fav_restaurant_ids, viandas, fav_vianda_ids)
        r["is_recommended"] = rest_score >= RECOMMENDATION_THRESHOLD
        r["_recommendation_score"] = rest_score

        for p in viandas:
            vianda_score = _compute_vianda_score(p, fav_vianda_ids, fav_restaurant_ids, r.get("restaurant_id"))
            p["is_recommended"] = vianda_score >= RECOMMENDATION_THRESHOLD
            p["_recommendation_score"] = vianda_score
