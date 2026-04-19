"""
Market Routes (Admin)

API endpoints for managing markets (country-based subscription regions).
Markets define the countries where the platform operates.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth.dependencies import get_current_user, get_employee_user, get_resolved_locale
from app.config import Status
from app.config.supported_countries import SUPPORTED_COUNTRY_CODES
from app.dependencies.database import get_db
from app.i18n.locale_names import localize_country_name, localize_currency_name
from app.schemas.consolidated_schemas import (
    MarketBillingConfigUpdateSchema,
    MarketCreateSchema,
    MarketPayoutAggregatorResponseSchema,
    MarketResponseSchema,
    MarketUpdateSchema,
)
from app.services.entity_service import get_enriched_market_by_id, get_enriched_markets
from app.services.error_handling import handle_business_operation
from app.services.market_service import is_global_market, market_has_active_plate_coverage, market_service
from app.utils.country import resolve_country_name
from app.utils.error_messages import entity_not_found
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(prefix="/markets", tags=["Markets"])


@router.get("", response_model=list[MarketResponseSchema])
async def list_markets(
    status: Status | None = Query(None, description="Filter by status"), current_user: dict = Depends(get_current_user)
):
    """
    List all markets. Non-archived only.

    **Authorization**: Any authenticated user (Internal, Supplier, Customer, Employer). Used for country dropdown when creating addresses.

    Markets represent the countries where the platform operates, each with
    its own currency, timezone, and subscription plans.

    **Query Parameters**:
    - `status`: Filter by status (Active/Inactive)

    **Returns**: List of markets
    """
    markets = market_service.get_all(include_archived=False, status=status)

    return markets


# =============================================================================
# ENRICHED MARKET ENDPOINTS (with currency_name and currency_code)
# Must be registered before /{market_id} so /enriched is not parsed as market_id.
# =============================================================================


@router.get("/enriched", response_model=list[MarketResponseSchema])
async def list_enriched_markets(
    response: Response,
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List all markets with enriched data (currency details). Non-archived only.

    **Authorization**: Any authenticated user (Internal, Supplier, Customer, Employer). Used for country dropdown when creating addresses.

    This enriched endpoint returns markets with currency information
    (currency_name and currency_code) from the currency_metadata table.
    Country and currency names are localized based on the user's resolved locale.

    **Returns**: List of markets with enriched currency data

    **Use Case**: Display markets with full currency details in admin UI
    """
    try:
        enriched_markets = get_enriched_markets(
            db,
            include_archived=False,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )
        if locale != "en":
            for m in enriched_markets:
                m.country_name = localize_country_name(m.country_code, locale)
                if m.currency_code:
                    m.currency_name = localize_currency_name(m.currency_code, locale)
        set_pagination_headers(response, enriched_markets)
        return enriched_markets
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched markets: {str(e)}") from None


