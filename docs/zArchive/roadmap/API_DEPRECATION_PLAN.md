# API Deprecation Plan: User Self-Update Endpoints

## Overview

This document outlines the deprecation strategy for legacy user endpoints that use `user_id` in the URL path for self-updates. The new `/me` endpoints provide better security by eliminating path parameter manipulation risks.

## Security Rationale

**Current Risk**: Endpoints like `PUT /users/{user_id}` allow clients to pass `user_id` in the URL path, which can be manipulated. While enforcement logic (`enforce_user()`) exists, it's error-prone and adds attack surface.

**Solution**: `/me` endpoints extract `user_id` directly from JWT token, eliminating path manipulation entirely.

## Access Pattern Matrix

### Role-Based Endpoint Usage

| Role | Self-Updates | Manage Others | Endpoint Pattern |
|------|--------------|---------------|------------------|
| **Customer** | `/me` only | ❌ None | `/me` endpoints only |
| **Supplier Admin** | `/me` (prevent user_id errors) | `/{user_id}` (institution scope) | `/me` for self, `/{user_id}` for institution users |
| **Supplier Operator** (if exists) | `/me` only | ❌ None | `/me` endpoints only |
| **Employee Admin** | `/me` (prevent user_id errors) | `/{user_id}` (global scope) | `/me` for self, `/{user_id}` for any user |
| **Employee Management** | `/me` (prevent user_id errors) | `/{user_id}` (institution scope) | `/me` for self, `/{user_id}` for institution users |
| **Employee Operator** | `/me` only | ❌ None | `/me` endpoints only |

**Key Principle**: All users should use `/me` endpoints for self-updates to prevent `user_id` ingestion errors. Only admins use `/{user_id}` endpoints for managing OTHER users.

## Endpoints to Deprecate (Self-Updates Only)

### 1. `PUT /users/{user_id}` - Update User Profile
**Status**: ⚠️ **DEPRECATE for Self-Updates, KEEP for Admin Operations**

**Current Behavior**:
- All users: Can update their own profile (enforced via `enforce_user()`)
- Admins: Can update users within their scope

**New Behavior**:
- **All users (Customers, Supplier Admins, Employee Admins, etc.)**: Must use `PUT /users/me` for self-updates (deprecation warning on old endpoint)
- **Admins only**: Continue using `PUT /users/{user_id}` for managing OTHER users (admin operation)

**Deprecation Strategy**:
```python
@router.put("/{user_id}", response_model=UserResponseSchema, deprecated=True)
def update(
    user_id: UUID,
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update a user
    
    ⚠️ DEPRECATED for self-updates: Use PUT /users/me instead for updating your own profile.
    This endpoint remains available for Admins to update OTHER users.
    
    Access Rules:
    - Self-updates: Use PUT /users/me (all users)
    - Admin operations: Use PUT /users/{user_id} (admins managing other users)
    """
    # Check if this is a self-update
    is_self_update = str(user_id) == str(current_user["user_id"])
    
    if is_self_update:
        # Log deprecation warning for self-updates
        log_warning(
            f"User {current_user['user_id']} ({current_user.get('role_type')}) used deprecated endpoint "
            f"PUT /users/{{user_id}} for self-update. Please migrate to PUT /users/me."
        )
        
        # Redirect to /me endpoint logic (or raise deprecation error)
        # For now, allow but warn - will enforce in Phase 5
        scope = None
    else:
        # Admin operation - update other user
        # Verify user has admin permissions
        role_type = current_user.get("role_type")
        role_name = current_user.get("role_name")
        
        if role_type == "Customer":
            raise HTTPException(
                status_code=403,
                detail="Customers cannot update other users"
            )
        
        if role_type == "Employee" and role_name == "Operator":
            raise HTTPException(
                status_code=403,
                detail="Employee Operators cannot update other users"
            )
        
        # Determine scope based on role
        if role_type == "Employee" and role_name in ["Admin", "Super Admin"]:
            # Employee Admin: Global scope
            scope = None  # No institution filtering
        elif role_type == "Employee" and role_name == "Manager":
            # Employee Management: Institution scope
            scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
        else:
            # Suppliers: Institution scope
            scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
    
    # ... rest of implementation
```

### 2. `GET /users/{user_id}` - Get User Profile
**Status**: ⚠️ **DEPRECATE for Self-Reads, KEEP for Admin Operations**

**Current Behavior**:
- All users: Can get their own profile (enforced via `enforce_user()`)
- Admins: Can get users within their scope

