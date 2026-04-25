import os
import uuid

import jwt
import psycopg2.extensions
from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer

from app.config.settings import settings  # Ensure settings.SECRET_KEY, ALGORITHM, etc. are defined
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.db import db_read
from app.utils.locale import SUPPORTED_LOCALES, resolve_locale_from_header

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
optional_bearer_scheme = HTTPBearer(auto_error=False)

ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DUMMY_ADMIN_USER_ID = os.getenv("DUMMY_ADMIN_USER_ID", None)


def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Retrieve the current user by decoding the token.
    In local development or when token is None, return a dummy admin user.
    The returned user payload includes the following keys: user_id, role_type, role_name, institution_id.
    Note: This implementation decodes the token and returns the payload directly.
    In a more fully-fleshed application, you might call a helper function in your User model
    to retrieve and/or enrich this user data from your database.
    """
    if ENVIRONMENT == "local" and token is None:
        if not DUMMY_ADMIN_USER_ID:
            # locale not available pre-auth; default to "en" (decision C)
            raise envelope_exception(
                ErrorCode.AUTH_DUMMY_ADMIN_NOT_CONFIGURED, status=status.HTTP_500_INTERNAL_SERVER_ERROR, locale="en"
            )
        # For local testing, generate a UUID for the dummy admin and static attributes.
        return {
            "user_id": uuid.UUID(DUMMY_ADMIN_USER_ID),
            "role_type": "client",
            "role_name": "Unknown",
            "institution_id": uuid.UUID("00000000-0000-0000-0000-000000000000"),
            "locale": "en",
            "credit_cost_local_currency": None,
            "subscription_market_id": None,
        }

    try:
        # Remove "Bearer " prefix if present.
        if token.startswith("Bearer "):
            token = token.split("Bearer ")[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Convert the user_id (sub) to UUID assuming it's stored as UUID in the DB.
        try:
            user_id = uuid.UUID(payload.get("sub"))
        except (ValueError, TypeError):
            # locale not available pre-auth; default to "en" (decision C)
            raise envelope_exception(
                ErrorCode.AUTH_TOKEN_USER_ID_INVALID, status=status.HTTP_401_UNAUTHORIZED, locale="en"
            ) from None

        role_type = payload.get("role_type")
        role_name = payload.get("role_name", "Unknown")  # Extract role_name from JWT payload
        institution_raw = payload.get("institution_id")

        # Convert institution_id to UUID.
        try:
            institution_id = uuid.UUID(institution_raw)
        except (ValueError, TypeError):
            raise envelope_exception(
                ErrorCode.AUTH_TOKEN_INSTITUTION_ID_INVALID, status=status.HTTP_401_UNAUTHORIZED, locale="en"
            ) from None

        if not role_type:
            raise envelope_exception(
                ErrorCode.AUTH_TOKEN_MISSING_FIELDS, status=status.HTTP_401_UNAUTHORIZED, locale="en"
            )

        # Return the full user payload including role_name and optional credit_cost_local_currency/subscription_market_id (single subscription per user).
        out = {
            "user_id": user_id,
            "role_type": role_type,
            "role_name": role_name,
            "institution_id": institution_id,
        }
        if "credit_cost_local_currency" in payload and "subscription_market_id" in payload:
            out["credit_cost_local_currency"] = payload["credit_cost_local_currency"]
            out["subscription_market_id"] = payload["subscription_market_id"]
        loc = payload.get("locale")
        if loc:
            out["locale"] = loc
        if "onboarding_status" in payload:
            out["onboarding_status"] = payload["onboarding_status"]
        return out

    except jwt.PyJWTError:
        raise envelope_exception(
            ErrorCode.AUTH_INVALID_TOKEN, status=status.HTTP_401_UNAUTHORIZED, locale="en"
        ) from None


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
) -> dict | None:
    """Optional Bearer JWT: returns None if missing or invalid (no 401)."""
    if credentials is None or not credentials.credentials:
        return None
    token = credentials.credentials
    try:
        if token.startswith("Bearer "):
            token = token.split("Bearer ", 1)[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = uuid.UUID(payload.get("sub"))
        role_type = payload.get("role_type")
        role_name = payload.get("role_name", "Unknown")
        try:
            institution_id = uuid.UUID(payload.get("institution_id"))
        except (ValueError, TypeError):
            return None
        if not role_type:
            return None
        out = {
            "user_id": user_id,
            "role_type": role_type,
            "role_name": role_name,
            "institution_id": institution_id,
        }
        if "credit_cost_local_currency" in payload and "subscription_market_id" in payload:
            out["credit_cost_local_currency"] = payload["credit_cost_local_currency"]
            out["subscription_market_id"] = payload["subscription_market_id"]
        loc = payload.get("locale")
        if loc:
            out["locale"] = loc
        if "onboarding_status" in payload:
            out["onboarding_status"] = payload["onboarding_status"]
        return out
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def get_resolved_locale(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> str:
    """DB user_info.locale wins; then Accept-Language; then default.
    Also stores resolved locale on request.state for ContentLanguageMiddleware."""
    accept = request.headers.get("Accept-Language")
    uid = current_user.get("user_id")
    if uid is not None:
        row = db_read(
            "SELECT locale FROM user_info WHERE user_id = %s",
            (str(uid),),
            connection=db,
            fetch_one=True,
        )
        if row and row.get("locale") and row["locale"] in SUPPORTED_LOCALES:
            locale = row["locale"]
            request.state.resolved_locale = locale
            return locale
    locale = resolve_locale_from_header(accept)
    request.state.resolved_locale = locale
    return locale


def get_resolved_locale_optional(
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> str:
    """Same as get_resolved_locale but for routes that allow anonymous access.
    Always sets request.state.resolved_locale so that exception handlers can
    use it via getattr(request.state, 'resolved_locale', None) without having
    to re-resolve from the header (Q-S6 in translation-phase-2-design.md)."""
    accept = request.headers.get("Accept-Language")
    if current_user and current_user.get("user_id") is not None:
        row = db_read(
            "SELECT locale FROM user_info WHERE user_id = %s",
            (str(current_user["user_id"]),),
            connection=db,
            fetch_one=True,
        )
        if row and row.get("locale") and row["locale"] in SUPPORTED_LOCALES:
            locale = row["locale"]
            request.state.resolved_locale = locale
            return locale
    locale = resolve_locale_from_header(accept)
    request.state.resolved_locale = locale
    return locale


def get_super_admin_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has super-admin role for discretionary credit approval.

    Super Admin users have role_type='Internal' and role_name='Super Admin'.
    This allows them to have global access (via Internal role_type) plus special
    approval permissions (via role_name).

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if super-admin (role_type='Internal' AND role_name='Super Admin')

    Raises:
        HTTPException: If user is not super-admin
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")

    # Check for positive outcomes: Super Admin must have both Internal role_type AND Super Admin role_name
    if role_type == "internal" and role_name == "super_admin":
        return current_user

    # locale not available in auth dependency chain; default to "en" (decision C)
    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_employee_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Internal role_type for system configuration access.

    Internal users (role_type='Internal') have global access and can manage system
    configuration such as Plans, Credit Currencies, and Discretionary credits.
    This includes both Admin and Super Admin users (both are Internal).

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Internal (any role_name: Admin, Super Admin, etc.)

    Raises:
        HTTPException: If user is not Internal
    """
    role_type = current_user.get("role_type")

    # Check for positive outcome: Internal role_type required for system configuration
    if role_type == "internal":
        return current_user

    # locale not available in auth dependency chain; default to "en" (decision C)
    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_client_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Customer role_type for client-only operations.

    Customer users (role_type='Customer') can view certain resources for payment processing.
    This is used for iOS/Android app access.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Customer

    Raises:
        HTTPException: If user is not a Customer
    """
    role_type = current_user.get("role_type")

    # Check for positive outcome: Customer role_type required
    if role_type == "customer":
        return current_user

    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_client_or_employee_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Customer or Internal role_type.

    Used for resources that both Customers (for mobile app) and Internal users (for backoffice)
    need to access, but Suppliers should not access (e.g., Plans).

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Customer or Internal

    Raises:
        HTTPException: If user is not a Customer or Internal
    """
    role_type = current_user.get("role_type")

    # Check for positive outcomes: Customer or Internal role_type required
    if role_type in ["customer", "internal"]:
        return current_user

    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_client_employee_or_supplier_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Customer, Internal, or Supplier role_type.

    Used for reference data (countries, provinces, cities) that all authenticated users
    need for address forms—Customers (B2C), Internal (back-office), and Suppliers (B2B).

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Customer, Internal, or Supplier

    Raises:
        HTTPException: If user has unrecognized role_type
    """
    role_type = current_user.get("role_type")
    if role_type in ["customer", "internal", "supplier"]:
        return current_user
    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_employee_or_customer_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user is Internal or Customer, explicitly blocking Suppliers.

    Used for resources that follow the "Internal global + Customer self-scope" pattern:
    - Internal: Global access (can see all records)
    - Customers: Self-scoped access (can only see their own records)
    - Suppliers: Blocked (403 Forbidden)

    This is different from get_client_or_employee_user in that it explicitly blocks
    Suppliers and is intended for user-owned resources (subscriptions, payment methods, etc.)
    where Suppliers should not have access.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Internal or Customer

    Raises:
        HTTPException(403): If user is Supplier or not Internal/Customer
    """
    role_type = current_user.get("role_type")

    # Explicitly block Suppliers
    if role_type == "supplier":
        raise envelope_exception(
            ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en"
        )

    # Allow Internal and Customers
    if role_type in ["internal", "customer"]:
        return current_user

    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_employee_or_supplier_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user is Internal or Supplier, blocking Customers.

    Used for resources that Suppliers and Internal users can access but Customers cannot,
    e.g. reading assignable roles for user create/edit forms.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Internal or Supplier

    Raises:
        HTTPException(403): If user is Customer
    """
    role_type = current_user.get("role_type")
    if role_type in ["internal", "supplier"]:
        return current_user
    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def get_admin_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has admin or super-admin role for discretionary credit operations.

    Admin users (role_type='Internal', role_name='Admin') can create discretionary requests.
    Super Admin users (role_type='Internal', role_name='Super Admin') can also create requests
    and approve them (approval uses get_super_admin_user).

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current user if Internal with role_name='Admin' or 'Super Admin'

    Raises:
        HTTPException: If user is not admin or super-admin
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")

    # Check for positive outcomes: Admin users must be Internal role_type with Admin or Super Admin role_name
    if role_type == "internal" and role_name in ["admin", "super_admin"]:
        return current_user

    raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=status.HTTP_403_FORBIDDEN, locale="en")


def require_supplier_admin(current_user: dict = Depends(get_current_user)):
    """
    Verify user is Supplier Admin.
    """
    from app.security.field_policies import ensure_supplier_admin_only

    ensure_supplier_admin_only(current_user)
    return current_user


def require_supplier_admin_or_employee_admin(current_user: dict = Depends(get_current_user)):
    """
    Verify user is Supplier Admin or Internal Admin/Super Admin.
    Used for institution entities (and formerly institution bank accounts).
    """
    role_type = (current_user.get("role_type") or "").strip()
    role_name = (current_user.get("role_name") or "").strip()
    allowed = (role_type == "supplier" and role_name == "admin") or (
        role_type == "internal" and role_name in ("admin", "super_admin")
    )
    if not allowed:
        raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale="en")
    return current_user
