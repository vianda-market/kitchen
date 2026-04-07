from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.security import create_access_token, verify_token, verify_password
from app.utils.rate_limit import limiter
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.auth.captcha_guard import require_captcha_after_threshold
from app.auth.ip_attempt_tracker import ip_tracker
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.dto.models import UserDTO
from app.services.crud_service import user_service
from app.auth.utils import build_token_data, merge_subscription_token_claims, merge_onboarding_token_claims
from app.services.entity_service import get_user_by_username
from app.config import Status
from app.config.settings import settings
import psycopg2.extensions

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

_login_captcha = require_captcha_after_threshold(
    action="login",
    threshold=settings.LOGIN_CAPTCHA_THRESHOLD,
    window_seconds=settings.LOGIN_CAPTCHA_WINDOW_SECONDS,
)

@router.post("/token")
@limiter.limit("20/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: psycopg2.extensions.connection = Depends(get_db),
    _captcha=Depends(_login_captcha),
):
    ip = request.client.host

    # Retrieve an active user record by username using simple auth method
    try:
        user = get_user_by_username(form_data.username, db)
        if not user:
            log_warning(f"Authentication failed: username '{form_data.username}' not found")
            ip_tracker.increment(ip, "login")
            raise HTTPException(status_code=400, detail="Username does not exist")
    except HTTPException:
        raise
    except Exception as e:
        log_warning(f"Authentication failed for username: {form_data.username} - {str(e)}")
        ip_tracker.increment(ip, "login")
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
        ip_tracker.increment(ip, "login")
        raise HTTPException(status_code=400, detail="Incorrect password")

    # Block Inactive users (invite-flow users before password set, or admin-deactivated)
    if user.status == Status.INACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Account not activated. Please set your password using the link from your invite email."
        )
    
    # Block Customer Comensal login on B2B platform (x-client-type: b2b)
    client_type = request.headers.get("x-client-type", "").strip().lower()
    if client_type == "b2b" and role_type == "Customer" and role_name == "Comensal":
        from app.config.settings import get_settings
        settings = get_settings()
        raise HTTPException(
            status_code=403,
            detail={
                "code": "customer_app_only",
                "message": "Customer accounts must use the Vianda mobile app.",
                "app_store_url": settings.APP_STORE_URL,
                "play_store_url": settings.PLAY_STORE_URL,
            }
        )

    # Successful auth — reset CAPTCHA counter for this IP
    ip_tracker.reset(ip, "login")
    log_info(f"User authenticated successfully with id: {user.user_id}")

    token_data = build_token_data(user)
    merge_subscription_token_claims(token_data, user.user_id, db)
    merge_onboarding_token_claims(token_data, db)

    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    user = user_service.get_by_id(current_user["user_id"], db)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.status == Status.INACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Account is inactive. Please contact support.",
        )

    token_data = build_token_data(user)
    merge_subscription_token_claims(token_data, user.user_id, db)
    merge_onboarding_token_claims(token_data, db)

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
