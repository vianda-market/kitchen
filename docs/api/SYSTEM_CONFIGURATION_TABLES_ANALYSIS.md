# System Configuration Tables Analysis

## Overview

This document analyzes whether the system configuration tables (`role_info`, `status_info`, `transaction_type_info`) should be accessible via API or remain system-managed.

## Table Analysis

### 1. `role_info` Table

**Current Usage:**
- **Foreign Key**: `user_info.role_id` → `role_info.role_id` (required)
- **Authentication**: JWT tokens include `role_type` and `role_name` from this table
- **Permission System**: Core to the entire authorization model
- **Business Logic**: 
  - `role_type` determines global vs. institution-scoped access
  - `role_name` determines specific permissions (e.g., "Super Admin" for discretionary approvals)
  - Used in `InstitutionScope`, `UserScope`, and all permission checks

**Risk Assessment:**
- **HIGH RISK**: Changing role names/types could break:
  - Authentication/authorization logic
  - Permission checks throughout the application
  - Institution scoping behavior
  - User scoping behavior

**Recommendation**: ❌ **DO NOT expose via API**
- These are core security configuration tables
- Changes require code updates to permission logic
- Risk of breaking the entire authorization system

---

### 2. `status_info` Table

**Current Usage:**
- **Foreign Keys**: Only referenced by `status_history` (its own history table)
- **Actual Usage**: Most tables use `status VARCHAR(20)` directly, NOT foreign keys to `status_info`
- **Pattern**: Tables define status values inline (e.g., `CHECK (status IN ('Active', 'Inactive', 'Cancelled'))`)
- **Application Code**: No active queries found using `status_info` table

**Risk Assessment:**
- **LOW-MEDIUM RISK**: Appears to be a legacy/reference table
- Not actively used in application logic
- Most tables have their own status values defined inline

**Recommendation**: ❌ **DO NOT expose via API**
- Table appears to be unused/legacy
- Status values are defined per-table, not centralized
- No business value in exposing unused reference data

---

### 3. `transaction_type_info` Table

**Current Usage:**
- **Foreign Keys**: Only referenced by `transaction_type_history` (its own history table)
- **Actual Usage**: Transaction types appear to be hardcoded in application logic
- **Application Code**: No active queries found using `transaction_type_info` table

**Risk Assessment:**
- **LOW-MEDIUM RISK**: Appears to be a legacy/reference table
- Not actively used in application logic
- Transaction types are likely hardcoded in business logic

**Recommendation**: ❌ **DO NOT expose via API**
- Table appears to be unused/legacy
- Transaction types are likely defined in code, not database
- No business value in exposing unused reference data

---

## Summary & Recommendations

### ❌ Keep All Three Tables Inaccessible via API

**Rationale:**

1. **Security & Stability**:
   - `role_info` is core to the security model - changes could break authorization
   - All three tables are system-level configuration, not user data

2. **Business Logic Dependencies**:
   - `role_info` changes require code updates to permission logic
   - `status_info` and `transaction_type_info` appear unused but may have future dependencies

3. **Data Integrity**:
   - These are reference/lookup tables that should remain stable
   - Changes could have cascading effects on existing records

4. **Current Architecture**:
   - Most tables use inline status values, not foreign keys to `status_info`
   - Transaction types are likely hardcoded in business logic
   - Only `role_info` is actively used, but it's too critical to expose

### Alternative: Read-Only Reference Endpoints (Optional)

If there's a need to display these values in the UI for reference purposes:

- **GET endpoints only** (no POST/PUT/DELETE)
- **Employee-only access**
- **Read-only** - for display/reference only
- **No business logic dependencies** - UI should not rely on these for critical operations

**Example:**
```python
@router.get("/roles/", response_model=List[RoleResponseSchema])
def list_roles(...):
    """Get all roles (read-only, for reference only)"""
    # Read-only, no modifications allowed
```

However, even read-only access should be carefully considered, as it might encourage UI dependencies on these system tables.

---

## Conclusion

**Recommendation: Keep all three tables inaccessible via API.**

These are system configuration tables that:
- Are core to security (`role_info`)
- Appear to be legacy/unused (`status_info`, `transaction_type_info`)
- Would require significant code changes if modified
- Should remain stable and system-managed

If changes are needed, they should be done:
1. Via database migrations/scripts
2. With careful testing of all dependent business logic
3. With code updates to handle new values
4. By system administrators, not via client API

---

*Last Updated: 2025-11-23*


