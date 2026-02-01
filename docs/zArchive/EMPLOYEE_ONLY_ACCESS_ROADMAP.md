# Employee-Only Access Control - Implementation Roadmap

## Executive Summary

This roadmap outlines the implementation plan for restricting low-level configuration APIs to **Vianda Enterprises employees only**. This adds a new permission layer on top of the existing institution scoping model.

**Primary File for Permission Enhancement**: `app/auth/dependencies.py`
- This file will be enhanced with a new `get_employee_user()` dependency function
- This follows the same pattern as existing `get_super_admin_user()` and `get_admin_user()` functions

**Secondary File (Optional Enhancement)**: `app/security/institution_scope.py`
- May add `is_employee` property to `InstitutionScope` for convenience
- Not required for core functionality

## Overview

This document outlines the implementation plan for restricting certain low-level configuration APIs to **Vianda Enterprises employees only**. This is an enhancement to the existing institution scoping model, adding a new permission layer for system-level configuration management.

## Problem Statement

The permission model uses a two-tier hierarchy:

1. **Role Type** (`role_type`): Determines institutional affiliation
   - **Employee**: Belongs to Vianda Enterprises, has global access (can see all institutions)
   - **Supplier**: Belongs to a restaurant/institution, scoped to their `institution_id`
   - **Customer**: End users (iOS/Android apps only, no backoffice access)

2. **Role Name** (`name` in `role_info`): Determines specific permissions within a role type
   - **Super Admin**: `role_type='Employee'`, `name='Super Admin'` (can approve discretionary credits)
   - **Admin**: `role_type='Employee'`, `name='Admin'` (can request discretionary credits)
   - **Admin**: `role_type='Supplier'`, `name='Admin'` (can manage supplier information)

**Important**: Super Admin is NOT a separate role type. Super Admin users have `role_type='Employee'` and `name='Super Admin'`.

Some APIs represent **low-level system configuration** that should only be accessible to **Vianda Enterprises employees** (`role_type='Employee'`), regardless of their role name (Super Admin, Admin, etc.), as these settings affect the entire platform.

## Current State Analysis

### Role Types
- **Employee**: Vianda Enterprises staff (should have access to system config)
  - Includes: Super Admin (role_name='Super Admin'), Admin (role_name='Admin'), etc.
- **Supplier**: Restaurant/institution administrators (should NOT have access to system config)
- **Customer**: End users, iOS/Android apps only (should NOT have access to system config)

### Current Permission Infrastructure

1. **`app/security/institution_scope.py`**
   - `InstitutionScope` dataclass with `is_global` property
   - `is_global` returns `True` for `role_type == "Employee"` (includes Super Admins)
   - **Current Issue**: Checks for `{"Employee", "Super Admin"}` but should only check `{"Employee"}`
   - Used for institution-based filtering

2. **`app/auth/dependencies.py`**
   - `get_current_user()`: Base authentication dependency (returns `user_id`, `role_type`, `institution_id`, `role_name`)
   - **Current Issue**: `get_current_user()` doesn't return `role_name` (needs fix)
   - `get_super_admin_user()`: **Current Issue**: Checks `role_type != "Super Admin"` but should check `role_type == "Employee" AND role_name == "Super Admin"`
   - `get_admin_user()`: Allows "Admin", "Super Admin", "Employee", "Supplier" (needs review)

3. **Route Factory Pattern** (`app/services/route_factory.py`)
   - Generic CRUD route generation
   - Currently no role-based restrictions at factory level

## Requirements

### APIs Requiring Employee-Only Access

1. **Plan Info** (`/plans/*`)
   - All operations (GET, POST, PUT, DELETE)
   - Employee-only

2. **Credit Currency** (`/credit-currencies/*`)
   - All operations (GET, POST, PUT, DELETE)
   - Employee-only

3. **Discretionary** (`/admin/discretionary/*`)
   - All operations (GET, POST, PUT, DELETE)
   - Employee-only
   - Note: Super Admin routes (`/super-admin/discretionary/*`) remain separate for approval/rejection
   - Current state: Uses `get_admin_user()` which allows "Admin", "Super Admin", "Employee", "Supplier"
   - Target state: Change to `get_employee_user()` for Employee-only access

