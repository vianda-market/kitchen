from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from app.dto.models import UserDTO
from app.services.user_signup_service import user_signup_service
from app.services.password_recovery_service import password_recovery_service
from app.services.error_handling import handle_business_operation
from app.schemas.consolidated_schemas import CustomerSignupSchema, UserResponseSchema
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
import psycopg2.extensions

router = APIRouter(
    prefix="/customers",
    tags=["Customer Signup"]
)

# Additional router for password recovery (no /customers prefix)
auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Get signup constants from service
SIGNUP_CONSTANTS = user_signup_service.get_signup_constants()

@router.post(
    "/signup",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Customer self-registration"
)
def signup_customer(
    user: CustomerSignupSchema,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Public signup endpoint for customers.
    Automatically assigns the 'Vianda Customers' institution and role,
    and marks creation by the bot account.
    """
    def _process_customer_signup():
        user_data = user.dict()
        return user_signup_service.process_customer_signup(user_data, db)
    
    result = handle_business_operation(
        _process_customer_signup,
        "customer signup",
        "Customer self-signed up successfully"
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error signing up customer"
        )
    
    return result


# =============================================================================
# PASSWORD RECOVERY ROUTES
# =============================================================================

class ForgotPasswordRequest(BaseModel):
    """Request schema for forgot password"""
    email: EmailStr = Field(..., description="Email address of the account")


class ResetPasswordRequest(BaseModel):
    """Request schema for password reset"""
    token: str = Field(..., min_length=1, description="Password reset token from email")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class PasswordRecoveryResponse(BaseModel):
    """Response schema for password recovery operations"""
    success: bool
    message: str


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
    """
)
def forgot_password(
    request: ForgotPasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Request password reset for an account.
    
    An email with a password reset link will be sent if the account exists.
    """
    def _request_password_reset():
        return password_recovery_service.request_password_reset(
            email=request.email,
            db=db
        )
    
    result = handle_business_operation(
        _request_password_reset,
        "password reset request"
    )
    
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
    """
)
def reset_password(
    request: ResetPasswordRequest,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Reset password using valid token from email.
    
    The token can only be used once and expires after 24 hours.
    """
    def _reset_password():
        return password_recovery_service.reset_password(
            token=request.token,
            new_password=request.new_password,
            db=db
        )
    
    result = handle_business_operation(
        _reset_password,
        "password reset"
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )
    
    return result
