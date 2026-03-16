"""
Supported Countries (back-office).

Read-only list of countries valid for creating a new market (e.g. Create Market dropdown).
Americas from Canada to Argentina; same source as validation for POST /api/v1/markets/.
"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import get_client_employee_or_supplier_user
from app.config.supported_countries import get_supported_countries_sorted_by_name

router = APIRouter(prefix="/countries", tags=["Countries"])


class SupportedCountrySchema(BaseModel):
    """One supported country for dropdowns (e.g. Create Market)."""
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 code (e.g. AR, US)")
    country_name: str = Field(..., description="Official country name (e.g. Argentina)")


@router.get("", response_model=List[SupportedCountrySchema])
async def list_supported_countries(
    current_user: dict = Depends(get_client_employee_or_supplier_user),
):
    """
    List supported countries for address forms and market creation.

    **Authorization**: Customer, Internal, or Supplier (all need country dropdown for addresses).

    **Returns**: JSON array of `{ country_code, country_name }` sorted by `country_name`.
    Use for "Country" dropdown in Create/Edit Market form. Only countries valid for
    new markets (Americas from Canada to Argentina by default; more regions can be added later).
    """
    items = get_supported_countries_sorted_by_name()
    return [SupportedCountrySchema(**x) for x in items]