4. **Fintech Link** (`/fintech-link/*`)
   - **GET operations**: Available to all authenticated users (customers can view links)
   - **POST, PUT, DELETE operations**: Employee-only
   - Special case: Mixed access model

## Proposed Solution Architecture

### 1. New Dependency Function

**File**: `app/auth/dependencies.py`

Add a new dependency function `get_employee_user()` that:
- Verifies `role_type == "Employee"`
- Raises `HTTPException(403)` if not Employee
- Returns the authenticated user dict

```python
def get_employee_user(current_user: dict = Depends(get_current_user)):
    """
    Verify user has Employee role for system configuration access.
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current user if Employee
        
    Raises:
        HTTPException: If user is not Employee
    """
    if current_user.get("role_type") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Employee access required for system configuration operations"
        )
    return current_user
```

### 2. Enhanced InstitutionScope (Optional Enhancement)

**File**: `app/security/institution_scope.py`

Add a new property to `InstitutionScope` for clarity:

```python
@property
def is_employee(self) -> bool:
    """Check if user is specifically an Employee (not Super Admin)"""
    return self.role_type == "Employee"
```

This provides a clean way to check Employee status in business logic, though the dependency function is the primary enforcement mechanism.

### 3. Route Updates

#### Plan Routes
**File**: `app/services/route_factory.py` → `create_plan_routes()`

- Add `get_employee_user` dependency to all route handlers (GET, POST, PUT, DELETE)
- Update enriched endpoints to also require Employee access

#### Credit Currency Routes
**File**: `app/services/route_factory.py` → `create_credit_currency_routes()`

- Add `get_employee_user` dependency to all route handlers (GET, POST, PUT, DELETE)

#### Discretionary Routes
**File**: `app/routes/admin/discretionary.py` (if exists) or create new routes

- Add `get_employee_user` dependency to all route handlers
- Note: Super Admin routes (`/super-admin/discretionary/*`) remain separate and unchanged

#### Fintech Link Routes
**File**: `app/routes/payment_methods/fintech_link.py`

- **GET endpoints**: Keep `get_current_user` (all authenticated users)
- **POST, PUT, DELETE endpoints**: Change to `get_employee_user`
- **Enriched GET endpoints**: Keep `get_current_user` (all authenticated users)

## Implementation Plan

### Phase 0: Fix Permission Model Implementation (CRITICAL)

**IMPORTANT**: Before implementing employee-only access, we must fix the existing permission model to match the correct role structure:

1. **Update Seed Data** (`app/db/seed.sql`)
   - Change Super Admin: `role_type='Super Admin'` → `role_type='Employee'`, keep `name='Super Admin'`
   - Super Admin should be: `('dddddddd-dddd-dddd-dddd-dddddddddddd', 'Employee', 'Super Admin', ...)`

2. **Fix `get_current_user()`** (`app/auth/dependencies.py`)
   - Add `role_name` extraction from JWT payload
   - Return `role_name` in the user dict: `{"user_id": ..., "role_type": ..., "role_name": ..., "institution_id": ...}`

3. **Fix `get_super_admin_user()`** (`app/auth/dependencies.py`)
   - Change from: `if current_user.get("role_type") != "Super Admin"`
   - To: `if current_user.get("role_type") != "Employee" or current_user.get("role_name") != "Super Admin"`
   - Super Admin requires BOTH: `role_type == "Employee" AND role_name == "Super Admin"`

4. **Fix `InstitutionScope.is_global`** (`app/security/institution_scope.py`)
   - Remove `"Super Admin"` from the check
   - Change from: `return self.role_type in {"Employee", "Super Admin"}`
   - To: `return self.role_type == "Employee"` (Super Admin is already an Employee)

5. **Update Tests**
   - Fix test mocks that use `role_type="Super Admin"` → use `role_type="Employee", role_name="Super Admin"`

### Phase 1: Core Infrastructure

1. **Add Employee Dependency** (`app/auth/dependencies.py`)
   - Add `get_employee_user()` function
   - Check: `if current_user.get("role_type") != "Employee"`
   - Add appropriate error messages
   - Follow same pattern as `get_super_admin_user()`

