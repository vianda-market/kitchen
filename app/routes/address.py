import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import List, Optional
from uuid import UUID
from app.services.crud_service import address_service
from app.services.address_service import address_business_service, get_addresses_for_customer
from app.services.entity_service import (
    get_enriched_addresses,
    get_enriched_address_by_id,
    get_enriched_addresses_search,
    get_enriched_addresses_for_customer,
)
from app.services.error_handling import handle_get_by_id, handle_get_all, handle_delete, handle_business_operation
from app.schemas.consolidated_schemas import (
    AddressCreateSchema,
    AddressUpdateSchema,
    AddressResponseSchema,
    AddressEnrichedResponseSchema,
    AddressSuggestResponseSchema,
)
from app.services.address_autocomplete_service import address_autocomplete_service
from app.config.address_autocomplete_config import get_address_autocomplete_config
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import institution_filter
from app.security.entity_scoping import EntityScopingService, ENTITY_ADDRESS
from app.security.scoping import get_user_scope, UserScope, resolve_institution_filter, InstitutionScope
from app.security.field_policies import ensure_supplier_can_create_edit_addresses, ensure_customer_cannot_edit_employer_address
from app.services.crud_service import user_service, institution_service
import psycopg2.extensions

router = APIRouter(
    prefix="/addresses",
    tags=["Addresses"],
    dependencies=[Depends(oauth2_scheme)]
)


# =============================================================================
# ADDRESS AUTOCOMPLETE (suggest / validate) – same API for web, iOS, Android, React Native
# =============================================================================

# Rate limit: 60 requests per user per 60 seconds
_SUGGEST_RATE_LIMIT_REQUESTS = 60
_SUGGEST_RATE_LIMIT_WINDOW_SECONDS = 60
_suggest_rate_limit_timestamps: dict = defaultdict(list)


def _rate_limit_address_suggest(request: Request, current_user: dict) -> None:
    """Allow at most 60 requests per user per 60 seconds."""
    key = str(current_user.get("user_id", "")) or (request.client.host if request.client else "unknown")
    now = time.time()
    # Prune old entries and evict stale keys to prevent unbounded growth
    for k, v in list(_suggest_rate_limit_timestamps.items()):
        pruned = [t for t in v if now - t < _SUGGEST_RATE_LIMIT_WINDOW_SECONDS]
        if pruned:
            _suggest_rate_limit_timestamps[k] = pruned
        else:
            del _suggest_rate_limit_timestamps[k]
    if len(_suggest_rate_limit_timestamps.get(key, [])) >= _SUGGEST_RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Too many address search requests. Please try again in 60 seconds.",
        )
    _suggest_rate_limit_timestamps.setdefault(key, []).append(now)


@router.get("/suggest", response_model=AddressSuggestResponseSchema)
def address_suggest(
    request: Request,
    q: str = Query(..., description="Partial address input (search box)"),
    country: Optional[str] = Query(None, description="Country code (ISO 3166-1 alpha-2 only, e.g. AR) or country name (e.g. Argentina) to bias or restrict results"),
    province: Optional[str] = Query(None, description="Province/state (e.g. WA, Washington) to narrow results when used with country and city"),
    city: Optional[str] = Query(None, description="City name to narrow results when used with country and province"),
    limit: int = Query(5, ge=1, le=10, description="Max number of suggestions (default 5)"),
    current_user: dict = Depends(get_current_user),
):
    """
    **Suggest (autocomplete)**. Returns structured address suggestions for form pre-fill.
    Suggestions return addresses anywhere in the country (no city bounds). Rate-limited.
    Frontend: search box calls with ?q=...&country=...&limit=5. Pass province and city to bias relevance.
    """
    _rate_limit_address_suggest(request, current_user)
    config = get_address_autocomplete_config()
    if len((q or "").strip()) < config.ADDRESS_AUTOCOMPLETE_MIN_CHARS:
        return AddressSuggestResponseSchema(suggestions=[])
    suggestions = address_autocomplete_service.suggest(q=q, country=country, province=province, city=city, limit=limit)
    return AddressSuggestResponseSchema(suggestions=suggestions)


