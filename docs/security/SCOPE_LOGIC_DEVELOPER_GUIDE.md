# Scope Logic Developer Guide

## Overview

This guide provides implementation patterns and best practices for developers implementing scope logic in new routes. It covers how to handle different role types, implement Employee Operator blocking, and use the scoping system correctly.

## Quick Reference: Scope Logic by Role

| Role | Scope | Implementation Pattern |
|------|-------|------------------------|
| **Employee Admin/Super Admin** | Global (`None`) | `scope = None` |
| **Employee Management** | Institution | `scope = EntityScopingService.get_scope_for_entity(...)` |
| **Employee Operator** | Self-only | Block if `user_id != current_user["user_id"]` (403) |
| **Supplier Admin** | Institution | `scope = EntityScopingService.get_scope_for_entity(...)` |
| **Customer** | Self-only | Block if `user_id != current_user["user_id"]` (403) |

## Core Scoping Components

### 1. Entity Scoping Service

**Location**: `app/security/entity_scoping.py`

**Purpose**: Provides entity-specific scope rules based on the current user's role.

**Usage**:
```python
from app.security.entity_scoping import EntityScopingService, ENTITY_USER

scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
```

**Returns**:
- `None` for global scope (Employee Admin/Super Admin)
- `InstitutionScope` for institution-scoped access (Employee Management, Supplier Admin)
- `None` for self-only roles (Employee Operator, Customer) - blocking handled in route

### 2. User Scope

**Location**: `app/security/scoping.py`

**Purpose**: Provides user-level access control (self-only vs. managing others).

**Usage**:
```python
from app.security.scoping import get_user_scope

user_scope = get_user_scope(current_user)
user_scope.enforce_user(user_id)  # Raises 403 if user_id doesn't match
```

**Methods**:
- `enforce_user(user_id)`: Raises 403 if user_id doesn't match current user (for self-only roles)
- `enforce_user_assignment(target_user_id, target_institution_id)`: Validates user_id assignment for admin roles

## Implementation Patterns

### Pattern 1: Routes with Employee Operator Blocking

**Use Case**: Routes that allow managing resources for other users (users, addresses, etc.)

**Example**: `PUT /users/{user_id}`

```python
@router.put("/{user_id}", response_model=UserResponseSchema)
def update(
    user_id: UUID,
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update a user"""
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    
    # Apply user scoping for Customers and Employee Operators (self-only access)
    if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
        user_scope = get_user_scope(current_user)
        user_scope.enforce_user(user_id)  # Raises 403 if not self
        scope = None  # No institution filtering needed for self-only roles
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        # Check if user exists first (without scope), then check access (with scope)
        # This ensures we return 403 for cross-institution access, not 404
        user_exists = user_service.get_by_id(user_id, db, scope=None)
        if not user_exists:
            raise user_not_found()
        
        # Now check if user has access with scope
        if scope and not scope.is_global:
            user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
            if not user_with_scope:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: You do not have access to this user"
                )
    
    existing_user = user_service.get_by_id(user_id, db, scope=scope)
    if not existing_user:
        raise user_not_found()
    
    # ... rest of update logic
```

**Key Points**:
1. Check for self-only roles first (Customer, Employee Operator)
2. Use `enforce_user()` to block cross-user access
3. For admin roles, check existence first (without scope), then check access (with scope)
4. This pattern returns 403 for cross-institution access (not 404)

### Pattern 2: Routes with Institution Scoping Only

**Use Case**: Routes that manage institution-level resources (restaurants, products, plates, etc.)

**Example**: `GET /restaurants/`

```python
@router.get("/", response_model=List[RestaurantResponseSchema])
def get_all_restaurants(
    include_archived: bool = include_archived_query("restaurants"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all restaurants"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
    
    return handle_get_all(
        restaurant_service.get_all,
        db,
        "restaurants",
        include_archived,
        extra_kwargs={"scope": scope}
    )
```

**Key Points**:
1. Use `EntityScopingService.get_scope_for_entity()` for scope determination
2. The service automatically handles:
   - Employee Admin/Super Admin → `None` (global)
   - Employee Management → Institution scope
   - Employee Operator → `None` (blocked in route if needed)
   - Supplier Admin → Institution scope
3. Pass scope to service methods via `extra_kwargs`

### Pattern 3: Address Creation with User Assignment

**Use Case**: Creating addresses where `user_id` can be assigned by admin roles

**Example**: `POST /addresses/`

```python
@router.post("/", response_model=AddressResponseSchema, status_code=status.HTTP_201_CREATED)
def create_address(
    addr_create: AddressCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new address with geocoding for restaurants"""
    user_scope = get_user_scope(current_user)
    addr_data = addr_create.dict()
    
    # Auto-set user_id from current_user for Customers
    if user_scope.is_customer:
        addr_data["user_id"] = current_user["user_id"]
    else:
        # For Suppliers/Employees: Validate that target user_id belongs to their institution
        target_user_id = addr_data.get("user_id")
        if target_user_id:
            target_user = user_service.get_by_id(target_user_id, db, scope=None)
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            user_scope.enforce_user_assignment(target_user_id, target_user.institution_id)
    
    # Use institution scope for Suppliers/Employees
    scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user) if not user_scope.is_customer else None

    def _create_address_with_geocoding():
        return address_business_service.create_address_with_geocoding(addr_data, current_user, db, scope=scope)
    
    return handle_business_operation(
        _create_address_with_geocoding,
        "address creation with geocoding",
        "Address created successfully"
    )
```

