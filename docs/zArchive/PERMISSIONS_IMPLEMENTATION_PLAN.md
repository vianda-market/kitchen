# Permissions Implementation Plan

This document outlines the implementation plan for the permission changes discussed for Users, Plates, Addresses, and Institutions APIs.

## Summary of Required Changes

### 1. Users API (`/users/`)
**Current State**: Customers cannot access user management API
**Target State**: Customers can GET, PUT, DELETE their own user record only

**Implementation Approach**:
- Add user scoping logic for Customers (similar to how institution scoping works for Suppliers)
- Customers can only access records where `user_id == current_user["user_id"]`
- Employees and Suppliers continue using institution scoping
- POST (create) remains restricted to Employees and Suppliers

**Files to Modify**:
- `app/routes/user.py` - Add user scoping checks for Customers
- `app/services/crud_service.py` - May need to add user scoping support (or handle in route layer)
- `app/security/institution_scope.py` - Consider adding `UserScope` class or extend existing scoping

---

### 2. Plates API (`/plates/`)
**Current State**: Customers cannot GET plates
**Target State**: Customers can GET all plates (no scoping) to browse available meals

**Implementation Approach**:
- Override GET endpoints in `create_plate_routes()` to use `get_client_or_employee_user()` instead of `get_current_user()`
- No scoping needed for Customers (they can see all available plates)
- POST/PUT/DELETE remain restricted to Suppliers and Employees with institution scoping

**Files to Modify**:
- `app/services/route_factory.py` - `create_plate_routes()` function

---

### 3. Addresses API (`/addresses/`)
**Current State**: Customers cannot access address management API
**Target State**: Customers can GET, POST, PUT, DELETE their own addresses only

**Implementation Approach**:
- Add user scoping logic for Customers (similar to Users API)
- Customers can only access addresses where `user_id == current_user["user_id"]`
- Employees and Suppliers continue using institution scoping

**Files to Modify**:
- `app/routes/address.py` - Add user scoping checks for Customers
- May need to extend scoping mechanism similar to Users API

---

### 4. Institutions API (`/institutions/`)
**Current State**: Suppliers can GET, POST, PUT, DELETE (with institution scoping)
**Target State**: Suppliers can GET, PUT, DELETE their own institution, but POST is Employee-only

**Implementation Approach**:
- Override POST endpoint in `create_institution_routes()` to use `get_employee_user()` instead of `get_current_user()`
- GET/PUT/DELETE continue using `get_current_user()` with institution scoping (Suppliers can only access their own institution)

**Files to Modify**:
- `app/services/route_factory.py` - `create_institution_routes()` function

---

## Implementation Strategy

### Phase 1: User Scoping Infrastructure (Users & Addresses)

**Option A: Extend InstitutionScope**
- Add `user_id` and `user_scoped` properties to `InstitutionScope`
- Modify scoping logic to check both institution and user scoping
- Pros: Reuses existing infrastructure
- Cons: Mixes concerns (institution + user scoping)

**Option B: Create UserScope Class**
- Create a new `UserScope` dataclass similar to `InstitutionScope`
- Create `get_user_scope(current_user)` function
- Modify routes to use appropriate scope based on role_type
- Pros: Clean separation of concerns
- Cons: More code duplication

**Option C: Route-Level Validation**
- Keep existing scoping as-is
- Add explicit checks in route handlers for Customers
- For Customers: Verify `user_id == current_user["user_id"]` before allowing access
- Pros: Simple, no infrastructure changes
- Cons: More repetitive code in routes

**Recommended**: Option C for MVP (simplest), Option B for long-term (cleanest)

---

### Phase 2: Plates API (Simple - Just Change Dependency)

1. Modify `create_plate_routes()` in `route_factory.py`
2. Override GET endpoints to use `get_client_or_employee_user()`
3. No scoping changes needed (Customers see all plates)

---

### Phase 3: Institutions API (Override POST)

1. Modify `create_institution_routes()` in `route_factory.py`
2. Override POST endpoint to use `get_employee_user()`
3. Keep GET/PUT/DELETE as-is (institution scoping already handles Suppliers correctly)

---

## Detailed Implementation Steps

### Step 1: Plates API (Easiest - Start Here)

```python
# In app/services/route_factory.py, create_plate_routes()
@router.get("/", response_model=List[PlateResponseSchema])
def get_all_plates(
    include_archived: bool = Query(False, ...),
    current_user: dict = Depends(get_client_or_employee_user),  # Changed
    db: psycopg2.extensions.connection = Depends(get_db)
):
    # ... existing logic
```

### Step 2: Institutions API (Override POST)

```python
# In app/services/route_factory.py, create_institution_routes()
@router.post("/", response_model=InstitutionResponseSchema, status_code=201)
def create_institution(
    create_data: InstitutionCreateSchema,
    current_user: dict = Depends(get_employee_user),  # Changed
    db: psycopg2.extensions.connection = Depends(get_db)
):
    # ... existing logic
```

### Step 3: Users API (User Scoping for Customers)

```python
# In app/routes/user.py
@router.get("/{user_id}", response_model=UserResponseSchema)
def get_user_by_id(
    user_id: UUID,
    include_archived: bool = include_archived_query("users"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    # Add user scoping check for Customers
    if current_user.get("role_type") == "Customer":
        if str(user_id) != str(current_user["user_id"]):
            raise HTTPException(status_code=403, detail="Customers can only access their own user record")
    
    scope = get_institution_scope(current_user)
    # ... rest of existing logic
```

### Step 4: Addresses API (User Scoping for Customers)

Similar approach to Users API - add user scoping checks for Customers in route handlers.

---

## Testing Requirements

1. **Users API**:
   - Customer can GET their own user → ✅ 200
   - Customer tries to GET another user → ❌ 403
   - Customer can PUT their own user → ✅ 200
   - Customer tries to PUT another user → ❌ 403
   - Customer tries to POST → ❌ 403 (or appropriate error)

2. **Plates API**:
   - Customer can GET all plates → ✅ 200
   - Customer tries to POST plate → ❌ 403
   - Supplier can GET plates in their institution → ✅ 200

3. **Addresses API**:
   - Customer can GET their own addresses → ✅ 200
   - Customer tries to GET another user's address → ❌ 403
   - Customer can POST address with their user_id → ✅ 201
   - Customer tries to POST address with different user_id → ❌ 403

4. **Institutions API**:
   - Supplier can GET their own institution → ✅ 200
   - Supplier tries to POST new institution → ❌ 403
   - Supplier can PUT their own institution → ✅ 200
   - Employee can POST new institution → ✅ 201

---

## Questions for Discussion

1. **User Scoping Implementation**: Which approach (A, B, or C) do you prefer?
2. **Address Creation**: Should Customers be able to specify `user_id` in the request, or should it be automatically set from `current_user["user_id"]`?
3. **User POST**: Should Customers be able to create other users (probably not), or is POST restricted to Employees/Suppliers only?
4. **Address POST**: Similar question - should `user_id` be auto-set from current_user for Customers?

---

*Created: 2025-11-17*

