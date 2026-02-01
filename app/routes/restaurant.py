# app/routes/restaurant.py
"""
Custom restaurant routes with automatic balance creation.
"""

from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from typing import List, Optional
import psycopg2.extensions

from app.schemas.consolidated_schemas import (
    RestaurantCreateSchema,
    RestaurantUpdateSchema,
    RestaurantResponseSchema,
    RestaurantEnrichedResponseSchema,
)
from app.services.crud_service import (
    restaurant_service,
    restaurant_balance_service,
    credit_currency_service,
    institution_entity_service,
)
from app.services.entity_service import (
    get_enriched_restaurants,
    get_enriched_restaurant_by_id,
)
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning, log_error
from app.utils.query_params import include_archived_optional_query, include_archived_query
from app.utils.error_messages import entity_not_found
from app.security.entity_scoping import EntityScopingService, ENTITY_RESTAURANT

router = APIRouter(
    prefix="/restaurants",
    tags=["Restaurants"],
)

@router.post("/", response_model=RestaurantResponseSchema)
def create_restaurant(
    restaurant_data: RestaurantCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create a new restaurant with automatic balance record creation.
    
    This endpoint atomically creates both the restaurant record and its
    associated restaurant balance record to prevent race conditions.
    """
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Validate that the credit currency exists
        credit_currency = credit_currency_service.get_by_id(restaurant_data.credit_currency_id, db)
        if not credit_currency:
            raise HTTPException(
                status_code=404, 
                detail=f"Credit currency not found for currency_id {restaurant_data.credit_currency_id}"
            )
        
        # Create restaurant data dict
        restaurant_dict = restaurant_data.dict()
        if not scope.is_global:
            provided_institution = restaurant_dict.get("institution_id")
            if provided_institution and not scope.matches(provided_institution):
                raise HTTPException(status_code=403, detail="Forbidden: institution mismatch")
            if not scope.institution_id:
                raise HTTPException(status_code=403, detail="Forbidden: missing institution scope")
            restaurant_dict["institution_id"] = scope.institution_id

        entity_id = restaurant_dict.get("institution_entity_id")
        if entity_id:
            entity = institution_entity_service.get_by_id(entity_id, db, scope=scope)
            if not entity:
                raise HTTPException(status_code=404, detail="Institution entity not found")

        restaurant_dict["modified_by"] = current_user["user_id"]
        
        # Create the restaurant record with commit=False for atomic transaction
        restaurant = restaurant_service.create(restaurant_dict, db, scope=scope, commit=False)
        if not restaurant:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create restaurant record")
        
        log_info(f"Created restaurant record: {restaurant.restaurant_id} (commit deferred)")
        
        # Create the restaurant balance record atomically (commit=False)
        log_info(f"🔍 Creating restaurant balance record for restaurant {restaurant.restaurant_id}")
        log_info(f"🔍 Credit currency ID: {restaurant.credit_currency_id}")
        log_info(f"🔍 Currency code: {credit_currency.currency_code}")
        log_info(f"🔍 Modified by: {current_user['user_id']}")
        
        try:
            balance_created = restaurant_balance_service.create_balance_record(
                restaurant.restaurant_id,
                restaurant.credit_currency_id,
                currency_code=credit_currency.currency_code,
                modified_by=current_user["user_id"],
                db=db,
                commit=False  # Defer commit for atomic transaction
            )
            
            log_info(f"🔍 Balance creation result: {balance_created}")
            
            if not balance_created:
                db.rollback()
                log_error(f"❌ Failed to create restaurant balance record for restaurant {restaurant.restaurant_id}")
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to create restaurant balance record"
                )
            
            # Commit both operations atomically
            db.commit()
            log_info(f"✅ Successfully created restaurant {restaurant.restaurant_id} with balance record (atomic transaction)")
            
        except HTTPException:
            # HTTPException already handled rollback, just re-raise
            raise
        except Exception as e:
            db.rollback()
            log_error(f"❌ Exception during balance creation: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to create restaurant: {str(e)}"
            )
        
        return restaurant
        
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error creating restaurant: {e}")
        raise HTTPException(status_code=500, detail="Failed to create restaurant")

@router.get("/", response_model=List[RestaurantResponseSchema])
def get_restaurants(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all restaurants"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        restaurants = restaurant_service.get_all(db, scope=scope)
        return restaurants
    except Exception as e:
        log_error(f"Error getting restaurants: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve restaurants")

@router.get("/{restaurant_id}", response_model=RestaurantResponseSchema)
def get_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a specific restaurant by ID"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not restaurant:
            raise HTTPException(status_code=404, detail=f"Restaurant not found for restaurant_id {restaurant_id}")
        return restaurant
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve restaurant")

@router.put("/{restaurant_id}", response_model=RestaurantResponseSchema)
def update_restaurant(
    restaurant_id: UUID,
    restaurant_data: RestaurantUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update a restaurant"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Check if restaurant exists
        existing_restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not existing_restaurant:
            raise HTTPException(status_code=404, detail=f"Restaurant not found for restaurant_id {restaurant_id}")
        
        # Prepare update data
        update_data = restaurant_data.dict(exclude_unset=True)
        update_data["modified_by"] = current_user["user_id"]
        
        # Update the restaurant
        updated_restaurant = restaurant_service.update(restaurant_id, update_data, db, scope=scope)
        if not updated_restaurant:
            raise HTTPException(status_code=500, detail="Failed to update restaurant")
        
        log_info(f"Successfully updated restaurant: {restaurant_id}")
        return updated_restaurant
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error updating restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update restaurant")

@router.delete("/{restaurant_id}")
def delete_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Soft delete a restaurant"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Check if restaurant exists
        existing_restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not existing_restaurant:
            raise HTTPException(status_code=404, detail=f"Restaurant not found for restaurant_id {restaurant_id}")
        
        # Soft delete the restaurant
        success = restaurant_service.soft_delete(restaurant_id, current_user["user_id"], db, scope=scope)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete restaurant")
        
        log_info(f"Successfully deleted restaurant: {restaurant_id}")
        return {"message": f"Restaurant {restaurant_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error deleting restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete restaurant")

@router.post("/{restaurant_id}/create-balance")
def create_balance_for_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Test endpoint to create balance record for a restaurant"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        # Check if restaurant exists
        restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=scope)
        if not restaurant:
            raise HTTPException(status_code=404, detail=f"Restaurant not found for restaurant_id {restaurant_id}")
        
        # Get credit currency
        credit_currency = credit_currency_service.get_by_id(restaurant.credit_currency_id, db)
        if not credit_currency:
            raise HTTPException(status_code=404, detail=f"Credit currency not found")
        
        # Create balance record
        log_info(f"Creating balance record for restaurant {restaurant_id}")
        balance_created = restaurant_balance_service.create_balance_record(
            restaurant.restaurant_id,
            restaurant.credit_currency_id,
            currency_code=credit_currency.currency_code,
            modified_by=current_user["user_id"],
            db=db
        )
        
        if balance_created:
            return {"message": f"Balance record created successfully for restaurant {restaurant_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create balance record")
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating balance for restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create balance record")

# =============================================================================
# ENRICHED RESTAURANT ENDPOINTS (with institution_name, entity_name, address details)
# =============================================================================

# GET /restaurants/enriched/ - List all restaurants with enriched data
@router.get("/enriched/", response_model=List[RestaurantEnrichedResponseSchema])
def list_enriched_restaurants(
    include_archived: Optional[bool] = include_archived_optional_query("restaurants"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all restaurants with enriched data (institution_name, entity_name, address details)"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        enriched_restaurants = get_enriched_restaurants(
            db,
            scope=scope,
            include_archived=include_archived or False
        )
        return enriched_restaurants
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched restaurants: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched restaurants")

# GET /restaurants/enriched/{restaurant_id} - Get a single restaurant with enriched data
@router.get("/enriched/{restaurant_id}", response_model=RestaurantEnrichedResponseSchema)
def get_enriched_restaurant_by_id_route(
    restaurant_id: UUID,
    include_archived: bool = include_archived_query("restaurants"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single restaurant by ID with enriched data (institution_name, entity_name, address details)"""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
        enriched_restaurant = get_enriched_restaurant_by_id(
            restaurant_id,
            db,
            scope=scope,
            include_archived=include_archived
        )
        if not enriched_restaurant:
            raise entity_not_found("Restaurant", restaurant_id)
        return enriched_restaurant
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched restaurant")
