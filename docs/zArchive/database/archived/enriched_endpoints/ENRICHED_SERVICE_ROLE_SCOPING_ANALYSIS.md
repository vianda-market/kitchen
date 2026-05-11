# Role-Based Scoping Analysis for EnrichedService

## Current State

### Role-Based Access Control (Route Level)
- **Purpose**: Controls WHO can access the endpoint
- **Implementation**: FastAPI dependencies (`get_super_admin_user()`, `get_admin_user()`, `get_employee_user()`)
- **Location**: Route handlers (e.g., `@router.get("/enriched/")`)
- **Current Behavior**:
  - Super Admin: Can access discretionary approval endpoints
  - Admin: Can access discretionary view endpoints
  - Employee: Can access system configuration endpoints
  - Supplier: Can access their institution's data
  - Customer: Can access their own data

### Data Filtering (Query Level)
- **Purpose**: Controls WHAT data they can see
- **Implementation**: `InstitutionScope` in `EnrichedService`
- **Current Behavior**:
  - Employees (all roles): Global access (`scope.is_global = True`) → See everything
  - Suppliers: Institution-scoped (`scope.is_global = False`) → See only their institution
  - Customers: User-scoped → See only their own data

## Question: Do We Need Role-Based Data Filtering?

### Current Reality
**All Employee roles (Super Admin, Admin, regular Employee) see the same data** - they all have global access via `InstitutionScope.is_global = True`.

### Potential Use Cases for Role-Based Data Filtering

1. **Sensitive Field Filtering**
   - Super Admin: Sees all fields (including sensitive ones like `account_number`, `routing_number`)
   - Admin: Sees most fields but masks sensitive data
   - Regular Employee: Sees basic fields only

2. **Record-Level Filtering**
   - Super Admin: Sees all records (including archived, deleted, test data)
   - Admin: Sees active records only
   - Regular Employee: Sees limited subset

3. **Institution-Level Filtering**
   - Super Admin: Sees all institutions
   - Admin: Sees assigned institutions only
   - Regular Employee: Sees their assigned institution only

## Implementation Complexity Assessment

### Option 1: Add Role-Based Filtering to EnrichedService (Medium Complexity)

**Work Required**: ~2-3 hours

**Changes Needed**:
1. Add `role_name` parameter to `EnrichedService.__init__()`
2. Add `RoleScope` dataclass (similar to `InstitutionScope`)
3. Modify `_build_where_clause()` to handle role-based conditions
4. Update route handlers to pass `role_name` from `current_user`

**Code Changes**:
```python
# In enriched_service.py
class RoleScope:
    def __init__(self, role_name: str):
        self.role_name = role_name
        self.is_super_admin = role_name == "Super Admin"
        self.is_admin = role_name in ["Admin", "Super Admin"]
        self.is_regular_employee = role_name not in ["Admin", "Super Admin"]

# In __init__
def __init__(
    self,
    ...
    role_column: Optional[str] = None,  # For role-based filtering
    role_table_alias: Optional[str] = None,
):
    ...
    self.role_column = role_column
    self.role_table_alias = role_table_alias

# In _build_where_clause
def _build_where_clause(
    self,
    ...
    role_scope: Optional[RoleScope] = None,
):
    ...
    # Add role-based filtering
    if role_scope and self.role_column:
        if role_scope.is_regular_employee:
            # Regular employees see limited data
            conditions.append(f"{self.role_table_alias}.{self.role_column} = %s")
            params.append(role_scope.role_name)
```

**Pros**:
- Flexible - can filter by role at query level
- Consistent with institution scoping pattern
- Can filter records or fields

**Cons**:
- Adds complexity to service
- May not be needed if all Employees see same data
- Requires database schema changes if filtering by role in DB

### Option 2: Field-Level Filtering (Post-Query) (Low Complexity)

**Work Required**: ~1 hour

**Changes Needed**:
1. Add field filtering logic after query execution
2. Create field mask configurations per role
3. Apply masks in `get_enriched()` before returning results

**Code Changes**:
```python
# In enriched_service.py
def __init__(
    self,
    ...
    field_masks: Optional[Dict[str, List[str]]] = None,  # {"Super Admin": [], "Admin": ["account_number"], ...}
):
    ...
    self.field_masks = field_masks or {}

def _apply_field_masks(self, row_dict: dict, role_name: str) -> dict:
    """Mask sensitive fields based on role"""
    masked = row_dict.copy()
    if role_name in self.field_masks:
        for field in self.field_masks[role_name]:
            if field in masked:
                masked[field] = "***MASKED***"
    return masked
```

**Pros**:
- Simple to implement
- No database schema changes
- Works for sensitive field masking

**Cons**:
- Only works for field masking, not record filtering
- Data still fetched from DB (less efficient)

### Option 3: Keep Current Approach (No Changes) (Zero Complexity)

**Current Behavior**: All Employee roles see the same data (global access)

**Pros**:
- Simple - no additional complexity
- Consistent with current architecture
- Role-based access control already handled at route level

**Cons**:
- Cannot differentiate data visibility by role
- All Employees see everything

## Recommendation

### If Role-Based Data Filtering is NOT Needed
**Keep current approach** - Role-based access control at route level is sufficient.

### If Role-Based Data Filtering IS Needed

**For Field Masking (sensitive data)**:
- Use **Option 2** (Post-Query Field Masking)
- ~1 hour implementation
- Simple and effective for hiding sensitive fields

**For Record Filtering (different records per role)**:
- Use **Option 1** (Role-Based Filtering in Query)
- ~2-3 hours implementation
- More complex but more powerful

## Questions to Answer

1. **Do Super Admin, Admin, and regular Employees need to see different data?**
   - If NO → Keep current approach
   - If YES → Which data should differ?

2. **Is this about sensitive field masking (e.g., account numbers)?**
   - If YES → Use Option 2 (Field Masking)
   - If NO → Use Option 1 (Record Filtering)

3. **Is this about record-level filtering (e.g., archived records)?**
   - If YES → Use Option 1 (Role-Based Filtering)
   - If NO → Keep current approach

## Implementation Estimate

- **Option 1 (Role-Based Filtering)**: 2-3 hours
- **Option 2 (Field Masking)**: 1 hour
- **Option 3 (No Changes)**: 0 hours

## Next Steps

1. **Clarify requirements**: What data should differ by role?
2. **Choose approach**: Based on requirements
3. **Implement**: If needed, add to `EnrichedService`
4. **Test**: Verify role-based filtering works correctly