**New Behavior**:
- **All users**: Must use `GET /users/me` for self-reads (deprecation warning on old endpoint)
- **Admins only**: Continue using `GET /users/{user_id}` for reading OTHER users (admin operation)

**Deprecation Strategy**: Same pattern as `PUT /users/{user_id}`

### 3. `GET /users/enriched/{user_id}` - Get Enriched User Profile
**Status**: ⚠️ **DEPRECATE for Self-Reads, KEEP for Admin Operations**

**Current Behavior**:
- All users: Can get their own enriched profile
- Admins: Can get enriched users within their scope

**New Behavior**:
- **All users**: Must use `GET /users/me` for self-reads (returns enriched data)
- **Admins only**: Continue using `GET /users/enriched/{user_id}` for reading OTHER users (admin operation)

**Deprecation Strategy**: Same pattern as above

### 4. Account Termination (Archive) - Separate Endpoint
**Status**: ✅ **NEW ENDPOINT REQUIRED**

**Decision**: Users should NOT be able to delete themselves, but they SHOULD be able to archive/terminate their accounts.

**New Endpoint**: `PUT /users/me/terminate` or `POST /users/me/terminate`

**Purpose**: Allow users to terminate their own account (soft delete via `is_archived = TRUE`)

**Rationale**: 
- More destructive than regular profile updates
- Requires separate endpoint for clarity and safety
- Allows for additional validation/confirmation if needed
- Clear separation from admin deletion operations

**Implementation**:
```python
@router.put("/me/terminate", response_model=dict)
def terminate_my_account(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Terminate current user's account (archive/soft delete)
    
    This is a destructive operation that archives the user's account.
    Users cannot delete themselves - only archive/terminate.
    """
    def _terminate_account():
        # Archive user (soft delete)
        success = user_service.soft_delete(
            current_user["user_id"],
            current_user["user_id"],  # Self-termination
            db,
            scope=None
        )
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to terminate account"
            )
        return {"detail": "Account terminated successfully"}
    
    return handle_business_operation(_terminate_account, "account termination")
```

**Note**: `DELETE /users/{user_id}` remains admin-only for hard deletes (if implemented) or soft deletes of other users.

### 5. `PUT /users/{user_id}/password` - Admin reset user password
**Status**: ⚠️ **DEPRECATE WHEN POSTMAN MIGRATED**

**Current Behavior**:
- Admins (Employee Admin/Manager, Supplier Admin/Manager) can set a new password for another user.
- B2B site no longer uses this; it uses the invite flow (`POST /users/` without password, then `POST /users/{user_id}/resend-invite` if needed).

**Reason for Deprecation**:
- B2B site uses invite-only flow. Admin reset is retained only for Postman collection testing.

**Migration Path**:
1. Enhance Postman collections to use invite flow (create user without password, resend-invite if needed) instead of admin reset.
2. Once Postman no longer depends on it: add `deprecated=True`, log warnings, then eventually remove.

**Replacement**: `POST /users/{user_id}/resend-invite` — resends the B2B invite email with set-password link. See [API_CLIENT_PASSWORD_MANAGEMENT.md](../api/b2b_client/API_CLIENT_PASSWORD_MANAGEMENT.md).

---

## Endpoints to Keep (Admin Operations Only)

These endpoints remain for **managing OTHER users** (not self-updates):
- `PUT /users/{user_id}` - Update other users (admin only, not for self-updates)
- `GET /users/{user_id}` - Get other users (admin only, not for self-reads)
- `GET /users/enriched/{user_id}` - Get other users enriched (admin only, not for self-reads)
- `DELETE /users/{user_id}` - Delete/archive other users (admin only)
- `POST /users/` - Create users (admin only, already restricted)

**Important**: These endpoints should ONLY be used when `user_id != current_user["user_id"]`. Self-updates must use `/me` endpoints.

## Migration Path

### Phase 1: Add New Endpoints (Current)
- [x] Add `GET /users/me` endpoint ✅ **COMPLETED**
- [x] Add `PUT /users/me` endpoint ✅ **COMPLETED**
- [x] Add `PUT /users/me/terminate` endpoint (account termination/archive) ✅ **COMPLETED**
- [x] Add `PUT /users/me/employer` endpoint (employer assignment) ✅ **COMPLETED**

### Phase 2: Add Deprecation Warnings (Immediate)
- [x] Add `deprecated=True` to path-parameter endpoints in FastAPI ✅ **COMPLETED**
- [x] Add deprecation warnings in docstrings ✅ **COMPLETED**
- [x] Add warning logs when users use deprecated endpoints for self-updates ✅ **COMPLETED**
- [x] Detect self-update attempts (`user_id == current_user["user_id"]`) ✅ **COMPLETED**
- [ ] Add `X-Deprecated-Endpoint` header to responses for self-updates (Optional - deferred)
- [ ] Return deprecation notice in response body (Optional - deferred)

