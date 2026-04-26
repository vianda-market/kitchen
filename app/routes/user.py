from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from pydantic import EmailStr

from app.auth.dependencies import get_current_user, get_resolved_locale, oauth2_scheme
from app.auth.security import hash_password, verify_password
from app.config.supported_cities import is_global_city
from app.dependencies.database import get_db
from app.dto.models import UserDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    AdminResetPasswordSchema,
    AssignEmployerRequest,
    AssignWorkplaceRequest,
    ChangePasswordSchema,
    EmailChangeVerifySchema,
    MessagingPreferencesResponseSchema,
    MessagingPreferencesUpdateSchema,
    UserCreateSchema,
    UserEnrichedResponseSchema,
    UserResponseSchema,
    UserSearchResponseSchema,
    UserSearchResultSchema,
    UserUpdateSchema,
)
from app.security.entity_scoping import ENTITY_USER, EntityScopingService
from app.security.field_policies import (
    ensure_can_assign_role_name,
    ensure_can_edit_user,
    ensure_employer_not_for_supplier_employee,
    ensure_institution_type_matches_role_type,
    ensure_operator_cannot_create_users,
    ensure_supplier_can_create_edit_users,
    ensure_supplier_can_reset_user_password,
    ensure_supplier_user_institution_only,
    ensure_user_role_name_allowed,
    ensure_user_role_type_allowed,
)
from app.security.scoping import get_user_scope, resolve_institution_filter
from app.services.crud_service import city_service, institution_service, user_service
from app.services.email_change_service import email_change_service
from app.services.entity_service import (
    get_assigned_market_ids,
    get_assigned_market_ids_bulk,
    get_enriched_user_by_id,
    get_enriched_users,
    get_user_by_email,
    get_user_by_username,
    search_users,
    set_user_market_assignments,
)
from app.services.error_handling import handle_business_operation, handle_get_by_id
from app.services.market_service import is_global_market, market_service
from app.services.messaging_preferences_service import (
    get_messaging_preferences,
    update_messaging_preferences,
)
from app.services.user_signup_service import user_signup_service
from app.utils.error_messages import user_not_found
from app.utils.log import log_employer_assign_debug, log_error, log_info
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.utils.query_params import institution_filter, limit_query, market_filter


