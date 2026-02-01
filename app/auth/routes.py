from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.security import create_access_token, verify_token, verify_password
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.dto.models import UserDTO
from app.services.crud_service import user_service
from app.services.entity_service import get_user_by_username 
import psycopg2.extensions

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

@router.post("/token")
async def login(
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
    
    # Log successful authentication
    log_info(f"User authenticated successfully with id: {user.user_id}")
    
    # Create the access token with additional role attributes and institution_id.
    access_token = create_access_token(
        data={
            "sub": str(user.user_id),            # Make sure to convert UUID to string if needed
            "role_type": role_type or "Unknown",  # Use the safely retrieved role_type
            "role_name": role_name or "Unknown",  # Use the safely retrieved role_name
            "institution_id": str(user.institution_id)
        }
    )
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