**Key Points**:
1. Customers: Auto-set `user_id` from token
2. Admin roles: Validate `user_id` assignment using `enforce_user_assignment()`
3. This method automatically blocks Employee Operators from assigning to others

### Pattern 4: Blocking Employee Operators Explicitly

**Use Case**: Routes where Employee Operators should be completely blocked (not just self-only)

**Example**: Restaurant management endpoints

```python
@router.post("/restaurants/", response_model=RestaurantResponseSchema)
def create_restaurant(
    restaurant_data: RestaurantCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new restaurant"""
    role_type = current_user.get("role_type")
    role_name = current_user.get("role_name")
    
    # Block Employee Operators from managing restaurants
    if role_type == "Employee" and role_name == "Operator":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Employee Operators cannot manage restaurants"
        )
    
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
    
    # ... rest of creation logic
```

**Key Points**:
1. Check role explicitly before proceeding
2. Return clear error message
3. Use 403 Forbidden status code

## Existence vs. Access Control Pattern

### The Problem

When checking if a user can access a resource, we need to distinguish between:
- Resource doesn't exist → 404 Not Found
- Resource exists but is outside scope → 403 Forbidden

### The Solution

**Check existence first (without scope), then check access (with scope)**:

```python
# Step 1: Check if user exists (without scope)
user_exists = user_service.get_by_id(user_id, db, scope=None)
if not user_exists:
    raise user_not_found()  # 404

# Step 2: Check if user has access with scope
if scope and not scope.is_global:
    user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
    if not user_with_scope:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have access to this user"
        )  # 403
```

**Why This Matters**:
- Prevents information disclosure (enumeration attacks)
- Provides accurate error messages
- Follows security best practices

## Testing Scope Logic

### Postman E2E Testing

**Recommended Approach**: Use Postman E2E tests for scope logic validation.

**Why**:
- Tests real HTTP requests with real authentication tokens
- Tests full stack (route → service → database)
- Easy to test all role combinations
- Verifies actual HTTP status codes (403, 404, 200)

**Test Cases to Cover**:
1. Employee Admin can access any user (200)
2. Employee Management can access institution users (200)
3. Employee Management blocked from cross-institution users (403)
4. Employee Operator blocked from accessing other users (403)
5. Employee Operator can use `/me` endpoints (200)
6. Cross-institution access returns 403 (not 404)

### Unit Testing Scope Calculation

**When to Use**: Test scope calculation logic, not HTTP endpoints.

**Example**:
```python
def test_institution_scope_is_global_for_employee_admin():
    current_user = {
        "role_type": "Employee",
        "role_name": "Admin",
        "institution_id": "33333333-3333-3333-3333-333333333333"
    }
    scope = get_institution_scope(current_user)
    assert scope.is_global == True

def test_institution_scope_not_global_for_employee_management():
    current_user = {
        "role_type": "Employee",
        "role_name": "Manager",
        "institution_id": "33333333-3333-3333-3333-333333333333"
    }
    scope = get_institution_scope(current_user)
    assert scope.is_global == False
    assert scope.institution_id == "33333333-3333-3333-3333-333333333333"
```

## Common Pitfalls

### ❌ Pitfall 1: Not Checking Employee Operator

**Bad**:
```python
if role_type == "Customer":
    user_scope.enforce_user(user_id)
else:
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
```

**Good**:
```python
if role_type == "Customer" or (role_type == "Employee" and role_name == "Operator"):
    user_scope.enforce_user(user_id)
else:
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
```

### ❌ Pitfall 2: Returning 404 for Cross-Institution Access

**Bad**:
```python
user = user_service.get_by_id(user_id, db, scope=scope)
if not user:
    raise user_not_found()  # Returns 404 even if user exists but is outside scope
```

**Good**:
```python
# Check existence first
user_exists = user_service.get_by_id(user_id, db, scope=None)
if not user_exists:
    raise user_not_found()  # 404

# Then check access
if scope and not scope.is_global:
    user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
    if not user_with_scope:
        raise HTTPException(status_code=403, detail="Forbidden")  # 403
```

### ❌ Pitfall 3: Not Using `/me` Endpoints

**Bad**: Allowing self-updates via `/{user_id}` endpoints

**Good**: Encourage use of `/me` endpoints for self-updates (more secure, no path parameter manipulation)

## Code Organization

### Where to Put Scope Logic

1. **Route Layer** (`app/routes/*.py`):
   - Determine scope based on current user
   - Block Employee Operators explicitly
   - Check existence vs. access control

2. **Service Layer** (`app/services/*.py`):
   - Use scope for database queries
   - Don't determine scope (that's the route's job)

3. **Entity Scoping Service** (`app/security/entity_scoping.py`):
   - Entity-specific scope rules
   - Returns `InstitutionScope` or `None`

4. **Core Scoping** (`app/security/scoping.py`):
   - Core scope classes (`InstitutionScope`, `UserScope`)
   - Helper functions (`get_institution_scope()`, `get_user_scope()`)

## Related Documentation

- [Role-Based Access Control](../api/ROLE_BASED_ACCESS_CONTROL.md) - API usage guide
- [Scoping System](../api/SCOPING_SYSTEM.md) - Technical details on scoping implementation
- [Scope Logic Implementation](../roadmap/SCOPE_LOGIC_IMPLEMENTATION.md) - Implementation roadmap

