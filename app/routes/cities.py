"""
Supported Cities (B2C and back-office).

Read-only list of cities for user onboarding and employer address scoping.
Returns from core.city_metadata (Vianda metadata layer) joined with external.geonames_city
for the display name and timezone. Legacy city_info table retired in PR1.
"""

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_client_employee_or_supplier_user
from app.config.supported_cities import GLOBAL_CITY_ID
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import CityResponseSchema
from app.utils.db import db_read

router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("", response_model=list[CityResponseSchema])
async def list_cities(
    country_code: str | None = Query(None, description="Filter by ISO 3166-1 alpha-2 country code (e.g. AR, PE)"),
    exclude_global: bool = Query(False, description="Exclude Global city (for Customer signup/profile picker)"),
    current_user: dict = Depends(get_client_employee_or_supplier_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List supported cities for user onboarding and employer address scoping.

    **Authorization**: Customer, Internal, or Supplier.

    **Returns**: JSON array of `{ city_metadata_id, name, country_code, is_archived, status }` sorted by
    country_code then name (case-insensitive). Backed by core.city_metadata joined with external.geonames_city.
    City display name uses `COALESCE(display_name_override, geonames_city.name)` — Vianda override wins, else
    the canonical GeoNames name.

    Use for "City" dropdown in user profile and employer address filter.
    Pass ?country_code=US to get cities in a specific country.

    Note: province/state filtering was removed with the PR1 city_info retirement. Structural province data
    now lives on external.geonames_admin1 and joins via geonames_city.admin1_code — if/when a province filter
    is needed again, add it via that path (PR2 superadmin picker scope).
    """
    params: list = []
    conditions = ["cm.is_archived = FALSE"]
    if country_code:
        conditions.append("cm.country_iso = %s")
        params.append(country_code.strip().upper())
    if exclude_global:
        conditions.append("cm.city_metadata_id != %s")
        params.append(str(GLOBAL_CITY_ID))

    query = f"""
        SELECT
            cm.city_metadata_id,
            COALESCE(cm.display_name_override, gc.name) AS name,
            cm.country_iso AS country_code,
            cm.is_archived,
            cm.status
        FROM core.city_metadata cm
        JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
        WHERE {" AND ".join(conditions)}
        ORDER BY cm.country_iso, LOWER(COALESCE(cm.display_name_override, gc.name))
    """
    rows = db_read(query, tuple(params), connection=db)
    return [
        CityResponseSchema(
            city_metadata_id=r["city_metadata_id"],
            name=r["name"],
            country_code=r["country_code"],
            is_archived=r["is_archived"],
            status=r["status"],
        )
        for r in (rows or [])
    ]
