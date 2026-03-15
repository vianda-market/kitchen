# Phase 3: Route Updates - Implementation Plan

## Current Status Assessment

### ✅ Already Complete (from recent fixes)

**`app/routes/user.py`**:
- ✅ `GET /users/{user_id}` - Employee Operator blocking implemented
- ✅ `PUT /users/{user_id}` - Employee Operator blocking implemented
- ✅ `GET /users/me` - Implemented
- ✅ `PUT /users/me` - Implemented

**`app/security/entity_scoping.py`**:
- ✅ All `_scope_*` methods updated (Phase 2 complete)
- ✅ Methods use `get_institution_scope()` which handles `role_name` automatically

### ❌ Still Needs Updates

**`app/routes/user.py`**:
- ❌ `DELETE /users/{user_id}` - Missing Employee Operator blocking (only checks Customer)
- ❌ `GET /users/enriched/{user_id}` - Need to verify Employee Operator blocking

**`app/routes/address.py`**:
- ⚠️ Uses `get_user_scope().enforce_user_assignment()` which should handle Employee Operators
- ⚠️ Need to verify explicit Employee Operator blocking for address operations

**Other Routes** (Lower Priority):
- Routes using `EntityScopingService.get_scope_for_entity()` are **already correct** (Phase 2 handles this)
- Routes that need explicit Employee Operator blocking checks (not just scope):
  - Address routes (if Employee Operators shouldn't manage addresses for others)
  - Any route that allows managing resources for other users

## Testing Strategy: Postman E2E vs Unit Tests

### Recommendation: **Postman E2E for Permissions Testing** ✅

**Why Postman E2E is Better for Permissions:**

1. **Real-World Scenarios**: Tests actual HTTP requests with real authentication tokens
2. **Integration Testing**: Tests the full stack (route → service → database)
3. **Role Coverage**: Easy to test all role combinations (Admin, Management, Operator, Customer, Supplier)
4. **Cross-Institution Testing**: Can test institution boundaries with real data
5. **Status Code Validation**: Verifies actual HTTP responses (403, 404, 200)
6. **Already Working**: Your Postman E2E tests have passed, proving the implementation works

**What Postman E2E Tests Cover:**
- ✅ Employee Operator blocked from accessing other users (403)
- ✅ Employee Management can access institution users (200)
- ✅ Employee Management blocked from cross-institution users (403)
- ✅ Employee Admin can access any user (200)
- ✅ Employee Operator can use `/me` endpoints (200)
- ✅ Cross-institution access returns 403 (not 404)

### Unit Tests: When to Use

**Unit Tests Should Focus On:**

1. **Business Logic Edge Cases** (not permissions):
   - Service layer logic
   - Data validation
   - Complex calculations
   - Error handling

2. **Scope Calculation Logic** (if complex):
   - Testing `InstitutionScope.is_global` with different role combinations
   - Testing `UserScope.matches_user()` edge cases
   - Testing scope determination for edge cases

3. **Service Layer Functions**:
   - `EntityScopingService.get_scope_for_entity()` with various inputs
   - Scope enforcement logic in services

**What Unit Tests Should NOT Cover:**
- ❌ HTTP status codes (Postman does this better)
- ❌ Full request/response cycle (Postman does this better)
- ❌ Authentication/authorization flow (Postman does this better)
- ❌ Cross-institution scenarios (Postman does this better)

### Recommended Testing Approach

**For Phase 3 Completion:**

1. **Postman E2E Tests** (Primary):
   - ✅ Already passing - confirms implementation works
   - ✅ Covers all role combinations
   - ✅ Tests real HTTP responses
   - **Action**: Verify all test cases in Postman collection are comprehensive

2. **Unit Tests** (Minimal, Focused):
   - ✅ Test `InstitutionScope.is_global` with all role combinations
   - ✅ Test `UserScope.enforce_user()` for Employee Operators
   - ✅ Test `EntityScopingService.get_scope_for_entity()` edge cases
   - **Action**: Add unit tests only for scope calculation logic, not HTTP endpoints

3. **No Additional Integration Tests Needed**:
   - Postman E2E already covers integration testing
   - Adding pytest integration tests would be redundant

## Phase 3 Implementation Checklist

### ✅ Critical Priority - COMPLETED

1. **`app/routes/user.py` - DELETE endpoint**
   - [x] Employee Operator blocking added to `DELETE /users/{user_id}` ✅
   - [x] Existence-then-scope check implemented (same pattern as GET/PUT) ✅
   - [x] Tested in Postman: Employee Operator gets 403 when trying to delete other users ✅

2. **`app/routes/user.py` - Enriched endpoint**
   - [x] `GET /users/enriched/{user_id}` has Employee Operator blocking ✅
   - [x] Uses same pattern as GET /users/{user_id} ✅

### ✅ Medium Priority - COMPLETED

3. **`app/routes/address.py` - Employee Operator blocking**
   - [x] `POST /addresses/` blocks Employee Operators from creating addresses for others ✅
   - [x] `PUT /addresses/{address_id}` blocks Employee Operators from updating addresses for others ✅
   - [x] `DELETE /addresses/{address_id}` blocks Employee Operators from deleting addresses for others ✅
   - **Note**: Uses `get_user_scope().enforce_user_assignment()` which handles Employee Operators correctly ✅

### Low Priority (Nice to Have)

4. **Other Routes** (if they allow managing resources for others):
   - Most routes use `EntityScopingService.get_scope_for_entity()` which is already correct
   - Only routes that need explicit Employee Operator blocking (not just scope) need updates

## Implementation Pattern

### Pattern for Routes with Employee Operator Blocking

```python
# Standard pattern for routes that manage resources for others
role_type = current_user.get("role_type")
role_name = current_user.get("role_name")

# Block Employee Operators from managing others
if role_type == "Employee" and role_name == "Operator":
    # Check if this is a self-operation
    if resource_user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Employee Operators can only manage their own resources"
        )
    scope = None  # Self-operation only
else:
    # Use EntityScopingService for scope determination
    scope = EntityScopingService.get_scope_for_entity(ENTITY_RESOURCE, current_user)
    # ... rest of logic
```

## Next Steps

1. **Fix DELETE /users/{user_id}** - Add Employee Operator blocking
2. **Verify GET /users/enriched/{user_id}** - Ensure Employee Operator blocking
3. **Verify address routes** - Ensure Employee Operator blocking works correctly
4. **Update roadmap** - Mark Phase 3 as complete
5. **Skip extensive unit tests** - Postman E2E already covers permissions testing