### Phase 3: Update Documentation (Immediate)
- [ ] Update API documentation to recommend `/me` endpoints for ALL users (self-updates)
- [ ] Document access pattern matrix (who uses what endpoints)
- [ ] Update Postman collections to use `/me` endpoints for self-updates
- [ ] Update vianda-platform client to use `/me` for Supplier Admin self-updates
- [ ] Add migration guide for API consumers
- [ ] Update OpenAPI/Swagger docs with deprecation notices

### Phase 4: Monitor Usage (1-2 months)
- [ ] Add metrics/logging to track usage of deprecated endpoints
- [ ] Monitor for self-update usage of deprecated endpoints (all user types)
- [ ] Track Supplier Admin usage patterns (should use `/me` for self-updates)
- [ ] Identify clients still using deprecated endpoints for self-updates

### Phase 5: Enforce Deprecation (3-6 months)
- [x] Return `410 Gone` for self-updates using deprecated endpoints (all user types) ✅ **COMPLETED**
- [x] Keep endpoints available for admin operations (updating OTHER users) ✅ **COMPLETED**
- [x] Update error messages to direct users to `/me` endpoints for self-updates ✅ **COMPLETED**
- [x] Enforce: `PUT /users/{user_id}` only works when `user_id != current_user["user_id"]` ✅ **COMPLETED**

### Phase 6: Complete Removal (6-12 months)
**Decision**: Should we completely remove path-parameter endpoints?

**Option A: Keep for Admins**
- Keep `PUT /users/{user_id}` for Employees/Suppliers (admin operations)
- Remove Customer access entirely
- **Pros**: Clear separation, admins can still update other users
- **Cons**: Two patterns (path-param for admins, `/me` for self)

**Option B: Unified Pattern**
- Force all self-updates to use `/me` (even for admins updating themselves)
- Keep path-parameter only for updating OTHER users
- **Pros**: Consistent pattern
- **Cons**: Admins need to know which endpoint to use

**Recommendation**: **Option A (Updated)** - Keep path-parameter endpoints for admin operations (updating OTHER users), remove self-update access for all users. This maintains clear separation:
- `/me` endpoints: Self-updates (all users)
- `/{user_id}` endpoints: Admin operations (updating other users, admins only)

## Implementation Details

### FastAPI Deprecation

```python
from fastapi import APIRouter, Depends, Header
from typing import Optional

@router.put(
    "/{user_id}",
    response_model=UserResponseSchema,
    deprecated=True,  # FastAPI will mark as deprecated in OpenAPI
    summary="Update user (DEPRECATED for Customers - use PUT /users/me)"
)
def update(
    user_id: UUID,
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update a user
    
    ⚠️ **DEPRECATED for Customers**: Use `PUT /users/me` for self-updates.
    
    This endpoint remains available for Employees/Suppliers to update other users.
    """
    if current_user.get("role_type") == "Customer":
        # Log deprecation warning
        log_warning(
            f"DEPRECATED: Customer {current_user['user_id']} used PUT /users/{{user_id}}. "
            f"Migrate to PUT /users/me"
        )
    
    # ... existing implementation
```

### Response Headers

```python
from fastapi import Response

@router.put("/{user_id}", ...)
def update(..., response: Response):
    if current_user.get("role_type") == "Customer":
        response.headers["X-Deprecated-Endpoint"] = "true"
        response.headers["X-Use-Instead"] = "PUT /users/me"
        response.headers["X-Deprecation-Date"] = "2025-12-04"
        response.headers["X-Removal-Date"] = "2026-06-04"  # 6 months
    
    # ... rest of implementation
```

### Monitoring

```python
from app.utils.log import log_warning, log_info

def _log_deprecated_endpoint_usage(endpoint: str, user_id: UUID, role_type: str):
    """Log usage of deprecated endpoint for monitoring"""
    log_warning(
        f"DEPRECATED ENDPOINT USAGE: {endpoint} by {role_type} user {user_id}. "
        f"Timestamp: {datetime.utcnow().isoformat()}"
    )
    # Could also send to metrics service (Prometheus, DataDog, etc.)
```

## Testing Updates

### Tests to Update
- [ ] Update Customer self-update tests to use `/me` endpoints
- [ ] Keep admin update tests using `/{user_id}` endpoints
- [ ] Add tests for deprecation warnings
- [ ] Add tests for `410 Gone` responses (Phase 5)

