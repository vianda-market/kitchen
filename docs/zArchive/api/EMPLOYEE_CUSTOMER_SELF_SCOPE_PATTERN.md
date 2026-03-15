# Employee Global + Customer Self-Scope Access Pattern

## Overview

This document describes a reusable access control pattern for APIs that should:
- **Employees**: Have global access (can see all records)
- **Customers**: Have self-scoped access (can only see their own records)
- **Suppliers**: Blocked (403 Forbidden)

## Current Implementation Status

**Status**: ✅ **Infrastructure Ready** - Centralized helpers available

**Infrastructure Created:**
- ✅ `get_employee_or_customer_user` dependency in `app/auth/dependencies.py`
- ✅ `EmployeeCustomerAccessControl` helper class in `app/security/access_control.py`

**Current Usage:**
- ⚠️ Subscription routes still use manual implementation (can be refactored)
- ✅ Ready to use for new routes

## Proposed Centralized Solution

### Option 1: Dependency Function (Recommended)

Create a reusable FastAPI dependency that handles the access control logic:

```python
# app/auth/dependencies.py

def get_employee_or_customer_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Verify user is Employee or Customer, blocking Suppliers.
    
    Returns:
        Current user if Employee or Customer
        
    Raises:
        HTTPException(403): If user is Supplier
    """
    role_type = current_user.get("role_type")
    
    if role_type == "Supplier":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Suppliers cannot access this resource"
        )
    
    if role_type not in ["Employee", "Customer"]:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )
    
    return current_user
```

### Option 2: Helper Function for Route Logic

Create a helper function that returns the appropriate scope and user_id filter:

```python
# app/security/scoping.py

def get_employee_customer_scope(
    current_user: dict,
    entity_user_id_column: str = "user_id"
) -> tuple[Optional[InstitutionScope], Optional[UUID], Optional[dict]]:
    """
    Get scope and filters for Employee global + Customer self-scope pattern.
    
    Returns:
        (scope, user_id, error_dict)
        - scope: None for global access, or InstitutionScope for filtering
        - user_id: UUID to filter by (for Customers), None for Employees
        - error_dict: Dict with status_code and detail if access denied, None otherwise
        
    Usage:
        scope, user_id, error = get_employee_customer_scope(current_user)
        if error:
            raise HTTPException(**error)
        
        # Use scope and user_id in query
    """
    role_type = current_user.get("role_type")
    
    if role_type == "Supplier":
        return None, None, {
            "status_code": 403,
            "detail": "Forbidden: Suppliers cannot access this resource"
        }
    
    if role_type == "Customer":
        user_id = current_user.get("user_id")
        if not user_id:
            return None, None, {
                "status_code": 401,
                "detail": "User ID not found in token"
            }
        return None, user_id, None  # No institution scope, filter by user_id
    
    if role_type == "Employee":
        return None, None, None  # Global access, no filtering
    
    return None, None, {
        "status_code": 403,
        "detail": "Access denied"
    }
```

### Option 3: Route Decorator/Helper Class

Create a helper class that wraps route logic:

```python
# app/security/access_control.py

class EmployeeCustomerAccessControl:
    """Helper class for Employee global + Customer self-scope access pattern"""
    
    @staticmethod
    def enforce_access(current_user: dict) -> tuple[Optional[UUID], Optional[dict]]:
        """
        Enforce access control and return user_id filter if needed.
        
        Returns:
            (user_id, error_dict)
            - user_id: UUID to filter by (for Customers), None for Employees
            - error_dict: Dict with status_code and detail if access denied, None otherwise
        """
        role_type = current_user.get("role_type")
        
        if role_type == "Supplier":
            return None, {
                "status_code": 403,
                "detail": "Forbidden: Suppliers cannot access this resource"
            }
        
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                return None, {
                    "status_code": 401,
                    "detail": "User ID not found in token"
                }
            return user_id, None
        
        if role_type == "Employee":
            return None, None  # Global access
        
        return None, {
            "status_code": 403,
            "detail": "Access denied"
        }
    
    @staticmethod
    def verify_ownership(
        record_user_id: UUID,
        current_user: dict
    ) -> Optional[dict]:
        """
        Verify that a record belongs to the current customer user.
        
        Returns:
            error_dict if access denied, None if allowed
        """
        role_type = current_user.get("role_type")
        
        if role_type == "Employee":
            return None  # Employees can access any record
        
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if record_user_id != user_id:
                return {
                    "status_code": 404,
                    "detail": "Resource not found"  # Don't reveal existence
                }
        
        return None
```

