# Scoping System Consolidation Plan

## Overview

This document identifies all scoping and access control artifacts and provides a plan to consolidate them into a single, manageable location with unified documentation.

## Current State Analysis

### Code Artifacts

#### 1. **Primary Scoping Module** (`app/security/scoping.py`)
**Purpose**: Core scoping classes and utilities
**Contents**:
- `InstitutionScope` class (dataclass for institution-based scoping)
- `UserScope` class (dataclass for user-level scoping)
- `get_institution_scope()` function
- `get_user_scope()` function
- `_normalize()` helper function

**Status**: ✅ Core module, should remain as primary location

#### 2. **Entity Scoping Service** (`app/security/entity_scoping.py`)
**Purpose**: Entity-specific scoping rules
**Contents**:
- `EntityScopingService` class
- Entity type constants (e.g., `ENTITY_SUBSCRIPTION`, `ENTITY_USER`)
- Entity-specific scoping methods (e.g., `_scope_subscription`, `_scope_user`)
- `get_scope_for_entity()` static method

**Status**: ✅ Entity-specific logic, should remain but may need refactoring

#### 3. **Institution Scope (Backward Compatibility)** (`app/security/institution_scope.py`)
**Purpose**: Backward compatibility for existing imports
**Contents**:
- Re-exports from `scoping.py`

**Status**: ⚠️ Can be removed after migration (or kept for compatibility)

#### 4. **Access Control Helpers** (`app/security/access_control.py`)
**Purpose**: Reusable access control patterns
**Contents**:
- `EmployeeCustomerAccessControl` class
  - `enforce_access()` method
  - `verify_ownership()` method
  - `get_scope_for_query()` method

**Status**: ⚠️ **NEW** - Should be merged into `scoping.py`

#### 5. **Auth Dependencies** (`app/auth/dependencies.py`)
**Purpose**: FastAPI dependencies for access control
**Contents**:
- `get_current_user()` - Base authentication
- `get_super_admin_user()` - Super admin access
- `get_admin_user()` - Admin access
- `get_employee_user()` - Employee access
- `get_client_user()` - Customer access
- `get_client_or_employee_user()` - Customer or Employee access
- `get_employee_or_customer_user()` - **NEW** - Employee or Customer (blocks Suppliers)

**Status**: ⚠️ Dependencies should remain in `dependencies.py`, but access control logic should reference `scoping.py`

### Documentation Artifacts

#### 1. **Core Scoping Documentation**
- `docs/api/SCOPING_SYSTEM.md` - Main scoping system documentation
- `docs/api/SCOPING_BEHAVIOR_FOR_UI.md` - UI-focused scoping guide
- `docs/api/client/SCOPING_BEHAVIOR_FOR_UI.md` - Client repo copy

**Status**: ⚠️ Should be consolidated into one document

#### 2. **Entity Scoping Documentation**
- `docs/api/INSTITUTION_SCOPING_STANDARD_ENDPOINTS_ROADMAP.md` - Implementation roadmap
- `docs/api/INSTITUTION_SCOPING_DESIGN.md` - Design document

**Status**: ⚠️ Historical/roadmap docs, can be archived or merged

#### 3. **Access Pattern Documentation**
- `docs/api/EMPLOYEE_CUSTOMER_SELF_SCOPE_PATTERN.md` - **NEW** - Employee/Customer pattern
- `docs/api/EMPLOYEE_ONLY_ACCESS_ROADMAP.md` - Employee-only access roadmap
- `docs/api/PERMISSIONS_IMPLEMENTATION_PLAN.md` - Permissions implementation plan

**Status**: ⚠️ Should be merged into main scoping documentation

#### 4. **Permission Matrix Documentation**
- `docs/api/API_PERMISSIONS_BY_ROLE.md` - Comprehensive permission matrix
- `docs/api/client/API_PERMISSIONS_BY_ROLE.md` - Client repo copy
- `docs/api/SUPPLIER_CLIENT_ACCESS_REQUIREMENTS.md` - Supplier/Client requirements

**Status**: ⚠️ Permission matrix should be separate (reference document), but access patterns should be in main doc

## Consolidation Plan

### Phase 1: Code Consolidation

#### Step 1.1: Merge Access Control into Scoping Module
**Action**: Move `EmployeeCustomerAccessControl` from `app/security/access_control.py` to `app/security/scoping.py`

**Rationale**: 
- Access control is a form of scoping
- Keeps all permission-based logic in one place
- Easier to find and maintain

