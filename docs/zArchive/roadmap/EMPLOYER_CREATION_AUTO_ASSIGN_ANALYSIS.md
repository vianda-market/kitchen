# Employer Creation Auto-Assign Analysis

## Current State

### Existing Endpoints

1. **POST /employers/** - Create employer with address (atomic)
   - Creates employer + address in single transaction
   - Works for both Employees and Customers
   - Does NOT assign employer to user

2. **PUT /users/me/employer?employer_id={uuid}** - Assign existing employer to current user
   - Separate endpoint for assignment
   - Requires employer to already exist
   - Works for all user types

### Current Flow (Option 1)

**For Customers:**
1. `GET /employers/` - Search for employer
2. If not found: `POST /employers/` - Create employer with address
3. `PUT /users/me/employer?employer_id={uuid}` - Assign employer to self

**For Employees:**
1. `POST /employers/` - Create employer with address (for catalog)
2. No assignment needed (they're just adding to catalog)

---

## Option 1: Current Two-Step Process

### Pros
- ✅ Clear separation of concerns (create vs assign)
- ✅ Works consistently for all user types
- ✅ Explicit user action for assignment (user must choose to assign)
- ✅ No role-based logic in employer creation
- ✅ Employees can create employers without affecting their own user record
- ✅ Simple to understand and maintain

### Cons
- ❌ Customers need 2 API calls (create + assign)
- ❌ Poor UX - user creates employer but must remember to assign it
- ❌ Risk of orphaned employers (created but never assigned)
- ❌ More complex client-side flow

### Implementation
- No changes needed
- Postman collection: Add 3 steps (GET, POST, PUT)

---

## Option 2: Auto-Assign for Customers

### Behavior
- **If Employee creates employer**: Just create (no assignment)
- **If Customer creates employer**: Create + auto-assign to that customer

### Pros
- ✅ Better UX for customers (single API call)
- ✅ Atomic operation for customer workflow
- ✅ Reduces risk of orphaned employers
- ✅ Matches user expectation (if I create it, I want it assigned)
- ✅ Still allows employees to create without assignment

### Cons
- ❌ Role-based logic in employer creation endpoint
- ❌ Less explicit (assignment happens automatically)
- ❌ Potential confusion if customer creates employer but doesn't want it assigned
- ❌ More complex endpoint logic

### Implementation Requirements

1. **Update `EmployerCreateSchema`**
   - Add optional `assign_employer: bool = True` field
   - Default `True` for better UX (matches common customer use case)
   - Document that this only applies to Customers (ignored for Employees/Suppliers)

2. **Update `AddressCreateSchema` (for adding address to existing employer)**
   - Add optional `assign_employer: bool = False` field
   - Default `False` (adding address doesn't imply assignment)
   - Document that this assigns the employer to the user if `True`

3. **Modify `create_employer_with_address()` service method**
   - Add `assign_to_user: bool = False` parameter
   - If `True`, update user's `employer_id` after employer creation
   - Must be atomic (within same transaction)

4. **Modify `POST /employers/` endpoint**
   - Extract `assign_employer` from request body (default `True`)
   - Check `current_user["role_type"]`
   - If `role_type == "Customer"`: Use `assign_employer` value from request
   - If `role_type == "Employee"` or `"Supplier"`: Ignore `assign_employer` (always `False`)

5. **Modify `POST /employers/{employer_id}/addresses` endpoint**
   - Extract `assign_employer` from request body (default `False`)
   - If `assign_employer == True` and user is Customer: Assign employer to user
   - If `assign_employer == False` or user is Employee/Supplier: Just add address

6. **Transaction Safety**
   - All operations (create address, create employer, assign to user) must be in single transaction
   - If any step fails, rollback everything

---

## Recommendation: **Option 2 (Enhanced) - Explicit `assign_employer` Parameter**

### Rationale

After considering edge cases, we recommend an **explicit boolean parameter** approach:

1. **Better UX**: Default `assign_employer=true` for customers (matches common case)
2. **User Control**: Customers can explicitly opt-out if creating employer for someone else
3. **Explicit Intent**: UI checkbox makes assignment decision clear to user
4. **Flexible**: Works for both creating employer and adding address to employer
5. **Atomic Operation**: All-or-nothing ensures data consistency
6. **Edge Case Support**: Handles cases where customer creates employer but doesn't want it assigned

### Edge Cases Handled

- ✅ Customer creates employer with `assign_employer=true` (default) → Auto-assigned
- ✅ Customer creates employer with `assign_employer=false` → Not assigned (for someone else)
- ✅ Customer adds address to existing employer with `assign_employer=true` → Employer assigned to customer
- ✅ Customer adds address to existing employer with `assign_employer=false` → Address added, employer not assigned
- ✅ Employee creates employer → `assign_employer` parameter ignored (employees don't auto-assign)
- ✅ Customer creates employer, then wants to unassign → Use `PUT /users/me/employer?employer_id=null` (if supported)
- ✅ Customer creates employer, then wants different employer → Use `PUT /users/me/employer?employer_id={other_id}`

### Implementation Plan

#### Phase 1: Schema Updates

**File**: `app/schemas/consolidated_schemas.py`

**Update `EmployerCreateSchema`**:
```python
class EmployerCreateSchema(BaseModel):
    """Schema for creating a new employer with embedded address"""
    name: str = Field(..., max_length=100, description="Employer company name")
    address: 'AddressCreateSchema' = Field(..., description="Complete address information for the employer location")
    assign_employer: bool = Field(
        True, 
        description="If True (default), assign this employer to the current user. Only applies to Customers. Ignored for Employees/Suppliers."
    )
```

**Update `AddressCreateSchema`** (for adding address to existing employer):
```python
class AddressCreateSchema(BaseModel):
    # ... existing fields ...
    assign_employer: Optional[bool] = Field(
        True,  # Default True - assume clients want least steps possible
        description="If True (default), assign the employer to the current user when adding address. Only applies to Customers. Can be unchecked to opt-out."
    )
```

#### Phase 2: Service Layer Update

**File**: `app/services/entity_service.py`

**Function**: `create_employer_with_address()`

**Changes**:
```python
def create_employer_with_address(
    employer_data: dict, 
    address_data: dict, 
    user_id: UUID, 
    db: psycopg2.extensions.connection,
    *,
    assign_to_user: bool = False  # NEW parameter
) -> EmployerDTO:
    """
    Create employer with address - business logic with transaction.
    
    Args:
        employer_data: Employer data dictionary
        address_data: Address data dictionary
        user_id: ID of user creating the employer
        db: Database connection
        assign_to_user: If True, automatically assign employer to user (for Customers)
        
    Returns:
        Created EmployerDTO
    """
    try:
        # All operations use same db connection (transactional if autocommit=False)
        # Create address
        address = address_service.create(address_data, db)
        if not address:
            raise HTTPException(status_code=500, detail="Failed to create address")
        
        # Create employer with address reference
        employer_data["address_id"] = address.address_id
        employer_data["modified_by"] = user_id
        employer = employer_service.create(employer_data, db)
        if not employer:
            raise HTTPException(status_code=500, detail="Failed to create employer")
        
        # Update address to link it to the employer (set employer_id)
        address_update_data = {
            "employer_id": employer.employer_id,
            "modified_by": user_id
        }
        updated_address = address_service.update(address.address_id, address_update_data, db)
        if not updated_address:
            log_warning(f"Failed to link address {address.address_id} to employer {employer.employer_id}")
        
        # NEW: Assign to user if requested
        if assign_to_user:
            from app.services.crud_service import user_service
            user_update_data = {
                "employer_id": employer.employer_id,
                "modified_by": user_id
            }
            updated_user = user_service.update(user_id, user_update_data, db)
            if not updated_user:
                # Raise error to trigger rollback (strict atomicity)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to assign employer to user"
                )
        
        return employer
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error creating employer with address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create employer: {e}")
```

#### Phase 3: Route Updates

**File**: `app/routes/employer.py`

**Function**: `create_employer()`

**Changes**:
```python
@router.post("/", response_model=EmployerResponseSchema, status_code=status.HTTP_201_CREATED)
def create_employer(
    employer_create: EmployerCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new employer with address"""
    def _create_employer_with_address():
        # Determine if we should assign based on user role and request parameter
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
```

**Function**: `add_employer_address()`

**Changes**:
```python
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
        
        # Determine if we should assign employer to user
        role_type = current_user.get("role_type")
        assign_to_user = False
        
        # Only Customers can use assign_employer parameter
        if role_type == "Customer":
            assign_to_user = address_create.assign_employer if address_create.assign_employer is not None else True  # Default True
        # Employees/Suppliers: assign_employer parameter is ignored
        
        # Prepare address data
        address_data = address_create.dict()
        address_data.pop("assign_employer", None)  # Remove from address data
        
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
        
        # Create address with geocoding
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
        
        # NEW: Assign employer to user if requested
        if assign_to_user:
            from app.services.crud_service import user_service
            user_update_data = {
                "employer_id": employer_id,
                "modified_by": current_user["user_id"]
            }
            updated_user = user_service.update(current_user["user_id"], user_update_data, db)
            if not updated_user:
                # Raise error to trigger rollback (strict atomicity)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to assign employer to user"
                )
            log_info(f"Assigned employer {employer_id} to user {current_user['user_id']}")
        
        return new_address
    
    return handle_business_operation(_add_employer_address, "employer address creation")
```

#### Phase 4: Transaction Safety

**Current Implementation Analysis**:
- FastAPI dependency `get_db()` provides database connection
- psycopg2 connections default to `autocommit=False` (transactional mode)
- Each operation (create, update) is automatically part of a transaction
- If any operation fails, the connection will rollback on exception

**Verification Needed**:
- Check `app/dependencies/database.py` to confirm autocommit setting
- If autocommit is False (default), operations are already transactional
- If autocommit is True, we need to wrap in explicit transaction

**Recommended Approach**:
Since `create_employer_with_address()` already creates address + employer atomically, we just need to add the user update within the same function. The existing error handling will ensure rollback if any step fails.

**Transaction Management Analysis**:
- `get_db_connection_context()` in `app/utils/db_pool.py` shows `conn.rollback()` on exception (line 157)
- No explicit `commit()` shown - need to verify if autocommit is enabled
- psycopg2 default is `autocommit=False` (transactional mode)
- If autocommit=False: Operations are transactional, need explicit commit or connection close commits
- If autocommit=True: Each statement commits immediately (not transactional)

**Action Required**: Verify autocommit setting in database connection initialization.

**Implementation** (assuming autocommit=False, which is psycopg2 default):
```python
def create_employer_with_address(...):
    try:
        # All operations use same db connection (transactional if autocommit=False)
        # Create address
        address = address_service.create(address_data, db)
        
        # Create employer
        employer = employer_service.create(employer_data, db)
        
        # Link address to employer
        address_service.update(address.address_id, {"employer_id": employer.employer_id}, db)
        
        # NEW: Auto-assign to user (if requested) - same transaction
        if auto_assign_to_user:
            from app.services.crud_service import user_service
            user_update_data = {
                "employer_id": employer.employer_id,
                "modified_by": user_id
            }
            updated_user = user_service.update(user_id, user_update_data, db)
            if not updated_user:
                # Raise error to trigger rollback
                raise HTTPException(
                    status_code=500,
                    detail="Failed to assign employer to user"
                )
        
        # If we reach here, all operations succeeded
        # Transaction will commit when connection context exits (or explicitly commit)
        return employer
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        # Any other exception will cause rollback (via context manager)
        log_error(f"Error creating employer with address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create employer: {e}")
```

**If autocommit=True is detected**, wrap operations in explicit transaction:
```python
# Save original autocommit setting
original_autocommit = db.autocommit
try:
    db.autocommit = False  # Enable transaction mode
    
    # ... all operations ...
    
    db.commit()  # Explicit commit
    return employer
except Exception as e:
    db.rollback()  # Explicit rollback
    raise
finally:
    db.autocommit = original_autocommit  # Restore original setting
```

#### Phase 5: Testing

**Unit Tests**:
- ✅ Customer creates employer with `assign_employer=true` (default) → employer_id assigned to user
- ✅ Customer creates employer with `assign_employer=false` → employer_id NOT assigned to user
- ✅ Customer adds address to employer with `assign_employer=true` (default) → employer_id assigned to user
- ✅ Customer adds address to employer with `assign_employer=false` → employer_id NOT assigned (opt-out)
- ✅ Employee creates employer with `assign_employer=true` → parameter ignored, employer_id NOT assigned
- ✅ Employee creates employer with `assign_employer=false` → parameter ignored, employer_id NOT assigned
- ✅ Supplier creates employer → `assign_employer` parameter ignored
- ✅ Transaction rollback on failure (address creation fails → no employer, no assignment)
- ✅ Transaction rollback on failure (employer creation fails → no assignment)
- ✅ Transaction rollback on failure (assignment fails → rollback employer and address)

**Integration Tests (Postman)**:
- ✅ Customer workflow: GET employers → none found → POST employer (assign_employer=true) → verify user.employer_id set
- ✅ Customer workflow: GET employers → none found → POST employer (assign_employer=false) → verify user.employer_id NOT set
- ✅ Customer workflow: POST employer/{id}/addresses (assign_employer=true) → verify user.employer_id set
- ✅ Employee workflow: POST employer → verify user.employer_id NOT set (regardless of assign_employer value)

#### Phase 6: Documentation Update

**Update**: `docs/api/client/EMPLOYER_ASSIGNMENT_WORKFLOW.md`

**Add Section**: "Employer Assignment Behavior"

**For Creating Employer (`POST /employers/`)**:
- `assign_employer: bool = true` (default) - Checkbox should be checked by default in UI
- If `true` and user is Customer: Employer is assigned to user atomically
- If `false` and user is Customer: Employer created but not assigned
- If user is Employee/Supplier: `assign_employer` parameter is ignored (always creates without assignment)

**For Adding Address to Employer (`POST /employers/{employer_id}/addresses`)**:
- `assign_employer: bool = true` (default) - Checkbox should be checked by default in UI
- If `true` (default) and user is Customer: Employer is assigned to user when adding address
- If `false` and user is Customer: Address added but employer not assigned (opt-out)
- If user is Employee/Supplier: `assign_employer` parameter is ignored

**UI Recommendations**:
- **Create Employer Form**: Show checkbox "Assign this employer to me" (✅ checked by default)
- **Add Address Form**: Show checkbox "Assign this employer to me" (✅ checked by default)
- **Rationale**: Clients want least steps possible and are adjusting data for themselves
- **Tooltip**: "If checked, this employer will be assigned to your account. Uncheck to add address without assignment."
- **Important**: Always show the checkbox so users are not surprised when change takes effect on their user_info record

---

## Alternative Approaches Considered

### Alternative 1: Query Parameter Approach

**POST /employers/?auto_assign=true**

**Pros**:
- Explicit user control
- Works for any role type
- More flexible

**Cons**:
- Requires client to remember to add parameter
- Less intuitive for customers
- Doesn't solve the "forgot to assign" problem
- Not part of request body (less discoverable)

**Recommendation**: Not recommended - request body parameter is better.

### Alternative 2: Role-Based Auto-Assignment (Original Option 2)

**Behavior**: Automatically assign if Customer, never assign if Employee/Supplier

**Pros**:
- Simple implementation
- Good UX for common case

**Cons**:
- No user control (can't opt-out)
- Doesn't handle edge cases (customer creating for someone else)
- Less flexible

**Recommendation**: Not recommended - explicit parameter is better.

---

## Summary

**Recommended**: **Option 2 (Enhanced) - Explicit `assign_employer` Parameter**

**Key Benefits**:
- ✅ Better UX (default `true` for customers, matches common case)
- ✅ User control (can opt-out if creating for someone else)
- ✅ Explicit intent (UI checkbox makes decision clear)
- ✅ Flexible (works for both creating employer and adding address)
- ✅ Handles edge cases (customer creating employer but not assigning)
- ✅ Still flexible for employees (parameter ignored)

**Implementation Complexity**: Medium
- Add `assign_employer` field to `EmployerCreateSchema` (default `True`)
- Add `assign_employer` field to `AddressCreateSchema` (default `False`)
- Add `assign_to_user` parameter to service method
- Add role check in routes (only Customers can use parameter)
- Ensure transaction safety

**Risk Level**: Low
- Backward compatible (defaults maintain current behavior for employees)
- Explicit parameter (clear intent)
- Easy to test
- UI can show checkbox with appropriate default

**UI Implementation**:
- **Create Employer**: Checkbox "Assign this employer to me" (✅ checked by default)
- **Add Address**: Checkbox "Assign this employer to me" (✅ checked by default)
- **Rationale**: Clients want least steps possible and are adjusting data for themselves
- **Tooltip**: "If checked, this employer will be assigned to your account. Uncheck to add address without assignment."
- **Important**: Always show the checkbox so users are not surprised when change takes effect on their user_info record

