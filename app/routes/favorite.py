"""
Favorite API routes.

Customer-only: add, remove, and list favorites (plates and restaurants).
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_client_user
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    FavoriteCreateSchema,
    FavoriteIdsResponseSchema,
    FavoriteResponseSchema,
)
from app.services.favorite_service import (
    add_favorite,
    get_favorite_ids,
    get_favorites_by_user,
    remove_favorite,
)
from app.utils.log import log_error

router = APIRouter(
    prefix="/favorites",
    tags=["Favorites"],
)


@router.post("", response_model=FavoriteResponseSchema, status_code=201)
def create_favorite(
    payload: FavoriteCreateSchema,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Add a favorite (plate or restaurant). Customer-only."""
    try:
        user_id = current_user["user_id"]
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        entity_type = payload.entity_type.value if hasattr(payload.entity_type, "value") else str(payload.entity_type)
        dto = add_favorite(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=payload.entity_id,
            db=db,
        )
        return FavoriteResponseSchema(
            favorite_id=dto.favorite_id,
            user_id=dto.user_id,
            entity_type=dto.entity_type,
            entity_id=dto.entity_id,
            created_date=dto.created_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error adding favorite: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.delete("/{entity_type}/{entity_id}", status_code=204)
def delete_favorite(
    entity_type: str,
    entity_id: UUID,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Remove a favorite. Idempotent. Customer-only."""
    try:
        user_id = current_user["user_id"]
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        remove_favorite(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            db=db,
        )
        return
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error removing favorite: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.get("/me", response_model=list[FavoriteResponseSchema])
def list_my_favorites(
    entity_type: str | None = Query(None, description="Filter by 'plate' or 'restaurant'"),
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List current user's favorites. Optional filter by entity_type. Customer-only."""
    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    dtos = get_favorites_by_user(user_id, db, entity_type=entity_type)
    return [
        FavoriteResponseSchema(
            favorite_id=d.favorite_id,
            user_id=d.user_id,
            entity_type=d.entity_type,
            entity_id=d.entity_id,
            created_date=d.created_date,
        )
        for d in dtos
    ]


@router.get("/me/ids", response_model=FavoriteIdsResponseSchema)
def get_my_favorite_ids(
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Lightweight: return plate_ids and restaurant_ids for client sorting/highlighting. Customer-only."""
    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = UUID(user_id)
    ids = get_favorite_ids(user_id, db)
    return FavoriteIdsResponseSchema(
        plate_ids=ids["plate_ids"],
        restaurant_ids=ids["restaurant_ids"],
    )
