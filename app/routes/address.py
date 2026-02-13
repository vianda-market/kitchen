from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from uuid import UUID
from app.services.crud_service import address_service
from app.services.address_service import address_business_service
from app.services.entity_service import (
    get_enriched_addresses, get_enriched_address_by_id
)
from app.services.error_handling import handle_get_by_id, handle_get_all, handle_delete, handle_business_operation
from app.schemas.consolidated_schemas import (
    AddressCreateSchema,
    AddressUpdateSchema,
    AddressResponseSchema,
    AddressEnrichedResponseSchema,
    AddressSuggestResponseSchema,
    AddressValidateRequestSchema,
    AddressValidateResponseSchema,
    AddressNormalizedSchema,
)
from app.services.address_autocomplete_service import address_autocomplete_service
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import include_archived_query, include_archived_optional_query
from app.security.entity_scoping import EntityScopingService, ENTITY_ADDRESS
from app.security.scoping import get_user_scope, UserScope
from app.services.crud_service import user_service
import psycopg2.extensions

router = APIRouter(
    prefix="/addresses",
    tags=["Addresses"],
    dependencies=[Depends(oauth2_scheme)]
)


# =============================================================================
# ADDRESS AUTOCOMPLETE (suggest / validate) – same API for web, iOS, Android, React Native
# =============================================================================

@router.get("/suggest", response_model=AddressSuggestResponseSchema)
def address_suggest(
    q: str,
    country: Optional[str] = None,
    limit: int = 5,
    current_user: dict = Depends(get_current_user),
):
    """
    Address autocomplete suggestions. Returns structured address suggestions for form pre-fill.
    q: partial address input. country: optional ISO alpha-2 or alpha-3 to restrict results. limit: max suggestions (default 5).
    """
    if limit < 1 or limit > 10:
        limit = 5
    suggestions = address_autocomplete_service.suggest(q=q, country=country, limit=limit)
    return AddressSuggestResponseSchema(suggestions=suggestions)


@router.post("/validate", response_model=AddressValidateResponseSchema)
def address_validate(
    body: AddressValidateRequestSchema,
    current_user: dict = Depends(get_current_user),
):
    """
    Validate and normalize an address. Returns is_valid, normalized address (for confirm before submit), formatted_address, confidence, message.
    """
    result = address_autocomplete_service.validate(body=body.dict())
    normalized = None
    if result.get("normalized"):
        normalized = AddressNormalizedSchema(**result["normalized"])
    return AddressValidateResponseSchema(
        is_valid=result["is_valid"],
        normalized=normalized,
        formatted_address=result.get("formatted_address"),
        confidence=result["confidence"],
        message=result.get("message"),
    )


