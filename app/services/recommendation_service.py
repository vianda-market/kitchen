"""
Recommendation layer for explore results.

Consumes signals (favorites today; ML, promoted post-MVP) and computes is_recommended
plus sort keys. Plates and restaurants surpassing the threshold are sorted to the top.
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.config.recommendation_config import (
    RECOMMENDATION_THRESHOLD,
    WEIGHT_PLATE_FAVORITED,
    WEIGHT_RESTAURANT_FAVORITED,
)
from app.services.favorite_service import get_favorite_ids


def _compute_plate_score(
    plate: dict,
    fav_plate_ids: set,
    fav_restaurant_ids: set,
    restaurant_id: Any,
) -> int:
    """Return recommendation score for one plate. MVP: plate favorited or restaurant favorited."""
    plate_id_str = str(plate.get("plate_id", ""))
    restaurant_id_str = str(restaurant_id) if restaurant_id else ""
    if plate_id_str in fav_plate_ids:
        return WEIGHT_PLATE_FAVORITED
    if restaurant_id_str in fav_restaurant_ids:
        return WEIGHT_RESTAURANT_FAVORITED
    return 0


def _compute_restaurant_score(
    restaurant: dict,
    fav_restaurant_ids: set,
    plates: list[dict],
    fav_plate_ids: set,
) -> int:
    """Return recommendation score for one restaurant. MVP: restaurant favorited or any plate favorited."""
    restaurant_id_str = str(restaurant.get("restaurant_id", ""))
    if restaurant_id_str in fav_restaurant_ids:
        return WEIGHT_RESTAURANT_FAVORITED
    if any(str(p.get("plate_id", "")) in fav_plate_ids for p in plates):
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
    Mutates restaurants and plates in-place: sets is_recommended and _recommendation_score.
    Uses favorite_ids if provided; otherwise fetches via get_favorite_ids(user_id, db).
    """
    if user_id is None:
        for r in restaurants:
            r["is_recommended"] = False
            r["_recommendation_score"] = 0
            for p in r.get("plates") or []:
                p["is_recommended"] = False
                p["_recommendation_score"] = 0
        return

    fav = favorite_ids if favorite_ids is not None else get_favorite_ids(user_id, db)
    fav_plate_ids = {str(pid) for pid in fav.get("plate_ids", [])}
    fav_restaurant_ids = {str(rid) for rid in fav.get("restaurant_ids", [])}

    for r in restaurants:
        plates = r.get("plates") or []
        rest_score = _compute_restaurant_score(r, fav_restaurant_ids, plates, fav_plate_ids)
        r["is_recommended"] = rest_score >= RECOMMENDATION_THRESHOLD
        r["_recommendation_score"] = rest_score

        for p in plates:
            plate_score = _compute_plate_score(p, fav_plate_ids, fav_restaurant_ids, r.get("restaurant_id"))
            p["is_recommended"] = plate_score >= RECOMMENDATION_THRESHOLD
            p["_recommendation_score"] = plate_score
