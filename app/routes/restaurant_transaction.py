# app/routes/restaurant_transaction.py
"""
Restaurant Transaction Routes - Read-Only Endpoints

This module provides read-only access to restaurant transaction information.
Restaurant transactions are automatically managed by the backend through plate
selection, QR code scanning, and billing operations. They cannot be created or
modified via API.

**Important**: These endpoints are read-only. All transaction creation and updates
are handled automatically by the system when:
- Customers place orders (via plate selection)
- Customers arrive at restaurants (via QR code scan)
- Orders are completed or marked as no-show
- Institution bills are generated and paid
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, Response

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    RestaurantTransactionEnrichedResponseSchema,
    RestaurantTransactionResponseSchema,
)
from app.security.entity_scoping import ENTITY_RESTAURANT_TRANSACTION, EntityScopingService
from app.services.crud_service import restaurant_transaction_service
from app.services.entity_service import (
    get_enriched_restaurant_transaction_by_id,
    get_enriched_restaurant_transactions,
)
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(
    prefix="/restaurant-transactions", tags=["Restaurant Transactions"], dependencies=[Depends(oauth2_scheme)]
)


# GET /restaurant-transactions/ – Get all restaurant transactions (read-only)
@router.get("", response_model=list[RestaurantTransactionResponseSchema])
def get_all_restaurant_transactions(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all restaurant transactions (read-only).

    **Note: This is a read-only endpoint. Restaurant transactions are automatically
    managed by the backend through plate selection, QR code scanning, and billing
    operations. They cannot be created or modified via API.**

    Restaurant transactions are created and updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Orders are completed or marked as no-show
    - Institution bills are generated and paid
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_TRANSACTION, current_user)

    def _get_restaurant_transactions():
        # Use CRUDService with JOIN-based scoping (handles Internal and Suppliers automatically)
        transactions = restaurant_transaction_service.get_all(db, scope=scope, include_archived=False)
        log_info(f"Retrieved {len(transactions)} restaurant transactions")
        return transactions

    return handle_business_operation(_get_restaurant_transactions, "restaurant transactions retrieval")


# Enriched routes MUST be before /{transaction_id} so /enriched is not parsed as transaction_id
# GET /restaurant-transactions/enriched – Get all enriched restaurant transactions (read-only)
@router.get("/enriched", response_model=list[RestaurantTransactionEnrichedResponseSchema])
def get_all_enriched_restaurant_transactions(
    response: Response,
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get all restaurant transactions with enriched data (institution name, entity name, restaurant name, plate name, currency code, country) (read-only).

    **Note: This is a read-only endpoint. Restaurant transactions are automatically
    managed by the backend through plate selection, QR code scanning, and billing
    operations. They cannot be created or modified via API.**

    Restaurant transactions are created and updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Orders are completed or marked as no-show
    - Institution bills are generated and paid
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_TRANSACTION, current_user)

    def _get_enriched_restaurant_transactions():
        transactions = get_enriched_restaurant_transactions(
            db,
            scope=scope,
            include_archived=False,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )
        log_info(f"Retrieved {len(transactions)} enriched restaurant transactions")
        return transactions

    result = handle_business_operation(
        _get_enriched_restaurant_transactions, "enriched restaurant transactions retrieval"
    )
    set_pagination_headers(response, result)
    return result


# GET /restaurant-transactions/enriched/{transaction_id} – Get single enriched restaurant transaction (read-only)
@router.get("/enriched/{transaction_id}", response_model=RestaurantTransactionEnrichedResponseSchema)
def get_enriched_restaurant_transaction(
    transaction_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get a single restaurant transaction by transaction ID with enriched data (institution name, entity name, restaurant name, plate name, currency code, country) (read-only).

    **Note: This is a read-only endpoint. Restaurant transactions are automatically
    managed by the backend through plate selection, QR code scanning, and billing
    operations. They cannot be created or modified via API.**

    Restaurant transactions are created and updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Orders are completed or marked as no-show
    - Institution bills are generated and paid
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_TRANSACTION, current_user)

    def _get_enriched_restaurant_transaction():
        transaction = get_enriched_restaurant_transaction_by_id(db, transaction_id, scope=scope, include_archived=False)

        if not transaction:
            raise envelope_exception(ErrorCode.RESTAURANT_TRANSACTION_NOT_FOUND, status=404, locale="en")

        log_info(f"Retrieved enriched restaurant transaction: {transaction_id}")
        return transaction

    return handle_business_operation(_get_enriched_restaurant_transaction, "enriched restaurant transaction retrieval")


# GET /restaurant-transactions/{transaction_id} – Get single restaurant transaction (read-only)
@router.get("/{transaction_id}", response_model=RestaurantTransactionResponseSchema)
def get_restaurant_transaction(
    transaction_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get a single restaurant transaction by transaction ID (read-only).

    **Note: This is a read-only endpoint. Restaurant transactions are automatically
    managed by the backend through plate selection, QR code scanning, and billing
    operations. They cannot be created or modified via API.**

    Restaurant transactions are created and updated automatically when:
    - Customers place orders (via plate selection)
    - Customers arrive at restaurants (via QR code scan)
    - Orders are completed or marked as no-show
    - Institution bills are generated and paid
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT_TRANSACTION, current_user)

    def _get_restaurant_transaction():
        # Use CRUDService with JOIN-based scoping (handles Internal and Suppliers automatically)
        transaction = restaurant_transaction_service.get_by_id(transaction_id, db, scope=scope)

        if not transaction:
            raise envelope_exception(ErrorCode.RESTAURANT_TRANSACTION_NOT_FOUND, status=404, locale="en")

        if transaction.is_archived:
            raise envelope_exception(ErrorCode.RESTAURANT_TRANSACTION_NOT_FOUND, status=404, locale="en")

        log_info(f"Retrieved restaurant transaction: {transaction_id}")
        return transaction

    return handle_business_operation(_get_restaurant_transaction, "restaurant transaction retrieval")
