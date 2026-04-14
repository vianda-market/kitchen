"""
Ingredients Routes

GET  /ingredients/search       — multilingual autocomplete (OFF-backed)
POST /ingredients/custom       — create a custom ingredient when OFF returns no match
"""
from typing import List, Optional
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    IngredientCustomCreateSchema,
    IngredientSearchResultSchema,
)
from app.services.ingredient_service import (
    create_custom_ingredient,
    search_ingredients,
)

router = APIRouter(prefix="/ingredients", tags=["Ingredients"])

_LANG_PATTERN = "^(es|en|pt)$"
_SUPPORTED_LANGS = {"es", "en", "pt"}


def _resolve_lang(lang: Optional[str], current_user: dict) -> str:
    """Derive language: use explicit param first, then user locale (short code), then 'en'."""
    if lang and lang in _SUPPORTED_LANGS:
        return lang
    locale = (current_user.get("locale") or "").split("-")[0].lower()
    return locale if locale in _SUPPORTED_LANGS else "en"


def _resolve_market_id(current_user: dict) -> Optional[str]:
    """Extract market_id string for dialect alias lookup. None when not available."""
    mid = current_user.get("subscription_market_id")
    return str(mid) if mid else None


@router.get("/search", response_model=List[IngredientSearchResultSchema])
def search_ingredients_route(
    query: str = Query(..., min_length=2, max_length=100),
    lang: Optional[str] = Query(None, pattern=_LANG_PATTERN),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Search the ingredient catalog. Falls back to Open Food Facts when
    fewer than OFF_LOCAL_MIN_VERIFIED_RESULTS verified entries exist locally.
    Returns up to 10 results ordered by is_verified DESC, enriched DESC.
    """
    resolved_lang = _resolve_lang(lang, current_user)
    market_id = _resolve_market_id(current_user)
    return search_ingredients(query, resolved_lang, market_id, db)


@router.post("/custom", response_model=IngredientSearchResultSchema, status_code=201)
def create_custom_ingredient_route(
    body: IngredientCustomCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a custom ingredient that does not exist in the catalog.
    Returns existing entry if an exact name match already exists.
    """
    resolved_lang = _resolve_lang(body.lang, current_user)
    return create_custom_ingredient(body.name, resolved_lang, current_user["user_id"], db)