# GET /addresses/{address_id}?include_archived=...
@router.get("/{address_id}", response_model=AddressResponseSchema)
def get_address(
    address_id: UUID,
    include_archived: bool = include_archived_query("addresses"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get an address by ID with optional archived records"""
    # Get address first to check user_id
    address = address_service.get_by_id(address_id, db, scope=None)
    if not address:
        from app.utils.error_messages import address_not_found
        raise address_not_found(address_id)
    
    # Apply user scoping for Customers
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(address.user_id)
        scope = None  # No institution filtering needed for Customers
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)
    
    return handle_get_by_id(
        address_service.get_by_id,
        address_id,
        db,
        "address",
        include_archived,
        extra_kwargs={"scope": scope}
    )

# GET /addresses/?include_archived=...
@router.get("/", response_model=List[AddressResponseSchema])
def get_all_addresses(
    include_archived: bool = include_archived_query("addresses"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all addresses with optional archived records"""
    # Apply user scoping for Customers
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        # Customers can only see their own addresses
        def fetch(connection: psycopg2.extensions.connection):
            all_addresses = address_service.get_all(connection, scope=None)
            return [addr for addr in all_addresses if str(addr.user_id) == str(user_scope.user_id)]
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)
        def fetch(connection: psycopg2.extensions.connection):
            return address_service.get_all(connection, scope=scope)

    return handle_get_all(fetch, db, "addresses", include_archived)


@router.post("/", response_model=AddressResponseSchema, status_code=status.HTTP_201_CREATED)
def create_address(
    addr_create: AddressCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new address with geocoding for restaurants"""
    user_scope = get_user_scope(current_user)
    addr_data = addr_create.dict()
    
    # Auto-set user_id from current_user for Customers
    if user_scope.is_customer:
        addr_data["user_id"] = current_user["user_id"]
    else:
        # For Suppliers: Validate that target user_id belongs to their institution
        target_user_id = addr_data.get("user_id")
        if target_user_id:
            target_user = user_service.get_by_id(target_user_id, db, scope=None)
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            user_scope.enforce_user_assignment(target_user_id, target_user.institution_id)
    
    # Use institution scope for Suppliers/Employees
    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user) if not user_scope.is_customer else None

    def _create_address_with_geocoding():
        return address_business_service.create_address_with_geocoding(addr_data, current_user, db, scope=scope)
    
    result = handle_business_operation(
        _create_address_with_geocoding,
        "address creation with geocoding",
        "Address created successfully"
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Error creating address")
    
    return result


@router.put("/{address_id}", response_model=AddressResponseSchema)
def update_address(
    address_id: UUID, 
    addr_update: AddressUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an existing address"""
    # Get existing address to check user_id
    existing_address = address_service.get_by_id(address_id, db, scope=None)
    if not existing_address:
        from app.utils.error_messages import address_not_found
        raise address_not_found(address_id)
    
    user_scope = get_user_scope(current_user)
    
    # Apply user scoping for Customers
    if user_scope.is_customer:
        user_scope.enforce_user(existing_address.user_id)
        # Customers cannot change user_id
        update_data = addr_update.dict(exclude_unset=True)
        if "user_id" in update_data:
            del update_data["user_id"]
        scope = None
    else:
        # For Suppliers: Validate user_id assignment if provided
        update_data = addr_update.dict(exclude_unset=True)
        if "user_id" in update_data:
            target_user_id = update_data["user_id"]
            target_user = user_service.get_by_id(target_user_id, db, scope=None)
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            user_scope.enforce_user_assignment(target_user_id, target_user.institution_id)
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)

    def _update_address():
        update_data["modified_by"] = current_user["user_id"]
        return address_business_service.update_address_with_geocoding(
            address_id,
            update_data,
            current_user,
            db,
            scope=scope
        )

    return handle_business_operation(_update_address, "address update")

# DELETE /addresses/{address_id} – Delete (soft-delete) an address
@router.delete("/{address_id}", response_model=dict)
def delete_address(
    address_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete (soft-delete) an address"""
    # Get existing address to check user_id
    existing_address = address_service.get_by_id(address_id, db, scope=None)
    if not existing_address:
        from app.utils.error_messages import address_not_found
        raise address_not_found(address_id)
    
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    
    # Apply user scoping for Customers and Employee Operators (self-only access)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(existing_address.user_id)
        scope = None  # No institution filtering needed for Customers and Employee Operators
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)

    def _delete(target_id: UUID, connection: psycopg2.extensions.connection) -> bool:
        return address_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)

    handle_delete(_delete, address_id, db, "address")
    return {"detail": "Address deleted successfully"}

# =============================================================================
# ENRICHED ADDRESS ENDPOINTS (with institution_name, user_username, user_first_name, user_last_name)
# =============================================================================

# GET /addresses/enriched/ - List all addresses with enriched data
@router.get("/enriched/", response_model=List[AddressEnrichedResponseSchema])
def list_enriched_addresses(
    include_archived: Optional[bool] = include_archived_optional_query("addresses"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all addresses with enriched data (institution_name, user_username, user_first_name, user_last_name)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)

    def _get_enriched_addresses():
        return get_enriched_addresses(db, scope=scope, include_archived=include_archived or False)

    return handle_business_operation(
        _get_enriched_addresses,
        "enriched address list retrieval"
    )

# GET /addresses/enriched/{address_id} - Get a single address with enriched data
@router.get("/enriched/{address_id}", response_model=AddressEnrichedResponseSchema)
def get_enriched_address_by_id_route(
    address_id: UUID,
    include_archived: bool = include_archived_query("addresses"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single address by ID with enriched data (institution_name, user_username, user_first_name, user_last_name)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)

    def _get_enriched_address():
        enriched_address = get_enriched_address_by_id(address_id, db, scope=scope, include_archived=include_archived)
        if not enriched_address:
            from app.utils.error_messages import address_not_found
            raise address_not_found(address_id)
        return enriched_address

    return handle_business_operation(
        _get_enriched_address,
        "enriched address retrieval"
    )