# =============================================================================
# ENRICHED ADDRESS ENDPOINTS (with institution_name, user_username, user_first_name, user_last_name)
# Must be registered before /{address_id} so /enriched and /search are not parsed as address_id.
# =============================================================================

# GET /addresses/enriched - List all addresses with enriched data
@router.get("/enriched", response_model=List[AddressEnrichedResponseSchema])
def list_enriched_addresses(
    institution_id: Optional[UUID] = institution_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all addresses with enriched data (institution_name, user_username, user_first_name, user_last_name). Optional institution_id filters by institution (B2B Employee dropdown scoping). Customers: home/billing = created by user; employer = only assigned employer_address_id. Non-archived only."""
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)

        def _get_enriched_addresses():
            return get_enriched_addresses_for_customer(
                user_scope.user_id, db, include_archived=False
            )

        return handle_business_operation(
            _get_enriched_addresses,
            "enriched address list retrieval"
        )

    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)

    def _get_enriched_addresses():
        return get_enriched_addresses(
            db, scope=scope, include_archived=False, institution_id=effective_institution_id
        )

    return handle_business_operation(
        _get_enriched_addresses,
        "enriched address list retrieval"
    )

# GET /addresses/search - Search addresses by institution and optional text (for B2B restaurant address picker)
@router.get("/search", response_model=List[AddressEnrichedResponseSchema])
def search_enriched_addresses(
    institution_id: Optional[UUID] = Query(None, description="Restrict to addresses for this institution"),
    q: Optional[str] = Query(None, description="Text search (street_name, city, postal_code, province)"),
    limit: int = Query(50, ge=1, le=100, description="Max results (default 50)"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Search addresses with enriched data. Optional institution_id and q for B2B dropdown/type-to-search. Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)

    def _search():
        return get_enriched_addresses_search(
            db,
            institution_id=institution_id,
            q=q,
            scope=scope,
            include_archived=False,
            limit=limit,
        )

    return handle_business_operation(_search, "address search")

# GET /addresses/enriched/{address_id} - Get a single address with enriched data
@router.get("/enriched/{address_id}", response_model=AddressEnrichedResponseSchema)
def get_enriched_address_by_id_route(
    address_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single address by ID with enriched data (institution_name, user_username, user_first_name, user_last_name). Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)

    def _get_enriched_address():
        enriched_address = get_enriched_address_by_id(address_id, db, scope=scope, include_archived=False)
        if not enriched_address:
            from app.utils.error_messages import address_not_found
            raise address_not_found(address_id)
        return enriched_address

    return handle_business_operation(
        _get_enriched_address,
        "enriched address retrieval"
    )

# GET /addresses/{address_id}
@router.get("/{address_id}", response_model=AddressResponseSchema)
def get_address(
    address_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get an address by ID. Non-archived only."""
    # Get address first to check user_id
    address = address_service.get_by_id(address_id, db, scope=None)
    if not address:
        from app.utils.error_messages import address_not_found
        raise address_not_found(address_id)
    
    # Apply user scoping for Customers: allow if created by user OR if it's their assigned employer_address_id
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        user = user_service.get_by_id(user_scope.user_id, db, scope=None)
        employer_address_id = getattr(user, "employer_address_id", None) if user else None
        if str(address.user_id) != str(user_scope.user_id):
            if not employer_address_id or str(address.address_id) != str(employer_address_id):
                user_scope.enforce_user(address.user_id)  # Raises 403
        scope = None  # No institution filtering needed for Customers
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)
    
    return handle_get_by_id(
        address_service.get_by_id,
        address_id,
        db,
        "address",
        extra_kwargs={"scope": scope}
    )

