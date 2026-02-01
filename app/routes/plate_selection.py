from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from app.dto.models import PlateSelectionDTO
from app.services.plate_selection_service import create_plate_selection_with_transactions
from app.schemas.consolidated_schemas import PlateSelectionResponseSchema
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.utils.log import log_info
from typing import Dict, Any, List
import psycopg2.extensions

router = APIRouter(
    prefix="/plate-selections",
    tags=["Plate Selections"],
)

@router.post("/", response_model=PlateSelectionResponseSchema)
def create_plate_selection(
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create a new plate selection using business logic service.
    
    Expected payload format:
    {
        "plate_id": "uuid",
        "pickup_time_range": "12:00-12:15",
        "target_kitchen_day": "Monday" (optional)
    }
    """
    try:
        # Validate required fields
        if "plate_id" not in payload:
            raise HTTPException(status_code=422, detail="plate_id is required")
        
        if "pickup_time_range" not in payload:
            raise HTTPException(status_code=422, detail="pickup_time_range is required")
        
        # Create plate selection using business logic service
        selection = create_plate_selection_with_transactions(payload, current_user, db)
        
        log_info(f"Successfully created plate selection: {selection.plate_selection_id}")
        return selection
        
    except HTTPException:
        # Re-raise HTTPExceptions (these have proper status codes and messages)
        raise
    except Exception as e:
        log_info(f"Error creating plate selection: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating plate selection: {str(e)}")

@router.get("/{plate_selection_id}", response_model=PlateSelectionResponseSchema)
def get_plate_selection(
    plate_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a plate selection by ID"""
    from app.services.crud_service import plate_selection_service
    from app.services.error_handling import handle_get_by_id
    
    return handle_get_by_id(
        plate_selection_service.get_by_id_non_archived,
        plate_selection_id,
        db,
        "plate selection",
        include_archived=False
    )

@router.get("/", response_model=list[PlateSelectionResponseSchema])
def list_plate_selections(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all plate selections for the current user"""
    from app.services.crud_service import get_all_by_user
    
    return get_all_by_user(current_user["user_id"], db)

@router.post("/kitchen-days/{plate_id}")
def assign_kitchen_days_to_plate(
    plate_id: UUID,
    kitchen_days: List[str],
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Assign kitchen days to a plate.
    
    **DEPRECATED**: Use `/plate-kitchen-days/` endpoints instead.
    This endpoint is kept for backward compatibility.
    
    Expected payload format:
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    """
    try:
        # Import services
        from app.services.crud_service import plate_service, plate_kitchen_days_service
        from app.security.entity_scoping import EntityScopingService, ENTITY_PLATE_KITCHEN_DAYS
        import psycopg2
        
        # Get scope for plate kitchen days
        scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE_KITCHEN_DAYS, current_user)
        
        # Validate that the plate exists
        plate = plate_service.get_by_id(plate_id, db)
        if not plate:
            raise HTTPException(status_code=404, detail=f"Plate not found for plate_id {plate_id}")
        
        # Validate kitchen days
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for day in kitchen_days:
            if day not in valid_days:
                raise HTTPException(
                    status_code=422, 
                    detail=f"Invalid kitchen day: {day}. Valid days are: {', '.join(valid_days)}"
                )
        
        # Hard delete ALL existing kitchen days for this plate (including archived ones)
        # This is necessary because the unique constraint doesn't exclude archived records
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM plate_kitchen_days WHERE plate_id = %s", (str(plate_id),))
            db.commit()
        
        # Create new kitchen days (CRUDService will validate plate belongs to institution via JOIN-based scoping)
        created_days = []
        for day in kitchen_days:
            kitchen_day_data = {
                'plate_id': str(plate_id),
                'kitchen_day': day,
                'is_archived': False,
                'modified_by': current_user["user_id"]
            }
            created_day = plate_kitchen_days_service.create(kitchen_day_data, db, scope=scope)
            if created_day:
                created_days.append(created_day.kitchen_day)
        
        log_info(f"Successfully assigned kitchen days to plate {plate_id}: {created_days}")
        
        return {
            "plate_id": str(plate_id),
            "kitchen_days": created_days,
            "message": f"Successfully assigned {len(created_days)} kitchen days to plate"
        }
        
    except HTTPException:
        # Re-raise HTTPExceptions (these have proper status codes and messages)
        raise
    except Exception as e:
        log_info(f"Error assigning kitchen days to plate {plate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error assigning kitchen days: {str(e)}")

@router.get("/kitchen-days/{plate_id}")
def get_plate_kitchen_days(
    plate_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get kitchen days for a specific plate.
    
    **DEPRECATED**: Use `/plate-kitchen-days/` endpoints instead.
    This endpoint is kept for backward compatibility.
    """
    try:
        from app.services.crud_service import plate_kitchen_days_service
        from app.security.entity_scoping import EntityScopingService, ENTITY_PLATE_KITCHEN_DAYS
        
        # Get scope for plate kitchen days
        scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE_KITCHEN_DAYS, current_user)
        
        # Get all kitchen days for this plate (with scoping)
        all_kitchen_days = plate_kitchen_days_service.get_all(db, scope=scope, include_archived=False)
        plate_kitchen_days = [
            kd.kitchen_day for kd in all_kitchen_days 
            if kd.plate_id == plate_id
        ]
        
        return {
            "plate_id": str(plate_id),
            "kitchen_days": plate_kitchen_days
        }
        
    except Exception as e:
        log_info(f"Error getting kitchen days for plate {plate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting kitchen days: {str(e)}")