def _validate_user_update_city_metadata_id(
    city_metadata_id: UUID,
    market_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> None:
    """Validate that city_metadata_id belongs to a city whose country_code matches the user's market."""
    # Global city (B2B sentinel) is allowed with any market; skip country check
    if is_global_city(city_metadata_id):
        return
    city = city_service.get_by_id(city_metadata_id, db, scope=None)
    if not city:
        raise envelope_exception(ErrorCode.USER_CITY_NOT_FOUND, status=400, locale=locale)
    if city.is_archived:
        raise envelope_exception(ErrorCode.USER_CITY_ARCHIVED, status=400, locale=locale)
    market = market_service.get_by_id(market_id)
    if not market:
        raise envelope_exception(ErrorCode.USER_MARKET_NOT_FOUND, status=400, locale=locale)
    market_country = (market.get("country_code") or "").strip().upper()
    city_country = (city.country_iso or "").strip().upper()
    if market_country != city_country:
        raise envelope_exception(ErrorCode.USER_CITY_COUNTRY_MISMATCH, status=400, locale=locale)


_IMMUTABLE_FIELDS = {"role_type", "institution_id", "username"}
_IMMUTABLE_MESSAGES = {
    "role_type": "role_type is immutable and cannot be changed after user creation",
    "institution_id": "institution_id is immutable and cannot be changed after user creation",
    "username": "username is immutable and cannot be changed after user creation.",
}


def _reject_immutable_fields(update_data: dict, locale: str = "en") -> None:
    """Raise 400 if any immutable field is explicitly set, then strip unsafe fields."""
    for field in _IMMUTABLE_FIELDS:
        if field in update_data:
            raise envelope_exception(ErrorCode.ENTITY_FIELD_IMMUTABLE, status=400, locale=locale, field=field)
    for key in ("role_type", "institution_id", "username", "password", "hashed_password"):
        update_data.pop(key, None)


def _extract_role_type_str(existing_user) -> str | None:
    """Extract role_type as a plain string from a user DTO."""
    rt = getattr(existing_user, "role_type", None)
    if rt and hasattr(rt, "value"):
        return rt.value
    return rt


def _apply_employer_rules(update_data: dict, existing_role_type: str | None) -> None:
    """Validate and clean employer-related fields."""
    if "employer_entity_id" in update_data:
        ensure_employer_not_for_supplier_employee(
            existing_role_type, update_data["employer_entity_id"], context="update"
        )
    if existing_role_type in ("supplier", "internal", "employer"):
        update_data.pop("employer_entity_id", None)
    if "employer_entity_id" in update_data and update_data["employer_entity_id"] is None:
        update_data["employer_address_id"] = None


def _apply_market_and_city_rules(
    update_data: dict,
    existing_user,
    existing_role_type: str | None,
    current_user: dict,
    user_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> None:
    """Validate and apply market_id, market_ids, and city_metadata_id rules."""
    if existing_role_type in ("customer", "supplier"):
        update_data.pop("market_id", None)
        update_data.pop("market_ids", None)
    _validate_user_update_market_id(update_data, current_user, locale=locale)
    if "market_ids" in update_data:
        set_user_market_assignments(user_id, update_data["market_ids"], db)
        update_data.pop("market_ids")
    if "city_metadata_id" in update_data and update_data["city_metadata_id"] is not None:
        _validate_city_metadata_update(update_data, existing_user, existing_role_type, db, locale=locale)
    elif _is_comensal(existing_user, existing_role_type) and "city_metadata_id" in update_data:
        raise envelope_exception(ErrorCode.USER_CITY_REQUIRED, status=400, locale=locale)


def _is_comensal(existing_user, existing_role_type: str | None) -> bool:
    """Check if user is a Customer Comensal."""
    if existing_role_type != "customer":
        return False
    rn = getattr(existing_user, "role_name", None)
    rn_str = (rn.value if hasattr(rn, "value") else str(rn)) if rn else ""
    return rn_str == "comensal"


def _validate_city_metadata_update(
    update_data: dict,
    existing_user,
    existing_role_type: str | None,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> None:
    """Validate city_metadata_id when it's being set (not None)."""
    if _is_comensal(existing_user, existing_role_type):
        cid = (
            update_data["city_metadata_id"]
            if isinstance(update_data["city_metadata_id"], UUID)
            else UUID(str(update_data["city_metadata_id"]))
        )
        if is_global_city(cid):
            raise envelope_exception(ErrorCode.USER_CITY_MUST_BE_SPECIFIC, status=400, locale=locale)
    effective_market_id = update_data.get("market_id") or existing_user.market_id
    _validate_user_update_city_metadata_id(update_data["city_metadata_id"], effective_market_id, db, locale=locale)


def _validate_user_update_market_id(update_data: dict, current_user: dict, locale: str = "en") -> None:
    """Validate market exists and not archived. Only Admin (Internal Admin, Super Admin, Supplier Admin) can set market_id to Global; Managers and Operators cannot."""
    if "market_id" not in update_data:
        return
    market_id = update_data["market_id"]
    if market_id is None:
        return
    try:
        from uuid import UUID

        market_id = UUID(str(market_id)) if not isinstance(market_id, UUID) else market_id
    except (ValueError, TypeError):
        raise envelope_exception(ErrorCode.USER_MARKET_ID_INVALID, status=400, locale=locale) from None
    market = market_service.get_by_id(market_id)
    if not market:
        raise envelope_exception(ErrorCode.USER_MARKET_NOT_FOUND, status=400, locale=locale)
    if market.get("is_archived"):
        raise envelope_exception(ErrorCode.USER_MARKET_ARCHIVED, status=400, locale=locale)
    role_name = current_user.get("role_name")
    rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
    # Only Admin roles (Super Admin, Internal Admin, Supplier Admin) can assign Global; Manager/Operator cannot
    if is_global_market(market_id) and rn_str not in ("super_admin", "admin"):
        raise envelope_exception(ErrorCode.USER_MARKET_GLOBAL_NOT_ALLOWED, status=403, locale=locale)


def _apply_mobile_number_verification_reset(update_data: dict, existing_user: UserDTO) -> None:
    """When mobile_number is in the payload and the value changed (including cleared to NULL), reset verification."""
    if "mobile_number" not in update_data:
        return
    new_mobile = update_data.get("mobile_number")
    existing_mobile = existing_user.mobile_number
    if new_mobile != existing_mobile:
        update_data["mobile_number_verified"] = False
        update_data["mobile_number_verified_at"] = None


def _apply_email_change_request(
    target_user_id: UUID,
    existing_user: UserDTO,
    update_data: dict,
    db: psycopg2.extensions.connection,
) -> str | None:
    """
    If payload requests a different email, start verification flow (do not write email to user_info yet).
    Returns email_change_message for UserResponseSchema, or None.
    """
    if "email" not in update_data:
        return None
    new_email = update_data.get("email")
    if new_email is None:
        update_data.pop("email", None)
        return None
    new_norm = str(new_email).strip().lower()
    existing_norm = (existing_user.email or "").strip().lower()
    if new_norm == existing_norm:
        update_data.pop("email", None)
        return None
    email_change_service.request_email_change(target_user_id, new_norm, db)
    update_data.pop("email", None)
    update_data["email_verified"] = False
    update_data["email_verified_at"] = None
    return f"A verification code has been sent to {new_norm}. Your email will be updated after verification."


def _user_dto_to_response(
    user: UserDTO,
    db: psycopg2.extensions.connection,
    *,
    email_change_message: str | None = None,
) -> UserResponseSchema:
    """Build UserResponseSchema from UserDTO with v2 market_ids."""
    market_ids = get_assigned_market_ids(user.user_id, db, fallback_primary=user.market_id)
    payload = user.model_dump()
    return UserResponseSchema(
        **payload,
        market_ids=market_ids,
        email_change_message=email_change_message,
    )


def _user_dtos_to_responses(users: list, db: psycopg2.extensions.connection) -> list[UserResponseSchema]:
    """Build list of UserResponseSchema from UserDTOs with v2 market_ids (bulk)."""
    if not users:
        return []
    user_ids = [u.user_id for u in users]
    primary_by_user = {u.user_id: u.market_id for u in users}
    bulk = get_assigned_market_ids_bulk(user_ids, db, primary_by_user=primary_by_user)
    return [UserResponseSchema(**u.model_dump(), market_ids=bulk.get(u.user_id, [u.market_id])) for u in users]


router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(oauth2_scheme)])


# 1. List all users
@router.get("", response_model=list[UserResponseSchema])
def list_users(current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)):
    """List all users. Non-archived only."""
    # Use institution scope for Internal users/Suppliers, user scope for Customers
    if current_user.get("role_type") == "customer":
        # Customers can only see themselves
        def _get_users():
            user = user_service.get_by_id(current_user["user_id"], db, scope=None)
            return _user_dtos_to_responses([user] if user else [], db)
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

        def _get_users():
            return _user_dtos_to_responses(user_service.get_all(db, scope=scope, include_archived=False), db)

    return handle_business_operation(_get_users, "user list retrieval")


