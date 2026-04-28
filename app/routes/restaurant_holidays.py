"""
Restaurant Holidays Routes

Routes for managing restaurant-specific holidays.
Supports single and bulk operations with national holiday validation.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user, get_employee_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.restaurant_holidays import (
    RestaurantHolidayBulkCreateSchema,
    RestaurantHolidayCreateSchema,
    RestaurantHolidayEnrichedResponseSchema,
    RestaurantHolidayResponseSchema,
    RestaurantHolidayUpdateSchema,
    RestaurantHolidayUpsertByKeySchema,
)
from app.security.entity_scoping import ENTITY_RESTAURANT_HOLIDAY, EntityScopingService
from app.services.crud_service import (
    address_service,
    find_restaurant_holiday_by_canonical_key,
    restaurant_holidays_service,
    restaurant_service,
)
from app.services.error_handling import handle_business_operation
from app.services.market_detection import MarketDetectionService
from app.services.plate_selection_validation import _is_date_national_holiday
from app.utils.db import db_batch_insert, db_read
from app.utils.log import log_info, log_warning


def _derive_restaurant_country_code(restaurant_id: UUID, db: psycopg2.extensions.connection, locale: str = "en") -> str:
    """ISO alpha-2 from address.country_code (preferred) or country name mapping."""
    restaurant = restaurant_service.get_by_id(restaurant_id, db)
    if not restaurant:
        raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=status.HTTP_404_NOT_FOUND, locale=locale)
    address = address_service.get_by_id(restaurant.address_id, db)
    if not address:
        raise envelope_exception(
            ErrorCode.ENTITY_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST,
            locale=locale,
            entity="Restaurant address",
        )
    cc = (address.country_code or "").strip()
    if len(cc) != 2 and address.country:
        mapped = MarketDetectionService._country_name_to_code(address.country)
        cc = (mapped or "").strip()
    if len(cc) != 2:
        raise envelope_exception(
            ErrorCode.VALIDATION_CUSTOM,
            status=status.HTTP_400_BAD_REQUEST,
            locale=locale,
            msg="Could not determine ISO country code for the restaurant address; ensure address.country_code is set.",
        )
    return cc


router = APIRouter(prefix="/restaurant-holidays", tags=["Restaurant Holidays"])


def _get_scope_for_entity(current_user: dict):
    """Get institution scope for restaurant holidays entity"""
    return EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_HOLIDAY, current_user)


def _validate_not_national_holiday(
    holiday_date: str, restaurant_id: UUID, db: psycopg2.extensions.connection, locale: str = "en"
) -> None:
    """
    Validate that a holiday date is not already a national holiday.

    Raises HTTPException if the date is a national holiday.

    Args:
        holiday_date: Date in YYYY-MM-DD format or date object
        restaurant_id: Restaurant ID to get country code
        db: Database connection
        locale: Locale for error messages

    Raises:
        HTTPException: If date is a national holiday
    """
    # Convert date to string if needed
    if hasattr(holiday_date, "isoformat"):
        date_str = holiday_date.isoformat()
    else:
        date_str = str(holiday_date)

    try:
        country_code = _derive_restaurant_country_code(restaurant_id, db, locale=locale)
    except HTTPException:
        log_warning(
            f"Could not determine country code for restaurant {restaurant_id}, skipping national holiday validation"
        )
        return

    # Check if date is a national holiday
    if _is_date_national_holiday(date_str, country_code, db):
        raise envelope_exception(
            ErrorCode.RESTAURANT_HOLIDAY_ON_NATIONAL_HOLIDAY,
            status=status.HTTP_409_CONFLICT,
            locale=locale,
            holiday_date=date_str,
        )


@router.get("", response_model=list[RestaurantHolidayResponseSchema])
def list_restaurant_holidays(
    restaurant_id: UUID | None = Query(None, description="Filter by restaurant ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List restaurant holidays.

    Suppliers can only see holidays for restaurants in their institution.
    Internal users can see all restaurant holidays.
    """
    scope = _get_scope_for_entity(current_user)

    def get_operation(connection: psycopg2.extensions.connection):
        # Build custom query with scoping
        conditions = []
        params = []

        conditions.append("restaurant_holidays.is_archived = FALSE")

        if restaurant_id:
            conditions.append("restaurant_holidays.restaurant_id = %s")
            params.append(str(restaurant_id))

        # Add institution scoping if needed
        if scope and not scope.is_global:
            conditions.append("r.institution_id = %s")
            params.append(str(scope.institution_id))

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Build query with JOIN for scoping
        query = f"""
            SELECT restaurant_holidays.*
            FROM restaurant_holidays
            INNER JOIN restaurant_info r ON restaurant_holidays.restaurant_id = r.restaurant_id
            {where_clause}
            ORDER BY restaurant_holidays.holiday_date DESC
        """

        results = db_read(query, tuple(params) if params else None, connection=connection)
        return [restaurant_holidays_service.dto_class(**row) for row in results] if results else []

    return handle_business_operation(get_operation, "restaurant holidays retrieval", None, db)


