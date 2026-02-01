import os
import uuid
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from app.config.settings import settings  # Ensure settings.SECRET_KEY, ALGORITHM, etc. are defined

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Dummy admin not configured."
            )
        # For local testing, generate a UUID for the dummy admin and static attributes.
        return {
            "user_id": uuid.UUID(DUMMY_ADMIN_USER_ID),
            "role_type": "client",           # Adjust as needed for local testing
            "role_name": "Unknown",          # Default for local testing
            "institution_id": uuid.UUID("00000000-0000-0000-0000-000000000000")  # Replace with dummy institution UUID
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user identifier in token"
            )
        
        role_type = payload.get("role_type")
        role_name = payload.get("role_name", "Unknown")  # Extract role_name from JWT payload
        institution_raw = payload.get("institution_id")
        
        # Convert institution_id to UUID.
        try:
            institution_id = uuid.UUID(institution_raw)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid institution identifier in token"
            )
        
        if not role_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is missing required fields."
            )
        
        # Return the full user payload including role_name.
        return {
            "user_id": user_id,
            "role_type": role_type,
            "role_name": role_name,
            "institution_id": institution_id
        }
    
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def get_super_admin_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has super-admin role for discretionary credit approval.
    
    Super Admin users have role_type='Employee' and role_name='Super Admin'.
    This allows them to have global access (via Employee role_type) plus special 
    approval permissions (via role_name).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if super-admin (role_type='Employee' AND role_name='Super Admin')
        
    Raises:
        HTTPException: If user is not super-admin
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    
    # Check for positive outcomes: Super Admin must have both Employee role_type AND Super Admin role_name
    if role_type == "Employee" and role_name == "Super Admin":
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Super-admin access required for discretionary credit operations"
    )


def get_employee_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Employee role_type for system configuration access.
    
    Employee users (role_type='Employee') have global access and can manage system
    configuration such as Plans, Credit Currencies, and Discretionary credits.
    This includes both Admin and Super Admin users (both are Employees).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if Employee (any role_name: Admin, Super Admin, etc.)
        
    Raises:
        HTTPException: If user is not an Employee
    """
    role_type = current_user.get("role_type")
    
    # Check for positive outcome: Employee role_type required for system configuration
    if role_type == "Employee":
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Employee access required for system configuration operations"
    )


def get_client_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Customer role_type for client-only operations.
    
    Customer users (role_type='Customer') can view certain resources like fintech links
    for payment processing. This is used for iOS/Android app access.
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if Customer
        
    Raises:
        HTTPException: If user is not a Customer
    """
    role_type = current_user.get("role_type")
    
    # Check for positive outcome: Customer role_type required
    if role_type == "Customer":
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Customer access required for this operation"
    )


def get_client_or_employee_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Customer or Employee role_type.
    
    Used for resources that both Customers (for mobile app) and Employees (for backoffice)
    need to access, but Suppliers should not access (e.g., Plans).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if Customer or Employee
        
    Raises:
        HTTPException: If user is not a Customer or Employee
    """
    role_type = current_user.get("role_type")
    
    # Check for positive outcomes: Customer or Employee role_type required
    if role_type in ["Customer", "Employee"]:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Customer or Employee access required for this operation"
    )


def get_employee_or_customer_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user is Employee or Customer, explicitly blocking Suppliers.
    
    Used for resources that follow the "Employee global + Customer self-scope" pattern:
    - Employees: Global access (can see all records)
    - Customers: Self-scoped access (can only see their own records)
    - Suppliers: Blocked (403 Forbidden)
    
    This is different from get_client_or_employee_user in that it explicitly blocks
    Suppliers and is intended for user-owned resources (subscriptions, payment methods, etc.)
    where Suppliers should not have access.
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if Employee or Customer
        
    Raises:
        HTTPException(403): If user is Supplier or not Employee/Customer
    """
    role_type = current_user.get("role_type")
    
    # Explicitly block Suppliers
    if role_type == "Supplier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Suppliers cannot access this resource"
        )
    
    # Allow Employees and Customers
    if role_type in ["Employee", "Customer"]:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Employee or Customer access required"
    )


def get_admin_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has admin or super-admin role for discretionary credit operations.
    
    Admin users (role_type='Employee', role_name='Admin') can create discretionary requests.
    Super Admin users (role_type='Employee', role_name='Super Admin') can also create requests
    and approve them (approval uses get_super_admin_user).
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if Employee with role_name='Admin' or 'Super Admin'
        
    Raises:
        HTTPException: If user is not admin or super-admin
    """
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    
    # Check for positive outcomes: Admin users must be Employee role_type with Admin or Super Admin role_name
    if role_type == "Employee" and role_name in ["Admin", "Super Admin"]:
        return current_user
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="Admin access required for discretionary credit operations"
    )