**Changes**:
1. Move `EmployeeCustomerAccessControl` class to `app/security/scoping.py`
2. Update imports in files using `access_control.py`
3. Delete `app/security/access_control.py`

**Files to Update**:
- `app/services/route_factory.py` (if using access_control)
- Any other files importing from `access_control.py`

#### Step 1.2: Organize Scoping Module Structure
**Action**: Reorganize `app/security/scoping.py` with clear sections

**Proposed Structure**:
```python
# app/security/scoping.py

# =============================================================================
# 1. CORE SCOPING CLASSES
# =============================================================================
class InstitutionScope:
    """Institution-based scoping"""
    ...

class UserScope:
    """User-level scoping"""
    ...

# =============================================================================
# 2. SCOPE CREATION FUNCTIONS
# =============================================================================
def get_institution_scope(current_user: dict) -> Optional[InstitutionScope]:
    """Create InstitutionScope from current_user"""
    ...

def get_user_scope(current_user: dict) -> UserScope:
    """Create UserScope from current_user"""
    ...

# =============================================================================
# 3. ACCESS CONTROL PATTERNS
# =============================================================================
class EmployeeCustomerAccessControl:
    """Employee global + Customer self-scope pattern"""
    ...

# =============================================================================
# 4. HELPER FUNCTIONS
# =============================================================================
def _normalize(value: Any) -> Any:
    """Normalize values for comparison"""
    ...
```

#### Step 1.3: Update Entity Scoping Service
**Action**: Ensure `EntityScopingService` references consolidated scoping module

**Changes**:
- Verify imports are correct
- Update any references to access control patterns

#### Step 1.4: Update Dependencies
**Action**: Ensure `app/auth/dependencies.py` imports from consolidated module

**Changes**:
- Update imports to use `app.security.scoping`
- Add comments referencing scoping patterns

### Phase 2: Documentation Consolidation

#### Step 2.1: Create Unified Scoping Documentation
**Action**: Merge all scoping documentation into `docs/api/SCOPING_SYSTEM.md`

**New Structure**:
```markdown
# Scoping and Access Control System

## 1. Overview
- Purpose and architecture
- Location of code

## 2. Core Concepts
- Institution Scoping
- User Scoping
- Access Control Patterns

## 3. Scoping Classes
- InstitutionScope
- UserScope

## 4. Access Control Patterns
- Employee Global + Customer Self-Scope
- Employee-Only Access
- Institution Scoping

## 5. Entity-Specific Scoping
- EntityScopingService
- Entity type constants
- Custom scoping rules

## 6. FastAPI Dependencies
- get_current_user
- get_employee_user
- get_client_user
- get_employee_or_customer_user
- etc.

## 7. Usage Examples
- Institution-scoped endpoints
- User-scoped endpoints
- Employee/Customer pattern
- Employee-only endpoints

## 8. UI Implementation Guide
- How scoping affects UI
- What UI should/shouldn't do
- Error handling

## 9. Permission Matrix Reference
- Link to API_PERMISSIONS_BY_ROLE.md
```

#### Step 2.2: Archive Historical Documentation
**Action**: Move roadmap/implementation docs to `docs/archived/`

**Files to Archive**:
- `docs/api/INSTITUTION_SCOPING_STANDARD_ENDPOINTS_ROADMAP.md`
- `docs/api/INSTITUTION_SCOPING_DESIGN.md`
- `docs/api/EMPLOYEE_ONLY_ACCESS_ROADMAP.md`
- `docs/api/PERMISSIONS_IMPLEMENTATION_PLAN.md`
- `docs/api/SUPPLIER_CLIENT_ACCESS_REQUIREMENTS.md`

**Rationale**: These are historical/implementation docs, not reference material

#### Step 2.3: Keep Permission Matrix Separate
**Action**: Keep `API_PERMISSIONS_BY_ROLE.md` as a separate reference document

**Rationale**: 
- It's a comprehensive matrix that's useful as a quick reference
- Main scoping doc will link to it
- It's already being copied to client repo

#### Step 2.4: Update Client Documentation
**Action**: Update `docs/api/client/` to reference consolidated documentation

**Changes**:
- Update `README.md` in `docs/api/client/` to reference new structure
- Ensure `SCOPING_BEHAVIOR_FOR_UI.md` is still available (or merged into main doc)

### Phase 3: Import Updates

