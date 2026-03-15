from fastapi import APIRouter, HTTPException, Depends, Query, Body, status, Response
from typing import Optional, List
from uuid import UUID
from pydantic import EmailStr
from app.utils.log import log_info, log_warning, log_employer_assign_debug, log_deprecated_endpoint_usage
from app.dto.models import UserDTO
from app.services.crud_service import user_service
from app.services.entity_service import (
    get_user_by_username,
    get_user_by_email,
    get_enriched_users,
    get_enriched_user_by_id,
    search_users,
    get_assigned_market_ids,
    get_assigned_market_ids_bulk,
    set_user_market_assignments,
)
from app.services.user_signup_service import user_signup_service
from app.services.error_handling import handle_business_operation, handle_get_by_id
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import limit_query, institution_filter, market_filter
from app.utils.error_messages import user_not_found
from app.schemas.consolidated_schemas import (
    UserCreateSchema,
    UserUpdateSchema,
    UserResponseSchema,
    UserEnrichedResponseSchema,
    UserSearchResultSchema,
    UserSearchResponseSchema,
    ChangePasswordSchema,
    AdminResetPasswordSchema,
    AssignEmployerRequest,
    MessagingPreferencesResponseSchema,
    MessagingPreferencesUpdateSchema,
)
from app.auth.security import hash_password, verify_password
from app.security.entity_scoping import EntityScopingService, ENTITY_USER
from app.security.scoping import get_user_scope, UserScope, resolve_institution_filter
from app.security.field_policies import (
    ensure_user_role_type_allowed,
    ensure_user_role_name_allowed,
    ensure_can_assign_role_name,
    ensure_can_edit_user,
    ensure_operator_cannot_create_users,
    ensure_supplier_can_create_edit_users,
    ensure_supplier_can_reset_user_password,
    ensure_supplier_user_institution_only,
    ensure_employer_not_for_supplier_employee,
    ensure_institution_type_matches_role_type,
)
from app.services.crud_service import institution_service, city_service
from app.services.messaging_preferences_service import (
    get_messaging_preferences,
    update_messaging_preferences,
)
from app.services.market_service import market_service, GLOBAL_MARKET_ID, is_global_market
from app.config.supported_cities import GLOBAL_CITY_ID, is_global_city
import psycopg2.extensions


def _validate_user_update_city_id(
    city_id: UUID,
    market_id: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """Validate that city_id belongs to a city whose country_code matches the user's market."""
    # Global city (B2B sentinel) is allowed with any market; skip country check
    if is_global_city(city_id):
        return
    city = city_service.get_by_id(city_id, db, scope=None)
    if not city:
        raise HTTPException(status_code=400, detail=f"City not found: {city_id}")
    if city.is_archived:
        raise HTTPException(status_code=400, detail=f"City is archived: {city_id}")
    market = market_service.get_by_id(market_id)
    if not market:
        raise HTTPException(status_code=400, detail=f"Market not found: {market_id}")
    market_country = (market.get("country_code") or "").strip().upper()
    city_country = (city.country_code or "").strip().upper()
    if market_country != city_country:
        raise HTTPException(
            status_code=400,
            detail=f"City must be in the same country as your market. City country: {city_country}, market country: {market_country}.",
        )


def _validate_user_update_market_id(update_data: dict, current_user: dict) -> None:
    """Validate market exists and not archived. Only Admin (Employee Admin, Super Admin, Supplier Admin) can set market_id to Global; Managers and Operators cannot."""
    if "market_id" not in update_data:
        return
    market_id = update_data["market_id"]
    if market_id is None:
        return
    try:
        from uuid import UUID
        market_id = UUID(str(market_id)) if not isinstance(market_id, UUID) else market_id
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid market_id")
    market = market_service.get_by_id(market_id)
    if not market:
        raise HTTPException(status_code=400, detail=f"Market not found: {market_id}")
    if market.get("is_archived"):
        raise HTTPException(status_code=400, detail=f"Market is archived: {market_id}")
    role_name = current_user.get("role_name")
    rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
    # Only Admin roles (Super Admin, Employee Admin, Supplier Admin) can assign Global; Manager/Operator cannot
    if is_global_market(market_id) and rn_str not in ("Super Admin", "Admin"):
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Super Admin can assign Global market. Managers and Operators cannot assign themselves or others to Global.",
        )


