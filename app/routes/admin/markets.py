"""
Market Routes (Admin)

API endpoints for managing markets (country-based subscription regions).
Markets define the countries where the platform operates.
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth.dependencies import get_current_user, get_employee_user, get_resolved_locale, get_super_admin_user
from app.config import Status
from app.config.supported_countries import SUPPORTED_COUNTRY_CODES
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.i18n.locale_names import localize_country_name, localize_currency_name
from app.schemas.consolidated_schemas import (
    MarketBillingConfigUpdateSchema,
    MarketCreateSchema,
    MarketPayoutAggregatorResponseSchema,
    MarketResponseSchema,
    MarketSpreadFloorUpdateSchema,
    MarketUpdateSchema,
    MarketUpsertByKeySchema,
    SpreadReadoutResponseSchema,
)
from app.services.entity_service import get_enriched_market_by_id, get_enriched_markets
from app.services.error_handling import handle_business_operation
from app.services.market_service import is_global_market, market_has_active_vianda_coverage, market_service
from app.utils.country import resolve_country_name
from app.utils.log import log_error
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(prefix="/markets", tags=["Markets"])


@router.get("", response_model=list[MarketResponseSchema])
async def list_markets(
    status: Status | None = Query(None, description="Filter by status"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
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
    current_user: dict[str, Any] = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> list[MarketResponseSchema]:
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
        log_error(f"Failed to retrieve enriched markets: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale) from None


@router.get("/enriched/{market_id}", response_model=MarketResponseSchema)
async def get_enriched_market(
    market_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MarketResponseSchema:
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
            raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=404, locale=locale)

        if locale != "en":
            enriched_market.country_name = localize_country_name(enriched_market.country_code, locale)
            if enriched_market.currency_code:
                enriched_market.currency_name = localize_currency_name(enriched_market.currency_code, locale)

        return enriched_market
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Failed to retrieve enriched market: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale) from None


@router.get("/{market_id}", response_model=MarketResponseSchema)
async def get_market(
    market_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
) -> Any:
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
        raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=404, locale=locale)

    return market


@router.post("", response_model=MarketResponseSchema, status_code=201)
async def create_market(
    market_data: MarketCreateSchema, current_user: dict[str, Any] = Depends(get_employee_user)
) -> Any:
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
        raise envelope_exception(ErrorCode.MARKET_COUNTRY_NOT_SUPPORTED, status=400, locale="en")
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


# PUT /markets/by-key — idempotent upsert (seed/fixture endpoint).
# MUST be registered before PUT /{market_id} so the static segment "by-key"
# wins over the UUID path parameter (FastAPI evaluates in registration order).
@router.put("/by-key", response_model=MarketResponseSchema, status_code=200)
def upsert_market_by_key(
    upsert_data: MarketUpsertByKeySchema,
    current_user: dict = Depends(get_employee_user),  # Internal-only
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MarketResponseSchema:
    """Idempotent upsert a market by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT — never use for ad-hoc market creation
    (use POST /markets instead).

    If a market with this canonical_key already exists it is updated in-place;
    otherwise a new market is inserted together with its billing_config record
    (same atomic transaction as POST /markets).

    Immutable fields on UPDATE: ``country_code`` is locked after insert and
    ignored on the update path (each market has a unique country_code that must
    not change after creation).

    Auth: Internal only (get_employee_user dependency).  Returns 403 for
    Customer/Supplier roles.

    Returns HTTP 200 on both insert and update (unlike POST which returns 201).
    """
    from app.services.crud_service import find_market_by_canonical_key
    from app.utils.log import log_info

    def _upsert() -> MarketResponseSchema:
        key = upsert_data.canonical_key
        country_code = upsert_data.country_code  # already normalized by schema validator
        modified_by = current_user["user_id"]

        # Primary lookup: by canonical_key.
        existing = find_market_by_canonical_key(key, db)

        # Secondary lookup: if no row has this canonical_key, check if a market already
        # exists for this country_code (e.g. the seeded canonical markets in reference_data.sql).
        # In that case we adopt the existing market and stamp it with the canonical_key rather
        # than attempting a duplicate INSERT that would violate the country_code UNIQUE constraint.
        if existing is None:
            existing = market_service.get_by_country_code(country_code)
            if existing is not None:
                # Convert the enriched dict to the minimal shape expected by the update path.
                # get_by_country_code returns the same enriched dict as get_by_id.
                pass  # existing is already the market dict; fall through to UPDATE path below

        if existing is not None:
            # UPDATE path — country_code is immutable; update all other supported fields.
            market_id = existing["market_id"]
            result = market_service.update(
                market_id=market_id,
                modified_by=modified_by,
                currency_metadata_id=upsert_data.currency_metadata_id,
                language=upsert_data.language,
                status=upsert_data.status,
            )
            if result is None:
                raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
            # Persist canonical_key + phone fields (market_service.update does not handle them)
            with db.cursor() as cur:
                cur.execute(
                    """UPDATE core.market_info
                       SET canonical_key = %s,
                           phone_dial_code = %s,
                           phone_local_digits = %s,
                           modified_date = CURRENT_TIMESTAMP
                       WHERE market_id = %s""",
                    (key, upsert_data.phone_dial_code, upsert_data.phone_local_digits, str(market_id)),
                )
            db.commit()
            log_info(f"Upsert updated market {market_id} with canonical_key '{key}'")
            enriched = market_service.get_by_id(market_id)
            if enriched is None:
                raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=404, locale="en")
            enriched["canonical_key"] = key
            return MarketResponseSchema(**enriched)

        # INSERT path — create market + billing config atomically (mirrors POST /markets).
        if country_code not in SUPPORTED_COUNTRY_CODES:
            raise envelope_exception(ErrorCode.MARKET_COUNTRY_NOT_SUPPORTED, status=400, locale="en")

        created = market_service.create(
            country_code=country_code,
            currency_metadata_id=upsert_data.currency_metadata_id,
            modified_by=modified_by,
            status=upsert_data.status,
            language=upsert_data.language,
        )
        # Set canonical_key + phone fields on the newly created row.
        # market_service.create() commits first; this is a follow-up UPDATE.
        new_market_id = created["market_id"]
        with db.cursor() as cur:
            cur.execute(
                """UPDATE core.market_info
                   SET canonical_key = %s,
                       phone_dial_code = %s,
                       phone_local_digits = %s,
                       modified_date = CURRENT_TIMESTAMP
                   WHERE market_id = %s""",
                (key, upsert_data.phone_dial_code, upsert_data.phone_local_digits, str(new_market_id)),
            )
        db.commit()
        log_info(f"Upsert inserted market {new_market_id} with canonical_key '{key}'")
        created["canonical_key"] = key
        created["phone_dial_code"] = upsert_data.phone_dial_code
        created["phone_local_digits"] = upsert_data.phone_local_digits
        return MarketResponseSchema(**created)

    return handle_business_operation(_upsert, "market upsert by canonical key")


@router.put("/{market_id}", response_model=MarketResponseSchema)
async def update_market(
    market_id: UUID,
    market_data: MarketUpdateSchema,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
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
        raise envelope_exception(ErrorCode.MARKET_SUPER_ADMIN_ONLY, status=403, locale=locale)

    # Admin status override guardrails (non-global markets only).
    # These keep the `status` field honest in the absence of the auto-flip cron
    # (tracked in docs/plans/market-status-cron.md).
    if market_data.status is not None and not is_global_market(market_id):
        has_coverage = market_has_active_vianda_coverage(market_id, db)
        if market_data.status == Status.ACTIVE and not has_coverage:
            raise envelope_exception(ErrorCode.MARKET_NO_COVERAGE_TO_ACTIVATE, status=400, locale=locale)
        if market_data.status == Status.INACTIVE and has_coverage and not market_data.confirm_deactivate:
            raise envelope_exception(ErrorCode.MARKET_HAS_COVERAGE_CONFIRM_DEACTIVATE, status=409, locale=locale)

    country_name = None
    country_code = None
    if market_data.country_code is not None:
        country_name = resolve_country_name(market_data.country_code)
        country_code = market_data.country_code  # already normalized by schema
        if country_code not in SUPPORTED_COUNTRY_CODES:
            raise envelope_exception(ErrorCode.MARKET_COUNTRY_NOT_SUPPORTED, status=400, locale=locale)
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
        raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=404, locale=locale)

    return market


@router.patch("/{market_id}/spread-floor", response_model=MarketResponseSchema)
def update_market_spread_floor(
    market_id: UUID,
    data: MarketSpreadFloorUpdateSchema,
    current_user: dict = Depends(get_super_admin_user),  # Super Admin only
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MarketResponseSchema:
    """
    Update the minimum credit spread floor for a market.

    **Authorization**: Super Admin only. The spread floor governs Vianda's gross margin
    per credit redemption; only Super Admin may lower or raise it.

    **Path Parameters**:
    - `market_id`: UUID of the market

    **Request Body**:
    - `min_credit_spread_pct`: New floor (0 to 1, e.g. 0.20 = 20%)
    - `acknowledge_spread_compression`: Set to true to accept if the new floor
      conflicts with existing active plans (warn-and-ack contract).
    - `spread_acknowledgement_justification`: Optional justification text for audit.

    **Returns**: Updated market with enriched data.

    **Raises**:
    - 403: Insufficient permissions (non-Super Admin)
    - 404: Market not found
    - 422: Spread floor conflicts with active plans (without ack)
    """
    from app.services.credit_spread import (
        SpreadAckContext,
        check_spread_floor_with_new_floor_pct,
        record_acknowledgement,
    )

    spread = check_spread_floor_with_new_floor_pct(
        db, market_id=market_id, proposed_floor_pct=data.min_credit_spread_pct
    )
    if not spread.ok:
        if not data.acknowledge_spread_compression:
            raise envelope_exception(
                ErrorCode.SPREAD_FLOOR_VIOLATION,
                status=422,
                locale=locale,
                observed_pct=float(spread.observed_pct),
                floor_pct=float(spread.floor_pct),
            )

    def _update() -> MarketResponseSchema:
        with db.cursor() as cur:
            cur.execute(
                """UPDATE core.market_info
                   SET min_credit_spread_pct = %s,
                       modified_by = %s::uuid,
                       modified_date = CURRENT_TIMESTAMP
                   WHERE market_id = %s""",
                (float(data.min_credit_spread_pct), str(current_user["user_id"]), str(market_id)),
            )
        db.commit()

        if not spread.ok and data.acknowledge_spread_compression:
            record_acknowledgement(
                db,
                SpreadAckContext(
                    actor_user_id=current_user["user_id"],
                    market_id=market_id,
                    write_kind="spread_floor",
                    entity_id=market_id,
                    justification=data.spread_acknowledgement_justification,
                ),
                spread,
            )

        enriched = market_service.get_by_id(market_id)
        if enriched is None:
            raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=404, locale=locale)
        return MarketResponseSchema(**enriched)

    return handle_business_operation(_update, "market spread floor update")


@router.get("/{market_id}/spread-readout", response_model=SpreadReadoutResponseSchema)
def get_market_spread_readout(
    market_id: UUID,
    current_user: dict = Depends(get_employee_user),  # Internal users (finance/market-admin)
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> SpreadReadoutResponseSchema:
    """
    Get the current credit spread readout for a market.

    **Authorization**: Internal users (employee or above).

    Returns the current spread between the cheapest active plan's per-credit
    price and the supplier credit value. Used by market admins to see whether
    the market is within the spread floor and which plans (if any) are offending.

    **Path Parameters**:
    - `market_id`: UUID of the market

    **Returns**:
    - `cheapest_plan_per_credit`: Cheapest per-credit price across active plans
    - `supplier_value`: credit_value_supplier_local for the market
    - `headroom_pct`: Observed spread (min(price/credit)/supplier_value - 1)
    - `floor_pct`: The market's min_credit_spread_pct
    - `offending_plan_ids`: Plans whose price/credit is below the floor threshold

    **Raises**:
    - 404: Market not found
    """
    from app.services.credit_spread import check_spread_floor

    spread = check_spread_floor(db, market_id=market_id)
    return SpreadReadoutResponseSchema(
        cheapest_plan_per_credit=spread.cheapest_per_credit,
        supplier_value=spread.supplier_value,
        headroom_pct=spread.observed_pct,
        floor_pct=spread.floor_pct,
        offending_plan_ids=spread.offending_plan_ids,
    )


@router.delete("/{market_id}", status_code=204)
async def archive_market(
    market_id: UUID,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
) -> None:
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
            raise envelope_exception(ErrorCode.MARKET_SUPER_ADMIN_ONLY, status=403, locale=locale)
        # Optionally disallow archiving Global even for Super Admin (keep it always active)
        raise envelope_exception(ErrorCode.MARKET_GLOBAL_CANNOT_BE_ARCHIVED, status=400, locale=locale)
    market = market_service.update(
        market_id=market_id, modified_by=current_user["user_id"], is_archived=True, status=Status.INACTIVE
    )

    if not market:
        raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=404, locale=locale)

    return


@router.get("/{market_id}/billing-config", response_model=MarketPayoutAggregatorResponseSchema)
def get_market_billing_config(
    market_id: UUID,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """Get billing configuration for a market. Internal only."""
    config = market_service.get_billing_config(market_id, db)
    if not config:
        raise envelope_exception(ErrorCode.MARKET_BILLING_CONFIG_NOT_FOUND, status=404, locale=locale)
    return config


@router.put("/{market_id}/billing-config", response_model=MarketPayoutAggregatorResponseSchema)
def update_market_billing_config(
    market_id: UUID,
    data: MarketBillingConfigUpdateSchema,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """Update billing configuration for a market. Internal only."""
    updated = market_service.update_billing_config(
        market_id,
        data.model_dump(exclude_unset=True),
        current_user["user_id"],
        db,
    )
    if not updated:
        raise envelope_exception(ErrorCode.MARKET_BILLING_CONFIG_NOT_FOUND, status=404, locale=locale)
    return updated


@router.get("/{market_id}/billing-config/propagation-preview")
def preview_billing_propagation(
    market_id: UUID,
    current_user: dict[str, Any] = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """Preview which suppliers inherit billing defaults from this market. Read-only. Internal only."""

    def _preview() -> Any:
        return market_service.get_billing_propagation_preview(market_id, db)

    return handle_business_operation(_preview, "billing propagation preview")