2. **Enhance InstitutionScope** (Optional) (`app/security/institution_scope.py`)
   - Add `is_employee` property for convenience
   - Update docstrings

### Phase 2: Route Protection

3. **Plan Routes** (`app/services/route_factory.py`)
   - Update `create_plan_routes()` to inject `get_employee_user` dependency
   - Apply to all CRUD operations
   - Apply to enriched endpoints

4. **Credit Currency Routes** (`app/services/route_factory.py`)
   - Update `create_credit_currency_routes()` to inject `get_employee_user` dependency
   - Apply to all CRUD operations

5. **Discretionary Routes** (`app/routes/admin/discretionary.py`)
   - Update all routes to use `get_employee_user` instead of `get_admin_user`
   - Routes affected:
     - `POST /admin/discretionary/requests/` (create)
     - `GET /admin/discretionary/requests/` (list)
     - `GET /admin/discretionary/requests/{request_id}` (get by ID)
     - `PUT /admin/discretionary/requests/{request_id}` (update)
   - Leave super-admin routes (`/super-admin/discretionary/*`) unchanged

6. **Fintech Link Routes** (`app/routes/payment_methods/fintech_link.py`)
   - Update POST, PUT, DELETE to use `get_employee_user`
   - Keep GET endpoints with `get_current_user`
   - Keep enriched GET endpoints with `get_current_user`

### Phase 3: Testing & Validation ✅ COMPLETED

7. **Unit Tests** ✅
   - ✅ Created `app/tests/auth/test_auth_dependencies.py`
   - ✅ Test `get_employee_user()` with different role types
   - ✅ Test `get_super_admin_user()`, `get_admin_user()`, `get_client_user()`, `get_client_or_employee_user()`
   - ✅ Verify 403 errors for non-Employee roles
   - ✅ All 20 tests passing

8. **Integration Tests**
   - ✅ Postman collection created for route-level testing
   - ✅ Tests cover Employee, Super Admin, Supplier, Customer roles
   - ✅ Tests cover Plan, Credit Currency, Discretionary, Fintech Link APIs
   - ✅ Positive and negative test cases included

9. **Postman Collection** ✅
   - ✅ Created `docs/postman/Permissions Testing - Employee-Only Access.postman_collection.json`
   - ✅ Created `docs/postman/PERMISSIONS_TESTING_GUIDE.md`
   - ✅ Test collections use correct credentials for each role type
   - ✅ Negative test cases verify 403 errors for unauthorized access

## Files to Modify

### Phase 0: Fix Permission Model (CRITICAL - Must be done first)

1. **`app/db/seed.sql`**
   - Fix Super Admin seed data: `role_type='Employee'`, `name='Super Admin'`

2. **`app/auth/dependencies.py`**
   - Fix `get_current_user()` to return `role_name`
   - Fix `get_super_admin_user()` to check both `role_type == "Employee" AND role_name == "Super Admin"`

3. **`app/security/institution_scope.py`**
   - Fix `is_global` to only check `role_type == "Employee"` (remove "Super Admin")

4. **Test Files** (`app/tests/...`)
   - Update any mocks that use `role_type="Super Admin"`

### Core Files
1. **`app/auth/dependencies.py`**
   - Add `get_employee_user()` function (after Phase 0 fixes)

2. **`app/security/institution_scope.py`** (Optional)
   - Add `is_employee` property to `InstitutionScope`

### Route Files
3. **`app/services/route_factory.py`**
   - Update `create_plan_routes()` function
   - Update `create_credit_currency_routes()` function

4. **`app/routes/payment_methods/fintech_link.py`**
   - Update POST, PUT, DELETE endpoints
   - Keep GET endpoints unchanged

5. **`app/routes/admin/discretionary.py`**
   - Replace `get_admin_user` with `get_employee_user` in all route handlers

### Documentation
6. **`docs/api/EMPLOYEE_ONLY_ACCESS_ROADMAP.md`** (this file)
   - Implementation guide

7. **`docs/CLAUDE.md`** (if needed)
   - Document the new permission pattern

## Design Decisions

