"""
Supported Currencies (back-office).

Read-only list of currencies valid for creating a credit currency (e.g. Currency dropdown).
Same source as validation for POST /api/v1/credit-currencies/ (backend assigns currency_code from name).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import get_employee_user
from app.config.supported_currencies import get_supported_currencies_sorted_by_name

router = APIRouter(prefix="/currencies", tags=["Currencies"])


class SupportedCurrencySchema(BaseModel):
    """One supported currency for dropdowns (e.g. Create Credit Currency)."""

    currency_name: str = Field(..., description="Display name (e.g. US Dollar)")
    currency_code: str = Field(..., description="ISO 4217 code (e.g. USD)")


@router.get("", response_model=list[SupportedCurrencySchema])
async def list_supported_currencies(
    current_user: dict = Depends(get_employee_user),
):
    """
    List supported currencies for creating a credit currency.

    **Authorization**: Internal only (same as other back-office endpoints).

    **Returns**: JSON array of `{ currency_name, currency_code }` sorted by `currency_name`.
    Use for "Currency" dropdown in Create Credit Currency / Create Market flow. When creating
    a credit currency, send only `currency_name` (and `credit_value`); backend assigns `currency_code`.
    """
    items = get_supported_currencies_sorted_by_name()
    return [SupportedCurrencySchema(**x) for x in items]
