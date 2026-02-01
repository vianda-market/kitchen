from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Depends
from app.dto.models import UserDTO
from app.services.user_signup_service import user_signup_service
from app.services.error_handling import handle_business_operation
from app.schemas.consolidated_schemas import CustomerSignupSchema, UserResponseSchema
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
import psycopg2.extensions

router = APIRouter(
    prefix="/customers",
    tags=["Customer Signup"]
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
