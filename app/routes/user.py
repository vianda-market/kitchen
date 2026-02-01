from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from uuid import UUID
from pydantic import EmailStr
from app.utils.log import log_info, log_warning
from app.dto.models import UserDTO
from app.services.crud_service import user_service
from app.services.entity_service import (
    get_user_by_username, get_user_by_email, get_enriched_users, get_enriched_user_by_id
)
from app.services.user_signup_service import user_signup_service
from app.services.error_handling import handle_business_operation, handle_get_by_id
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import include_archived_query, include_archived_optional_query
from app.utils.error_messages import user_not_found
from app.schemas.consolidated_schemas import UserCreateSchema, UserUpdateSchema, UserResponseSchema, UserEnrichedResponseSchema
from app.security.entity_scoping import EntityScopingService, ENTITY_USER
from app.security.scoping import get_user_scope, UserScope
import psycopg2.extensions

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(oauth2_scheme)]
)

# 1. List all users
@router.get("/", response_model=List[UserResponseSchema])
def list_users(
    include_archived: Optional[bool] = include_archived_optional_query("users"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all users with optional archived records"""
    # Use institution scope for Employees/Suppliers, user scope for Customers
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        # Customers can only see themselves
        def _get_users():
            user = user_service.get_by_id(current_user["user_id"], db, scope=None)
            return [user] if user else []
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        def _get_users():
            return user_service.get_all(db, scope=scope)

    return handle_business_operation(
        _get_users,
        "user list retrieval"
    )


# 2. Lookup a single user by username or email (and optional is_archived filter)
@router.get("/lookup", response_model=UserResponseSchema)
def get_user_by_lookup(
    username: Optional[str] = Query(None, description="Username"),
    email: Optional[EmailStr] = Query(None, description="Email"),
    include_archived: bool = Query(False, description="Filter for non-archived users"),
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
        return user
    
    return handle_business_operation(_lookup_user, "user lookup by username/email")

# GET /users/me - Get current user's profile
@router.get("/me", response_model=UserEnrichedResponseSchema)
def get_current_user_profile(
    include_archived: bool = Query(False, description="Include archived records"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get current user's own profile with enriched data"""
    user_id = current_user["user_id"]
    scope = None  # No scope needed for self-access
    
    def _get_enriched_user():
        enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=include_archived)
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

    def _update_user():
        update_data = user_update.dict(exclude_unset=True)
        update_data["modified_by"] = current_user["user_id"]
        updated = user_service.update(user_id, update_data, db, scope=scope)
        if not updated:
            raise user_not_found()
        return updated

    return handle_business_operation(
        _update_user,
        "current user profile update",
        "User updated successfully"
    )

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
    """
    def _terminate_account():
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

# PUT /users/me/employer - Assign existing employer to current user
@router.put("/me/employer", response_model=UserResponseSchema)
def assign_my_employer(
    employer_id: UUID = Query(..., description="Employer ID to assign to current user"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Assign an existing employer to current user"""
    from app.services.crud_service import employer_service
    from app.utils.error_messages import employer_not_found
    
    def _assign_employer():
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise employer_not_found(employer_id)
        
        # Update user's employer_id
        update_data = {
            "employer_id": employer_id,
            "modified_by": current_user["user_id"]
        }
        
        updated = user_service.update(
            current_user["user_id"],
            update_data,
            db,
            scope=None
        )
        
        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Failed to assign employer"
            )
        return updated
    
    return handle_business_operation(_assign_employer, "employer assignment")

# 3. Get a single user by primary key (user_id)
@router.get("/{user_id}", response_model=UserResponseSchema, deprecated=True)
def get_user_by_id(
    user_id: UUID,
    include_archived: bool = include_archived_query("users"),
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
        log_warning(
            f"DEPRECATED: User {current_user_id} ({role_type}/{role_name}) used GET /users/{{user_id}} "
            f"for self-read. Please migrate to GET /users/me"
        )
    
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
    
    return handle_get_by_id(
        user_service.get_by_id,
        user_id,
        db,
        "user",
        include_archived,
        extra_kwargs={"scope": scope}
    )

# POST /users - Create a new user
@router.post("/", response_model=UserResponseSchema, status_code=201)
def create(
    user: UserCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new user - Restricted to Employees and Suppliers only"""
    # Customers cannot create users
    if current_user.get("role_type") == "Customer":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: customers cannot create users"
        )
    
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _create_user_with_validation():
        user_data = user.dict()
        return user_signup_service.process_admin_user_creation(
            user_data,
            current_user,
            db,
            scope=scope
        )
    
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
        log_warning(
            f"DEPRECATED: User {current_user_id} ({role_type}/{role_name}) used PUT /users/{{user_id}} "
            f"for self-update. Please migrate to PUT /users/me"
        )
    
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

    def _update_user():
        update_data = user_update.dict(exclude_unset=True)
        update_data["modified_by"] = current_user["user_id"]
        updated = user_service.update(user_id, update_data, db, scope=scope)
        if not updated:
            raise user_not_found()
        return updated

    return handle_business_operation(
        _update_user,
        "user update",
        "User updated successfully"
    )

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
@router.get("/enriched/", response_model=List[UserEnrichedResponseSchema])
def list_enriched_users(
    include_archived: Optional[bool] = include_archived_optional_query("users"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all users with enriched data (role_name, role_type, institution_name)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _get_enriched_users():
        return get_enriched_users(db, scope=scope, include_archived=include_archived or False)

    return handle_business_operation(
        _get_enriched_users,
        "enriched user list retrieval"
    )

# GET /users/enriched/{user_id} - Get a single user with enriched data
@router.get("/enriched/{user_id}", response_model=UserEnrichedResponseSchema, deprecated=True)
def get_enriched_user_by_id_route(
    user_id: UUID,
    include_archived: bool = include_archived_query("users"),
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
        log_warning(
            f"DEPRECATED: User {current_user_id} ({role_type}/{role_name}) used GET /users/enriched/{{user_id}} "
            f"for self-read. Please migrate to GET /users/me"
        )
    
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
        enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=include_archived)
        if not enriched_user:
            raise user_not_found()
        return enriched_user

    return handle_business_operation(
        _get_enriched_user,
        "enriched user retrieval"
    )