# GET /addresses
@router.get("", response_model=List[AddressResponseSchema])
def get_all_addresses(
    institution_id: Optional[UUID] = institution_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all addresses. Optional institution_id filters by institution (B2B Employee dropdown scoping). Non-archived only."""
    # Apply user scoping for Customers
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        # Customers: home/billing = created by user; employer = only assigned employer_address_id
        def fetch(connection: psycopg2.extensions.connection):
            return get_addresses_for_customer(
                user_scope.user_id, connection, include_archived=False
            )
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)
        effective_institution_id = resolve_institution_filter(institution_id, scope)
        if effective_institution_id is not None:
            effective_scope = InstitutionScope(
                institution_id=str(effective_institution_id), role_type="Employee", role_name="Manager"
            )
        else:
            effective_scope = scope
        def fetch(connection: psycopg2.extensions.connection):
            return address_service.get_all(connection, scope=effective_scope, include_archived=False)

    return handle_get_all(fetch, db, "addresses")


@router.post("", response_model=AddressResponseSchema, status_code=status.HTTP_201_CREATED)
def create_address(
    addr_create: AddressCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new address with geocoding for restaurants. address_type is derived from linkages only (not accepted from client)."""
    user_scope = get_user_scope(current_user)
    ensure_supplier_can_create_edit_addresses(current_user)
    addr_data = addr_create.model_dump()
    # address_type is never taken from client; backend derives it from connected objects
    addr_data.pop("address_type", None)

    # B2B: require institution_id; user_id optional (Supplier/Employee may omit)
    if not user_scope.is_customer:
        if addr_data.get("institution_id") is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="institution_id is required for B2B address creation.",
            )

    # Auto-set user_id and institution_id for Customers. user_id only for Comensal creating home/other (not employer)
    if user_scope.is_customer:
        if current_user.get("institution_id") is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer address requires institution context; missing institution_id on user.",
            )
        addr_data["institution_id"] = current_user["institution_id"]
        # Only Comensal creating home/other (not employer address) gets user_id set
        if current_user.get("role_name") == "Comensal" and not addr_data.get("employer_id"):
            addr_data["user_id"] = current_user["user_id"]
    else:
        # For Suppliers/Employees: user_id optional; if provided, validate target user belongs to their institution
        target_user_id = addr_data.get("user_id")
        if target_user_id is not None:
            target_user = user_service.get_by_id(target_user_id, db, scope=None)
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            user_scope.enforce_user_assignment(target_user_id, target_user.institution_id)
            # User assigned to the address must be of the same institution as the address
            addr_institution_id = addr_data.get("institution_id")
            if addr_institution_id is not None and str(target_user.institution_id) != str(addr_institution_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The user assigned to the address must belong to the same institution as the address.",
                )
    
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


_SUBPREMISE_UPDATE_KEYS = {"floor", "apartment_unit", "is_default"}


@router.put("/{address_id}", response_model=AddressResponseSchema)
def update_address(
    address_id: UUID, 
    addr_update: AddressUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an existing address. institution_id is immutable after creation."""
    ensure_supplier_can_create_edit_addresses(current_user)
    # Get existing address to check user_id
    existing_address = address_service.get_by_id(address_id, db, scope=None)
    if not existing_address:
        from app.utils.error_messages import address_not_found
        raise address_not_found(address_id)

    update_data = addr_update.model_dump(exclude_unset=True)

    # Exception: Customer may update subpremise (floor, unit, is_default) on their assigned employer address
    customer_editing_own_employer_subpremise = False
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        user = user_service.get_by_id(user_scope.user_id, db, scope=None)
        employer_address_id = getattr(user, "employer_address_id", None) if user else None
        if (
            getattr(existing_address, "employer_id", None) is not None
            and employer_address_id
            and str(existing_address.address_id) == str(employer_address_id)
            and set(update_data.keys()) <= _SUBPREMISE_UPDATE_KEYS
        ):
            customer_editing_own_employer_subpremise = True

    if not customer_editing_own_employer_subpremise:
        ensure_customer_cannot_edit_employer_address(existing_address, current_user)

    user_scope = get_user_scope(current_user)

    # Apply user scoping for Customers
    if user_scope.is_customer:
        if customer_editing_own_employer_subpremise:
            scope = None  # Ownership implied by employer_address_id
        else:
            user_scope.enforce_user(existing_address.user_id)
            scope = None
    else:
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
    ensure_supplier_can_create_edit_addresses(current_user)
    # Get existing address to check user_id
    existing_address = address_service.get_by_id(address_id, db, scope=None)
    if not existing_address:
        from app.utils.error_messages import address_not_found
        raise address_not_found(address_id)
    
    ensure_customer_cannot_edit_employer_address(existing_address, current_user)
    
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