#### Step 3.1: Update All Imports
**Action**: Update all files importing from old locations

**Files to Check**:
```bash
# Find all files importing scoping/access_control
grep -r "from app.security.access_control" app/
grep -r "from app.security.institution_scope" app/
grep -r "import.*access_control" app/
```

**Update Pattern**:
```python
# OLD
from app.security.access_control import EmployeeCustomerAccessControl

# NEW
from app.security.scoping import EmployeeCustomerAccessControl
```

#### Step 3.2: Verify No Broken Imports
**Action**: Run tests and check for import errors

**Verification**:
- Run linter
- Check for runtime import errors
- Verify all routes still work

## Implementation Checklist

### Code Consolidation
- [x] Move `EmployeeCustomerAccessControl` to `app/security/scoping.py`
- [x] Reorganize `scoping.py` with clear sections
- [x] Update all imports from `access_control.py` (none found - was new)
- [x] Delete `app/security/access_control.py`
- [x] Update `EntityScopingService` imports if needed (not needed)
- [x] Update `dependencies.py` comments/references (not needed)
- [x] Run linter to check for errors
- [x] Test imports to ensure no regressions

### Documentation Consolidation
- [x] Read all existing scoping documentation
- [x] Create unified `SCOPING_SYSTEM.md` structure
- [x] Merge content from:
  - `EMPLOYEE_CUSTOMER_SELF_SCOPE_PATTERN.md`
  - `SCOPING_BEHAVIOR_FOR_UI.md`
  - Relevant sections from other docs
- [x] Archive historical docs to `docs/zArchive/`
- [ ] Update `API_PERMISSIONS_BY_ROLE.md` to reference main doc (optional)
- [ ] Update `docs/api/client/README.md` (optional)
- [ ] Verify client repo documentation is still accurate (optional)

### Verification
- [x] All imports work correctly
- [x] Documentation is comprehensive and accurate
- [x] No duplicate information
- [x] Clear navigation/structure
- [ ] All routes function as expected (requires runtime testing)

## File Structure After Consolidation

```
app/security/
├── __init__.py
├── scoping.py                    # ✅ ALL scoping and access control logic
├── entity_scoping.py             # ✅ Entity-specific scoping rules
└── institution_scope.py          # ⚠️ Backward compatibility (optional)

docs/api/
├── SCOPING_SYSTEM.md             # ✅ Unified scoping documentation
├── API_PERMISSIONS_BY_ROLE.md   # ✅ Permission matrix (reference)
└── client/
    ├── README.md                 # ✅ Updated to reference main doc
    ├── SCOPING_BEHAVIOR_FOR_UI.md # ✅ Or merged into main doc
    └── API_PERMISSIONS_BY_ROLE.md # ✅ Copy for client repo

docs/archived/
├── INSTITUTION_SCOPING_STANDARD_ENDPOINTS_ROADMAP.md
├── INSTITUTION_SCOPING_DESIGN.md
├── EMPLOYEE_ONLY_ACCESS_ROADMAP.md
├── PERMISSIONS_IMPLEMENTATION_PLAN.md
└── SUPPLIER_CLIENT_ACCESS_REQUIREMENTS.md
```

## Benefits of Consolidation

1. **Single Source of Truth**: All scoping logic in one file
2. **Easier Maintenance**: Changes in one place
3. **Better Discoverability**: Developers know where to look
4. **Unified Documentation**: One comprehensive guide
5. **Reduced Duplication**: No scattered patterns
6. **Clearer Architecture**: Logical organization

## Risks and Mitigation

**Risk**: Breaking existing imports
**Mitigation**: 
- Update all imports in one pass
- Run comprehensive tests
- Keep backward compatibility file temporarily

**Risk**: Losing important documentation
**Mitigation**:
- Archive, don't delete historical docs
- Review all content before merging
- Keep permission matrix separate as reference

**Risk**: Large file size
**Mitigation**:
- Use clear sections and organization
- Consider splitting only if file exceeds 1000 lines
- Use type hints and docstrings for clarity

## Next Steps

1. **Review this plan** with stakeholders
2. **Approve implementation approach**
3. **Execute Phase 1** (Code Consolidation)
4. **Execute Phase 2** (Documentation Consolidation)
5. **Execute Phase 3** (Import Updates)
6. **Verify and test**
7. **Update client repo documentation**

---

*Last Updated: 2025-11-23*
*Status: Planning Phase - Awaiting Approval*

