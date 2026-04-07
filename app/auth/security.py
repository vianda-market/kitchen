from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
from app.config.settings import settings  # Ensure settings.SECRET_KEY, ALGORITHM, etc. exist

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    """
    Hash the password using the configured algorithm.
    """
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify the plain password against the hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    data should include keys such as:
        - "sub": user_id
        - "role_type": high-level role (e.g., "client")
        - "institution_id": the institution identifier
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """
    Decodes the token and returns its payload.
    In this updated version, we return the full payload (a dict) so that downstream
    functions can access user_id, role_type, institution_id, etc.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Ensure the required fields are present; raise an exception if not.
        user_id = payload.get("sub")
        role_type = payload.get("role_type")
        institution_id = payload.get("institution_id")
        if not user_id or not role_type or not institution_id:
            return None
        return payload  # returning the full dictionary
    except jwt.PyJWTError:
        return None
