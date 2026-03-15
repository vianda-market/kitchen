from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.security import create_access_token, verify_token, verify_password
from app.utils.rate_limit import limiter
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.dto.models import UserDTO
from app.services.crud_service import user_service, subscription_service, plan_service
from app.services.entity_service import get_user_by_username
from app.config import Status
import psycopg2.extensions

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

@router.post("/token")
@limiter.limit("20/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    # Retrieve an active user record by username using simple auth method
    try:
        user = get_user_by_username(form_data.username, db)
        if not user:
            log_warning(f"Authentication failed: username '{form_data.username}' not found")
            raise HTTPException(status_code=400, detail="Username does not exist")
    except HTTPException:
        # Re-raise HTTPException (already properly formatted)
        raise
    except Exception as e:
        log_warning(f"Authentication failed for username: {form_data.username} - {str(e)}")
        raise HTTPException(status_code=400, detail="Username does not exist")
    
    # Debug logging for password verification
    log_info(f"🔐 Password verification debug:")
    log_info(f"   Username: {form_data.username}")
    log_info(f"   Plain password from form: {form_data.password}")
    log_info(f"   Hashed password from DB: {user.hashed_password}")
    log_info(f"   Password length: {len(form_data.password) if form_data.password else 0}")
    log_info(f"   Hashed password length: {len(user.hashed_password) if user.hashed_password else 0}")
    
    # Debug logging for role information
    log_info(f"🔑 Role information debug:")
    log_info(f"   User ID: {user.user_id}")
    log_info(f"   Role Type: {user.role_type}")
    log_info(f"   Role Name: {user.role_name}")
    log_info(f"   Institution ID: {user.institution_id}")
    
    # Role information is now stored directly on user_info table as enums
    role_type = user.role_type.value if hasattr(user.role_type, 'value') else str(user.role_type)
    role_name = user.role_name.value if hasattr(user.role_name, 'value') else str(user.role_name)
    log_info(f"   Role type: {role_type}")
    log_info(f"   Role name: {role_name}")
    
    # Verify the password
    password_verified = verify_password(form_data.password, user.hashed_password)
    log_info(f"   Password verification result: {password_verified}")
    
    if not password_verified:
        log_warning(f"Invalid password for username: {form_data.username}")
        raise HTTPException(status_code=400, detail="Incorrect password")

    # Block Inactive users (invite-flow users before password set, or admin-deactivated)
    if user.status == Status.INACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Account not activated. Please set your password using the link from your invite email."
        )
    
    # Log successful authentication
    log_info(f"User authenticated successfully with id: {user.user_id}")

    # Resolve credit_worth for JWT (single subscription per user; used by explore/by-city for savings).
    # A future traveler program will allow ordering in other markets using the in-market subscription.
    credit_worth = None
    subscription_market_id = None
    try:
        subscription = subscription_service.get_by_user(user.user_id, db)
        if subscription:
            plan = plan_service.get_by_id(subscription.plan_id, db)
            if plan:
                credit_worth = float(plan.credit_worth)
                subscription_market_id = str(subscription.market_id)
    except Exception:
        pass  # Optional: token works without credit_worth; by-city returns savings=0

    token_data = {
        "sub": str(user.user_id),
        "role_type": role_type or "Unknown",
        "role_name": role_name or "Unknown",
        "institution_id": str(user.institution_id),
    }
    if credit_worth is not None and subscription_market_id is not None:
        token_data["credit_worth"] = credit_worth
        token_data["subscription_market_id"] = subscription_market_id

    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me")
async def read_users_me(
    token: str = Depends(oauth2_scheme),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    log_info(f"[get_current_user] raw token: {token}")
    user_data = verify_token(token)
    log_info(f"[get_current_user] decoded user_data: {user_data}")
    if not user_data:
        log_warning("Could not validate credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    log_info(f"Token validated successfully for user_id: {user_data.get('sub')}")
    return user_data