@router.get("/enriched/{market_id}", response_model=MarketResponseSchema)
async def get_enriched_market(
    market_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get a specific market by ID with enriched data (currency details). Non-archived only.

    **Authorization**: Any authenticated user (Internal, Supplier, Customer, Employer).

    **Path Parameters**:
    - `market_id`: UUID of the market

    **Returns**: Market with enriched currency data (country and currency names localized)

    **Raises**:
    - 404: Market not found

    **Use Case**: Display market details with full currency information in admin UI
    """
    try:
        enriched_market = get_enriched_market_by_id(market_id, db, include_archived=False)

        if not enriched_market:
            raise entity_not_found("Market", market_id, locale=locale)

        if locale != "en":
            enriched_market.country_name = localize_country_name(enriched_market.country_code, locale)
            if enriched_market.currency_code:
                enriched_market.currency_name = localize_currency_name(enriched_market.currency_code, locale)

        return enriched_market
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched market: {str(e)}") from None


@router.get("/{market_id}", response_model=MarketResponseSchema)
async def get_market(market_id: UUID, current_user: dict = Depends(get_current_user)):
    """
    Get a specific market by ID.

    **Authorization**: Any authenticated user (Internal, Supplier, Customer, Employer).

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
async def create_market(market_data: MarketCreateSchema, current_user: dict = Depends(get_employee_user)):
    """
    Create a new market.

    **Authorization**: Internal only (system configuration)

    **Request Body**: Market creation data (country_name is derived from country_code)
    - `country_code`: ISO 3166-1 alpha-2 code (e.g., "AR", "DE")
    - `currency_metadata_id`: FK to currency_metadata (UUID)
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
    billing_config = market_data.billing_config.model_dump() if market_data.billing_config else None
    market = market_service.create(
        country_name=country_name,
        country_code=country_code,
        currency_metadata_id=market_data.currency_metadata_id,
        timezone=market_data.timezone,
        modified_by=current_user["user_id"],
        status=market_data.status or Status.ACTIVE,
        language=market_data.language,
        billing_config=billing_config,
    )

    return market


@router.put("/{market_id}", response_model=MarketResponseSchema)
async def update_market(
    market_id: UUID,
    market_data: MarketUpdateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Update an existing market.

    **Authorization**: Internal only. **Global Marketplace** (market_id = Global) is editable **only by Super Admin**.

    **Path Parameters**:
    - `market_id`: UUID of the market to update

    **Request Body**: Market update data (all fields optional). When country_code is provided, country_name is derived by the backend.
    - `country_code`: New ISO 3166-1 alpha-2 country code (if provided, country_name is resolved from it)
    - `currency_metadata_id`: New FK to currency_metadata
    - `timezone`: New timezone
    - `status`: New status
    - `is_archived`: Archive status

    **Returns**: Updated market with enriched currency info

    **Raises**:
    - 400: Invalid country_code
    - 403: Insufficient permissions (Supplier; or Internal Admin trying to edit Global Marketplace)
    - 404: Market not found
    """
    if is_global_market(market_id) and current_user.get("role_name") != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super Admin can edit the Global Marketplace.",
        )

    # Admin status override guardrails (non-global markets only).
    # These keep the `status` field honest in the absence of the auto-flip cron
    # (tracked in docs/plans/market-status-cron.md).
    if market_data.status is not None and not is_global_market(market_id):
        has_coverage = market_has_active_plate_coverage(market_id, db)
        if market_data.status == Status.ACTIVE and not has_coverage:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot activate: market has no active restaurant with an active plate on an "
                    "active weekly kitchen-day. Schedule coverage first, then set status='active'."
                ),
            )
        if market_data.status == Status.INACTIVE and has_coverage and not market_data.confirm_deactivate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This market currently has active plate coverage. Deactivating will hide it "
                    "from customers immediately. Resubmit with confirm_deactivate=true to proceed."
                ),
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
    market = market_service.update(
        market_id=market_id,
        modified_by=current_user["user_id"],
        country_name=country_name,
        country_code=country_code,
        currency_metadata_id=market_data.currency_metadata_id,
        timezone=market_data.timezone,
        status=market_data.status,
        is_archived=market_data.is_archived,
        language=market_data.language,
    )

    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")

    return market


@router.delete("/{market_id}", status_code=204)
async def archive_market(market_id: UUID, current_user: dict = Depends(get_employee_user)):
    """
    Archive a market (soft delete).

    **Authorization**: Internal only. **Global Marketplace** cannot be archived (or only Super Admin could; we disallow archiving it).

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
        if current_user.get("role_name") != "super_admin":
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
        market_id=market_id, modified_by=current_user["user_id"], is_archived=True, status=Status.INACTIVE
    )

    if not market:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")

    return


@router.get("/{market_id}/billing-config", response_model=MarketPayoutAggregatorResponseSchema)
def get_market_billing_config(
    market_id: UUID,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get billing configuration for a market. Internal only."""
    config = market_service.get_billing_config(market_id, db)
    if not config:
        raise HTTPException(status_code=404, detail=f"No billing config for market {market_id}")
    return config


@router.put("/{market_id}/billing-config", response_model=MarketPayoutAggregatorResponseSchema)
def update_market_billing_config(
    market_id: UUID,
    data: MarketBillingConfigUpdateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update billing configuration for a market. Internal only."""
    updated = market_service.update_billing_config(
        market_id,
        data.model_dump(exclude_unset=True),
        current_user["user_id"],
        db,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"No billing config for market {market_id}")
    return updated


@router.get("/{market_id}/billing-config/propagation-preview")
def preview_billing_propagation(
    market_id: UUID,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Preview which suppliers inherit billing defaults from this market. Read-only. Internal only."""

    def _preview():
        return market_service.get_billing_propagation_preview(market_id, db)

    return handle_business_operation(_preview, "billing propagation preview")
