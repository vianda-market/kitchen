"""
Cuisines API — public list/search and supplier suggestion endpoints.

Replaces the static config-based cuisine list with DB-backed queries.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from psycopg2.extensions import connection

from app.auth.dependencies import (
    get_client_employee_or_supplier_user,
    get_employee_or_supplier_user,
)
from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.locale_names import resolve_cuisine_name_dict
from app.schemas.consolidated_schemas import (
    CuisineResponseSchema,
    CuisineSuggestionCreateSchema,
    CuisineSuggestionResponseSchema,
)
from app.services import cuisine_service
from app.utils.locale import resolve_locale_from_header

router = APIRouter(prefix="/cuisines", tags=["Cuisines"])


@router.get("", response_model=list[CuisineResponseSchema])
def list_cuisines(
    request: Request,
    search: str | None = Query(None, description="Filter by cuisine name (case-insensitive partial match)"),
    language: str = Query(
        None,
        description="Locale for cuisine names (en, es, pt). Falls back to Accept-Language header, then 'en'.",
    ),
    current_user: dict = Depends(get_client_employee_or_supplier_user),
    db: connection = Depends(get_db),
):
    """
    List active cuisines for dropdown/autocomplete.

    **Authorization**: Customer, Internal, or Supplier.

    **Query params**:
    - `search`: optional partial match on cuisine_name or slug
    - `language`: locale for display names (en, es, pt). Falls back to Accept-Language header.

    **Returns**: sorted list of cuisines with parent/child hierarchy. Names localized per requested language.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    rows = cuisine_service.search_cuisines(db, search=search)
    if locale != "en":
        for row in rows:
            resolve_cuisine_name_dict(row, locale)
    return [CuisineResponseSchema(**row) for row in rows]


@router.post("/suggestions", response_model=CuisineSuggestionResponseSchema, status_code=201)
def create_cuisine_suggestion(
    data: CuisineSuggestionCreateSchema,
    current_user: dict = Depends(get_employee_or_supplier_user),
    db: connection = Depends(get_db),
):
    """
    Suggest a new cuisine (supplier "Other" flow).

    Creates a Pending suggestion for Internal admin review.
    The linked restaurant keeps cuisine_id = NULL until approved.

    **Authorization**: Internal or Supplier.
    """
    user_id = UUID(str(current_user["user_id"]))
    row = cuisine_service.create_suggestion(
        suggested_name=data.suggested_name,
        suggested_by=user_id,
        restaurant_id=data.restaurant_id,
        modified_by=user_id,
        db=db,
    )
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create suggestion")
    return CuisineSuggestionResponseSchema(**row)