# 2. Lookup a single user by username or email
@router.get("/lookup", response_model=UserResponseSchema)
def get_user_by_lookup(
    request: Request,
    username: str | None = Query(None, description="Username"),
    email: EmailStr | None = Query(None, description="Email"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    # Ensure at least one unique identifier is provided
    if username is None and email is None:
        raise envelope_exception(ErrorCode.USER_LOOKUP_PARAM_REQUIRED, status=400, locale=locale)
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
    request: Request,
    q: str = Query("", description="Search string (substring match)"),
    search_by: str = Query(..., description="Field to search: name, username, or email"),
    limit: int = limit_query(20, 1, 100),
    offset: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    role_type: str | None = Query(None, description="Filter by role_type (e.g. Customer)"),
    institution_id: UUID | None = institution_filter(),
    market_id: UUID | None = market_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Search users by name, username, or email with optional role_type filter and pagination.
    Used by the discretionary request modal (Customer picker) and other search-by-select UIs.
    Same auth and institution scoping as other user list endpoints.
    Optional institution_id and market_id restrict results (Internal users may pass any institution; market-scoped Internal users only their assigned markets).
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

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
                raise envelope_exception(ErrorCode.USER_MARKET_NOT_ASSIGNED, status=403, locale=locale)

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
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get current user's own profile with enriched data. Non-archived only."""
    user_id = current_user["user_id"]
    scope = None  # No scope needed for self-access

    def _get_enriched_user():
        enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=False)
        if not enriched_user:
            raise user_not_found()
        return enriched_user

    return handle_business_operation(_get_enriched_user, "current user profile retrieval")


# PUT /users/me - Update current user's profile
@router.put("/me", response_model=UserResponseSchema)
def update_current_user_profile(
    request: Request,
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
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
    if current_user.get("role_type") in ("customer", "supplier"):
        update_data.pop("market_id", None)
        update_data.pop("market_ids", None)
    _validate_user_update_market_id(update_data, current_user, locale=locale)
    # v2: persist market_ids to user_market_assignment (and set primary); then remove from update_data
    if "market_ids" in update_data:
        set_user_market_assignments(user_id, update_data["market_ids"], db)
        update_data.pop("market_ids")
    # Customer Comensal: cannot remove city or set to Global
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    rt_str = (role_type.value if hasattr(role_type, "value") else str(role_type)) if role_type else ""
    rn_str = (role_name.value if hasattr(role_name, "value") else str(role_name)) if role_name else ""
    if rt_str == "customer" and rn_str == "comensal" and "city_metadata_id" in update_data:
        if update_data["city_metadata_id"] is None:
            raise envelope_exception(ErrorCode.USER_CITY_REQUIRED, status=400, locale=locale)
        cid = (
            update_data["city_metadata_id"]
            if isinstance(update_data["city_metadata_id"], UUID)
            else UUID(str(update_data["city_metadata_id"]))
        )
        if is_global_city(cid):
            raise envelope_exception(ErrorCode.USER_CITY_MUST_BE_SPECIFIC, status=400, locale=locale)
    # Validate city_metadata_id matches user's market country (use effective market: update or existing)
    if "city_metadata_id" in update_data and update_data["city_metadata_id"] is not None:
        effective_market_id = update_data.get("market_id") or existing_user.market_id
        _validate_user_update_city_metadata_id(update_data["city_metadata_id"], effective_market_id, db, locale=locale)
    # When clearing employer, also clear employer_address_id
    if "employer_entity_id" in update_data and update_data["employer_entity_id"] is None:
        update_data["employer_address_id"] = None

    _apply_mobile_number_verification_reset(update_data, existing_user)
    email_change_message = _apply_email_change_request(user_id, existing_user, update_data, db)

    def _update_user():
        update_data["modified_by"] = current_user["user_id"]
        updated = user_service.update(user_id, update_data, db, scope=scope)
        if not updated:
            raise user_not_found()
        return _user_dto_to_response(updated, db, email_change_message=email_change_message)

    return handle_business_operation(_update_user, "current user profile update", "User updated successfully")


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


# POST /users/me/fcm-token - Register or update FCM device token
@router.post("/me/fcm-token", status_code=status.HTTP_200_OK)
def register_fcm_token(
    request: Request,
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Register or update FCM device token for push notifications. Called on login and token refresh."""
    from uuid import UUID as _UUID

    from app.services.fcm_token_service import register_fcm_token as _register

    token = (body.get("token") or "").strip()
    platform = (body.get("platform") or "").strip().lower()

    if not token:
        raise envelope_exception(ErrorCode.VALIDATION_FIELD_REQUIRED, status=400, locale=locale)
    if platform not in ("ios", "android", "web"):
        raise envelope_exception(ErrorCode.VALIDATION_INVALID_FORMAT, status=400, locale=locale)

    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = _UUID(user_id)

    _register(user_id, token, platform, db)
    return {"detail": "FCM token registered"}


# DELETE /users/me/fcm-token - Remove all FCM tokens for current user (logout)
@router.delete("/me/fcm-token", status_code=status.HTTP_200_OK)
def delete_my_fcm_tokens(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Remove all FCM tokens for the current user. Called on logout."""
    from uuid import UUID as _UUID

    from app.services.fcm_token_service import delete_user_fcm_tokens

    user_id = current_user["user_id"]
    if isinstance(user_id, str):
        user_id = _UUID(user_id)

    count = delete_user_fcm_tokens(user_id, db)
    return {"detail": f"Deleted {count} FCM token(s)"}


# PUT /users/me/password - Change current user's password
@router.put("/me/password", response_model=dict, status_code=status.HTTP_200_OK)
def change_my_password(
    request: Request,
    body: ChangePasswordSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Change current user's password. Requires current password, new password, and confirmation."""
    user_id = current_user["user_id"]
    existing_user = user_service.get_by_id(user_id, db, scope=None)
    if not existing_user:
        raise user_not_found()
    if not verify_password(body.current_password, existing_user.hashed_password):
        raise envelope_exception(ErrorCode.AUTH_CREDENTIALS_INVALID, status=401, locale=locale)
    hashed = hash_password(body.new_password)
    user_service.update(
        user_id,
        {"hashed_password": hashed, "modified_by": user_id},
        db,
        scope=None,
    )
    return {"detail": "Password updated successfully"}


# POST /users/me/verify-email-change - Confirm pending email change with code sent to new address
@router.post("/me/verify-email-change", response_model=dict, status_code=status.HTTP_200_OK)
def verify_my_email_change(
    body: EmailChangeVerifySchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Complete email change using the verification code sent to the new email address."""

    def _verify():
        email_change_service.verify_email_change(current_user["user_id"], body.code, db)
        return {"message": "Email updated successfully"}

    return handle_business_operation(
        _verify,
        "verify email change",
        "Email updated successfully",
    )


# PUT /users/me/terminate - Terminate current user's account
@router.put("/me/terminate", response_model=dict)
def terminate_my_account(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
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
            log_error(
                f"terminate_my_account: user_id={current_user['user_id']} not found in DB during termination check"
            )
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
        if row.get("is_archived"):
            return {"detail": "Account already terminated"}
        # Archive user (soft delete via is_archived = TRUE)
        success = user_service.soft_delete(
            current_user["user_id"],
            current_user["user_id"],  # Self-termination
            db,
            scope=None,
        )
        if not success:
            log_error(f"terminate_my_account: soft_delete returned False for user_id={current_user['user_id']}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
        return {"detail": "Account terminated successfully"}

    return handle_business_operation(_terminate_account, "account termination")


# PUT /users/me/employer - Assign existing employer and address to current user (Customers only)
@router.put("/me/employer", response_model=UserResponseSchema)
def assign_my_employer(
    request: Request,
    body: AssignEmployerRequest = Body(..., description="Employer ID and address ID (office user works at)"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Assign an existing employer entity and address to current user. Both employer_entity_id and address_id required; address must belong to employer. Only Customer users can have an employer; Supplier and Internal get 403."""
    log_employer_assign_debug(
        f"PUT /users/me/employer received: user_id={current_user.get('user_id')} "
        f"employer_entity_id={body.employer_entity_id} address_id={body.address_id}"
    )
    role_type = (current_user.get("role_type") or "").strip()
    if role_type in ("supplier", "internal", "employer"):
        raise envelope_exception(ErrorCode.SECURITY_EMPLOYER_NOT_FOR_SUPPLIER, status=403, locale=locale)
    from app.services.crud_service import address_service, institution_entity_service
    from app.utils.error_messages import entity_not_found

    def _assign_employer():
        employer_entity_id = body.employer_entity_id
        address_id = body.address_id

        # Validate employer entity exists
        employer_entity = institution_entity_service.get_by_id(employer_entity_id, db, scope=None)
        if not employer_entity:
            raise entity_not_found("Employer entity", employer_entity_id)

        # Validate address exists, not archived, and belongs to employer
        address = address_service.get_by_id(address_id, db, scope=None)
        if not address:
            raise envelope_exception(ErrorCode.USER_ADDRESS_NOT_FOUND, status=400, locale=locale)
        if address.is_archived:
            raise envelope_exception(ErrorCode.USER_ADDRESS_ARCHIVED, status=400, locale=locale)
        addr_institution_id = getattr(address, "institution_id", None)
        employer_institution_id = getattr(employer_entity, "institution_id", None)
        if not addr_institution_id or str(addr_institution_id) != str(employer_institution_id):
            raise envelope_exception(ErrorCode.USER_ADDRESS_INSTITUTION_MISMATCH, status=400, locale=locale)

        # Update user's employer_entity_id and employer_address_id
        update_data = {
            "employer_entity_id": employer_entity_id,
            "employer_address_id": address_id,
            "modified_by": current_user["user_id"],
        }

        updated = user_service.update(current_user["user_id"], update_data, db, scope=None)

        # Store floor/unit in address_subpremise when provided (per-user at employer address)
        if updated and (body.floor is not None or body.apartment_unit is not None):
            from app.services.address_service import _upsert_address_subpremise

            _upsert_address_subpremise(
                address_id,
                UUID(str(current_user["user_id"]))
                if isinstance(current_user["user_id"], str)
                else current_user["user_id"],
                UUID(str(current_user["user_id"]))
                if isinstance(current_user["user_id"], str)
                else current_user["user_id"],
                db,
                floor=body.floor,
                apartment_unit=body.apartment_unit,
                is_default=False,
                commit=True,
            )

        if not updated:
            log_employer_assign_debug(
                f"employer entity assignment FAILED: user_service.update returned None for user_id={current_user['user_id']}"
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
                    log_error(
                        f"assign_my_employer: user_id={current_user['user_id']} not found in DB after failed update"
                    )
                    raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
                if row.get("is_archived"):
                    # Decision F: internal-ops jargon suppressed; original: "Run 000 Client Setup..."
                    log_error(
                        f"assign_my_employer: user_id={current_user['user_id']} is archived — "
                        "Run 000 Client Setup to create a fresh customer, then complete Employer Assignment Workflow"
                    )
                    raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
            except HTTPException:
                raise
            log_error(f"assign_my_employer: user_service.update returned None for user_id={current_user['user_id']}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
        log_employer_assign_debug(
            f"employer assignment SUCCESS: user_id={current_user['user_id']} "
            f"employer_entity_id={employer_entity_id} employer_address_id={address_id}"
        )
        return _user_dto_to_response(updated, db)

    return handle_business_operation(_assign_employer, "employer assignment")


# PUT /users/me/workplace - Assign workplace group and pickup address to current user (Customers only)
@router.put("/me/workplace", response_model=UserResponseSchema)
def assign_my_workplace(
    request: Request,
    body: AssignWorkplaceRequest = Body(..., description="Workplace group ID and pickup address ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Assign a workplace group and pickup address to the current user. Only Customer users."""
    role_type = (current_user.get("role_type") or "").strip()
    if role_type in ("supplier", "internal", "employer"):
        raise envelope_exception(ErrorCode.SECURITY_EMPLOYER_NOT_FOR_SUPPLIER, status=403, locale=locale)
    from app.services.crud_service import address_service, workplace_group_service

    def _assign_workplace():
        group_id = body.workplace_group_id
        address_id = body.address_id

        # Validate workplace group exists and is active
        group = workplace_group_service.get_by_id(group_id, db, scope=None)
        if not group:
            raise envelope_exception(ErrorCode.USER_WORKPLACE_GROUP_NOT_FOUND, status=400, locale=locale)
        if group.is_archived:
            raise envelope_exception(ErrorCode.USER_WORKPLACE_GROUP_ARCHIVED, status=400, locale=locale)

        # Validate address exists and is not archived
        address = address_service.get_by_id(address_id, db, scope=None)
        if not address:
            raise envelope_exception(ErrorCode.USER_ADDRESS_NOT_FOUND, status=400, locale=locale)
        if address.is_archived:
            raise envelope_exception(ErrorCode.USER_ADDRESS_ARCHIVED, status=400, locale=locale)

        # Validate address belongs to the workplace group
        addr_wg_id = getattr(address, "workplace_group_id", None)
        if not addr_wg_id or str(addr_wg_id) != str(group_id):
            raise envelope_exception(ErrorCode.USER_ADDRESS_INSTITUTION_MISMATCH, status=400, locale=locale)

        # Update user: workplace_group_id + employer_address_id (pickup location)
        update_data = {
            "workplace_group_id": group_id,
            "employer_address_id": address_id,
            "modified_by": current_user["user_id"],
        }

        updated = user_service.update(
            current_user["user_id"],
            update_data,
            db,
            scope=None,
        )
        if not updated:
            log_error(f"assign_my_workplace: user_service.update returned None for user_id={current_user['user_id']}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)
        log_info(
            f"Workplace assignment SUCCESS: user_id={current_user['user_id']} "
            f"workplace_group_id={group_id} employer_address_id={address_id}"
        )
        return _user_dto_to_response(updated, db)

    return handle_business_operation(_assign_workplace, "workplace assignment")


# =============================================================================
# ENRICHED USER ENDPOINTS (with role_name, role_type, institution_name)
# Must be registered before /{user_id} so /enriched is not parsed as user_id.
# =============================================================================


# GET /users/enriched - List all users with enriched data
@router.get("/enriched", response_model=list[UserEnrichedResponseSchema])
def list_enriched_users(
    response: Response,
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all users with enriched data (role_name, role_type, institution_name). Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _get_enriched_users():
        return get_enriched_users(
            db,
            scope=scope,
            include_archived=False,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )

    result = handle_business_operation(_get_enriched_users, "enriched user list retrieval")
    set_pagination_headers(response, result)
    return result


# GET /users/enriched/{user_id} - Get a single user with enriched data
@router.get("/enriched/{user_id}", response_model=UserEnrichedResponseSchema)
def get_enriched_user_by_id_route(
    request: Request,
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Get a single user by ID with enriched data (role_name, role_type, institution_name).
    For reading your own profile, use GET /users/me instead.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]

    if str(user_id) == str(current_user_id):
        raise envelope_exception(ErrorCode.USER_USE_ME_ENDPOINT, status=410, locale="en")

    # Apply user scoping for Customers and Internal Operators (self-only access)
    if role_type == "customer" or (role_type == "internal" and role_name == "operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        # Check if user exists first (without scope), then check access (with scope)
        # This ensures we return 403 for cross-institution access, not 404
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)

    def _get_enriched_user():
        enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=False)
        if not enriched_user:
            raise user_not_found()
        return enriched_user

    return handle_business_operation(_get_enriched_user, "enriched user retrieval")


# 3. Get a single user by primary key (user_id)
@router.get("/{user_id}", response_model=UserResponseSchema)
def get_user_by_id(
    request: Request,
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Get a user by ID. For reading your own profile, use GET /users/me instead.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]

    if str(user_id) == str(current_user_id):
        raise envelope_exception(ErrorCode.USER_USE_ME_ENDPOINT, status=410, locale="en")

    # Apply user scoping for Customers and Internal Operators (self-only access)
    if role_type == "customer" or (role_type == "internal" and role_name == "operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        # Customers and Internal Operators can only access their own user_id, so scope is None (no institution filtering needed)
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
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)

    user = handle_get_by_id(user_service.get_by_id, user_id, db, "user", extra_kwargs={"scope": scope})
    return _user_dto_to_response(user, db)


# POST /users - Create a new user
@router.post("", response_model=UserResponseSchema, status_code=201)
def create(
    request: Request,
    user: UserCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Create a new user - Restricted to Internal users and Suppliers (Admin/Manager only)"""
    # Customers cannot create users
    if current_user.get("role_type") == "customer":
        raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)

    ensure_operator_cannot_create_users(current_user)
    ensure_supplier_can_create_edit_users(current_user)
    user_data = user.model_dump()
    rt = user_data.get("role_type")
    rt_str = rt.value if hasattr(rt, "value") else str(rt)
    if rt_str == "customer":
        raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=400, locale=locale)
    ensure_supplier_user_institution_only(user_data.get("institution_id"), current_user, action="create")
    # Require institution_type == role_type (Internal→Internal, Customer→Customer, Supplier→Supplier, Employer→Employer)
    institution_id = user_data.get("institution_id")
    if institution_id:
        institution = institution_service.get_by_id(institution_id, db, scope=None)
        if not institution:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=400, locale=locale, entity="Institution")
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
    ensure_employer_not_for_supplier_employee(
        user_data.get("role_type"), user_data.get("employer_entity_id"), context="create"
    )
    if rt_str in ("supplier", "internal", "employer"):
        user_data["employer_entity_id"] = None

    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

    def _create_user_with_validation():
        created = user_signup_service.process_admin_user_creation(
            user_data, current_user, db, scope=scope, locale=locale
        )
        return _user_dto_to_response(created, db)

    return handle_business_operation(
        _create_user_with_validation, "user creation with validation", "User created successfully"
    )


# PUT /users/{user_id} - Update an existing user
@router.put("/{user_id}", response_model=UserResponseSchema)
def update(
    request: Request,
    user_id: UUID,
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Update a user. For updating your own profile, use PUT /users/me instead.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]

    if str(user_id) == str(current_user_id):
        raise envelope_exception(ErrorCode.USER_USE_ME_ENDPOINT, status=410, locale="en")

    ensure_supplier_can_create_edit_users(current_user)
    # Apply user scoping for Customers and Internal Operators (self-only access)
    if role_type == "customer" or (role_type == "internal" and role_name == "operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None  # No institution filtering needed for Customers and Internal Operators
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
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)

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
    _reject_immutable_fields(update_data, locale=locale)
    existing_role_type = _extract_role_type_str(existing_user)
    _apply_employer_rules(update_data, existing_role_type)
    if "role_name" in update_data:
        ensure_user_role_name_allowed(existing_role_type, update_data["role_name"], current_user, "update")
        ensure_can_assign_role_name(
            role_type,
            role_name,
            existing_role_type,
            update_data["role_name"],
        )

    _apply_market_and_city_rules(
        update_data, existing_user, existing_role_type, current_user, user_id, db, locale=locale
    )

    _apply_mobile_number_verification_reset(update_data, existing_user)
    email_change_message = _apply_email_change_request(user_id, existing_user, update_data, db)

    def _update_user():
        update_data["modified_by"] = current_user["user_id"]
        updated = user_service.update(user_id, update_data, db, scope=scope)
        if not updated:
            raise user_not_found()
        return _user_dto_to_response(updated, db, email_change_message=email_change_message)

    return handle_business_operation(_update_user, "user update", "User updated successfully")


# POST /users/{user_id}/resend-invite - Resend B2B invite email (set-password link)
@router.post("/{user_id}/resend-invite", response_model=dict, status_code=status.HTTP_200_OK)
def resend_user_invite(
    request: Request,
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Resend the B2B invite email with set-password link. Same access rules as PUT /users/{user_id}.
    Use when the original invite had wrong URL or expired. Generates new code, invalidates prior codes,
    sends email. User sets password via the link → POST /auth/reset-password.
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")

    ensure_supplier_can_reset_user_password(current_user)
    if role_type == "customer" or (role_type == "internal" and role_name == "operator"):
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
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)

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
        raise envelope_exception(ErrorCode.USER_INVITE_NO_EMAIL, status=400, locale=locale)

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
    request: Request,
    user_id: UUID,
    body: AdminResetPasswordSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Reset another user's password. Same access rules as PUT /users/{user_id}."""
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    current_user_id = current_user["user_id"]

    ensure_supplier_can_reset_user_password(current_user)
    if role_type == "customer" or (role_type == "internal" and role_name == "operator"):
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
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)

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
    request: Request,
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """Delete a user"""
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")

    ensure_supplier_can_create_edit_users(current_user)
    # Apply user scoping for Customers and Internal Operators (self-only access)
    if role_type == "customer" or (role_type == "internal" and role_name == "operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)
        scope = None  # No institution filtering needed for Customers and Internal Operators
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
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)

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
