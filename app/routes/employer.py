from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from uuid import UUID
from app.dto.models import EmployerDTO
from app.services.crud_service import employer_service
from app.services.entity_service import create_employer_with_address, get_employers_by_name, get_enriched_employers, get_enriched_employer_by_id
from app.services.error_handling import handle_get_by_id, handle_get_all, handle_business_operation
from app.schemas.consolidated_schemas import (
    EmployerCreateSchema,
    EmployerUpdateSchema,
    EmployerResponseSchema,
    EmployerEnrichedResponseSchema,
    EmployerSearchSchema,
    AddressCreateSchema,
    AddressResponseSchema,
)
from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.utils.query_params import include_archived_query, limit_query
from app.utils.error_messages import employer_not_found
import psycopg2.extensions

router = APIRouter(
    prefix="/employers",
    tags=["Employers"],
    dependencies=[Depends(oauth2_scheme)]
)

# GET /employers/{employer_id}/addresses - Get all addresses for an employer
# NOTE: This route must come BEFORE /{employer_id} to ensure FastAPI matches it correctly
@router.get("/{employer_id}/addresses", response_model=List[AddressResponseSchema])
def get_employer_addresses(
    employer_id: UUID,
    include_archived: bool = include_archived_query("addresses"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all addresses for a specific employer"""
    from app.services.crud_service import address_service
    
    def _get_employer_addresses():
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise employer_not_found(employer_id)
        
        # Query all addresses for this employer using employer_id
        # This is efficient with the partial index on employer_id
        addresses = address_service.get_by_field(
            "employer_id",
            employer_id,
            db,
            scope=None
        )
        
        # Filter out archived addresses if needed
        if not include_archived:
            if isinstance(addresses, list):
                addresses = [addr for addr in addresses if not addr.is_archived]
            elif addresses and addresses.is_archived:
                addresses = None
        
        # Return as list (get_by_field may return single object or list)
        if not addresses:
            return []
        if isinstance(addresses, list):
            return addresses
        return [addresses]
    
    return handle_business_operation(_get_employer_addresses, "employer addresses retrieval")

# POST /employers/{employer_id}/addresses - Add an additional address to an existing employer
# NOTE: This route must come BEFORE /{employer_id} to ensure FastAPI matches it correctly
@router.post("/{employer_id}/addresses", response_model=AddressResponseSchema, status_code=status.HTTP_201_CREATED)
def add_employer_address(
    employer_id: UUID,
    address_create: AddressCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Add an additional address to an existing employer"""
    from app.services.crud_service import address_service
    from app.services.address_service import address_business_service
    from app.config.enums.address_types import AddressType
    
    def _add_employer_address():
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise employer_not_found(employer_id)
        
        # Determine if we should assign employer to user based on role and request parameter
        role_type = current_user.get("role_type")
        assign_to_user = False
        
        # Only Customers can use assign_employer parameter
        if role_type == "Customer":
            assign_to_user = address_create.assign_employer if address_create.assign_employer is not None else True  # Default True
        # Employees/Suppliers: assign_employer parameter is ignored (always False)
        
        # Prepare address data
        address_data = address_create.dict()
        
        # Remove assign_employer from address data (it's a control parameter, not part of address)
        address_data.pop("assign_employer", None)
        
        # Ensure address_type includes "Customer Employer"
        address_types = address_data.get("address_type", [])
        if AddressType.CUSTOMER_EMPLOYER.value not in address_types:
            if isinstance(address_types, list):
                address_types.append(AddressType.CUSTOMER_EMPLOYER.value)
            else:
                address_data["address_type"] = [AddressType.CUSTOMER_EMPLOYER.value]
            address_data["address_type"] = address_types
        
        # Link address to employer
        address_data["employer_id"] = employer_id
        address_data["modified_by"] = current_user["user_id"]
        
        # Create address with geocoding (if restaurant address)
        new_address = address_business_service.create_address_with_geocoding(
            address_data,
            current_user,
            db,
            scope=None
        )
        
        if not new_address:
            raise HTTPException(
                status_code=500,
                detail="Failed to create address"
            )
        
        # NEW: Assign employer to user if requested (atomic within same transaction)
        if assign_to_user:
            from app.services.crud_service import user_service
            user_update_data = {
                "employer_id": employer_id,
                "modified_by": current_user["user_id"]
            }
            updated_user = user_service.update(current_user["user_id"], user_update_data, db, scope=None)
            if not updated_user:
                # Raise error to trigger rollback (strict atomicity)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to assign employer to user"
                )
            log_info(f"Assigned employer {employer_id} to user {current_user['user_id']}")
        
        return new_address
    
    return handle_business_operation(_add_employer_address, "employer address creation")

# GET /employers/{employer_id}?include_archived=...
@router.get("/{employer_id}", response_model=EmployerResponseSchema)
def get_employer(
    employer_id: UUID,
    include_archived: bool = include_archived_query("employers"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get an employer by ID with optional archived records"""
    return handle_get_by_id(
        employer_service.get_by_id,
        employer_id,
        db,
        "employer",
        include_archived
    )

# GET /employers/enriched/ - Get all employers with enriched address data
@router.get("/enriched/", response_model=List[EmployerEnrichedResponseSchema])
def get_all_employers_enriched(
    include_archived: bool = include_archived_query("employers"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all employers with enriched address data"""
    def _get_enriched_employers():
        return get_enriched_employers(db, include_archived=include_archived)
    
    return handle_business_operation(_get_enriched_employers, "enriched employers retrieval")

# GET /employers/enriched/{employer_id} - Get single employer with enriched address data
@router.get("/enriched/{employer_id}", response_model=EmployerEnrichedResponseSchema)
def get_employer_enriched(
    employer_id: UUID,
    include_archived: bool = include_archived_query("employers"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single employer by ID with enriched address data"""
    def _get_enriched_employer():
        enriched_employer = get_enriched_employer_by_id(employer_id, db, include_archived=include_archived)
        if not enriched_employer:
            raise employer_not_found(employer_id)
        return enriched_employer
    
    return handle_business_operation(_get_enriched_employer, "enriched employer retrieval")

# GET /employers/?include_archived=...
@router.get("/", response_model=List[EmployerResponseSchema])
def get_all_employers(
    include_archived: bool = include_archived_query("employers"),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all employers with optional archived records"""
    return handle_get_all(employer_service.get_all, db, "employers", include_archived)


# POST /employers/ – Create a new employer with address
@router.post("/", response_model=EmployerResponseSchema, status_code=status.HTTP_201_CREATED)
def create_employer(
    employer_create: EmployerCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new employer with address"""
    def _create_employer_with_address():
        # Determine if we should assign employer to user based on role and request parameter
        role_type = current_user.get("role_type")
        assign_to_user = False
        
        # Only Customers can use assign_employer parameter
        if role_type == "Customer":
            assign_to_user = employer_create.assign_employer  # Use value from request (default True)
        # Employees/Suppliers: assign_employer parameter is ignored (always False)
        
        # Prepare employer data
        employer_data = {
            "name": employer_create.name,
            "modified_by": current_user["user_id"]
        }
        
        # Prepare address data (remove assign_employer if present - it's for employer creation only)
        address_data = employer_create.address.dict()
        address_data.pop("assign_employer", None)  # Remove if present
        address_data["modified_by"] = current_user["user_id"]
        
        log_info(f"Creating employer with address: {employer_create.name} (assign_to_user={assign_to_user}, role={role_type})")
        
        # Create employer with address atomically (with optional assignment)
        new_employer = create_employer_with_address(
            employer_data=employer_data,
            address_data=address_data,
            user_id=current_user["user_id"],
            db=db,
            assign_to_user=assign_to_user  # NEW parameter
        )
        
        if not new_employer:
            raise HTTPException(
                status_code=500, 
                detail="Failed to create employer with address"
            )
            
        log_info(f"Created employer: {new_employer.employer_id}" + 
                 (f" (assigned to user {current_user['user_id']})" if assign_to_user else ""))
        return new_employer
    
    result = handle_business_operation(
        _create_employer_with_address,
        "employer creation with address",
        "Employer created successfully"
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Error creating employer")
    
    return result

# GET /employers/search?search_term=...&limit=...
@router.get("/search", response_model=List[EmployerResponseSchema])
def search_employers(
    search_term: Optional[str] = Query(None, description="Search term for employer name"),
    limit: int = limit_query(10, 1, 50),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Search employers by name"""
    def _search_employers():
        if not search_term:
            return employer_service.get_all(db)
            
        employers = get_employers_by_name(search_term, db)
        log_info(f"Search for '{search_term}' returned {len(employers)} results")
        return employers
    
    return handle_business_operation(_search_employers, "employer search")

# PUT /employers/{employer_id} – Update an existing employer (Employees only)
@router.put("/{employer_id}", response_model=EmployerResponseSchema)
def update_employer(
    employer_id: UUID,
    employer_update: EmployerUpdateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an existing employer"""
    def _update_employer():
        # Get existing employer
        existing_employer = employer_service.get_by_id(employer_id, db)
        if not existing_employer:
            raise employer_not_found()
        
        # Prepare update data (only include fields that are being updated)
        update_data = {}
        for field, value in employer_update.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            return existing_employer
            
        update_data["modified_by"] = current_user["user_id"]
        
        updated_employer = employer_service.update(employer_id, update_data, db)
        if not updated_employer:
            raise HTTPException(status_code=500, detail="Failed to update employer")
            
        log_info(f"Updated employer: {employer_id}")
        return updated_employer
    
    return handle_business_operation(_update_employer, "employer update")

# DELETE /employers/{employer_id} – Soft delete an employer (archive) (Employees only)
@router.delete("/{employer_id}", response_model=dict)
def delete_employer(
    employer_id: UUID,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Soft delete an employer (archive)"""
    def _delete_employer():
        # Check if employer exists and is not archived
        existing_employer = employer_service.get_by_id(employer_id, db)
        if not existing_employer:
            raise employer_not_found()
        
        # Soft delete using the generic service
        success = employer_service.soft_delete(employer_id, current_user["user_id"], db)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to archive employer")
            
        log_info(f"Archived employer: {employer_id}")
        return {"message": "Employer archived successfully", "employer_id": str(employer_id)}
    
    return handle_business_operation(_delete_employer, "employer deletion")
