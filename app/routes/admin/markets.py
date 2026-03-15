"""
Market Routes (Admin)

API endpoints for managing markets (country-based subscription regions).
Markets define the countries where the platform operates.
"""

from datetime import datetime
import time
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
import psycopg2.extensions

from app.auth.dependencies import get_current_user, get_employee_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    MarketResponseSchema,
    MarketPublicMinimalSchema,
    MarketCreateSchema,
    MarketUpdateSchema
)
from app.services.market_service import market_service, GLOBAL_MARKET_ID, is_global_market
from app.services.entity_service import get_enriched_markets, get_enriched_market_by_id
from app.config import Status
from app.config.supported_countries import SUPPORTED_COUNTRY_CODES
from app.utils.country import resolve_country_name
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/markets", tags=["Markets"])


# -----------------------------------------------------------------------------
# Public markets endpoint (no auth): rate limit and cache
# -----------------------------------------------------------------------------
_available_markets_cache: Optional[List[dict]] = None
_available_markets_cache_expiry: float = 0
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_available_markets_cached() -> List[MarketPublicMinimalSchema]:
    """Return active non-archived markets (excluding Global Marketplace); country_code + country_name only for unauthenticated."""
    global _available_markets_cache, _available_markets_cache_expiry
    now = time.time()
    if _available_markets_cache is not None and now < _available_markets_cache_expiry:
        return [MarketPublicMinimalSchema(**m) for m in _available_markets_cache]
    raw = market_service.get_all(include_archived=False, status=Status.ACTIVE)
    # Exclude Global Marketplace from public list (B2C selector); it is for assignment only.
    # Return only country_code + country_name (no market_id, timezone, currency, etc.)
    slim = [
        {"country_code": m["country_code"], "country_name": m["country_name"]}
        for m in raw
        if not is_global_market(m.get("market_id"))
    ]
    # Only cache non-empty results so transient empty responses don't stick
    if slim:
        _available_markets_cache = slim
        _available_markets_cache_expiry = now + CACHE_TTL_SECONDS
    return [MarketPublicMinimalSchema(**m) for m in slim]


@router.get("/available", response_model=List[MarketPublicMinimalSchema])
@limiter.limit("60/minute")
async def list_available_markets_public(request: Request):
    """
    Public (no auth) list of active markets for UI dropdown.

    Source of truth for which countries clients can operate in. Rate-limited and cached.
    Use for market selector (e.g. default by browser country, fallback to US).
    """
    return _get_available_markets_cached()


