"""
Supported Cities (B2C and back-office).

Read-only list of cities for user onboarding and employer address scoping.
Returns from city_info (seeded from supported_cities config).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
import psycopg2.extensions

from app.auth.dependencies import get_client_employee_or_supplier_user
from app.dependencies.database import get_db
from app.services.crud_service import city_service
from app.schemas.consolidated_schemas import CityResponseSchema
from app.config.supported_cities import GLOBAL_CITY_ID

router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("", response_model=List[CityResponseSchema])
async def list_cities(
    country_code: Optional[str] = Query(None, description="Filter by ISO 3166-1 alpha-2 country code (e.g. AR, PE)"),
    province_code: Optional[str] = Query(None, description="Filter by province/state code (e.g. WA, FL). Use with country_code for cascading dropdown."),
    exclude_global: bool = Query(False, description="Exclude Global city (for Customer signup/profile picker)"),
    current_user: dict = Depends(get_client_employee_or_supplier_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List supported cities for user onboarding and employer address scoping.

    **Authorization**: Customer, Internal, or Supplier.

    **Returns**: JSON array of `{ city_id, name, country_code, province_code }` sorted by country_code, province_code, name.
    Use for "City" dropdown in user profile and employer address filter.
    Pass ?country_code=US&province_code=WA to get cities in Washington state.
    """
    if country_code:
        cc = country_code.strip().upper()
        cities = city_service.get_all_by_field("country_code", cc, db, scope=None)
    else:
        cities = city_service.get_all(db, include_archived=False)
    if province_code:
        pcode = province_code.strip()
        cities = [c for c in cities if getattr(c, "province_code", None) == pcode]
    # Sort by country_code, province_code (if present), then name (case-insensitive)
    cities.sort(key=lambda c: (c.country_code, getattr(c, "province_code", "") or "", c.name.lower()))
    if exclude_global:
        cities = [c for c in cities if c.city_id != GLOBAL_CITY_ID]
    return [
        CityResponseSchema(
            city_id=c.city_id,
            name=c.name,
            country_code=c.country_code,
            province_code=c.province_code if hasattr(c, "province_code") else None,
            is_archived=c.is_archived,
            status=c.status,
        )
        for c in cities
    ]
