"""
Restaurant Holidays Routes

Routes for managing restaurant-specific holidays.
Supports single and bulk operations with national holiday validation.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from typing import List, Optional
import psycopg2.extensions

from app.schemas.restaurant_holidays import (
    RestaurantHolidayCreateSchema,
    RestaurantHolidayUpdateSchema,
    RestaurantHolidayResponseSchema,
    RestaurantHolidayBulkCreateSchema,
    RestaurantHolidayEnrichedResponseSchema
)
from app.services.crud_service import restaurant_holidays_service, restaurant_service, address_service
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_batch_insert, db_read
from app.security.entity_scoping import EntityScopingService, ENTITY_RESTAURANT_HOLIDAY
from app.services.market_detection import MarketDetectionService
from app.services.plate_selection_validation import _is_date_national_holiday

router = APIRouter(
    prefix="/restaurant-holidays",
    tags=["Restaurant Holidays"]
)


def _get_scope_for_entity(current_user: dict):
    """Get institution scope for restaurant holidays entity"""
    return EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_HOLIDAY, current_user)


def _get_restaurant_country_code(restaurant_id: UUID, db: psycopg2.extensions.connection) -> Optional[str]:
    """
    Get country code for a restaurant by looking up its address.
    
    Args:
        restaurant_id: Restaurant ID
        db: Database connection
        
    Returns:
        Country code (2-letter ISO code) or None if not found
    """
    try:
        restaurant = restaurant_service.get_by_id(restaurant_id, db)
        if not restaurant:
            return None
        
        address = address_service.get_by_id(restaurant.address_id, db)
        if not address or not address.country:
            return None
        
        # Convert country name to country code
        country_code = MarketDetectionService._country_name_to_code(address.country)
        return country_code
    except Exception as e:
        log_error(f"Error getting country code for restaurant {restaurant_id}: {e}")
        return None


def _validate_not_national_holiday(
    holiday_date: str,
    restaurant_id: UUID,
    db: psycopg2.extensions.connection
) -> None:
    """
    Validate that a holiday date is not already a national holiday.
    
    Raises HTTPException if the date is a national holiday.
    
    Args:
        holiday_date: Date in YYYY-MM-DD format or date object
        restaurant_id: Restaurant ID to get country code
        db: Database connection
        
    Raises:
        HTTPException: If date is a national holiday
    """
    # Convert date to string if needed
    if hasattr(holiday_date, 'isoformat'):
        date_str = holiday_date.isoformat()
    else:
        date_str = str(holiday_date)
    
    # Get country code for the restaurant
    country_code = _get_restaurant_country_code(restaurant_id, db)
    if not country_code:
        log_warning(f"Could not determine country code for restaurant {restaurant_id}, skipping national holiday validation")
        return  # Can't validate without country code, allow it
    
    # Check if date is a national holiday
    if _is_date_national_holiday(date_str, country_code, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Date {date_str} is already a national holiday. Restaurants cannot register holidays on national holidays."
        )


@router.get("", response_model=List[RestaurantHolidayResponseSchema])
def list_restaurant_holidays(
    restaurant_id: Optional[UUID] = Query(None, description="Filter by restaurant ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List restaurant holidays.
    
    Suppliers can only see holidays for restaurants in their institution.
    Employees can see all restaurant holidays.
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


@router.get("/{holiday_id}", response_model=RestaurantHolidayResponseSchema)
def get_restaurant_holiday(
    holiday_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single restaurant holiday by ID. Non-archived only."""
    scope = _get_scope_for_entity(current_user)
    
    def get_operation(connection: psycopg2.extensions.connection):
        holiday = restaurant_holidays_service.get_by_id(holiday_id, connection, scope=scope)
        if not holiday:
            raise HTTPException(status_code=404, detail=f"Restaurant holiday not found: {holiday_id}")
        
        if holiday.is_archived:
            raise HTTPException(status_code=404, detail=f"Restaurant holiday not found: {holiday_id}")
        
        return holiday
    
    return handle_business_operation(get_operation, "restaurant holiday retrieval", None, db)


@router.post("", response_model=RestaurantHolidayResponseSchema, status_code=status.HTTP_201_CREATED)
def create_restaurant_holiday(
    payload: RestaurantHolidayCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
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
            raise HTTPException(status_code=404, detail=f"Restaurant not found: {payload.restaurant_id}")
        
        # Validate that date is not a national holiday
        _validate_not_national_holiday(payload.holiday_date, payload.restaurant_id, connection)
        
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
            fetch_one=True
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Restaurant already has a holiday registered for {payload.holiday_date}"
            )
        
        # Prepare data for insert
        holiday_data = {
            "restaurant_id": str(payload.restaurant_id),
            "country": payload.country,
            "holiday_date": payload.holiday_date.isoformat(),
            "holiday_name": payload.holiday_name,
            "is_recurring": payload.is_recurring,
            "recurring_month_day": payload.recurring_month_day,
            "is_archived": False,
            "modified_by": current_user["user_id"]
        }
        
        # Create holiday
        created_holiday = restaurant_holidays_service.create(holiday_data, connection, scope=scope)
        
        log_info(f"Created restaurant holiday: {created_holiday.holiday_id} for restaurant {payload.restaurant_id}")
        return created_holiday
    
    return handle_business_operation(create_operation, "restaurant holiday creation", None, db)


