"""
Supported Provinces/States (B2C and back-office).

Read-only list of provinces for address forms and cascading dropdowns.
Returns from supported_provinces config. Filter by country for form UX.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_client_employee_or_supplier_user
from app.config.supported_provinces import (
    get_supported_provinces_by_country,
    get_all_supported_provinces,
)

router = APIRouter(prefix="/provinces", tags=["Provinces"])


class SupportedProvinceSchema(BaseModel):
    """One supported province for dropdowns (e.g. address form, cascading with country)."""
    province_code: str = Field(..., description="Province/state code (e.g. WA, FL)")
    province_name: str = Field(..., description="Province/state name (e.g. Washington)")
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 country code (e.g. US)")


@router.get("", response_model=List[SupportedProvinceSchema])
async def list_supported_provinces(
    country_code: Optional[str] = Query(
        None,
        description="Filter by ISO 3166-1 alpha-2 country code (e.g. US, AR). When provided, returns only provinces for that country.",
    ),
    current_user: dict = Depends(get_client_employee_or_supplier_user),
):
    """
    List supported provinces for address forms and cascading dropdowns.

    **Authorization**: Customer, Internal, or Supplier.

    **Returns**: JSON array of `{ province_code, province_name, country_code }`.
    Use for "Province/State" dropdown after user selects country. Pass ?country_code=US
    to restrict to that country's provinces.
    """
    if country_code:
        items = get_supported_provinces_by_country(country_code)
    else:
        items = get_all_supported_provinces()
    return [SupportedProvinceSchema(**x) for x in items]