### Why Not Use `get_admin_user()`?
The existing `get_admin_user()` allows "Admin", "Super Admin", "Employee", and "Supplier" role types. For system configuration, we need **strictly Employee-only** access (`role_type == "Employee"`), as these settings affect the entire platform and should not be accessible to Suppliers (who have `role_type == "Supplier"`).

Note: Super Admin is already an Employee (`role_type == "Employee"`, `role_name == "Super Admin"`), so they will have access via `get_employee_user()`.

### Why Separate from Institution Scoping?
- **Institution scoping** controls **what data** a user can see (based on institution_id)
- **Employee-only access** controls **which APIs** a user can access (based on role_type)
- These are orthogonal concerns that can be combined:
  - Employee users have global institution scope AND can access system config APIs
  - Supplier users have institution-scoped data access BUT cannot access system config APIs

### Fintech Link Special Case
Fintech links need to be **viewable by customers** (for payment flows) but **manageable only by employees**. This is a legitimate use case for mixed access control:
- GET: All authenticated users (customers need to see payment links)
- POST/PUT/DELETE: Employee only (configuration management)

## Error Messages

Standardize error messages for consistency:

```python
"Employee access required for system configuration operations"
"Employee access required for plan management"
"Employee access required for credit currency management"
"Employee access required for discretionary credit management"
"Employee access required for fintech link management"
```

## Future Considerations

This pattern can be extended for other permission requirements:

1. **Super Admin Only**: Already exists (`get_super_admin_user`)
2. **Employee Only**: This implementation
3. **Supplier Only**: Could add `get_supplier_user()` if needed
4. **Customer Only**: Could add `get_customer_user()` if needed
5. **Combined Roles**: Could create `get_employee_or_super_admin_user()` if needed

The dependency injection pattern makes it easy to add new permission checks without modifying route logic.

## Testing Checklist

- [ ] Employee can access Plan APIs
- [ ] Super Admin cannot access Plan APIs (403)
- [ ] Supplier cannot access Plan APIs (403)
- [ ] Customer cannot access Plan APIs (403)
- [ ] Employee can access Credit Currency APIs
- [ ] Non-Employee cannot access Credit Currency APIs (403)
- [ ] Employee can access Discretionary APIs
- [ ] Non-Employee cannot access Discretionary APIs (403)
- [ ] All authenticated users can GET Fintech Links
- [ ] Only Employee can POST/PUT/DELETE Fintech Links
- [ ] All authenticated users can GET Enriched Fintech Links
- [ ] Error messages are clear and consistent

## Rollout Strategy

1. **Development**: Implement in feature branch
2. **Testing**: Comprehensive test suite (unit + integration)
3. **Documentation**: Update API docs and Postman collections
4. **Staging**: Deploy to staging environment
5. **Production**: Deploy with monitoring for 403 errors

## Additional Areas to Revisit

Based on the corrected permission model understanding, the following areas should be reviewed:

1. **Seed Data** (`app/db/seed.sql`)
   - Super Admin must have `role_type='Employee'`, not `role_type='Super Admin'`

2. **Authentication Token Creation** (`app/auth/routes.py`)
   - Already includes `role_name` in JWT payload ✓
   - Ensure seed users have correct role assignments

3. **Super Admin User Creation**
   - When creating Super Admin users, ensure they have:
     - `role_id` pointing to the role with `role_type='Employee'` and `name='Super Admin'`
     - Correct `institution_id` (Vianda Enterprises institution)

4. **Institution Scoping Logic** (`app/security/institution_scope.py`)
   - Remove "Super Admin" from `is_global` check (Super Admin is an Employee)

5. **Test Mocks** (`app/tests/...`)
   - Update any test fixtures that mock `role_type="Super Admin"`
   - Use `role_type="Employee", role_name="Super Admin"` instead

6. **ABAC Policies** (`app/config/abac_policies.yaml`)
   - Review and update if they reference "Super Admin" as a role type

## Notes

- **CRITICAL**: Phase 0 fixes must be completed before implementing employee-only access
- This enhancement does NOT affect existing institution scoping logic (only corrects it)
- Super Admin routes remain unchanged (separate concern, but use correct permission checks)
- The pattern is extensible for future permission requirements
- All changes are backward-compatible after Phase 0 fixes (only adding restrictions, not removing access)

