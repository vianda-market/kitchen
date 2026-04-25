import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.auth.captcha_guard import always_require_captcha_for_web, require_captcha_after_threshold
from app.auth.ip_attempt_tracker import ip_tracker
from app.auth.security import create_access_token
from app.auth.utils import build_token_data, merge_onboarding_token_claims, merge_subscription_token_claims
from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import CustomerSignupSchema, UserEnrichedResponseSchema
from app.services.entity_service import get_enriched_user_by_id
from app.services.error_handling import handle_business_operation
from app.services.password_recovery_service import password_recovery_service
from app.services.user_signup_service import user_signup_service
from app.utils.db import db_read
from app.utils.log import log_password_recovery_debug
from app.utils.rate_limit import limiter


class SignupRequestResponse(BaseModel):
    """Response for POST /customers/signup/request (email verification flow)."""

    success: bool
    message: str
    already_registered: bool = Field(
        default=False,
        description="True when the email is already registered; frontend should prompt user to log in.",
    )


class VerifySignupRequest(BaseModel):
    """Request for POST /customers/signup/verify."""

    code: str | None = Field(None, description="6-digit verification code from email")
    token: str | None = Field(None, description="Legacy verification token (use code instead)")

    @model_validator(mode="after")
    def require_code_or_token(self):
        code = (self.code or "").strip()
        token = (self.token or "").strip()
        if not code and not token:
            raise ValueError("Either code or token is required")
        return self


class VerifySignupResponse(BaseModel):
    """Response for POST /customers/signup/verify: enriched user (incl. city_name for B2C search) and JWT."""

    user: UserEnrichedResponseSchema
    access_token: str


router = APIRouter(prefix="/customers", tags=["Customer Signup"])

# Additional router for password recovery (no /customers prefix)
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# Get signup constants from service
SIGNUP_CONSTANTS = user_signup_service.get_signup_constants()

# ── Conditional reCAPTCHA guards ──────────────────────────────────────────────
_signup_captcha = always_require_captcha_for_web(action="signup")
_signup_verify_captcha = require_captcha_after_threshold(
    action="signup_verify",
    threshold=settings.SIGNUP_VERIFY_CAPTCHA_THRESHOLD,
    window_seconds=settings.SIGNUP_VERIFY_CAPTCHA_WINDOW_SECONDS,
)
_forgot_password_captcha = require_captcha_after_threshold(
    action="forgot_password",
    threshold=settings.FORGOT_PASSWORD_CAPTCHA_THRESHOLD,
    window_seconds=settings.FORGOT_PASSWORD_CAPTCHA_WINDOW_SECONDS,
    track_all_requests=True,
)
_forgot_username_captcha = require_captcha_after_threshold(
    action="forgot_username",
    threshold=settings.FORGOT_USERNAME_CAPTCHA_THRESHOLD,
    window_seconds=settings.FORGOT_USERNAME_CAPTCHA_WINDOW_SECONDS,
    track_all_requests=True,
)
_reset_password_captcha = require_captcha_after_threshold(
    action="reset_password",
    threshold=settings.RESET_PASSWORD_CAPTCHA_THRESHOLD,
    window_seconds=settings.RESET_PASSWORD_CAPTCHA_WINDOW_SECONDS,
)


# =============================================================================
# CUSTOMER SIGNUP (EMAIL VERIFICATION FLOW)
# =============================================================================


@router.post(
    "/signup/request",
    response_model=SignupRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request customer signup (send verification email)",
    responses={
        201: {"description": "Verification email sent; check inbox."},
        409: {
            "description": "Email already registered; user should log in.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {"type": "string", "example": "This email is already registered. Please log in."}
                        },
                    }
                }
            },
        },
    },
)
@limiter.limit("10/minute")
def signup_request(
    request: Request,
    user: CustomerSignupSchema,
    db: psycopg2.extensions.connection = Depends(get_db),
    _captcha=Depends(_signup_captcha),
):
    """
    Step 1 of customer signup: validate payload, store pending signup, send verification email.
    Returns 409 when the email is already registered so the frontend can prompt the user to log in.
    """

    def _request():
        data = user.model_dump()
        # Pass device_id for referral code fallback (deep link lifecycle)
        device_id = request.headers.get("X-Device-Id")
        if device_id:
            data["_device_id"] = device_id
        return user_signup_service.request_customer_signup(data, db)

    result = handle_business_operation(
        _request,
        "customer signup request",
        "A verification link has been sent to your email.",
    )
    if not result:
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
    if result.get("already_registered"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result["message"],
        )
    return result


@router.post(
    "/signup/verify",
    response_model=VerifySignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Verify email and complete customer signup",
)
@limiter.limit("20/minute")
def signup_verify(
    request: Request,
    body: VerifySignupRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    _captcha=Depends(_signup_verify_captcha),
):
    """
    Step 2 of customer signup: validate verification code (or legacy token) from email, create user, return user and JWT.
    """
    code_or_token = (body.code and body.code.strip()) or (body.token and body.token.strip()) or ""

    def _verify():
        return user_signup_service.verify_and_complete_signup(code_or_token, db)

    result = handle_business_operation(
        _verify,
        "customer signup verify",
        "Signup verified",
    )
    if not result:
        ip_tracker.increment(request.client.host, "signup_verify")
        raise envelope_exception(ErrorCode.USER_SIGNUP_CODE_INVALID, status=400, locale="en")
    user_dto, access_token = result
    # Return enriched user (city_name, market_name, etc.) for B2C search box and profile display
    enriched_user = get_enriched_user_by_id(user_dto.user_id, db, scope=None, include_archived=False)
    if not enriched_user:
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
    return VerifySignupResponse(user=enriched_user, access_token=access_token)


