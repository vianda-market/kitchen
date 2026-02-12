"""
Market Routes (Admin)

API endpoints for managing markets (country-based subscription regions).
Markets define the countries where the platform operates.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
import psycopg2.extensions

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    MarketResponseSchema,
    MarketCreateSchema,
    MarketUpdateSchema
)
from app.services.market_service import market_service
from app.services.entity_service import get_enriched_markets, get_enriched_market_by_id
from app.config import Status

router = APIRouter(prefix="/markets", tags=["Markets"])


@router.get("/", response_model=List[MarketResponseSchema])
async def list_markets(
    include_archived: bool = Query(False, description="Include archived markets"),
    status: Optional[Status] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    List all markets.
    
    **Authorization**: Employee, Supplier (read-only)
    
    Markets represent the countries where the platform operates, each with
    its own currency, timezone, and subscription plans.
    
    **Query Parameters**:
    - `include_archived`: Include archived markets (default: false)
    - `status`: Filter by status (Active/Inactive)
    
    **Returns**: List of markets
    """
    # TODO: Add role-based authorization check
    # For now, requires authentication (Employee/Supplier can read)
    
    markets = market_service.get_all(
        include_archived=include_archived,
        status=status
    )
    
    return markets


@router.get("/{market_id}", response_model=MarketResponseSchema)
async def get_market(
    market_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific market by ID.
    
    **Authorization**: Employee, Supplier (read-only)
    
    **Path Parameters**:
    - `market_id`: UUID of the market
    
    **Returns**: Market details
    
    **Raises**:
    - 404: Market not found
    """
    # TODO: Add role-based authorization check
    # For now, requires authentication (Employee/Supplier can read)
    
    market = market_service.get_by_id(market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    return market


@router.post("/", response_model=MarketResponseSchema, status_code=201)
async def create_market(
    market_data: MarketCreateSchema,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new market.
    
    **Authorization**: Employee only (system configuration)
    
    **Request Body**: Market creation data
    - `country_name`: Full country name (e.g., "Argentina")
    - `country_code`: ISO 3166-1 alpha-3 code (e.g., "ARG")
    - `credit_currency_id`: FK to credit_currency_info (UUID)
    - `timezone`: Timezone (e.g., "America/Argentina/Buenos_Aires")
    - `status`: Market status (default: Active)
    
    **Returns**: Created market with enriched currency info
    
    **Raises**:
    - 403: Insufficient permissions
    - 409: Market already exists
    """
    # TODO: Add role-based authorization check (Employee only)
    # For now, requires authentication
    
    market = market_service.create(
        country_name=market_data.country_name,
        country_code=market_data.country_code,
        credit_currency_id=market_data.credit_currency_id,
        timezone=market_data.timezone,
        modified_by=UUID(current_user["user_id"]),
        status=market_data.status or Status.ACTIVE
    )
    
    return market


@router.put("/{market_id}", response_model=MarketResponseSchema)
async def update_market(
    market_id: UUID,
    market_data: MarketUpdateSchema,
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing market.
    
    **Authorization**: Employee only (system configuration)
    
    **Path Parameters**:
    - `market_id`: UUID of the market to update
    
    **Request Body**: Market update data (all fields optional)
    - `country_name`: New country name
    - `country_code`: New country code
    - `credit_currency_id`: New FK to credit_currency_info
    - `timezone`: New timezone
    - `status`: New status
    - `is_archived`: Archive status
    
    **Returns**: Updated market with enriched currency info
    
    **Raises**:
    - 403: Insufficient permissions
    - 404: Market not found
    """
    # TODO: Add role-based authorization check (Employee only)
    # For now, requires authentication
    
    market = market_service.update(
        market_id=market_id,
        modified_by=UUID(current_user["user_id"]),
        country_name=market_data.country_name,
        country_code=market_data.country_code,
        credit_currency_id=market_data.credit_currency_id,
        timezone=market_data.timezone,
        status=market_data.status,
        is_archived=market_data.is_archived
    )
    
    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    return market


@router.delete("/{market_id}", status_code=204)
async def archive_market(
    market_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """
    Archive a market (soft delete).
    
    **Authorization**: Employee only (system configuration)
    
    **Path Parameters**:
    - `market_id`: UUID of the market to archive
    
    **Returns**: 204 No Content
    
    **Raises**:
    - 403: Insufficient permissions
    - 404: Market not found
    
    **Note**: This is a soft delete. The market is marked as archived but
    not removed from the database.
    """
    # TODO: Add role-based authorization check (Employee only)
    # For now, requires authentication
    
    market = market_service.update(
        market_id=market_id,
        modified_by=UUID(current_user["user_id"]),
        is_archived=True,
        status=Status.INACTIVE
    )
    
    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    return None


# =============================================================================
# ENRICHED MARKET ENDPOINTS (with currency_name and currency_code)
# =============================================================================

@router.get("/enriched/", response_model=List[MarketResponseSchema])
async def list_enriched_markets(
    include_archived: bool = Query(False, description="Include archived markets"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all markets with enriched data (currency details).
    
    **Authorization**: Employee, Supplier (read-only)
    
    This enriched endpoint returns markets with currency information
    (currency_name and currency_code) from the credit_currency_info table.
    
    **Query Parameters**:
    - `include_archived`: Include archived markets (default: false)
    
    **Returns**: List of markets with enriched currency data
    
    **Use Case**: Display markets with full currency details in admin UI
    """
    # TODO: Add role-based authorization check
    # For now, requires authentication (Employee/Supplier can read)
    
    try:
        enriched_markets = get_enriched_markets(
            db,
            include_archived=include_archived
        )
        return enriched_markets
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched markets: {str(e)}")


@router.get("/enriched/{market_id}", response_model=MarketResponseSchema)
async def get_enriched_market(
    market_id: UUID,
    include_archived: bool = Query(False, description="Include archived markets"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a specific market by ID with enriched data (currency details).
    
    **Authorization**: Employee, Supplier (read-only)
    
    **Path Parameters**:
    - `market_id`: UUID of the market
    
    **Query Parameters**:
    - `include_archived`: Include archived markets (default: false)
    
    **Returns**: Market with enriched currency data
    
    **Raises**:
    - 404: Market not found
    
    **Use Case**: Display market details with full currency information in admin UI
    """
    # TODO: Add role-based authorization check
    # For now, requires authentication (Employee/Supplier can read)
    
    try:
        enriched_market = get_enriched_market_by_id(
            market_id,
            db,
            include_archived=include_archived
        )
        
        if not enriched_market:
            raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
        
        return enriched_market
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched market: {str(e)}")
