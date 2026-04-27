# app/routes/restaurant.py
"""
Custom restaurant routes with automatic balance creation.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth.dependencies import get_client_or_employee_user, get_current_user, get_resolved_locale
from app.config import Status
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.i18n.locale_names import resolve_cuisine_name, resolve_i18n_field, resolve_i18n_list_field
from app.schemas.consolidated_schemas import (
    CoworkerPickupWindowsResponseSchema,
    ExploreKitchenDaysResponseSchema,
    PickupWindowsResponseSchema,
    RestaurantCreateSchema,
    RestaurantEnrichedResponseSchema,
    RestaurantExplorerCitiesResponseSchema,
    RestaurantExplorerItemSchema,
    RestaurantResponseSchema,
    RestaurantsByCityResponseSchema,
    RestaurantSearchResponseSchema,
    RestaurantSearchResultSchema,
    RestaurantUpdateSchema,
)
from app.security.entity_scoping import ENTITY_RESTAURANT, EntityScopingService
from app.security.scoping import resolve_institution_filter
from app.services.city_metrics_service import get_cities_with_coverage
from app.services.crud_service import (
    credit_currency_service,
    get_credit_cost_local_currency_of_most_expensive_plan_for_market,
    institution_entity_service,
    restaurant_balance_service,
    restaurant_service,
)
from app.services.entity_service import (
    get_assigned_market_ids,
    get_currency_metadata_id_for_restaurant,
    get_enriched_restaurant_by_id,
    get_enriched_restaurants,
    search_restaurants,
)
from app.services.error_handling import handle_business_operation
from app.services.market_service import is_global_market, market_service
from app.services.restaurant_explorer_service import (
    get_allowed_kitchen_days_sorted_by_date,
    get_coworker_pickup_windows,
    get_pickup_windows_for_kitchen_day,
    get_restaurants_by_city,
    resolve_weekday_to_next_occurrence,
    validate_kitchen_day_in_window,
)
from app.services.restaurant_visibility import (
    restaurant_has_active_plate_kitchen_days,
    restaurant_has_active_qr_code,
)
from app.utils.country import normalize_country_code
from app.utils.error_messages import entity_not_found
from app.utils.filter_builder import build_filter_conditions
from app.utils.log import log_error, log_info
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.utils.query_params import institution_filter, limit_query, market_filter

router = APIRouter(
    prefix="/restaurants",
    tags=["Restaurants"],
)


@router.post("", response_model=RestaurantResponseSchema)
def create_restaurant(
    restaurant_data: RestaurantCreateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a new restaurant with automatic balance record creation.

    This endpoint atomically creates both the restaurant record and its
    associated restaurant balance record to prevent race conditions.
    """
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Create restaurant data dict (credit_currency comes from institution_entity).
        # exclude_none=True: fields the client didn't send (e.g. is_featured, review_count,
        # verified_badge) stay out of the INSERT column list so the DB's NOT NULL DEFAULT
        # values apply. Without this, Pydantic's Optional[bool] = None default gets
        # passed to the CRUD service which builds an explicit `NULL` INSERT and violates
        # the NOT NULL constraint.
        restaurant_dict = restaurant_data.model_dump(exclude_none=True)
        if not scope.is_global:
            provided_institution = restaurant_dict.get("institution_id")
            if provided_institution and not scope.matches(provided_institution):
                raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=403, locale=locale)
            if not scope.institution_id:
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)
            restaurant_dict["institution_id"] = scope.institution_id

        # Restricted-institution validation (Vianda Customers / Vianda Enterprises) is enforced in CRUDService.create

        entity_id = restaurant_dict.get("institution_entity_id")
        if not entity_id:
            raise envelope_exception(ErrorCode.RESTAURANT_ENTITY_ID_REQUIRED, status=400, locale=locale)
        entity = institution_entity_service.get_by_id(entity_id, db, scope=scope)
        if not entity:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Institution entity")

        credit_currency = credit_currency_service.get_by_id(entity.currency_metadata_id, db)
        if not credit_currency:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Credit currency")

        restaurant_dict["modified_by"] = current_user["user_id"]
        restaurant_dict["status"] = "pending"

        # Create the restaurant record with commit=False for atomic transaction
        restaurant = restaurant_service.create(restaurant_dict, db, scope=scope, commit=False)
        if not restaurant:
            db.rollback()
            raise envelope_exception(ErrorCode.RESTAURANT_CREATION_FAILED, status=500, locale="en")

        log_info(f"Created restaurant record: {restaurant.restaurant_id} (commit deferred)")

        # Create the restaurant balance record atomically (commit=False)
        log_info(f"🔍 Creating restaurant balance record for restaurant {restaurant.restaurant_id}")
        log_info(f"🔍 Credit currency ID: {entity.currency_metadata_id}")
        log_info(f"🔍 Currency code: {credit_currency.currency_code}")
        log_info(f"🔍 Modified by: {current_user['user_id']}")

        try:
            balance_created = restaurant_balance_service.create_balance_record(
                restaurant.restaurant_id,
                entity.currency_metadata_id,
                currency_code=credit_currency.currency_code,
                modified_by=current_user["user_id"],
                db=db,
                commit=False,  # Defer commit for atomic transaction
            )

            log_info(f"🔍 Balance creation result: {balance_created}")

            if not balance_created:
                db.rollback()
                log_error(f"❌ Failed to create restaurant balance record for restaurant {restaurant.restaurant_id}")
                raise envelope_exception(ErrorCode.RESTAURANT_BALANCE_CREATION_FAILED, status=500, locale="en")

            # Commit both operations atomically
            db.commit()
            from app.services.address_service import update_address_type_from_linkages

            update_address_type_from_linkages(restaurant.address_id, db)
            log_info(
                f"✅ Successfully created restaurant {restaurant.restaurant_id} with balance record (atomic transaction)"
            )
            return RestaurantResponseSchema(**_restaurant_to_response(restaurant, db))

        except HTTPException:
            # HTTPException already handled rollback, just re-raise
            raise
        except Exception as e:
            db.rollback()
            log_error(f"❌ Exception during balance creation: {e}")
            raise envelope_exception(ErrorCode.RESTAURANT_CREATION_FAILED, status=500, locale="en") from None

    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error creating restaurant: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_CREATION_FAILED, status=500, locale="en") from None


