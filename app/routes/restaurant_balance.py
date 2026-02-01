# app/routes/restaurant_balance.py
"""
Restaurant Balance Routes - Read-Only Endpoints

This module provides read-only access to restaurant balance information.
Restaurant balances are automatically managed by the backend through transactions
and billing operations. They cannot be created or modified via API.

**Important**: These endpoints are read-only. All balance updates are handled
automatically by the system when:
- Customers place orders (via plate selection)
- Customers arrive at restaurants (via QR code scan)
- Institution bills are generated and paid
- Transactions are processed
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from uuid import UUID
import psycopg2.extensions

from app.schemas.consolidated_schemas import (
    RestaurantBalanceResponseSchema,
    RestaurantBalanceEnrichedResponseSchema,
)
from app.services.crud_service import restaurant_balance_service
from app.services.entity_service import (
    get_enriched_restaurant_balances,
    get_enriched_restaurant_balance_by_id,
)
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info
from app.utils.query_params import include_archived_query
from app.services.error_handling import handle_business_operation
from app.security.institution_scope import InstitutionScope
from app.security.entity_scoping import EntityScopingService, ENTITY_RESTAURANT_BALANCE

router = APIRouter(
    prefix="/restaurant-balances",
    tags=["Restaurant Balances"],
    dependencies=[Depends(oauth2_scheme)]
)


def _restaurant_balance_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Restaurant balance not found"
    )


# GET /restaurant-balances/ – Get all restaurant balances (read-only)
@router.get("/", response_model=List[RestaurantBalanceResponseSchema])
def get_all_restaurant_balances(
    include_archived: bool = include_archived_query("restaurant balances"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all restaurant balances (read-only).
    
    **Note: This is a read-only endpoint. Restaurant balances are automatically
    managed by the backend through transactions and billing operations. They
    cannot be created or modified via API.**
    
    Restaurant balances are updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Institution bills are generated and paid
    - Transactions are processed
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_BALANCE, current_user)

    def _get_restaurant_balances():
        # Use CRUDService with JOIN-based scoping (handles Employees and Suppliers automatically)
        balances = restaurant_balance_service.get_all(
            db,
            scope=scope,
            include_archived=include_archived
        )
        log_info(f"Retrieved {len(balances)} restaurant balances")
        return balances
    
    return handle_business_operation(
        _get_restaurant_balances,
        "restaurant balances retrieval"
    )


# GET /restaurant-balances/{restaurant_id} – Get single restaurant balance (read-only)
@router.get("/{restaurant_id}", response_model=RestaurantBalanceResponseSchema)
def get_restaurant_balance(
    restaurant_id: UUID,
    include_archived: bool = include_archived_query("restaurant balances"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single restaurant balance by restaurant ID (read-only).
    
    **Note: This is a read-only endpoint. Restaurant balances are automatically
    managed by the backend through transactions and billing operations. They
    cannot be created or modified via API.**
    
    Restaurant balances are updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Institution bills are generated and paid
    - Transactions are processed
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_BALANCE, current_user)

    def _get_restaurant_balance():
        # Use CRUDService with JOIN-based scoping (handles Employees and Suppliers automatically)
        # Note: restaurant_balance_info uses restaurant_id as the ID column
        balance = restaurant_balance_service.get_by_id(restaurant_id, db, scope=scope)
        
        if not balance:
            raise _restaurant_balance_not_found()
        
        if not include_archived and balance.is_archived:
            raise _restaurant_balance_not_found()
        
        log_info(f"Retrieved restaurant balance for restaurant: {restaurant_id}")
        return balance
    
    return handle_business_operation(
        _get_restaurant_balance,
        "restaurant balance retrieval"
    )


# GET /restaurant-balances/enriched/ – Get all enriched restaurant balances (read-only)
@router.get("/enriched/", response_model=List[RestaurantBalanceEnrichedResponseSchema])
def get_all_enriched_restaurant_balances(
    include_archived: bool = include_archived_query("restaurant balances"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all restaurant balances with enriched data (institution name, entity name, restaurant name, country) (read-only).
    
    **Note: This is a read-only endpoint. Restaurant balances are automatically
    managed by the backend through transactions and billing operations. They
    cannot be created or modified via API.**
    
    Restaurant balances are updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Institution bills are generated and paid
    - Transactions are processed
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_BALANCE, current_user)

    def _get_enriched_restaurant_balances():
        balances = get_enriched_restaurant_balances(
            db,
            scope=scope,
            include_archived=include_archived
        )
        log_info(f"Retrieved {len(balances)} enriched restaurant balances")
        return balances
    
    return handle_business_operation(
        _get_enriched_restaurant_balances,
        "enriched restaurant balances retrieval"
    )


# GET /restaurant-balances/enriched/{restaurant_id} – Get single enriched restaurant balance (read-only)
@router.get("/enriched/{restaurant_id}", response_model=RestaurantBalanceEnrichedResponseSchema)
def get_enriched_restaurant_balance(
    restaurant_id: UUID,
    include_archived: bool = include_archived_query("restaurant balances"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single restaurant balance by restaurant ID with enriched data (institution name, entity name, restaurant name, country) (read-only).
    
    **Note: This is a read-only endpoint. Restaurant balances are automatically
    managed by the backend through transactions and billing operations. They
    cannot be created or modified via API.**
    
    Restaurant balances are updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Institution bills are generated and paid
    - Transactions are processed
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_BALANCE, current_user)

    def _get_enriched_restaurant_balance():
        balance = get_enriched_restaurant_balance_by_id(
            db,
            restaurant_id,
            scope=scope,
            include_archived=include_archived
        )
        
        if not balance:
            raise _restaurant_balance_not_found()
        
        log_info(f"Retrieved enriched restaurant balance for restaurant: {restaurant_id}")
        return balance
    
    return handle_business_operation(
        _get_enriched_restaurant_balance,
        "enriched restaurant balance retrieval"
    )