def _user_dto_to_response(user: UserDTO, db: psycopg2.extensions.connection) -> UserResponseSchema:
    """Build UserResponseSchema from UserDTO with v2 market_ids."""
    market_ids = get_assigned_market_ids(user.user_id, db, fallback_primary=user.market_id)
    return UserResponseSchema(**user.model_dump(), market_ids=market_ids)


def _user_dtos_to_responses(users: list, db: psycopg2.extensions.connection) -> List[UserResponseSchema]:
    """Build list of UserResponseSchema from UserDTOs with v2 market_ids (bulk)."""
    if not users:
        return []
    user_ids = [u.user_id for u in users]
    primary_by_user = {u.user_id: u.market_id for u in users}
    bulk = get_assigned_market_ids_bulk(user_ids, db, primary_by_user=primary_by_user)
    return [
        UserResponseSchema(**u.model_dump(), market_ids=bulk.get(u.user_id, [u.market_id]))
        for u in users
    ]


router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(oauth2_scheme)]
)

# 1. List all users
@router.get("", response_model=List[UserResponseSchema])
def list_users(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all users. Non-archived only."""
    # Use institution scope for Employees/Suppliers, user scope for Customers
    if current_user.get("role_type") == "Customer":
        # Customers can only see themselves
        def _get_users():
            user = user_service.get_by_id(current_user["user_id"], db, scope=None)
            return _user_dtos_to_responses([user] if user else [], db)
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        def _get_users():
            return _user_dtos_to_responses(user_service.get_all(db, scope=scope, include_archived=False), db)

    return handle_business_operation(
        _get_users,
        "user list retrieval"
    )


# 2. Lookup a single user by username or email
@router.get("/lookup", response_model=UserResponseSchema)
def get_user_by_lookup(
    username: Optional[str] = Query(None, description="Username"),
    email: Optional[EmailStr] = Query(None, description="Email"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    # Ensure at least one unique identifier is provided
    if username is None and email is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of username or email must be provided."
        )
    """Lookup user by username or email"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _lookup_user():
        user = None
        if username is not None:
            user = get_user_by_username(username, db, scope=scope)
            log_info(f"Queried user by username: {username}")
        elif email is not None:
            user = get_user_by_email(email, db, scope=scope)
            log_info(f"Queried user by email: {email}")

        if user is None:
            raise user_not_found()
        return _user_dto_to_response(user, db)

    return handle_business_operation(_lookup_user, "user lookup by username/email")


# GET /users/search - Search users by name, username, or email (e.g. discretionary recipient picker)
# Defined before GET /{user_id} so that "/search" is not interpreted as user_id.
@router.get("/search", response_model=UserSearchResponseSchema)
def search_users_route(
    q: str = Query("", description="Search string (substring match)"),
    search_by: str = Query(..., description="Field to search: name, username, or email"),
    limit: int = limit_query(20, 1, 100),
    offset: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    role_type: Optional[str] = Query(None, description="Filter by role_type (e.g. Customer)"),
    institution_id: Optional[UUID] = institution_filter(),
    market_id: Optional[UUID] = market_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Search users by name, username, or email with optional role_type filter and pagination.
    Used by the discretionary request modal (Customer picker) and other search-by-select UIs.
    Same auth and institution scoping as other user list endpoints.
    Optional institution_id and market_id restrict results (Employees may pass any institution; market-scoped Employees only their assigned markets).
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    # Effective institution: Employees may pass any; non-Employees only their own (resolve_institution_filter).
    if institution_id is not None:
        if current_user.get("role_type") == "Employee":
            effective_institution_id = institution_id
        else:
            effective_institution_id = resolve_institution_filter(institution_id, scope)
    else:
        effective_institution_id = None

    # market_id: market-scoped Employees (Manager, Operator) may only pass one of their assigned markets.
    if market_id is not None and current_user.get("role_type") == "Employee":
        role_name = current_user.get("role_name")
        rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
        if rn_str in ("Manager", "Operator"):
            assigned = get_assigned_market_ids(
                current_user["user_id"], db, fallback_primary=current_user.get("market_id")
            )
            if not assigned or market_id not in assigned:
                raise HTTPException(
                    status_code=403,
                    detail="market_id must be one of your assigned markets",
                )

    def _search():
        rows, total = search_users(
            q=q,
            search_by=search_by,
            db=db,
            limit=limit,
            offset=offset,
            role_type=role_type,
            scope=scope,
            institution_id=effective_institution_id,
            market_id=market_id,
        )
        return {
            "results": [UserSearchResultSchema(**r) for r in rows],
            "total": total,
        }

    return handle_business_operation(_search, "user search")


# GET /users/me - Get current user's profile
@router.get("/me", response_model=UserEnrichedResponseSchema)
def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get current user's own profile with enriched data. Non-archived only."""
    user_id = current_user["user_id"]
    scope = None  # No scope needed for self-access
    
    def _get_enriched_user():
        enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=False)
        if not enriched_user:
            raise user_not_found()
        return enriched_user

    return handle_business_operation(
        _get_enriched_user,
        "current user profile retrieval"
    )

# PUT /users/me - Update current user's profile
@router.put("/me", response_model=UserResponseSchema)
def update_current_user_profile(
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update current user's own profile"""
    user_id = current_user["user_id"]
    scope = None  # No scope needed for self-access
    
    existing_user = user_service.get_by_id(user_id, db, scope=scope)
    if not existing_user:
        raise user_not_found()

    update_data = user_update.model_dump(exclude_unset=True)
    update_data.pop("role_type", None)
    update_data.pop("institution_id", None)  # immutable
    update_data.pop("username", None)  # immutable; login identifier, no change without dedicated flow
    update_data.pop("password", None)
    update_data.pop("hashed_password", None)
    # Customers (Comensal, Customer Employer) and Suppliers: market is non-editable; only paid upgrade flow can add markets
    if current_user.get("role_type") in ("Customer", "Supplier"):
        update_data.pop("market_id", None)
        update_data.pop("market_ids", None)
    _validate_user_update_market_id(update_data, current_user)
    # v2: persist market_ids to user_market_assignment (and set primary); then remove from update_data
    if "market_ids" in update_data:
        set_user_market_assignments(user_id, update_data["market_ids"], db)
        update_data.pop("market_ids")
    # Customer Comensal: cannot remove city or set to Global
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    rt_str = (role_type.value if hasattr(role_type, "value") else str(role_type)) if role_type else ""
    rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
    if rt_str == "Customer" and rn_str == "Comensal" and "city_id" in update_data:
        if update_data["city_id"] is None:
            raise HTTPException(status_code=400, detail="City is required and cannot be removed")
        cid = update_data["city_id"] if isinstance(update_data["city_id"], UUID) else UUID(str(update_data["city_id"]))
        if is_global_city(cid):
            raise HTTPException(status_code=400, detail="Customers must have a specific city")
    # Validate city_id matches user's market country (use effective market: update or existing)
    if "city_id" in update_data and update_data["city_id"] is not None:
        effective_market_id = update_data.get("market_id") or existing_user.market_id
        _validate_user_update_city_id(update_data["city_id"], effective_market_id, db)
    # When clearing employer, also clear employer_address_id
    if "employer_id" in update_data and update_data["employer_id"] is None:
        update_data["employer_address_id"] = None

    def _update_user():
        update_data["modified_by"] = current_user["user_id"]
        updated = user_service.update(user_id, update_data, db, scope=scope)
        if not updated:
            raise user_not_found()
        return _user_dto_to_response(updated, db)

    return handle_business_operation(
        _update_user,
        "current user profile update",
        "User updated successfully"
    )


# GET /users/me/messaging-preferences - Get current user's messaging preferences
@router.get("/me/messaging-preferences", response_model=MessagingPreferencesResponseSchema)
def get_my_messaging_preferences(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get current user's messaging preference toggles. Creates default row (all on) if missing."""
    prefs = get_messaging_preferences(current_user["user_id"], db)
    return MessagingPreferencesResponseSchema(
        notify_coworker_pickup_alert=prefs.notify_coworker_pickup_alert,
        notify_plate_readiness_alert=prefs.notify_plate_readiness_alert,
        notify_promotions_push=prefs.notify_promotions_push,
        notify_promotions_email=prefs.notify_promotions_email,
        coworkers_can_see_my_orders=prefs.coworkers_can_see_my_orders,
        can_participate_in_plate_pickups=prefs.can_participate_in_plate_pickups,
    )


# PUT /users/me/messaging-preferences - Update current user's messaging preferences
@router.put("/me/messaging-preferences", response_model=MessagingPreferencesResponseSchema)
def update_my_messaging_preferences(
    body: MessagingPreferencesUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update messaging preference toggles. Only sent fields are updated. All default to true if never set."""
    update_data = body.model_dump(exclude_unset=True)
    prefs = update_messaging_preferences(current_user["user_id"], update_data, db)
    return MessagingPreferencesResponseSchema(
        notify_coworker_pickup_alert=prefs.notify_coworker_pickup_alert,
        notify_plate_readiness_alert=prefs.notify_plate_readiness_alert,
        notify_promotions_push=prefs.notify_promotions_push,
        notify_promotions_email=prefs.notify_promotions_email,
        coworkers_can_see_my_orders=prefs.coworkers_can_see_my_orders,
        can_participate_in_plate_pickups=prefs.can_participate_in_plate_pickups,
    )


# PUT /users/me/password - Change current user's password
@router.put("/me/password", response_model=dict, status_code=status.HTTP_200_OK)
def change_my_password(
    body: ChangePasswordSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Change current user's password. Requires current password, new password, and confirmation."""
    user_id = current_user["user_id"]
    existing_user = user_service.get_by_id(user_id, db, scope=None)
    if not existing_user:
        raise user_not_found()
    if not verify_password(body.current_password, existing_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    hashed = hash_password(body.new_password)
    user_service.update(
        user_id,
        {"hashed_password": hashed, "modified_by": user_id},
        db,
        scope=None,
    )
    return {"detail": "Password updated successfully"}


# PUT /users/me/terminate - Terminate current user's account
@router.put("/me/terminate", response_model=dict)
def terminate_my_account(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Terminate current user's account (archive/soft delete)
    
    This is a destructive operation that archives the user's account.
    Users cannot delete themselves - only archive/terminate.
    Separate endpoint from regular profile updates for safety.
    Idempotent: if already archived, returns 200 with "Account already terminated".
    """
    def _terminate_account():
        from app.utils.db import db_read
        # Check if already archived (idempotent: avoid 500 when Postman runs Terminate twice)
        row = db_read(
            "SELECT user_id, is_archived FROM user_info WHERE user_id = %s",
            (str(current_user["user_id"]),),
            connection=db,
            fetch_one=True,
        )
        if not row:
            raise HTTPException(status_code=500, detail="User not found")
        if row.get("is_archived"):
            return {"detail": "Account already terminated"}
        # Archive user (soft delete via is_archived = TRUE)
        success = user_service.soft_delete(
            current_user["user_id"],
            current_user["user_id"],  # Self-termination
            db,
            scope=None
        )
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to terminate account"
            )
        return {"detail": "Account terminated successfully"}
    
    return handle_business_operation(_terminate_account, "account termination")

# PUT /users/me/employer - Assign existing employer and address to current user (Customers only)
@router.put("/me/employer", response_model=UserResponseSchema)
def assign_my_employer(
    body: AssignEmployerRequest = Body(..., description="Employer ID and address ID (office user works at)"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Assign an existing employer and address to current user. Both employer_id and address_id required; address must belong to employer. Only Customer users can have an employer; Supplier and Employee get 403."""
    log_employer_assign_debug(
        f"PUT /users/me/employer received: user_id={current_user.get('user_id')} "
        f"employer_id={body.employer_id} address_id={body.address_id}"
    )
    role_type = (current_user.get("role_type") or "").strip()
    if role_type in ("Supplier", "Employee"):
        raise HTTPException(
            status_code=403,
            detail="Employer is not applicable to Supplier or Employee users. Only Customer users can assign an employer.",
        )
    from app.services.crud_service import employer_service, address_service
    from app.utils.error_messages import employer_not_found
    
    def _assign_employer():
        employer_id = body.employer_id
        address_id = body.address_id
        
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise employer_not_found(employer_id)
        
        # Validate address exists, not archived, and belongs to employer
        address = address_service.get_by_id(address_id, db, scope=None)
        if not address:
            raise HTTPException(
                status_code=400,
                detail=f"Address not found: {address_id}. The address must exist and belong to the employer.",
            )
        if address.is_archived:
            raise HTTPException(
                status_code=400,
                detail=f"Address is archived: {address_id}. Use an active address.",
            )
        addr_employer_id = getattr(address, "employer_id", None)
        if not addr_employer_id or str(addr_employer_id) != str(employer_id):
            raise HTTPException(
                status_code=400,
                detail="Address does not belong to the specified employer. Use an address from GET /employers/{id}/addresses.",
            )
        
        # Update user's employer_id and employer_address_id
        update_data = {
            "employer_id": employer_id,
            "employer_address_id": address_id,
            "modified_by": current_user["user_id"]
        }
        
        updated = user_service.update(
            current_user["user_id"],
            update_data,
            db,
            scope=None
        )

        # Store floor/unit in address_subpremise when provided (per-user at employer address)
        if updated and (body.floor is not None or body.apartment_unit is not None):
            from app.services.address_service import _upsert_address_subpremise
            _upsert_address_subpremise(
                address_id,
                UUID(str(current_user["user_id"])) if isinstance(current_user["user_id"], str) else current_user["user_id"],
                UUID(str(current_user["user_id"])) if isinstance(current_user["user_id"], str) else current_user["user_id"],
                db,
                floor=body.floor,
                apartment_unit=body.apartment_unit,
                is_default=False,
                commit=True,
            )
        
        if not updated:
            log_employer_assign_debug(
                f"employer assignment FAILED: user_service.update returned None for user_id={current_user['user_id']}"
            )
            # Diagnostic: check if user exists (including archived) to surface actionable errors
            from app.utils.db import db_read
            try:
                row = db_read(
                    "SELECT user_id, is_archived FROM user_info WHERE user_id = %s",
                    (str(current_user["user_id"]),),
                    connection=db,
                    fetch_one=True,
                )
                if not row:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to assign employer: user not found in database."
                    )
                if row.get("is_archived"):
                    raise HTTPException(
                        status_code=400,
                        detail="User account has been terminated. Run 000 Client Setup to create a fresh customer, then complete Employer Assignment Workflow from the start."
                    )
            except HTTPException:
                raise
            raise HTTPException(
                status_code=500,
                detail="Failed to assign employer"
            )
        log_employer_assign_debug(
            f"employer assignment SUCCESS: user_id={current_user['user_id']} "
            f"employer_id={employer_id} employer_address_id={address_id}"
        )
        return _user_dto_to_response(updated, db)

    return handle_business_operation(_assign_employer, "employer assignment")

# 3. Get a single user by primary key (user_id)
@router.get("/{user_id}", response_model=UserResponseSchema, deprecated=True)
def get_user_by_id(
    user_id: UUID,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a user by ID with optional archived records
    
    ⚠️ **DEPRECATED for self-reads**: Use `GET /users/me` for reading your own profile.
    This endpoint remains available for Admins to read OTHER users' profiles.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]
    
    # Detect self-read and log deprecation warning
    is_self_read = str(user_id) == str(current_user_id)
    if is_self_read:
        log_deprecated_endpoint_usage(
            "GET /api/v1/users/{user_id} (self-read)",
            str(current_user_id),
            role_type or "",
            role_name or "",
        )
        log_warning(
            f"DEPRECATED: User {current_user_id} ({role_type}/{role_name}) used GET /users/{{user_id}} "
            f"for self-read. Please migrate to GET /users/me"
        )
        response.headers["X-Deprecated-Endpoint"] = "true"
        response.headers["X-Use-Instead"] = "GET /api/v1/users/me"
        response.headers["X-Deprecation-Date"] = "2024-12-04"
        response.headers["X-Removal-Date"] = "2026-06-04"
    
    # Apply user scoping for Customers and Employee Operators (self-only access)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        # Customers and Employee Operators can only access their own user_id, so scope is None (no institution filtering needed)
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        # Check if user exists first (without scope), then check access (with scope)
        # This ensures we return 403 for cross-institution access, not 404
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        
        # Now check if user has access with scope
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: You do not have access to this user"
                )
    
    user = handle_get_by_id(
        user_service.get_by_id,
        user_id,
        db,
        "user",
        extra_kwargs={"scope": scope}
    )
    return _user_dto_to_response(user, db)

# POST /users - Create a new user
@router.post("", response_model=UserResponseSchema, status_code=201)
def create(
    user: UserCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new user - Restricted to Employees and Suppliers (Admin/Manager only)"""
    # Customers cannot create users
    if current_user.get("role_type") == "Customer":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: customers cannot create users"
        )

    ensure_operator_cannot_create_users(current_user)
    ensure_supplier_can_create_edit_users(current_user)
    user_data = user.model_dump()
    ensure_supplier_user_institution_only(user_data.get("institution_id"), current_user, action="create")
    # Require institution_type == role_type (Employee→Employee, Customer→Customer, Supplier→Supplier)
    institution_id = user_data.get("institution_id")
    if institution_id:
        institution = institution_service.get_by_id(institution_id, db, scope=None)
        if not institution:
            raise HTTPException(status_code=400, detail="Invalid institution_id: institution not found.")
        ensure_institution_type_matches_role_type(
            user_data.get("role_type"),
            getattr(institution, "institution_type", None),
            context="create",
        )
    ensure_user_role_type_allowed(user_data.get("role_type"), current_user, "create")
    ensure_user_role_name_allowed(user_data.get("role_type"), user_data.get("role_name"), current_user, "create")
    ensure_can_assign_role_name(
        current_user.get("role_type"),
        current_user.get("role_name"),
        user_data.get("role_type"),
        user_data.get("role_name"),
    )
    ensure_employer_not_for_supplier_employee(user_data.get("role_type"), user_data.get("employer_id"), context="create")
    rt = user_data.get("role_type")
    rt_str = rt.value if hasattr(rt, "value") else str(rt)
    if rt_str in ("Supplier", "Employee"):
        user_data["employer_id"] = None

    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _create_user_with_validation():
        created = user_signup_service.process_admin_user_creation(
            user_data,
            current_user,
            db,
            scope=scope
        )
        return _user_dto_to_response(created, db)

    return handle_business_operation(
        _create_user_with_validation,
        "user creation with validation",
        "User created successfully"
    )


# PUT /users/{user_id} - Update an existing user
@router.put("/{user_id}", response_model=UserResponseSchema, deprecated=True)
def update(
    user_id: UUID,
    user_update: UserUpdateSchema,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Update a user
    
    ⚠️ **DEPRECATED for self-updates**: Use `PUT /users/me` for updating your own profile.
    This endpoint remains available for Admins to update OTHER users' profiles.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]
    
    # Detect self-update and log deprecation warning
    is_self_update = str(user_id) == str(current_user_id)
    if is_self_update:
        log_deprecated_endpoint_usage(
            "PUT /api/v1/users/{user_id} (self-update)",
            str(current_user_id),
            role_type or "",
            role_name or "",
        )
        log_warning(
            f"DEPRECATED: User {current_user_id} ({role_type}/{role_name}) used PUT /users/{{user_id}} "
            f"for self-update. Please migrate to PUT /users/me"
        )
        response.headers["X-Deprecated-Endpoint"] = "true"
        response.headers["X-Use-Instead"] = "PUT /api/v1/users/me"
        response.headers["X-Deprecation-Date"] = "2024-12-04"
        response.headers["X-Removal-Date"] = "2026-06-04"
    
    ensure_supplier_can_create_edit_users(current_user)
    # Apply user scoping for Customers and Employee Operators (self-only access)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None  # No institution filtering needed for Customers and Employee Operators
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        # Check if user exists first (without scope), then check access (with scope)
        # This ensures we return 403 for cross-institution access, not 404
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        
        # Now check if user has access with scope
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: You do not have access to this user"
                )
    
    existing_user = user_service.get_by_id(user_id, db, scope=scope)
    if not existing_user:
        raise user_not_found()

    # Manager cannot edit Admin; Admin cannot edit Super Admin
    ensure_can_edit_user(
        role_type,
        role_name,
        getattr(existing_user, "role_type", None),
        getattr(existing_user, "role_name", None),
    )

    update_data = user_update.model_dump(exclude_unset=True)
    if "role_type" in update_data:
        raise HTTPException(status_code=400, detail="role_type is immutable and cannot be changed after user creation")
    if "institution_id" in update_data:
        raise HTTPException(status_code=400, detail="institution_id is immutable and cannot be changed after user creation")
    if "username" in update_data:
        raise HTTPException(status_code=400, detail="username is immutable and cannot be changed after user creation.")
    update_data.pop("role_type", None)
    update_data.pop("institution_id", None)
    update_data.pop("username", None)
    update_data.pop("password", None)
    update_data.pop("hashed_password", None)
    existing_role_type = getattr(existing_user, "role_type", None)
    if existing_role_type and hasattr(existing_role_type, "value"):
        existing_role_type = existing_role_type.value
    if "employer_id" in update_data:
        ensure_employer_not_for_supplier_employee(existing_role_type, update_data["employer_id"], context="update")
    if existing_role_type in ("Supplier", "Employee"):
        update_data.pop("employer_id", None)
    # When clearing employer, also clear employer_address_id
    if "employer_id" in update_data and update_data["employer_id"] is None:
        update_data["employer_address_id"] = None
    if "role_name" in update_data:
        ensure_user_role_name_allowed(existing_role_type, update_data["role_name"], current_user, "update")
        ensure_can_assign_role_name(
            role_type,
            role_name,
            existing_role_type,
            update_data["role_name"],
        )

    # Target user is Customer (Comensal or Customer Employer) or Supplier: market is non-editable; only paid upgrade flow can add markets
    if existing_role_type in ("Customer", "Supplier"):
        update_data.pop("market_id", None)
        update_data.pop("market_ids", None)
    _validate_user_update_market_id(update_data, current_user)
    # v2: persist market_ids to user_market_assignment (and set primary); then remove from update_data
    if "market_ids" in update_data:
        set_user_market_assignments(user_id, update_data["market_ids"], db)
        update_data.pop("market_ids")
    # Customer Comensal: cannot remove city or set to Global (B2B updating Customer)
    existing_role_name = getattr(existing_user, "role_name", None)
    rn_str = (existing_role_name.value if hasattr(existing_role_name, "value") else str(existing_role_name)) if existing_role_name else ""
    if existing_role_type == "Customer" and rn_str == "Comensal" and "city_id" in update_data:
        if update_data["city_id"] is None:
            raise HTTPException(status_code=400, detail="City is required and cannot be removed")
        cid = update_data["city_id"] if isinstance(update_data["city_id"], UUID) else UUID(str(update_data["city_id"]))
        if is_global_city(cid):
            raise HTTPException(status_code=400, detail="Customers must have a specific city")
        effective_market_id = update_data.get("market_id") or existing_user.market_id
        _validate_user_update_city_id(update_data["city_id"], effective_market_id, db)
    elif "city_id" in update_data and update_data["city_id"] is not None:
        # Non-Comensal or non-Customer: validate city matches market when provided
        effective_market_id = update_data.get("market_id") or existing_user.market_id
        _validate_user_update_city_id(update_data["city_id"], effective_market_id, db)

    def _update_user():
        update_data["modified_by"] = current_user["user_id"]
        updated = user_service.update(user_id, update_data, db, scope=scope)
        if not updated:
            raise user_not_found()
        return _user_dto_to_response(updated, db)

    return handle_business_operation(
        _update_user,
        "user update",
        "User updated successfully"
    )


# POST /users/{user_id}/resend-invite - Resend B2B invite email (set-password link)
@router.post("/{user_id}/resend-invite", response_model=dict, status_code=status.HTTP_200_OK)
def resend_user_invite(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Resend the B2B invite email with set-password link. Same access rules as PUT /users/{user_id}.
    Use when the original invite had wrong URL or expired. Generates new code, invalidates prior codes,
    sends email. User sets password via the link → POST /auth/reset-password.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")

    ensure_supplier_can_reset_user_password(current_user)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have access to this user",
                )

    existing_user = user_service.get_by_id(user_id, db, scope=scope)
    if not existing_user:
        raise user_not_found()

    ensure_can_edit_user(
        role_type,
        role_name,
        getattr(existing_user, "role_type", None),
        getattr(existing_user, "role_name", None),
    )

    user_email = getattr(existing_user, "email", None)
    if not user_email or not str(user_email).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no email address. Cannot send invite.",
        )

    first_name = getattr(existing_user, "first_name", None)
    user_signup_service.resend_b2b_invite_email(
        user_id=user_id,
        email=str(user_email).strip(),
        first_name=first_name,
        db=db,
    )
    return {"detail": "Invite email sent successfully"}


# PUT /users/{user_id}/password - Admin reset another user's password
# NOTE: Kept for Postman collection testing. B2B site uses invite flow only.
# Roadmap: deprecate once Postman is enhanced to not depend on it.
@router.put("/{user_id}/password", response_model=dict, status_code=status.HTTP_200_OK)
def reset_user_password(
    user_id: UUID,
    body: AdminResetPasswordSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Reset another user's password. Same access rules as PUT /users/{user_id}."""
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]

    ensure_supplier_can_reset_user_password(current_user)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have access to this user",
                )

    existing_user = user_service.get_by_id(user_id, db, scope=scope)
    if not existing_user:
        raise user_not_found()

    # Manager cannot edit Admin; Admin cannot edit Super Admin
    ensure_can_edit_user(
        role_type,
        role_name,
        getattr(existing_user, "role_type", None),
        getattr(existing_user, "role_name", None),
    )

    hashed = hash_password(body.new_password)
    user_service.update(
        user_id,
        {"hashed_password": hashed, "modified_by": current_user_id},
        db,
        scope=scope,
    )
    return {"detail": "Password reset successfully"}


# DELETE /users/{user_id} - Delete a user
@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete a user"""
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    
    ensure_supplier_can_create_edit_users(current_user)
    # Apply user scoping for Customers and Employee Operators (self-only access)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None  # No institution filtering needed for Customers and Employee Operators
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        # Check if user exists first (without scope), then check access (with scope)
        # This ensures we return 403 for cross-institution access, not 404
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        
        # Now check if user has access with scope
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: You do not have access to this user"
                )

    existing_user = user_service.get_by_id(user_id, db, scope=scope)
    if not existing_user:
        raise user_not_found()

    # Manager cannot edit/delete Admin; Admin cannot edit/delete Super Admin
    ensure_can_edit_user(
        role_type,
        role_name,
        getattr(existing_user, "role_type", None),
        getattr(existing_user, "role_name", None),
    )

    def _delete_user():
        success = user_service.soft_delete(user_id, current_user["user_id"], db, scope=scope)
        if not success:
            raise user_not_found()
        log_info(f"Deleted user with ID: {user_id}")
        return {"detail": "User deleted successfully"}
    
    return handle_business_operation(_delete_user, "user deletion")

# =============================================================================
# ENRICHED USER ENDPOINTS (with role_name, role_type, institution_name)
# =============================================================================

# GET /users/enriched/ - List all users with enriched data
@router.get("/enriched", response_model=List[UserEnrichedResponseSchema])
def list_enriched_users(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all users with enriched data (role_name, role_type, institution_name). Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _get_enriched_users():
        return get_enriched_users(db, scope=scope, include_archived=False)

    return handle_business_operation(
        _get_enriched_users,
        "enriched user list retrieval"
    )

# GET /users/enriched/{user_id} - Get a single user with enriched data
@router.get("/enriched/{user_id}", response_model=UserEnrichedResponseSchema, deprecated=True)
def get_enriched_user_by_id_route(
    user_id: UUID,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single user by ID with enriched data (role_name, role_type, institution_name)
    
    ⚠️ **DEPRECATED for self-reads**: Use `GET /users/me` for reading your own profile (returns enriched data).
    This endpoint remains available for Admins to read OTHER users' profiles.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]
    
    # Detect self-read and log deprecation warning
    is_self_read = str(user_id) == str(current_user_id)
    if is_self_read:
        log_deprecated_endpoint_usage(
            "GET /api/v1/users/enriched/{user_id} (self-read)",
            str(current_user_id),
            role_type or "",
            role_name or "",
        )
        log_warning(
            f"DEPRECATED: User {current_user_id} ({role_type}/{role_name}) used GET /users/enriched/{{user_id}} "
            f"for self-read. Please migrate to GET /users/me"
        )
        response.headers["X-Deprecated-Endpoint"] = "true"
        response.headers["X-Use-Instead"] = "GET /api/v1/users/me"
        response.headers["X-Deprecation-Date"] = "2024-12-04"
        response.headers["X-Removal-Date"] = "2026-06-04"
    
    # Apply user scoping for Customers and Employee Operators (self-only access)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        # Customers and Employee Operators can only access their own user_id, so scope is None (no institution filtering needed)
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        # Check if user exists first (without scope), then check access (with scope)
        # This ensures we return 403 for cross-institution access, not 404
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        
        # Now check if user has access with scope
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: You do not have access to this user"
                )

    def _get_enriched_user():
        enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=False)
        if not enriched_user:
            raise user_not_found()
        return enriched_user

    return handle_business_operation(
        _get_enriched_user,
        "enriched user retrieval"
    )