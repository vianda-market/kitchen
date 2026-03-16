"""
Supported Cuisines (B2B and back-office).

Read-only list of cuisines for restaurant create/edit dropdown.
Returns from supported_cuisines config. Use for Cuisine dropdown in restaurant form.
"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import get_client_employee_or_supplier_user
from app.config.supported_cuisines import get_supported_cuisines_sorted

router = APIRouter(prefix="/cuisines", tags=["Cuisines"])


class SupportedCuisineSchema(BaseModel):
    """One supported cuisine for dropdowns (e.g. restaurant create/edit form)."""
    cuisine_name: str = Field(..., description="Cuisine name for dropdown and restaurant.cuisine value")


@router.get("", response_model=List[SupportedCuisineSchema])
async def list_supported_cuisines(
    current_user: dict = Depends(get_client_employee_or_supplier_user),
):
    """
    List supported cuisines for restaurant create/edit dropdown.

    **Authorization**: Customer, Internal, or Supplier.

    **Returns**: JSON array of `{ cuisine_name }` sorted alphabetically.
    Use for "Cuisine" dropdown in restaurant form. Same values are valid for
    `cuisine` on POST/PUT /api/v1/restaurants/.
    """
    items = get_supported_cuisines_sorted()
    return [SupportedCuisineSchema(**x) for x in items]