### Tests to Remove
- [ ] Remove tests that test Customer self-updates via `/{user_id}` (after Phase 5)
- [ ] Remove tests that test Employee Operator self-updates via `/{user_id}` (after Phase 5)
- [ ] Keep tests for admin operations via `/{user_id}` (Employee Admin, Employee Management, Supplier Admin)

## Postman Collection Updates

### Collections to Update
- [ ] `E2E Plate Selection.postman_collection.json`
- [ ] `Permissions Testing - Employee-Only Access.postman_collection.json`
- [ ] `DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`
- [ ] Any other collections using user update endpoints

### Changes Needed
- Replace `PUT /users/{user_id}` with `PUT /users/me` for Customer workflows
- Replace `GET /users/{user_id}` with `GET /users/me` for Customer workflows
- Keep `PUT /users/{user_id}` for admin workflows (updating other users)

## Documentation Updates

### Files to Update
- [ ] API documentation (if separate from code)
- [ ] README files
- [ ] Developer guides
- [ ] OpenAPI/Swagger schema (auto-generated from FastAPI)

### Content to Add
- Migration guide: "How to migrate from `PUT /users/{user_id}` to `PUT /users/me`"
- Security best practices: "Why `/me` endpoints are more secure"
- Examples: Code samples showing new vs. old patterns

## Rollback Plan

If issues arise:
1. **Immediate**: Remove `deprecated=True` flag (endpoints work normally)
2. **Short-term**: Remove deprecation warnings/logging
3. **Long-term**: Keep both patterns if needed (not recommended for security)

## Success Criteria

Deprecation is successful when:
- ✅ Zero Customer usage of deprecated endpoints (monitored via logs)
- ✅ All Postman collections updated
- ✅ All documentation updated
- ✅ All tests updated
- ✅ Customers receive clear error messages directing to `/me` endpoints

## Timeline Summary

| Phase | Duration | Actions |
|-------|----------|---------|
| Phase 1 | Current | Add `/me` endpoints |
| Phase 2 | Immediate | Add deprecation warnings |
| Phase 3 | Immediate | Update documentation |
| Phase 4 | 1-2 months | Monitor usage |
| Phase 5 | 3-6 months | Enforce deprecation (410 for Customers) |
| Phase 6 | 6-12 months | Complete removal (if decided) |

## Decision Log

### Decision 1: Keep path-parameter endpoints for admins?
**Decision**: ✅ Yes - Keep `PUT /users/{user_id}` for Employees/Suppliers (admin operations)
**Rationale**: Clear separation between self-updates (`/me`) and admin operations (`/{user_id}`)

### Decision 2: Allow customer self-deletion?
**Decision**: ⚠️ **TBD** - Needs product decision
**Options**:
- Option A: Allow `DELETE /users/me` for customers
- Option B: Customers cannot delete themselves (admin-only operation)

### Decision 3: Complete removal timeline?
**Decision**: ⚠️ **TBD** - Monitor usage first
**Recommendation**: Keep path-parameter endpoints for admin operations indefinitely, remove self-update access after 6 months

### Decision 4: Supplier Admin access pattern?
**Decision**: ✅ **RESOLVED** - Supplier Admins use `/me` for self-updates
**Rationale**: 
- Prevents `user_id` ingestion errors in vianda-platform client
- Clear separation: `/me` for self, `/{user_id}` for managing institution users
- Applies to all admins (Supplier Admin, Employee Admin, Employee Super Admin)

### Decision 5: Supplier Operator access?
**Decision**: ✅ **RESOLVED** - Supplier Operators (if they exist) use `/me` only
**Note**: Currently, Supplier role type only supports Admin role_name. If Supplier Operator role is added in the future, they would only have access to `/me` endpoints (no admin operations).

### Decision 6: Employee role structure?
**Decision**: ✅ **RESOLVED** - Three-tier Employee role structure
**Structure**:
- **Employee Admin**: Global scope (can manage any user across all institutions)
- **Employee Management**: Institution scope (can manage users within their institution)
- **Employee Operator**: Self-updates only (`/me` endpoints, no management capabilities)

**Note**: This requires adding `OPERATOR` and `MANAGEMENT` role names to `RoleName` enum. Current system has `ADMIN` and `SUPER_ADMIN` for Employees. The mapping should be:
- `SUPER_ADMIN` → Employee Admin (global scope) - or rename to `ADMIN` with global scope
- New `MANAGEMENT` → Employee Management (institution scope)
- New `OPERATOR` → Employee Operator (self-updates only)