## Implementation

**✅ IMPLEMENTED**: **Option 1 (Dependency) + Option 3 (Helper Class)**

1. **Dependency Function**: `get_employee_or_customer_user` in `app/auth/dependencies.py` - blocks Suppliers at route level
2. **Helper Class**: `EmployeeCustomerAccessControl` in `app/security/access_control.py` - provides filtering logic

This provides:
- ✅ Early blocking of Suppliers (via dependency)
- ✅ Reusable filtering logic (via helper class)
- ✅ Consistent error messages
- ✅ Easy to apply to new routes
- ✅ Type-safe UUID handling

## Implementation Status

### ✅ Phase 1: Helper Infrastructure - COMPLETE
1. ✅ Added `get_employee_or_customer_user` dependency to `app/auth/dependencies.py`
2. ✅ Added `EmployeeCustomerAccessControl` class to `app/security/access_control.py`

### 🔄 Phase 2: Refactor Existing Routes - OPTIONAL
1. ⚠️ Subscription routes can be refactored to use the new pattern (currently manual)
2. This is optional - existing implementation works correctly

### ✅ Phase 3: Ready for New Routes - COMPLETE
1. ✅ Infrastructure is ready
2. ✅ See usage example below

## Usage Examples

### Example 1: List Endpoint

```python
from app.auth.dependencies import get_employee_or_customer_user
from app.security.access_control import EmployeeCustomerAccessControl
from app.services.error_handling import handle_business_operation

@router.get("/enriched/", response_model=List[EntityEnrichedResponseSchema])
def list_enriched_entities(
    include_archived: Optional[bool] = False,
    current_user: dict = Depends(get_employee_or_customer_user),  # Blocks Suppliers
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List entities with Employee global + Customer self-scope access"""
    # Get user_id filter (None for Employees, UUID for Customers)
    user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
    if error:
        raise HTTPException(**error)
    
    # Build additional conditions for Customers
    additional_conditions = []
    if user_id:
        additional_conditions.append(("user_id = %s::uuid", str(user_id)))
    
    def _get_entities():
        return entity_service.get_all(
            db,
            scope=None,  # No institution scoping for this pattern
            include_archived=include_archived or False,
            additional_conditions=additional_conditions if additional_conditions else None
        )
    
    return handle_business_operation(_get_entities, "entity list retrieval")
```

### Example 2: Get by ID Endpoint

```python
@router.get("/enriched/{entity_id}", response_model=EntityEnrichedResponseSchema)
def get_enriched_entity_by_id(
    entity_id: UUID,
    include_archived: Optional[bool] = False,
    current_user: dict = Depends(get_employee_or_customer_user),  # Blocks Suppliers
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get single entity with Employee global + Customer self-scope access"""
    def _get_entity():
        entity = entity_service.get_by_id(
            entity_id,
            db,
            scope=None,
            include_archived=include_archived
        )
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        # Verify ownership for Customers
        error = EmployeeCustomerAccessControl.verify_ownership(
            entity.user_id,
            current_user
        )
        if error:
            raise HTTPException(**error)
        
        return entity
    
    return handle_business_operation(_get_entity, "entity retrieval")
```

### Example 3: Using EnrichedService

```python
from app.services.entity_service import get_enriched_entities, get_enriched_entity_by_id

@router.get("/enriched/", response_model=List[EntityEnrichedResponseSchema])
def list_enriched_entities(
    include_archived: Optional[bool] = False,
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List entities with Employee global + Customer self-scope access"""
    user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
    if error:
        raise HTTPException(**error)
    
    def _get_entities():
        return get_enriched_entities(
            db,
            scope=None,  # No institution scoping
            include_archived=include_archived or False,
            user_id=user_id  # Pass user_id for filtering (None for Employees)
        )
    
    return handle_business_operation(_get_entities, "enriched entity list retrieval")
```

## Entities That Should Use This Pattern

Based on business logic, the following entities likely need this pattern:
- ✅ Subscriptions (already implemented)
- 🔄 Payment Methods (user-owned)
- 🔄 Client Bills (user-owned)
- 🔄 Plate Selections (user-owned)
- 🔄 Plate Pickups (user-owned, but may have company matching)
- 🔄 Client Payment Attempts (user-owned)

## Next Steps

1. **Create the helper infrastructure** (Option 1 + Option 3)
2. **Refactor subscription routes** to use the new pattern
3. **Apply to other user-owned entities** as needed
4. **Document in route factory** for future routes

---

*Last Updated: 2025-11-23*