# Enriched routes MUST be before /{holiday_id} so /enriched is not parsed as holiday_id
@router.get("/enriched", response_model=list[RestaurantHolidayEnrichedResponseSchema])
def list_enriched_restaurant_holidays(
    restaurant_id: UUID | None = Query(None, description="Filter by restaurant ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get enriched restaurant holidays including both restaurant-specific holidays
    and applicable national holidays.

    This endpoint allows restaurant people (Suppliers) to see national holidays
    that apply to their restaurants without direct access to the employee-only
    national holidays API.

    Suppliers can only see holidays for restaurants in their institution.
    Internal users can see holidays for all restaurants.
    """
    scope = _get_scope_for_entity(current_user)

    def get_operation(connection: psycopg2.extensions.connection):
        from app.services.entity_service import get_enriched_restaurant_holidays

        return get_enriched_restaurant_holidays(
            restaurant_id=restaurant_id, db=connection, scope=scope, include_archived=False
        )

    return handle_business_operation(get_operation, "enriched restaurant holidays retrieval", None, db)


@router.get("/enriched/{restaurant_id}", response_model=list[RestaurantHolidayEnrichedResponseSchema])
def get_enriched_restaurant_holidays_by_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get enriched restaurant holidays for a specific restaurant.

    Returns both restaurant-specific holidays and applicable national holidays
    for the specified restaurant.
    """
    scope = _get_scope_for_entity(current_user)

    def get_operation(connection: psycopg2.extensions.connection):
        from app.services.entity_service import get_enriched_restaurant_holidays_by_restaurant

        return get_enriched_restaurant_holidays_by_restaurant(
            restaurant_id=restaurant_id, db=connection, scope=scope, include_archived=False
        )

    return handle_business_operation(get_operation, "enriched restaurant holidays retrieval by restaurant", None, db)


@router.get("/{holiday_id}", response_model=RestaurantHolidayResponseSchema)
def get_restaurant_holiday(
    holiday_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single restaurant holiday by ID. Non-archived only."""
    scope = _get_scope_for_entity(current_user)

    def get_operation(connection: psycopg2.extensions.connection):
        holiday = restaurant_holidays_service.get_by_id(holiday_id, connection, scope=scope)
        if not holiday:
            raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_NOT_FOUND, status=404, locale=locale)

        if holiday.is_archived:
            raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_NOT_FOUND, status=404, locale=locale)

        return holiday

    return handle_business_operation(get_operation, "restaurant holiday retrieval", None, db)


@router.post("", response_model=RestaurantHolidayResponseSchema, status_code=status.HTTP_201_CREATED)
def create_restaurant_holiday(
    payload: RestaurantHolidayCreateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a single restaurant holiday.

    Validates that the date is not already a national holiday.
    Suppliers can only create holidays for restaurants in their institution.
    """
    scope = _get_scope_for_entity(current_user)

    def create_operation(connection: psycopg2.extensions.connection):
        # Validate restaurant exists and belongs to user's institution (via scoping)
        restaurant = restaurant_service.get_by_id(payload.restaurant_id, connection, scope=scope)
        if not restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

        # Validate that date is not a national holiday
        _validate_not_national_holiday(payload.holiday_date, payload.restaurant_id, connection, locale=locale)

        # Check for duplicate restaurant holiday
        existing_query = """
            SELECT holiday_id FROM restaurant_holidays
            WHERE restaurant_id = %s
            AND holiday_date = %s
            AND is_archived = FALSE
        """
        existing = db_read(
            existing_query,
            (str(payload.restaurant_id), payload.holiday_date.isoformat()),
            connection=connection,
            fetch_one=True,
        )
        if existing:
            raise envelope_exception(
                ErrorCode.RESTAURANT_HOLIDAY_DUPLICATE,
                status=status.HTTP_409_CONFLICT,
                locale=locale,
                holiday_date=str(payload.holiday_date),
            )

        country_code = _derive_restaurant_country_code(payload.restaurant_id, connection, locale=locale)

        holiday_data = {
            "restaurant_id": str(payload.restaurant_id),
            "country_code": country_code,
            "holiday_date": payload.holiday_date.isoformat(),
            "holiday_name": payload.holiday_name,
            "is_recurring": payload.is_recurring,
            "recurring_month": payload.recurring_month,
            "recurring_day": payload.recurring_day,
            "is_archived": False,
            "modified_by": current_user["user_id"],
            "source": "manual",
        }

        # Create holiday
        created_holiday = restaurant_holidays_service.create(holiday_data, connection, scope=scope)

        log_info(f"Created restaurant holiday: {created_holiday.holiday_id} for restaurant {payload.restaurant_id}")
        return created_holiday

    return handle_business_operation(create_operation, "restaurant holiday creation", None, db)


@router.post("/bulk", response_model=list[RestaurantHolidayResponseSchema], status_code=status.HTTP_201_CREATED)
def create_restaurant_holidays_bulk(
    payload: RestaurantHolidayBulkCreateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create multiple restaurant holidays atomically.

    Validates that none of the dates are national holidays.
    If any date is a national holiday, the entire batch is rejected.
    Suppliers can only create holidays for restaurants in their institution.
    """
    scope = _get_scope_for_entity(current_user)

    def create_bulk_operation(connection: psycopg2.extensions.connection):
        # Validate all holidays before creating any (fail fast)
        for holiday in payload.holidays:
            # Validate restaurant exists and belongs to user's institution
            restaurant = restaurant_service.get_by_id(holiday.restaurant_id, connection, scope=scope)
            if not restaurant:
                raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

            # Validate that date is not a national holiday
            _validate_not_national_holiday(holiday.holiday_date, holiday.restaurant_id, connection, locale=locale)

            # Check for duplicate restaurant holiday
            existing_query = """
                SELECT holiday_id FROM restaurant_holidays
                WHERE restaurant_id = %s
                AND holiday_date = %s
                AND is_archived = FALSE
            """
            existing = db_read(
                existing_query,
                (str(holiday.restaurant_id), holiday.holiday_date.isoformat()),
                connection=connection,
                fetch_one=True,
            )
            if existing:
                raise envelope_exception(
                    ErrorCode.RESTAURANT_HOLIDAY_DUPLICATE,
                    status=status.HTTP_409_CONFLICT,
                    locale=locale,
                    holiday_date=str(holiday.holiday_date),
                )

        # Prepare data for batch insert
        data_list = []
        for holiday in payload.holidays:
            cc = _derive_restaurant_country_code(holiday.restaurant_id, connection, locale=locale)
            data_list.append(
                {
                    "restaurant_id": str(holiday.restaurant_id),
                    "country_code": cc,
                    "holiday_date": holiday.holiday_date.isoformat(),
                    "holiday_name": holiday.holiday_name,
                    "is_recurring": holiday.is_recurring,
                    "recurring_month": holiday.recurring_month,
                    "recurring_day": holiday.recurring_day,
                    "is_archived": False,
                    "modified_by": current_user["user_id"],
                    "source": "manual",
                }
            )

        # Batch insert all holidays atomically using db_batch_insert
        inserted_ids = db_batch_insert("restaurant_holidays", data_list, connection)

        # Fetch created records to return
        created_holidays = []
        for inserted_id in inserted_ids:
            holiday = restaurant_holidays_service.get_by_id(UUID(inserted_id), connection, scope=scope)
            if holiday:
                created_holidays.append(holiday)

        log_info(f"Created {len(created_holidays)} restaurant holidays in bulk")
        return created_holidays

    return handle_business_operation(create_bulk_operation, "restaurant holidays bulk creation", None, db)


# PUT /restaurant-holidays/by-key — idempotent upsert (seed/fixture endpoint).
# MUST be registered before PUT /{holiday_id} so the static segment "by-key"
# wins over the UUID path parameter (FastAPI evaluates in registration order).
@router.put("/by-key", response_model=RestaurantHolidayResponseSchema, status_code=200)
def upsert_restaurant_holiday_by_key(
    upsert_data: RestaurantHolidayUpsertByKeySchema,
    current_user: dict = Depends(get_employee_user),  # Internal-only
    db: psycopg2.extensions.connection = Depends(get_db),
) -> RestaurantHolidayResponseSchema:
    """Idempotent upsert a restaurant holiday by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT — never use for ad-hoc holiday creation
    (use POST /restaurant-holidays instead).

    If a holiday with this canonical_key already exists it is updated in-place;
    otherwise a new holiday is inserted.

    Immutable fields on UPDATE: ``restaurant_id`` and ``holiday_date`` are
    locked after insert and ignored on the update path (the identity of a holiday
    is the (restaurant_id, holiday_date) pair; changing either would create a
    logically different holiday).

    Auth: Internal only (get_employee_user dependency).  Returns 403 for
    Customer/Supplier roles.

    Returns HTTP 200 on both insert and update (unlike POST which returns 201).
    """

    def _upsert() -> RestaurantHolidayResponseSchema:
        key = upsert_data.canonical_key
        modified_by = current_user["user_id"]

        # Primary lookup: by canonical_key.
        existing = find_restaurant_holiday_by_canonical_key(key, db)

        if existing is not None:
            # UPDATE path — restaurant_id and holiday_date are immutable; update all other fields.
            holiday_id = existing.holiday_id
            update_data = {
                "holiday_name": upsert_data.holiday_name,
                "is_recurring": upsert_data.is_recurring,
                "recurring_month": upsert_data.recurring_month,
                "recurring_day": upsert_data.recurring_day,
                "status": upsert_data.status.value if hasattr(upsert_data.status, "value") else upsert_data.status,
                "modified_by": str(modified_by),
            }
            updated = restaurant_holidays_service.update(holiday_id, update_data, db)
            if updated is None:
                raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
            # Persist canonical_key (restaurant_holidays_service.update does not touch it)
            with db.cursor() as cur:
                cur.execute(
                    """UPDATE ops.restaurant_holidays
                       SET canonical_key = %s,
                           modified_date = CURRENT_TIMESTAMP
                       WHERE holiday_id = %s""",
                    (key, str(holiday_id)),
                )
            db.commit()
            log_info(f"Upsert updated restaurant holiday {holiday_id} with canonical_key '{key}'")
            refreshed = restaurant_holidays_service.get_by_id(holiday_id, db)
            if refreshed is None:
                raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_NOT_FOUND, status=404, locale="en")
            return RestaurantHolidayResponseSchema.model_validate(refreshed)

        # INSERT path — validate restaurant exists, derive country_code, create holiday.
        restaurant = restaurant_service.get_by_id(upsert_data.restaurant_id, db)
        if not restaurant:
            raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale="en")

        country_code = _derive_restaurant_country_code(upsert_data.restaurant_id, db, locale="en")

        holiday_data = {
            "restaurant_id": str(upsert_data.restaurant_id),
            "country_code": country_code,
            "holiday_date": upsert_data.holiday_date.isoformat(),
            "holiday_name": upsert_data.holiday_name,
            "is_recurring": upsert_data.is_recurring,
            "recurring_month": upsert_data.recurring_month,
            "recurring_day": upsert_data.recurring_day,
            "is_archived": False,
            "modified_by": str(modified_by),
            "source": "manual",
            "canonical_key": key,
            "status": upsert_data.status.value if hasattr(upsert_data.status, "value") else upsert_data.status,
        }

        created = restaurant_holidays_service.create(holiday_data, db)
        if created is None:
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
        log_info(f"Upsert inserted restaurant holiday {created.holiday_id} with canonical_key '{key}'")
        return RestaurantHolidayResponseSchema.model_validate(created)

    return handle_business_operation(_upsert, "restaurant holiday upsert by canonical key")


@router.put("/{holiday_id}", response_model=RestaurantHolidayResponseSchema)
def update_restaurant_holiday(
    holiday_id: UUID,
    payload: RestaurantHolidayUpdateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Update an existing restaurant holiday.

    If holiday_date is being updated, validates that the new date is not a national holiday.
    Suppliers can only update holidays for restaurants in their institution.
    """
    scope = _get_scope_for_entity(current_user)

    def update_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = restaurant_holidays_service.get_by_id(holiday_id, connection, scope=scope)
        if not existing:
            raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_NOT_FOUND, status=404, locale=locale)

        # Determine restaurant_id to use (existing or updated)
        restaurant_id = payload.restaurant_id if payload.restaurant_id is not None else existing.restaurant_id

        # If restaurant_id is being changed, validate new restaurant
        if payload.restaurant_id is not None:
            restaurant = restaurant_service.get_by_id(payload.restaurant_id, connection, scope=scope)
            if not restaurant:
                raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

        # If holiday_date is being updated, validate it's not a national holiday
        if payload.holiday_date is not None:
            _validate_not_national_holiday(payload.holiday_date, restaurant_id, connection, locale=locale)

            # Check for duplicate restaurant holiday (excluding current record)
            existing_query = """
                SELECT holiday_id FROM restaurant_holidays
                WHERE restaurant_id = %s
                AND holiday_date = %s
                AND holiday_id != %s
                AND is_archived = FALSE
            """
            existing_duplicate = db_read(
                existing_query,
                (str(restaurant_id), payload.holiday_date.isoformat(), str(holiday_id)),
                connection=connection,
                fetch_one=True,
            )
            if existing_duplicate:
                raise envelope_exception(
                    ErrorCode.RESTAURANT_HOLIDAY_DUPLICATE,
                    status=status.HTTP_409_CONFLICT,
                    locale=locale,
                    holiday_date=str(payload.holiday_date),
                )

        update_data: dict = {}
        if payload.restaurant_id is not None:
            update_data["restaurant_id"] = str(payload.restaurant_id)
            update_data["country_code"] = _derive_restaurant_country_code(
                payload.restaurant_id, connection, locale=locale
            )
        if payload.holiday_date is not None:
            update_data["holiday_date"] = payload.holiday_date.isoformat()
        if payload.holiday_name is not None:
            update_data["holiday_name"] = payload.holiday_name
        if payload.is_recurring is not None:
            update_data["is_recurring"] = payload.is_recurring
            if payload.is_recurring is False:
                update_data["recurring_month"] = None
                update_data["recurring_day"] = None
        if payload.recurring_month is not None:
            update_data["recurring_month"] = payload.recurring_month
        if payload.recurring_day is not None:
            update_data["recurring_day"] = payload.recurring_day

        update_data["modified_by"] = current_user["user_id"]

        # Update holiday
        updated = restaurant_holidays_service.update(holiday_id, update_data, connection, scope=scope)
        if not updated:
            raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_UPDATE_FAILED, status=500, locale="en")
        log_info(f"Updated restaurant holiday: {holiday_id}")
        return updated

    return handle_business_operation(update_operation, "restaurant holiday update", None, db)


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restaurant_holiday(
    holiday_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Soft delete (archive) a restaurant holiday"""
    scope = _get_scope_for_entity(current_user)

    def delete_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = restaurant_holidays_service.get_by_id(holiday_id, connection, scope=scope)
        if not existing:
            raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_NOT_FOUND, status=404, locale=locale)

        # Soft delete (archive) - CRUDService handles scoping automatically
        success = restaurant_holidays_service.soft_delete(holiday_id, current_user["user_id"], connection, scope=scope)
        if not success:
            raise envelope_exception(ErrorCode.RESTAURANT_HOLIDAY_DELETE_FAILED, status=500, locale="en")
        log_info(f"Deleted (archived) restaurant holiday: {holiday_id}")
        return

    handle_business_operation(delete_operation, "restaurant holiday deletion", None, db)
    return