@router.get("", response_model=List[MarketResponseSchema])
async def list_markets(
    status: Optional[Status] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    List all markets. Non-archived only.

    **Authorization**: Any authenticated user (Employee, Supplier, Customer). Used for country dropdown when creating addresses.

    Markets represent the countries where the platform operates, each with
    its own currency, timezone, and subscription plans.

    **Query Parameters**:
    - `status`: Filter by status (Active/Inactive)

    **Returns**: List of markets
    """
    markets = market_service.get_all(
        include_archived=False,
        status=status
    )
    
    return markets


# =============================================================================
# ENRICHED MARKET ENDPOINTS (with currency_name and currency_code)
# Must be registered before /{market_id} so /enriched is not parsed as market_id.
# =============================================================================

@router.get("/enriched", response_model=List[MarketResponseSchema])
async def list_enriched_markets(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all markets with enriched data (currency details). Non-archived only.

    **Authorization**: Any authenticated user (Employee, Supplier, Customer). Used for country dropdown when creating addresses.

    This enriched endpoint returns markets with currency information
    (currency_name and currency_code) from the credit_currency_info table.

    **Returns**: List of markets with enriched currency data

    **Use Case**: Display markets with full currency details in admin UI
    """
    try:
        enriched_markets = get_enriched_markets(
            db,
            include_archived=False
        )
        return enriched_markets
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched markets: {str(e)}")


@router.get("/enriched/{market_id}", response_model=MarketResponseSchema)
async def get_enriched_market(
    market_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a specific market by ID with enriched data (currency details). Non-archived only.

    **Authorization**: Any authenticated user (Employee, Supplier, Customer).

    **Path Parameters**:
    - `market_id`: UUID of the market

    **Returns**: Market with enriched currency data

    **Raises**:
    - 404: Market not found

    **Use Case**: Display market details with full currency information in admin UI
    """
    try:
        enriched_market = get_enriched_market_by_id(
            market_id,
            db,
            include_archived=False
        )
        
        if not enriched_market:
            raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
        
        return enriched_market
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched market: {str(e)}")


@router.get("/{market_id}", response_model=MarketResponseSchema)
async def get_market(
    market_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific market by ID.
    
    **Authorization**: Any authenticated user (Employee, Supplier, Customer).
    
    **Path Parameters**:
    - `market_id`: UUID of the market
    
    **Returns**: Market details
    
    **Raises**:
    - 404: Market not found
    """
    market = market_service.get_by_id(market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    return market


@router.post("", response_model=MarketResponseSchema, status_code=201)
async def create_market(
    market_data: MarketCreateSchema,
    current_user: dict = Depends(get_employee_user)
):
    """
    Create a new market.
    
    **Authorization**: Employee only (system configuration)
    
    **Request Body**: Market creation data (country_name is derived from country_code)
    - `country_code`: ISO 3166-1 alpha-2 code (e.g., "AR", "DE")
    - `credit_currency_id`: FK to credit_currency_info (UUID)
    - `timezone`: Timezone (e.g., "America/Argentina/Buenos_Aires")
    - `status`: Market status (default: Active)
    
    **Returns**: Created market with enriched currency info (includes country_name and country_code)
    
    **Raises**:
    - 400: Invalid country_code
    - 403: Insufficient permissions (e.g. Supplier)
    - 409: Market already exists
    """
    country_name = resolve_country_name(market_data.country_code)
    country_code = market_data.country_code  # already normalized by schema
    if country_code not in SUPPORTED_COUNTRY_CODES:
        raise HTTPException(
            status_code=400,
            detail="Country not supported for new markets. Use GET /api/v1/countries/ for the list of supported countries.",
        )
    kitchen_close_time = None
    if market_data.kitchen_close_time:
        kitchen_close_time = datetime.strptime(market_data.kitchen_close_time, "%H:%M").time()
    market = market_service.create(
        country_name=country_name,
        country_code=country_code,
        credit_currency_id=market_data.credit_currency_id,
        timezone=market_data.timezone,
        modified_by=current_user["user_id"],
        status=market_data.status or Status.ACTIVE,
        kitchen_close_time=kitchen_close_time
    )
    
    return market


@router.put("/{market_id}", response_model=MarketResponseSchema)
async def update_market(
    market_id: UUID,
    market_data: MarketUpdateSchema,
    current_user: dict = Depends(get_employee_user)
):
    """
    Update an existing market.
    
    **Authorization**: Employee only. **Global Marketplace** (market_id = Global) is editable **only by Super Admin**.
    
    **Path Parameters**:
    - `market_id`: UUID of the market to update
    
    **Request Body**: Market update data (all fields optional). When country_code is provided, country_name is derived by the backend.
    - `country_code`: New ISO 3166-1 alpha-2 country code (if provided, country_name is resolved from it)
    - `credit_currency_id`: New FK to credit_currency_info
    - `timezone`: New timezone
    - `status`: New status
    - `is_archived`: Archive status
    
    **Returns**: Updated market with enriched currency info
    
    **Raises**:
    - 400: Invalid country_code
    - 403: Insufficient permissions (Supplier; or Employee Admin trying to edit Global Marketplace)
    - 404: Market not found
    """
    if is_global_market(market_id) and current_user.get("role_name") != "Super Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super Admin can edit the Global Marketplace.",
        )
    country_name = None
    country_code = None
    if market_data.country_code is not None:
        country_name = resolve_country_name(market_data.country_code)
        country_code = market_data.country_code  # already normalized by schema
        if country_code not in SUPPORTED_COUNTRY_CODES:
            raise HTTPException(
                status_code=400,
                detail="Country not supported for new markets. Use GET /api/v1/countries/ for the list of supported countries.",
            )
    kitchen_close_time = None
    if market_data.kitchen_close_time is not None:
        kitchen_close_time = datetime.strptime(market_data.kitchen_close_time, "%H:%M").time()
    market = market_service.update(
        market_id=market_id,
        modified_by=current_user["user_id"],
        country_name=country_name,
        country_code=country_code,
        credit_currency_id=market_data.credit_currency_id,
        timezone=market_data.timezone,
        kitchen_close_time=kitchen_close_time,
        status=market_data.status,
        is_archived=market_data.is_archived
    )
    
    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    return market


@router.delete("/{market_id}", status_code=204)
async def archive_market(
    market_id: UUID,
    current_user: dict = Depends(get_employee_user)
):
    """
    Archive a market (soft delete).
    
    **Authorization**: Employee only. **Global Marketplace** cannot be archived (or only Super Admin could; we disallow archiving it).
    
    **Path Parameters**:
    - `market_id`: UUID of the market to archive
    
    **Returns**: 204 No Content
    
    **Raises**:
    - 403: Insufficient permissions (Supplier; or non–Super Admin trying to archive Global Marketplace)
    - 404: Market not found
    
    **Note**: This is a soft delete. The market is marked as archived but
    not removed from the database.
    """
    if is_global_market(market_id):
        if current_user.get("role_name") != "Super Admin":
            raise HTTPException(
                status_code=403,
                detail="Only Super Admin can archive the Global Marketplace.",
            )
        # Optionally disallow archiving Global even for Super Admin (keep it always active)
        raise HTTPException(
            status_code=400,
            detail="The Global Marketplace cannot be archived.",
        )
    market = market_service.update(
        market_id=market_id,
        modified_by=current_user["user_id"],
        is_archived=True,
        status=Status.INACTIVE
    )
    
    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    return None
