# Scoping and Access Control System

This document provides a comprehensive overview of the centralized scoping and access control system used in the FastAPI application.

## Overview

The scoping system provides a unified approach to restricting data access based on:
- **Institution Scoping**: Restricts access to resources within a user's institution
- **User Scoping**: Restricts access to resources owned by a specific user
- **Access Control Patterns**: Reusable patterns for common access control scenarios

All scope classes follow a consistent pattern with `is_global`, `matches()`, and `enforce()` methods.

## Location

All scoping classes, functions, and access control patterns are centralized in:
- **Primary Module**: `app/security/scoping.py`
- **Entity-Specific Rules**: `app/security/entity_scoping.py`
- **FastAPI Dependencies**: `app/auth/dependencies.py`
- **Backward Compatibility**: `app/security/institution_scope.py` (re-exports for existing imports)

---

## Table of Contents

1. [Core Scoping Classes](#core-scoping-classes)
2. [Access Control Patterns](#access-control-patterns)
3. [Entity-Specific Scoping](#entity-specific-scoping)
4. [FastAPI Dependencies](#fastapi-dependencies)
5. [Usage Examples](#usage-examples)
6. [UI Implementation Guide](#ui-implementation-guide)
7. [Best Practices](#best-practices)
8. [Testing](#testing)

---

## Core Scoping Classes

### 1. InstitutionScope

**Purpose**: Restricts access to resources that belong to institutions (restaurants, products, plates, QR codes, etc.)

**Behavior by Role**:
- **Employees**: Global access (can see all institutions)
- **Suppliers**: Scoped to their `institution_id` only
- **Customers**: Not typically used (customers use UserScope instead)

**Usage Example**:
```python
from app.security.scoping import get_institution_scope

scope = get_institution_scope(current_user)
# scope.is_global → True for Employees, False for Suppliers
# scope.matches(resource_institution_id) → Returns True if access allowed
# scope.enforce(resource_institution_id) → Raises 403 if access denied
```

**Key Methods**:
- `is_global`: Returns `True` if user has global access (Employees only)
- `is_employee`: Returns `True` if user is an Employee
- `matches(resource_institution_id)`: Returns `True` if resource matches scope
- `enforce(resource_institution_id)`: Raises `HTTPException(403)` if resource doesn't match

---

### 2. UserScope

**Purpose**: Restricts access to resources that belong to individual users (user records, addresses, etc.)

**Behavior by Role**:
- **Employees**: Global access (can see all users)
- **Suppliers**: Can access users within their institution (requires database validation)
- **Customers**: Can only access their own `user_id`

**Usage Example**:
```python
from app.security.scoping import get_user_scope

user_scope = get_user_scope(current_user)
# user_scope.is_global → True for Employees, False for others
# user_scope.matches_user(resource_user_id) → Returns True if access allowed
# user_scope.enforce_user(resource_user_id) → Raises 403 if access denied
```

**Key Methods**:
- `is_global`: Returns `True` if user has global access (Employees only)
- `is_customer`: Returns `True` if user is a Customer
- `is_supplier`: Returns `True` if user is a Supplier
- `matches_user(resource_user_id)`: Returns `True` if resource's user_id matches scope
- `enforce_user(resource_user_id)`: Raises `HTTPException(403)` if resource doesn't match
- `can_assign_user_id(target_user_id, target_user_institution_id)`: Returns `True` if user can assign user_id to target
- `enforce_user_assignment(target_user_id, target_user_institution_id)`: Raises `HTTPException(403)` if assignment not allowed

**Special Address Logic**:
- **Customers**: Can only manage addresses where `user_id == their own user_id`
- **Suppliers**: Can manage addresses for any user within their `institution_id`
- **Employees**: Global access

---

## Access Control Patterns

### Employee Global + Customer Self-Scope Pattern

**Purpose**: Pattern for user-owned resources where:
- **Employees**: Have global access (can see all records)
- **Customers**: Have self-scoped access (can only see their own records)
- **Suppliers**: Are blocked (403 Forbidden)

**Implementation**: 
- **Dependency**: `get_employee_or_customer_user()` in `app/auth/dependencies.py` - blocks Suppliers at route level
- **Helper Class**: `EmployeeCustomerAccessControl` in `app/security/scoping.py` - provides filtering logic

**Usage Example**:
```python
from app.auth.dependencies import get_employee_or_customer_user
from app.security.scoping import EmployeeCustomerAccessControl

@router.get("/enriched/", response_model=List[EntityEnrichedResponseSchema])
def list_enriched_entities(
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

**For Single Record Access**:
```python
@router.get("/enriched/{entity_id}", response_model=EntityEnrichedResponseSchema)
def get_enriched_entity_by_id(
    entity_id: UUID,
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get single entity with Employee global + Customer self-scope access"""
    def _get_entity():
        entity = entity_service.get_by_id(entity_id, db, scope=None, include_archived=include_archived)
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

**Entities That Should Use This Pattern**:
- ✅ Subscriptions
- 🔄 Payment Methods (user-owned)
- 🔄 Client Bills (user-owned)
- 🔄 Plate Selections (user-owned)
- 🔄 Plate Pickups (user-owned, but may have company matching)
- 🔄 Client Payment Attempts (user-owned)

---

## Entity-Specific Scoping

### EntityScopingService

**Purpose**: Centralized service for determining entity-specific scoping rules.

**Location**: `app/security/entity_scoping.py`

**Usage**:
```python
from app.security.entity_scoping import EntityScopingService, ENTITY_SUBSCRIPTION

scope = EntityScopingService.get_scope_for_entity(ENTITY_SUBSCRIPTION, current_user)
```

**Entity Types**:
- `ENTITY_PLATE_KITCHEN_DAYS`
- `ENTITY_RESTAURANT_BALANCE`
- `ENTITY_RESTAURANT_TRANSACTION`
- `ENTITY_PLATE_PICKUP_LIVE`
- `ENTITY_QR_CODE`
- `ENTITY_RESTAURANT`
- `ENTITY_PLATE`
- `ENTITY_PRODUCT`
- `ENTITY_INSTITUTION_ENTITY`
- `ENTITY_INSTITUTION_BANK_ACCOUNT`
- `ENTITY_INSTITUTION_BILL`
- `ENTITY_INSTITUTION_PAYMENT_ATTEMPT`
- `ENTITY_USER`
- `ENTITY_ADDRESS`
- `ENTITY_SUBSCRIPTION`
- `ENTITY_RESTAURANT_HOLIDAY`

Each entity type can have custom scoping rules defined in `EntityScopingService._SCOPING_RULES`.

---

## FastAPI Dependencies

### Authentication Dependencies

**Location**: `app/auth/dependencies.py`

#### `get_current_user()`
Base authentication dependency. Returns the authenticated user from JWT token.

#### `get_employee_user()`
Verifies user has `role_type='Employee'` for system configuration access.

#### `get_client_user()`
Verifies user has `role_type='Customer'` for client-only operations.

#### `get_client_or_employee_user()`
Verifies user has `role_type` in `['Customer', 'Employee']`. Used for resources that both Customers and Employees need to access, but Suppliers should not (e.g., Plans).

#### `get_employee_or_customer_user()`
Verifies user is Employee or Customer, explicitly blocking Suppliers. Used for the "Employee global + Customer self-scope" pattern.

#### `get_super_admin_user()`
Verifies user has `role_type='Employee'` AND `role_name='Super Admin'` for super-admin operations.

#### `get_admin_user()`
Verifies user has `role_type='Employee'` AND `role_name` in `['Admin', 'Super Admin']` for admin operations.

---

## Usage Examples

### Example 1: Institution-Scoped Resource (Restaurants)

```python
from app.security.scoping import get_institution_scope
from app.security.entity_scoping import EntityScopingService, ENTITY_RESTAURANT

@router.get("/", response_model=List[RestaurantResponseSchema])
def list_restaurants(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List restaurants with institution scoping"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)
    
    def _get_restaurants():
        return restaurant_service.get_all(db, scope=scope, include_archived=False)
    
    return handle_business_operation(_get_restaurants, "restaurant list retrieval")
```

### Example 2: User-Scoped Resource (Addresses)

```python
from app.security.scoping import get_user_scope

@router.get("/", response_model=List[AddressResponseSchema])
def list_addresses(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List addresses with user scoping"""
    if current_user.get("role_type") == "Customer":
        user_scope = get_user_scope(current_user)
        # Customers can only see their own addresses
        def _get_addresses():
            return address_service.get_all(
                db,
                scope=None,
                additional_conditions=[("user_id = %s::uuid", str(user_scope.user_id))]
            )
    else:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_ADDRESS, current_user)
        def _get_addresses():
            return address_service.get_all(db, scope=scope)
    
    return handle_business_operation(_get_addresses, "address list retrieval")
```

### Example 3: Employee/Customer Pattern (Subscriptions)

```python
from app.auth.dependencies import get_employee_or_customer_user
from app.security.scoping import EmployeeCustomerAccessControl

@router.get("/enriched/", response_model=List[SubscriptionEnrichedResponseSchema])
def list_enriched_subscriptions(
    current_user: dict = Depends(get_employee_or_customer_user),  # Blocks Suppliers
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List subscriptions with Employee global + Customer self-scope"""
    user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
    if error:
        raise HTTPException(**error)
    
    def _get_subscriptions():
        return get_enriched_subscriptions(
            db,
            scope=None,
            include_archived=False,
            user_id=user_id  # None for Employees, UUID for Customers
        )
    
    return handle_business_operation(_get_subscriptions, "subscription list retrieval")
```

---

## UI Implementation Guide

### Key Principle

**Backend enforces scoping → UI receives pre-filtered data → No client-side filtering needed**

If a user tries to access data outside their scope, the backend will return a `403 Forbidden` error.

### Role Types

- **Employee**: Global access (can see all data across all institutions)
- **Supplier**: Institution-scoped (can only see data from their institution)
- **Customer**: User-scoped (can only see their own data)

### Scoping Behavior by Resource Type

#### Institution-Scoped Resources

**Behavior**: Suppliers see only their institution's data, Employees see all.

**Resources**:
- Restaurants
- Products
- Plates (for Suppliers - see special case below)
- QR Codes
- Institution Entities
- Institution Bank Accounts
- Institution Bills
- Institution Payment Attempts
- Restaurant Balance Info

**Example**:
- A Supplier from "Acme Restaurant" can only see restaurants, products, and plates from "Acme Restaurant"
- An Employee can see restaurants, products, and plates from all institutions

#### User-Scoped Resources

**Behavior**: Customers see only their own data, Suppliers see their institution's users, Employees see all.

**Resources**:
- Users
- Addresses

**Example**:
- A Customer can only see their own user record and their own addresses
- A Supplier can see all users and addresses within their institution
- An Employee can see all users and addresses across all institutions

#### Employee/Customer Pattern Resources

**Behavior**: Employees see all, Customers see only their own, Suppliers are blocked.

**Resources**:
- Subscriptions
- Payment Methods
- Client Bills
- Plate Selections
- Plate Pickups
- Client Payment Attempts

**Example**:
- A Customer can only see their own subscriptions
- An Employee can see all subscriptions
- A Supplier cannot access subscriptions (403 Forbidden)

### Special Cases

#### Plates API

**Behavior**: 
- **Customers**: Can GET all plates (no scoping) to browse available meals, but cannot create/modify them
- **Suppliers**: Can only see plates from their institution's restaurants
- **Employees**: Can see all plates

**Why**: Customers need to browse all available meals to make selections, but they cannot create or modify plates.

#### Addresses API

**Behavior**:
- **Customers**: 
  - `user_id` is automatically set from their own `user_id` on creation (cannot be changed)
  - Can only GET/PUT/DELETE addresses where `user_id` matches their own
- **Suppliers**: 
  - Can assign `user_id` to any user within their institution
  - Can manage addresses for any user within their institution
- **Employees**: 
  - Can assign `user_id` to any user
  - Can manage addresses for any user

#### Users API

**Behavior**:
- **Customers**: 
  - Can GET/PUT/DELETE their own user record only
  - Cannot POST (create users) - returns 403
- **Suppliers**: 
  - Can manage users within their institution
  - Cannot create users outside their institution
- **Employees**: 
  - Global access (can manage all users)

### What the UI Should Do

#### ✅ DO

1. **Trust the backend**: Backend already filters data based on user's role
2. **Handle 403 errors gracefully**: Show user-friendly messages when access is denied
3. **Use appropriate endpoints**: Use enriched endpoints when you need related entity names
4. **Omit `include_archived`**: Let backend exclude archived records by default
5. **Auto-set fields for Customers**: Don't send `user_id` when creating addresses as a Customer (backend sets it automatically)

#### ❌ DON'T

1. **Don't filter client-side**: Backend already filters - filtering again is redundant and can cause issues
2. **Don't try to access out-of-scope data**: The backend will return 403
3. **Don't send `user_id` for Customers**: When creating addresses as a Customer, let the backend set it automatically
4. **Don't assume all data is available**: Check permissions first (see `API_PERMISSIONS_BY_ROLE.md`)

### Error Handling

#### 403 Forbidden

**When it occurs**:
- User tries to access data outside their scope
- User tries to perform an operation not allowed for their role

**What to do**:
```typescript
if (response.status === 403) {
  // Show user-friendly message
  showError("You don't have permission to access this resource");
  // Optionally redirect or hide UI elements
}
```

**Example scenarios**:
- Customer trying to access another user's record
- Supplier trying to create a new institution
- Customer trying to create a user
- Supplier trying to access another institution's data

#### 401 Unauthorized

**When it occurs**:
- Missing or invalid authentication token
- Token expired

**What to do**:
```typescript
if (response.status === 401) {
  // Redirect to login
  redirectToLogin();
}
```

### Implementation Examples

#### Example 1: Users List Page

```typescript
// ✅ GOOD: Backend handles scoping automatically
const fetchUsers = async () => {
  const response = await fetch('/users/enriched/', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.status === 403) {
    throw new Error('Access denied');
  }
  
  const users = await response.json();
  // Users are already filtered by backend:
  // - Customers: Only their own user
  // - Suppliers: Users from their institution
  // - Employees: All users
  
  return users;
};
```

#### Example 2: Address Creation (Customer)

```typescript
// ✅ GOOD: Don't send user_id - backend sets it automatically
const createAddress = async (addressData) => {
  // Remove user_id if present (for Customers)
  const { user_id, ...data } = addressData;
  
  const response = await fetch('/addresses/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)  // user_id not included
  });
  
  return response.json();
};
```

---

## Best Practices

1. **Always use scoping for data access**: Don't bypass scoping unless absolutely necessary
2. **Use appropriate scope type**: Use `InstitutionScope` for institution-scoped resources, `UserScope` for user-scoped resources, `EmployeeCustomerAccessControl` for Employee/Customer pattern
3. **Validate early**: Use `enforce()` methods at the route level before database queries
4. **Auto-set fields for Customers**: For Customers, automatically set `user_id` from `current_user` rather than requiring it in the request
5. **Document scope behavior**: Add comments explaining scoping logic in route handlers
6. **Use FastAPI dependencies**: Leverage dependency injection for access control (e.g., `get_employee_or_customer_user`)
7. **Centralize scoping logic**: Use `EntityScopingService` for entity-specific rules

---

## Testing

When testing scoped endpoints:

1. **Test Customer restrictions**: Verify Customers can only access their own records
2. **Test Supplier restrictions**: Verify Suppliers can only access resources within their institution
3. **Test Employee global access**: Verify Employees can access all resources
4. **Test assignment validation**: For addresses, verify Suppliers can assign to users in their institution but not outside
5. **Test Employee/Customer pattern**: Verify Suppliers are blocked, Customers see only their own, Employees see all
6. **Test error handling**: Verify 403 errors are returned appropriately

---

## Related Documentation

- **API Permissions**: See `API_PERMISSIONS_BY_ROLE.md` for detailed permission matrices
- **Enriched Endpoints**: See `ENRICHED_ENDPOINT_PATTERN.md` for using enriched endpoints
- **Archived Records**: See `ARCHIVED_RECORDS_PATTERN.md` for handling archived records

---

*Last Updated: 2025-11-23*