def _restaurant_to_response(restaurant, db: psycopg2.extensions.connection) -> dict:
    """Enrich restaurant DTO with currency_metadata_id from institution_entity for response schema."""
    to_dict = getattr(restaurant, "model_dump", None) or getattr(restaurant, "dict", None)
    d = to_dict() if to_dict else dict(restaurant)
    d["currency_metadata_id"] = get_currency_metadata_id_for_restaurant(restaurant, db)
    return d


@router.get("", response_model=list[RestaurantResponseSchema])
def get_restaurants(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all restaurants"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        restaurants = restaurant_service.get_all(db, scope=scope)
        return [RestaurantResponseSchema(**_restaurant_to_response(r, db)) for r in restaurants]
    except Exception as e:
        log_error(f"Error getting restaurants: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_LIST_FAILED, status=500, locale="en") from None


# GET /restaurants/search/ - Search restaurants by name (e.g. discretionary recipient picker)
# Defined before GET /{restaurant_id} so that "/search" is not interpreted as restaurant_id.
@router.get("/search", response_model=RestaurantSearchResponseSchema)
def search_restaurants_route(
    q: str = Query("", description="Search string (substring match on name)"),
    search_by: str = Query("name", description="Field to search (only 'name' supported)"),
    limit: int = limit_query(20, 1, 100),
    offset: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    institution_id: UUID | None = institution_filter(),
    market_id: UUID | None = market_filter(),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Search restaurants by name with pagination.
    Used by the discretionary request modal (Restaurant picker) and other search-by-select UIs.
    Same auth and institution scoping as other restaurant list endpoints.
    Optional institution_id and market_id restrict results (Internal users may pass any institution; market-scoped Internal users only their assigned markets).
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)

    # Effective institution: Internal users may pass any; non-Internal users only their own (resolve_institution_filter).
    if institution_id is not None:
        if current_user.get("role_type") == "internal":
            effective_institution_id = institution_id
        else:
            effective_institution_id = resolve_institution_filter(institution_id, scope)
    else:
        effective_institution_id = None

    # market_id: market-scoped Internal users (Manager, Operator) may only pass one of their assigned markets.
    if market_id is not None and current_user.get("role_type") == "internal":
        role_name = current_user.get("role_name")
        rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
        if rn_str in ("manager", "operator"):
            assigned = get_assigned_market_ids(
                current_user["user_id"], db, fallback_primary=current_user.get("market_id")
            )
            if not assigned or market_id not in assigned:
                raise envelope_exception(ErrorCode.RESTAURANT_MARKET_ACCESS_DENIED, status=403, locale=locale)

    def _search():
        rows, total = search_restaurants(
            q=q,
            search_by=search_by,
            db=db,
            limit=limit,
            offset=offset,
            scope=scope,
            institution_id=effective_institution_id,
            market_id=market_id,
        )
        return {
            "results": [RestaurantSearchResultSchema(**r) for r in rows],
            "total": total,
        }

    return handle_business_operation(_search, "restaurant search")


# GET /restaurants/cities — B2C explore: list cities with restaurants for dropdown (Customer or Internal only; no institution scope)
@router.get("/cities", response_model=RestaurantExplorerCitiesResponseSchema)
def get_restaurant_cities(
    country_code: str | None = Query("US", description="ISO 3166-1 alpha-2 (e.g. US, AR)"),
    current_user: dict = Depends(get_client_or_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List city names that have at least one restaurant in the given country.
    Used to populate the explore UI city dropdown. Customer or Internal only; 403 for Supplier. No institution scope.
    """
    try:
        country = normalize_country_code(country_code, default="US")
        cities = get_cities_with_coverage(country, db)
        return RestaurantExplorerCitiesResponseSchema(cities=cities)
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error in GET /restaurants/cities: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_CITIES_LIST_FAILED, status=500, locale="en") from None


# GET /restaurants/explore/kitchen-days — B2C explore: allowed kitchen days for dropdown, ordered by date (closest first)
@router.get("/explore/kitchen-days", response_model=ExploreKitchenDaysResponseSchema)
def get_explore_kitchen_days(
    market_id: UUID | None = Query(None, description="Market for timezone; if omitted, user's primary market is used"),
    current_user: dict = Depends(get_client_or_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return the list of allowed kitchen days for the explore window (today through next week's Friday),
    ordered by date ascending (closest first). Use for the kitchen-day dropdown; default to the first item.
    Requires a market (send market_id or have a primary market).
    """
    user_id = current_user.get("user_id")
    assigned = get_assigned_market_ids(user_id, db, fallback_primary=current_user.get("market_id")) if user_id else []
    effective_market_id = market_id if market_id is not None else (assigned[0] if assigned else None)
    if effective_market_id is None:
        raise envelope_exception(ErrorCode.RESTAURANT_MARKET_REQUIRED, status=400, locale=locale)
    if market_id is not None and effective_market_id not in assigned:
        raise envelope_exception(ErrorCode.RESTAURANT_MARKET_ACCESS_DENIED, status=403, locale=locale)
    market = market_service.get_by_id(effective_market_id)
    if not market:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Market")
    timezone_str = market.get("timezone") or "UTC"
    country_code = (market.get("country_code") or "").strip().upper()
    items = get_allowed_kitchen_days_sorted_by_date(timezone_str, country_code)
    return ExploreKitchenDaysResponseSchema(kitchen_days=items)


# GET /restaurants/explore/pickup-windows — B2C explore: 15-minute pickup windows for a kitchen day
@router.get("/explore/pickup-windows", response_model=PickupWindowsResponseSchema)
def get_explore_pickup_windows(
    kitchen_day: str = Query(..., description="Weekday (Monday–Friday)"),
    date_str: str | None = Query(
        None, description="ISO date (YYYY-MM-DD); if omitted, next occurrence of kitchen_day is used"
    ),
    market_id: UUID | None = Query(None, description="Market for timezone; if omitted, user's primary market is used"),
    current_user: dict = Depends(get_client_or_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return 15-minute pickup windows for the given kitchen day in market local time.
    Use for the "Select pickup window" modal when reserving a plate.
    Requires a market (send market_id or have a primary market).
    """
    if kitchen_day not in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        raise envelope_exception(
            ErrorCode.VALIDATION_CUSTOM,
            status=400,
            locale=locale,
            msg="kitchen_day must be Monday, Tuesday, Wednesday, Thursday, or Friday",
        )
    user_id = current_user.get("user_id")
    assigned = get_assigned_market_ids(user_id, db, fallback_primary=current_user.get("market_id")) if user_id else []
    effective_market_id = market_id if market_id is not None else (assigned[0] if assigned else None)
    if effective_market_id is None:
        raise envelope_exception(ErrorCode.RESTAURANT_MARKET_REQUIRED, status=400, locale=locale)
    if market_id is not None and effective_market_id not in assigned:
        raise envelope_exception(ErrorCode.RESTAURANT_MARKET_ACCESS_DENIED, status=403, locale=locale)
    market = market_service.get_by_id(effective_market_id)
    if not market:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Market")
    timezone_str = market.get("timezone") or "UTC"
    country_code = (market.get("country_code") or "").strip().upper()
    try:
        validate_kitchen_day_in_window(kitchen_day, timezone_str)
    except ValueError as e:
        raise envelope_exception(ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg=str(e)) from None
    if date_str:
        from datetime import date

        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            raise envelope_exception(
                ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg="date must be YYYY-MM-DD"
            ) from None
    else:
        target_date = resolve_weekday_to_next_occurrence(kitchen_day, timezone_str)
    windows = get_pickup_windows_for_kitchen_day(country_code, kitchen_day, target_date)
    return PickupWindowsResponseSchema(
        kitchen_day=kitchen_day,
        date=target_date.isoformat(),
        pickup_windows=windows,
    )


# GET /restaurants/by-city — B2C explore: restaurants in a city for list/map; market + kitchen_day required for plates
@router.get("/by-city", response_model=RestaurantsByCityResponseSchema)
def get_restaurants_by_city_route(  # noqa: PLR0913 -- declarative FastAPI Query params, not algorithmic args
    city: str = Query(..., description="City name (from dropdown)"),
    country_code: str | None = Query("US", description="ISO 3166-1 alpha-2 (e.g. US, AR)"),
    market_id: UUID | None = Query(None, description="User's market; if omitted, primary market is used"),
    kitchen_day: str | None = Query(
        None,
        description="Monday–Friday; required when using market to get plates; must be this week or next week (through next Friday)",
    ),
    cursor: str | None = Query(
        None, description="Opaque cursor from previous response's next_cursor (infinite scroll)"
    ),
    limit: int | None = Query(
        None, ge=1, description="Max plates per page (clamped to 10–50); enables cursor pagination"
    ),
    cuisine: list[str] | None = Query(
        None,
        description="Filter by one or more cuisine names (multi-select OR logic; restaurant-level). Omit for all cuisines.",
    ),
    max_credits: int | None = Query(
        None,
        ge=1,
        description="Show only plates costing at most this many credits. Restaurants with no surviving plates are dropped.",
    ),
    dietary: list[str] | None = Query(
        None,
        description=(
            "Filter by dietary flags (multi-select OR logic). "
            "Plates must have AT LEAST ONE of the requested flags in their dietary TEXT[] column. "
            "Valid values: vegan, vegetarian, gluten_free, dairy_free, nut_free, halal, kosher. "
            "Restaurants with no surviving plates are dropped."
        ),
    ),
    lat: float | None = Query(
        None, description="Latitude of user center point for distance filter. Requires lng and radius_km."
    ),
    lng: float | None = Query(
        None, description="Longitude of user center point for distance filter. Requires lat and radius_km."
    ),
    radius_km: float | None = Query(
        None, gt=0, description="Radius in kilometres for distance filter. Requires lat and lng."
    ),
    current_user: dict = Depends(get_client_or_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return restaurants in the given city (name, cuisine, lat/lng) for list and map.
    When a market is used (market_id or user's primary market), kitchen_day is required to return plates.
    kitchen_day must fall within this week and next week (next week ends Friday); otherwise 400.
    City is matched case-insensitively. Customer or Internal only; 403 for Supplier. No institution scope.

    Optional filter params (all backward-compatible; omit for existing behavior):
    - cuisine: multi-select cuisine names (restaurant-level OR logic).
    - max_credits: integer threshold; plates with credit > max_credits are excluded.
      Restaurants with 0 surviving plates after this filter are dropped.
    - dietary: multi-select DietaryFlag values (vegan/vegetarian/gluten_free/dairy_free/nut_free/halal/kosher).
      Uses PostgreSQL array overlap (&&); plates match if they have AT LEAST ONE requested flag.
      Restaurants with 0 surviving plates are dropped. Invalid flag values return 400.
    - lat/lng/radius_km: distance filter via PostGIS ST_DWithin. All three must be present together
      or all absent; mixed presence returns 400. City-vs-radius: both constraints apply (AND).
    """
    if kitchen_day is not None and kitchen_day not in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        raise envelope_exception(
            ErrorCode.VALIDATION_CUSTOM,
            status=400,
            locale=locale,
            msg="kitchen_day must be Monday, Tuesday, Wednesday, Thursday, or Friday",
        )

    # K4: validate dietary flag values against the DietaryFlag enum
    if dietary:
        from app.config.enums.dietary_flags import DietaryFlag

        valid_flags = set(DietaryFlag.values())
        invalid = [d for d in dietary if d not in valid_flags]
        if invalid:
            raise envelope_exception(
                ErrorCode.VALIDATION_CUSTOM,
                status=400,
                locale=locale,
                msg=f"Unknown dietary flag(s): {', '.join(sorted(invalid))}. Valid values: {', '.join(sorted(valid_flags))}",
            )

    # K5: validate that lat/lng/radius_km are all-or-nothing
    geo_params = [lat, lng, radius_km]
    geo_present = [p is not None for p in geo_params]
    if any(geo_present) and not all(geo_present):
        missing = []
        if lat is None:
            missing.append("lat")
        if lng is None:
            missing.append("lng")
        if radius_km is None:
            missing.append("radius_km")
        raise envelope_exception(
            ErrorCode.VALIDATION_CUSTOM,
            status=400,
            locale=locale,
            msg=f"Distance filter requires all three params together: lat, lng, radius_km. Missing: {', '.join(missing)}",
        )
    geo_filter: tuple[float, float, float] | None = (lat, lng, radius_km) if lat is not None else None

    user_id = current_user.get("user_id")
    assigned = get_assigned_market_ids(user_id, db, fallback_primary=current_user.get("market_id")) if user_id else []
    effective_market_id = market_id if market_id is not None else (assigned[0] if assigned else None)
    country = normalize_country_code(country_code, default="US")
    timezone_str: str | None = None

    if effective_market_id is not None:
        if market_id is not None and effective_market_id not in assigned:
            raise envelope_exception(ErrorCode.RESTAURANT_MARKET_ACCESS_DENIED, status=403, locale=locale)
        market = market_service.get_by_id(effective_market_id)
        if not market:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Market")
        country = (market.get("country_code") or country).upper()
        timezone_str = market.get("timezone") or None
        # Only require kitchen_day when the client explicitly sent market_id (so explore-with-plates works).
        # When market is inferred from user assignment, allow omitting kitchen_day (no plates returned).
        if market_id is not None and not kitchen_day:
            raise envelope_exception(
                ErrorCode.VALIDATION_CUSTOM,
                status=400,
                locale=locale,
                msg="kitchen_day is required when using a market to get restaurant plates. Choose a weekday from this week or next week (through next Friday).",
            )
        if kitchen_day and timezone_str:
            try:
                validate_kitchen_day_in_window(kitchen_day, timezone_str)
            except ValueError as e:
                raise envelope_exception(ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg=str(e)) from None

    # Single subscription per user; savings use credit_cost_local_currency only when exploring in the user's subscription market.
    credit_cost_local_currency = None
    if effective_market_id and str(effective_market_id) == current_user.get("subscription_market_id"):
        credit_cost_local_currency = current_user.get("credit_cost_local_currency")
    # When no subscription in this market, show best savings from the most expensive plan in the market (teaser).
    if credit_cost_local_currency is None and effective_market_id is not None:
        credit_cost_local_currency = get_credit_cost_local_currency_of_most_expensive_plan_for_market(
            effective_market_id, db
        )

    user_id = current_user.get("user_id")
    if isinstance(user_id, str) and user_id:
        try:
            from uuid import UUID

            user_id = UUID(user_id)
        except (ValueError, TypeError):
            user_id = None
    elif not user_id:
        user_id = None

    employer_entity_id: UUID | None = None
    employer_address_id: UUID | None = None
    workplace_group_id: UUID | None = None
    if user_id:
        from app.utils.db import db_read

        user_row = db_read(
            "SELECT employer_entity_id, employer_address_id, workplace_group_id FROM user_info WHERE user_id = %s",
            (str(user_id),),
            connection=db,
            fetch_one=True,
        )
        if user_row:
            if user_row.get("employer_entity_id"):
                employer_entity_id = user_row["employer_entity_id"]
                employer_address_id = user_row.get("employer_address_id")
            workplace_group_id = user_row.get("workplace_group_id")

    try:
        data = get_restaurants_by_city(
            city=city,
            country_code=country,
            db=db,
            timezone_str=timezone_str,
            kitchen_day=kitchen_day,
            credit_cost_local_currency=credit_cost_local_currency,
            user_id=user_id,
            employer_entity_id=employer_entity_id,
            employer_address_id=employer_address_id,
            workplace_group_id=workplace_group_id,
            locale=locale,
            cursor=cursor,
            limit=limit,
            cuisine_filter=cuisine or None,
            max_credits=max_credits,
            dietary_filter=dietary or None,
            geo_filter=geo_filter,
        )
    except ValueError as exc:
        raise envelope_exception(ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg=str(exc)) from None
    data["restaurants"] = [RestaurantExplorerItemSchema(**r) for r in data["restaurants"]]
    return RestaurantsByCityResponseSchema(**data)


# =============================================================================
# ENRICHED RESTAURANT ENDPOINTS (with institution_name, entity_name, address details)
# Must be registered before /{restaurant_id} so /enriched is not parsed as restaurant_id.
# =============================================================================


# GET /restaurants/enriched - List all restaurants with enriched data
@router.get("/enriched", response_model=list[RestaurantEnrichedResponseSchema])
def list_enriched_restaurants(  # noqa: PLR0913 -- declarative FastAPI Query params, not algorithmic args
    response: Response,
    institution_id: UUID | None = institution_filter(),
    city: str | None = Query(None, description="Filter by city name (case-sensitive)"),
    market_id: UUID | None = Query(None, description="Filter by market ID"),
    kitchen_day: str | None = Query(None, description="Filter to restaurants serving this kitchen day (monday-friday)"),
    cuisine: list[str] | None = Query(None, description="Filter by one or more cuisine names (multi-select)"),
    search: str | None = Query(
        None, description="Search across restaurant name and tagline (case-insensitive substring)"
    ),
    bbox: str | None = Query(
        None,
        description=(
            "Bounding box filter (PostGIS). Comma-separated: min_lng,min_lat,max_lng,max_lat. "
            "Example: ?bbox=-74.05,40.68,-73.91,40.83 (lon/lat, WGS84). "
            "Requires PostGIS on the database."
        ),
    ),
    center: str | None = Query(
        None,
        description=(
            "Center point for radius filter (PostGIS). Comma-separated: lat,lng. "
            "Must be combined with radius_m. Example: ?center=40.7484,-73.9857&radius_m=1000"
        ),
    ),
    radius_m: float | None = Query(
        None,
        description="Search radius in metres for proximity filter. Must be combined with center.",
        gt=0,
    ),
    status: list[str] | None = Query(None, description="Filter by restaurant status(es) (multi-select)"),
    country_code: list[str] | None = Query(None, description="Filter by country code(s) (multi-select)"),
    institution_id_in: list[UUID] | None = Query(
        None,
        alias="institution_id_in",
        description="Filter by institution ID(s) (multi-select; distinct from scoping institution_id)",
    ),
    institution_entity_id: list[UUID] | None = Query(
        None, description="Filter by institution entity ID(s) (multi-select)"
    ),
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all restaurants with enriched data (institution_name, entity_name, address details). Optional institution_id filters by institution (B2B Internal dropdown scoping). Optional filters: city, market_id, kitchen_day, cuisine (multi-select), search, bbox (bounding box), center+radius_m (proximity), status, country_code, institution_id_in (multi-select), institution_entity_id (multi-select). When institution has a local market_id (v1), only restaurants in that market are returned. Non-archived only."""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        effective_institution_id = resolve_institution_filter(institution_id, scope)
        institution_market_id: UUID | None = None
        if effective_institution_id is not None:
            from app.services.entity_service import get_institution_market_ids

            inst_markets = get_institution_market_ids(effective_institution_id, db)
            if inst_markets and len(inst_markets) == 1 and not is_global_market(inst_markets[0]):
                institution_market_id = inst_markets[0]

        # Parse geo params from query string into the shapes filter_builder expects.
        bbox_value: list[float] | None = None
        if bbox is not None:
            try:
                parts = [p.strip() for p in bbox.split(",")]
                if len(parts) != 4:
                    raise ValueError(
                        f"bbox requires 4 comma-separated values (min_lng,min_lat,max_lng,max_lat), got {len(parts)}"
                    )
                bbox_value = [float(p) for p in parts]
            except ValueError as exc:
                raise envelope_exception(ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg=str(exc)) from None

        radius_value: list[float] | None = None
        if center is not None or radius_m is not None:
            if center is None or radius_m is None:
                raise envelope_exception(
                    ErrorCode.VALIDATION_CUSTOM,
                    status=400,
                    locale=locale,
                    msg="Both center (lat,lng) and radius_m are required for proximity filtering",
                )
            try:
                center_parts = [p.strip() for p in center.split(",")]
                if len(center_parts) != 2:
                    raise ValueError(f"center requires 2 comma-separated values (lat,lng), got {len(center_parts)}")
                lat = float(center_parts[0])
                lng = float(center_parts[1])
                radius_value = [lat, lng, float(radius_m)]
            except ValueError as exc:
                raise envelope_exception(ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg=str(exc)) from None

        try:
            filter_conditions = build_filter_conditions(
                "restaurants",
                {
                    "city": city,
                    "market_id": market_id,
                    "kitchen_day": kitchen_day,
                    "cuisine": cuisine,
                    "search": search,
                    "bbox": bbox_value,
                    "radius": radius_value,
                    "status": status,
                    "country_code": country_code,
                    "institution_id": [str(i) for i in institution_id_in] if institution_id_in else None,
                    "institution_entity_id": [str(e) for e in institution_entity_id] if institution_entity_id else None,
                },
            )
        except ValueError as exc:
            raise envelope_exception(ErrorCode.VALIDATION_CUSTOM, status=400, locale=locale, msg=str(exc)) from None
        enriched_restaurants = get_enriched_restaurants(
            db,
            scope=scope,
            include_archived=False,
            institution_id=effective_institution_id,
            institution_market_id=institution_market_id,
            additional_conditions=filter_conditions,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )
        if locale != "en":
            for r in enriched_restaurants:
                resolve_cuisine_name(r, locale)
                resolve_i18n_field(r, "tagline", locale)
                resolve_i18n_field(r, "spotlight_label", locale)
                resolve_i18n_list_field(r, "member_perks", locale)
        set_pagination_headers(response, enriched_restaurants)
        return enriched_restaurants
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched restaurants: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_ENRICHED_LIST_FAILED, status=500, locale="en") from None


# GET /restaurants/enriched/{restaurant_id} - Get a single restaurant with enriched data
@router.get("/enriched/{restaurant_id}", response_model=RestaurantEnrichedResponseSchema)
def get_enriched_restaurant_by_id_route(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single restaurant by ID with enriched data (institution_name, entity_name, address details). Non-archived only."""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        enriched_restaurant = get_enriched_restaurant_by_id(restaurant_id, db, scope=scope, include_archived=False)
        if not enriched_restaurant:
            raise entity_not_found("Restaurant", restaurant_id, locale=locale)
        if locale != "en":
            resolve_cuisine_name(enriched_restaurant, locale)
            resolve_i18n_field(enriched_restaurant, "tagline", locale)
            resolve_i18n_field(enriched_restaurant, "spotlight_label", locale)
            resolve_i18n_list_field(enriched_restaurant, "member_perks", locale)
        return enriched_restaurant
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched restaurant {restaurant_id}: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_ENRICHED_GET_FAILED, status=500, locale="en") from None


# GET /restaurants/{restaurant_id}/coworker-pickup-windows — must be before GET /{restaurant_id}
@router.get("/{restaurant_id}/coworker-pickup-windows", response_model=CoworkerPickupWindowsResponseSchema)
def get_coworker_pickup_windows_route(
    restaurant_id: UUID,
    kitchen_day: str = Query(..., description="Weekday (Monday–Friday) for pickup windows"),
    current_user: dict = Depends(get_client_or_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return coworker pickup windows (offer/request) for this restaurant and kitchen day.
    Modal fetches only when has_coworker_offer or has_coworker_request from by-city/enriched.
    Returns empty when user has no employer.
    """
    if kitchen_day not in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        raise envelope_exception(
            ErrorCode.VALIDATION_CUSTOM,
            status=400,
            locale=locale,
            msg="kitchen_day must be Monday, Tuesday, Wednesday, Thursday, or Friday",
        )
    user_id = current_user.get("user_id")
    if not user_id:
        raise envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale=locale)
    if isinstance(user_id, str):
        try:
            user_id = UUID(user_id)
        except (ValueError, TypeError):
            raise envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale=locale) from None
    windows = get_coworker_pickup_windows(restaurant_id, kitchen_day, user_id, db)
    return CoworkerPickupWindowsResponseSchema(pickup_windows=windows)


@router.get("/{restaurant_id}", response_model=RestaurantResponseSchema)
def get_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a specific restaurant by ID"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)
        return RestaurantResponseSchema(**_restaurant_to_response(restaurant, db))
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting restaurant {restaurant_id}: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_GET_FAILED, status=500, locale="en") from None


@router.put("/{restaurant_id}", response_model=RestaurantResponseSchema)
def update_restaurant(
    restaurant_id: UUID,
    restaurant_data: RestaurantUpdateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update a restaurant"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Check if restaurant exists
        existing_restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not existing_restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

        # Prepare update data
        update_data = restaurant_data.model_dump(exclude_unset=True)
        update_data["modified_by"] = current_user["user_id"]

        # institution_id is immutable after creation
        if "institution_id" in update_data:
            if str(update_data["institution_id"]) != str(existing_restaurant.institution_id):
                raise envelope_exception(
                    ErrorCode.ENTITY_FIELD_IMMUTABLE, status=400, locale=locale, field="institution_id"
                )
            update_data.pop("institution_id", None)

        # Setting status to Active requires (a) active plate_kitchen_days and (b) active QR code
        if update_data.get("status") == Status.ACTIVE:
            has_plate_kitchen_days = restaurant_has_active_plate_kitchen_days(restaurant_id, db)
            has_qr_code = restaurant_has_active_qr_code(restaurant_id, db)
            if not has_plate_kitchen_days and not has_qr_code:
                raise envelope_exception(ErrorCode.RESTAURANT_ACTIVE_REQUIRES_SETUP, status=400, locale=locale)
            if not has_plate_kitchen_days:
                raise envelope_exception(ErrorCode.RESTAURANT_ACTIVE_REQUIRES_PLATE_DAYS, status=400, locale=locale)
            if not has_qr_code:
                raise envelope_exception(ErrorCode.RESTAURANT_ACTIVE_REQUIRES_QR, status=400, locale=locale)

        # Update the restaurant
        updated_restaurant = restaurant_service.update(restaurant_id, update_data, db, scope=scope)
        if not updated_restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_UPDATE_FAILED, status=500, locale="en")

        # Check onboarding regression when status changes away from Active
        if "status" in update_data and update_data["status"] != Status.ACTIVE:
            from app.services.onboarding_service import check_onboarding_regression

            check_onboarding_regression("restaurant_info", restaurant_id, db)

        log_info(f"Successfully updated restaurant: {restaurant_id}")
        return RestaurantResponseSchema(**_restaurant_to_response(updated_restaurant, db))

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error updating restaurant {restaurant_id}: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_UPDATE_FAILED, status=500, locale="en") from None


@router.delete("/{restaurant_id}")
def delete_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Soft delete a restaurant"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Check if restaurant exists
        existing_restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not existing_restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

        from app.services.entity_service import validate_restaurant_can_be_archived

        validate_restaurant_can_be_archived(restaurant_id, db)

        # Soft delete the restaurant
        success = restaurant_service.soft_delete(restaurant_id, current_user["user_id"], db, scope=scope)
        if not success:
            raise envelope_exception(ErrorCode.RESTAURANT_DELETE_FAILED, status=500, locale="en")

        log_info(f"Successfully deleted restaurant: {restaurant_id}")
        return {"message": f"Restaurant {restaurant_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error deleting restaurant {restaurant_id}: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_DELETE_FAILED, status=500, locale="en") from None


@router.post("/{restaurant_id}/create-balance")
def create_balance_for_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Test endpoint to create balance record for a restaurant"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Check if restaurant exists
        restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

        entity = institution_entity_service.get_by_id(restaurant.institution_entity_id, db, scope=scope)
        if not entity:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Institution entity")
        credit_currency = credit_currency_service.get_by_id(entity.currency_metadata_id, db)
        if not credit_currency:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Credit currency")

        # Create balance record
        log_info(f"Creating balance record for restaurant {restaurant_id}")
        balance_created = restaurant_balance_service.create_balance_record(
            restaurant.restaurant_id,
            entity.currency_metadata_id,
            currency_code=credit_currency.currency_code,
            modified_by=current_user["user_id"],
            db=db,
        )

        if balance_created:
            return {"message": f"Balance record created successfully for restaurant {restaurant_id}"}
        raise envelope_exception(ErrorCode.RESTAURANT_BALANCE_CREATION_FAILED, status=500, locale="en")

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating balance for restaurant {restaurant_id}: {e}")
        raise envelope_exception(ErrorCode.RESTAURANT_BALANCE_CREATION_FAILED, status=500, locale="en") from None