@router.post("/bulk", response_model=List[RestaurantHolidayResponseSchema], status_code=status.HTTP_201_CREATED)
def create_restaurant_holidays_bulk(
    payload: RestaurantHolidayBulkCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
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
                raise HTTPException(
                    status_code=404,
                    detail=f"Restaurant not found: {holiday.restaurant_id}"
                )
            
            # Validate that date is not a national holiday
            _validate_not_national_holiday(holiday.holiday_date, holiday.restaurant_id, connection)
            
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
                fetch_one=True
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Restaurant {holiday.restaurant_id} already has a holiday registered for {holiday.holiday_date}"
                )
        
        # Prepare data for batch insert
        data_list = []
        for holiday in payload.holidays:
            data_list.append({
                "restaurant_id": str(holiday.restaurant_id),
                "country": holiday.country,
                "holiday_date": holiday.holiday_date.isoformat(),
                "holiday_name": holiday.holiday_name,
                "is_recurring": holiday.is_recurring,
                "recurring_month_day": holiday.recurring_month_day,
                "is_archived": False,
                "modified_by": current_user["user_id"]
            })
        
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


@router.put("/{holiday_id}", response_model=RestaurantHolidayResponseSchema)
def update_restaurant_holiday(
    holiday_id: UUID,
    payload: RestaurantHolidayUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
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
            raise HTTPException(status_code=404, detail="Restaurant holiday not found")
        
        # Determine restaurant_id to use (existing or updated)
        restaurant_id = payload.restaurant_id if payload.restaurant_id is not None else existing.restaurant_id
        
        # If restaurant_id is being changed, validate new restaurant
        if payload.restaurant_id is not None:
            restaurant = restaurant_service.get_by_id(payload.restaurant_id, connection, scope=scope)
            if not restaurant:
                raise HTTPException(status_code=404, detail=f"Restaurant not found: {payload.restaurant_id}")
        
        # If holiday_date is being updated, validate it's not a national holiday
        if payload.holiday_date is not None:
            _validate_not_national_holiday(payload.holiday_date, restaurant_id, connection)
            
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
                fetch_one=True
            )
            if existing_duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Restaurant already has a holiday registered for {payload.holiday_date}"
                )
        
        # Build update data
        update_data = {}
        if payload.restaurant_id is not None:
            update_data["restaurant_id"] = str(payload.restaurant_id)
        if payload.country is not None:
            update_data["country"] = payload.country
        if payload.holiday_date is not None:
            update_data["holiday_date"] = payload.holiday_date.isoformat()
        if payload.holiday_name is not None:
            update_data["holiday_name"] = payload.holiday_name
        if payload.is_recurring is not None:
            update_data["is_recurring"] = payload.is_recurring
        if payload.recurring_month_day is not None:
            update_data["recurring_month_day"] = payload.recurring_month_day
        
        update_data["modified_by"] = current_user["user_id"]
        
        # Update holiday
        updated = restaurant_holidays_service.update(holiday_id, update_data, connection, scope=scope)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update restaurant holiday")
        
        log_info(f"Updated restaurant holiday: {holiday_id}")
        return updated
    
    return handle_business_operation(update_operation, "restaurant holiday update", None, db)


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restaurant_holiday(
    holiday_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Soft delete (archive) a restaurant holiday"""
    scope = _get_scope_for_entity(current_user)
    
    def delete_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = restaurant_holidays_service.get_by_id(holiday_id, connection, scope=scope)
        if not existing:
            raise HTTPException(status_code=404, detail="Restaurant holiday not found")
        
        # Soft delete (archive) - CRUDService handles scoping automatically
        success = restaurant_holidays_service.soft_delete(
            holiday_id,
            current_user["user_id"],
            connection,
            scope=scope
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete restaurant holiday")
        
        log_info(f"Deleted (archived) restaurant holiday: {holiday_id}")
        return None
    
    handle_business_operation(delete_operation, "restaurant holiday deletion", None, db)
    return None


@router.get("/enriched", response_model=List[RestaurantHolidayEnrichedResponseSchema])
def list_enriched_restaurant_holidays(
    restaurant_id: Optional[UUID] = Query(None, description="Filter by restaurant ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get enriched restaurant holidays including both restaurant-specific holidays
    and applicable national holidays.
    
    This endpoint allows restaurant people (Suppliers) to see national holidays
    that apply to their restaurants without direct access to the employee-only
    national holidays API.
    
    Suppliers can only see holidays for restaurants in their institution.
    Employees can see holidays for all restaurants.
    """
    scope = _get_scope_for_entity(current_user)
    
    def get_operation(connection: psycopg2.extensions.connection):
        from app.services.entity_service import get_enriched_restaurant_holidays
        return get_enriched_restaurant_holidays(
            restaurant_id=restaurant_id,
            db=connection,
            scope=scope,
            include_archived=False
        )
    
    return handle_business_operation(get_operation, "enriched restaurant holidays retrieval", None, db)


@router.get("/enriched/{restaurant_id}", response_model=List[RestaurantHolidayEnrichedResponseSchema])
def get_enriched_restaurant_holidays_by_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
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
            restaurant_id=restaurant_id,
            db=connection,
            scope=scope,
            include_archived=False
        )
    
    return handle_business_operation(get_operation, "enriched restaurant holidays retrieval by restaurant", None, db)

