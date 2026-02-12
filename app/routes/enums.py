"""
Enum Routes

API endpoints for retrieving system enum values.
Provides centralized access to all valid enum values for frontend dropdowns.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.schemas.consolidated_schemas import EnumsResponseSchema
from app.services.enum_service import enum_service
from app.utils.log import log_info, log_error

router = APIRouter(prefix="/enums", tags=["Enums"])


@router.get("/", response_model=EnumsResponseSchema)
async def get_all_enums(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all system enum values.
    
    **Authorization**: All authenticated users (Employee, Supplier, Customer)
    
    Returns all valid enum values used throughout the system, primarily
    for populating frontend dropdown menus and form validation.
    
    **Returns**: Dictionary mapping enum type names to their valid values
    
    **Caching**: This endpoint returns static configuration data.
    Frontend should cache for 1 hour to minimize API calls.
    
    **Example Response**:
    ```json
    {
        "status": ["Active", "Inactive", "Pending", ...],
        "address_type": ["Restaurant", "Customer Home", ...],
        "role_type": ["Employee", "Supplier", "Customer"],
        ...
    }
    ```
    """
    log_info(f"User {current_user.get('user_id')} fetching system enums")
    
    try:
        enums = enum_service.get_all_enums()
        
        # Add cache-control headers for frontend caching
        return JSONResponse(
            content=enums,
            headers={
                "Cache-Control": "public, max-age=3600",  # 1 hour cache
                "X-Content-Type-Options": "nosniff"
            }
        )
    except Exception as e:
        log_error(f"Error fetching enums: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enum values")


@router.get("/{enum_name}", response_model=List[str])
async def get_enum_by_name(
    enum_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get values for a specific enum type.
    
    **Authorization**: All authenticated users (Employee, Supplier, Customer)
    
    **Path Parameters**:
    - `enum_name`: Name of the enum (e.g., 'status', 'role_type', 'subscription_status')
    
    **Returns**: List of valid values for the requested enum
    
    **Caching**: Frontend should cache individual enum responses for 1 hour.
    
    **Example**: GET /api/v1/enums/status
    ```json
    ["Active", "Inactive", "Pending", "Arrived", "Complete", "Cancelled", "Processed"]
    ```
    
    **Error Responses**:
    - 404: Unknown enum type requested
    - 401: Not authenticated
    - 500: Server error
    """
    log_info(f"User {current_user.get('user_id')} fetching enum: {enum_name}")
    
    try:
        enum_values = enum_service.get_enum_by_name(enum_name)
        
        return JSONResponse(
            content=enum_values,
            headers={
                "Cache-Control": "public, max-age=3600",  # 1 hour cache
                "X-Content-Type-Options": "nosniff"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log_error(f"Error fetching enum {enum_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enum values")