class DevPendingTokenResponse(BaseModel):
    """Dev-only: verification token for the given email (for E2E/Postman)."""

    token: str


@router.get(
    "/signup/dev-pending-token",
    response_model=DevPendingTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="(Dev only) Get pending verification token by email",
    deprecated=False,
)
def get_dev_pending_token(
    email: str,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    **Only available when DEV_MODE is True.** Returns the current verification token
    for a pending signup with the given email. Use for E2E/Postman after calling
    POST /signup/request so you can call POST /signup/verify without reading email.
    """
    if not getattr(settings, "DEV_MODE", False):
        raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale="en")
    row = db_read(
        """
        SELECT verification_code FROM pending_customer_signup
        WHERE email = %s AND used = FALSE AND token_expiry > CURRENT_TIMESTAMP
        ORDER BY pending_id DESC LIMIT 1
        """,
        (email.strip().lower(),),
        connection=db,
        fetch_one=True,
    )
    if not row or not row.get("verification_code"):
        raise envelope_exception(ErrorCode.USER_SIGNUP_CODE_INVALID, status=404, locale="en")
    return DevPendingTokenResponse(token=row["verification_code"])


# =============================================================================
# USERNAME RECOVERY (forgot username) - rate limited, no auth
# =============================================================================


class ForgotUsernameRequest(BaseModel):
    """Request for POST /auth/forgot-username."""

    email: EmailStr = Field(..., description="Email address of the account")
    send_password_reset: bool = Field(False, description="If true, also send a password reset link to this email")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_lowercase(cls, v):
        """Normalize email to lowercase for case-insensitive lookup."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()


# =============================================================================
# PASSWORD RECOVERY ROUTES
# =============================================================================


class ForgotPasswordRequest(BaseModel):
    """Request schema for forgot password"""

    email: EmailStr = Field(..., description="Email address of the account")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_lowercase(cls, v):
        """Normalize email to lowercase for case-insensitive lookup."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    """Request schema for password reset"""

    code: str | None = Field(None, description="6-digit reset code from email")
    token: str | None = Field(None, description="Legacy reset token (use code instead)")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")

    @model_validator(mode="after")
    def require_code_or_token(self):
        code = (self.code or "").strip()
        token = (self.token or "").strip()
        if not code and not token:
            raise ValueError("Either code or token is required")
        return self


class PasswordRecoveryResponse(BaseModel):
    """Response schema for password recovery operations"""

    success: bool
    message: str
    access_token: str | None = None
    token_type: str | None = None


@auth_router.post(
    "/forgot-username",
    response_model=PasswordRecoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Request username recovery (forgot username)",
    description="""
    Send the account username to the given email. Optionally also send a password reset link.
    No authentication required. Rate limited per IP.
    Always returns the same generic message to prevent email enumeration.
    """,
)
@limiter.limit("10/minute")
def forgot_username(
    request: Request,
    body: ForgotUsernameRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    _captcha=Depends(_forgot_username_captcha),
):
    """Request username recovery; optionally also trigger password reset email."""
    log_password_recovery_debug(
        f"POST /forgot-username received email={body.email!r} send_password_reset={body.send_password_reset}"
    )
    result = password_recovery_service.request_username_recovery(
        email=body.email, send_password_reset=body.send_password_reset, db=db
    )
    return result


@auth_router.post(
    "/forgot-password",
    response_model=PasswordRecoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="""
    Request a password reset link to be sent to the provided email address.

    **Security Note**: This endpoint always returns success, even if the email doesn't exist.
    This prevents email enumeration attacks.

    **Flow**:
    1. User provides email address
    2. If account exists, an email with reset link is sent
    3. Link expires in 24 hours
    4. User clicks link and provides new password
    """,
)
@limiter.limit("10/minute")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    _captcha=Depends(_forgot_password_captcha),
):
    """
    Request password reset for an account.

    An email with a password reset link will be sent if the account exists.
    """
    log_password_recovery_debug(f"POST /forgot-password received email={body.email!r}")

    def _request_password_reset():
        return password_recovery_service.request_password_reset(email=body.email, db=db)

    result = handle_business_operation(_request_password_reset, "password reset request")

    return result


@auth_router.post(
    "/reset-password",
    response_model=PasswordRecoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    description="""
    Reset password using the token received via email.

    **Requirements**:
    - Token must be valid and not expired (24-hour expiry)
    - Token can only be used once
    - New password must be at least 8 characters

    **Error Cases**:
    - Invalid or expired token
    - Token already used
    - Weak password (handled by validation)
    """,
)
@limiter.limit("20/minute")
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
    _captcha=Depends(_reset_password_captcha),
):
    """
    Reset password using valid reset code (or legacy token) from email.
    Code can only be used once and expires after 24 hours.
    """
    code_or_token = (body.code and body.code.strip()) or (body.token and body.token.strip()) or ""
    log_password_recovery_debug("POST /reset-password received (code/token and new_password present)")

    def _reset_password():
        return password_recovery_service.reset_password(code=code_or_token, new_password=body.new_password, db=db)

    result = handle_business_operation(_reset_password, "password reset")

    if not result["success"]:
        ip_tracker.increment(request.client.host, "reset_password")
        raise envelope_exception(ErrorCode.USER_SIGNUP_CODE_INVALID, status=400, locale="en")

    user_dto = result.get("user")
    out: dict = {"success": result["success"], "message": result["message"]}
    if user_dto is not None:
        token_data = build_token_data(user_dto)
        merge_subscription_token_claims(token_data, user_dto.user_id, db)
        merge_onboarding_token_claims(token_data, db)
        out["access_token"] = create_access_token(data=token_data)
        out["token_type"] = "bearer"
    return out
