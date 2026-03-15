# Institution Scoping for Standard (Non-Enriched) Endpoints - Roadmap

## Problem Statement

Currently, **enriched endpoints** use `EnrichedService` which supports JOIN-based institution scoping via `institution_table_alias`. However, **standard (non-enriched) endpoints** use `CRUDService`, which only supports direct `institution_id` column filtering.

### Current State

#### Tables with Direct `institution_id` Column
These work seamlessly with `CRUDService` scoping:
- `user_info` ✅
- `institution_info` ✅
- `product_info` ✅
- `institution_entity_info` ✅
- `address_info` ✅
- `qr_code` (via `restaurant_id` → but actually needs JOIN) ⚠️

#### Tables Requiring JOIN-Based Scoping
These need manual implementation (like `plate_kitchen_days`):
- `plate_kitchen_days` → `plate_info` → `restaurant_info` → `institution_id` ❌
- `plate_info` → `restaurant_info` → `institution_id` ❌
- `plate_pickup_live` → `restaurant_info` → `institution_id` ❌
- `restaurant_transaction` → `restaurant_info` → `institution_id` ❌
- `restaurant_balance_info` → `restaurant_info` → `institution_id` ❌
- `qr_code` → `restaurant_info` → `institution_id` ❌

### Current Implementation Issues

**Example: `plate_kitchen_days` standard endpoints**
- **Lines of code**: ~70 lines for GET /, ~30 lines for GET /{id}, ~50 lines for POST, etc.
- **Manual JOIN queries**: Each endpoint manually constructs JOIN queries
- **Code duplication**: Similar logic repeated across endpoints
- **Inconsistency**: Enriched endpoints use framework, standard endpoints use manual code
- **Security risk**: Manual implementation increases chance of missing scoping checks

**Example: `plate_kitchen_days` enriched endpoints**
- **Lines of code**: ~10 lines per endpoint (uses `EnrichedService`)
- **Consistent**: Uses framework pattern
- **Secure**: Scoping handled automatically

## Proposed Solutions

### Option 1: Extend CRUDService with JOIN-Based Scoping (Recommended)

**Approach**: Add optional JOIN configuration to `CRUDService` similar to `EnrichedService`.

**Benefits**:
- ✅ Consistent with existing `CRUDService` pattern
- ✅ Minimal changes to existing code
- ✅ Reuses proven `EnrichedService` JOIN logic
- ✅ Backward compatible (existing services unaffected)

**Implementation**:
```python
class CRUDService(Generic[T]):
    def __init__(
        self,
        table_name: str,
        dto_class: Type[T],
        id_column: str,
        institution_column: Optional[str] = None,
        # NEW: JOIN-based scoping support
        institution_join_path: Optional[List[Tuple[str, str, str]]] = None
        # Format: [("table", "alias", "join_condition"), ...]
        # Example: [("plate_info", "p", "pkd.plate_id = p.plate_id"),
        #          ("restaurant_info", "r", "p.restaurant_id = r.restaurant_id")]
        institution_table_alias: Optional[str] = None  # Alias where institution_id exists
    ):
        # ... existing code ...
        self.institution_join_path = institution_join_path
        self.institution_table_alias = institution_table_alias or table_alias
```

**Modified `get_all()` method**:
```python
def get_all(self, db, limit=None, *, scope=None):
    if scope and not scope.is_global and self.institution_join_path:
        # Use JOIN-based scoping
        query = self._build_join_query_with_scope(scope)
    else:
        # Use existing direct column scoping
        query = self._build_direct_query_with_scope(scope)
    # ... execute query ...
```

**Example Usage**:
```python
plate_kitchen_days_service = CRUDService(
    "plate_kitchen_days",
    PlateKitchenDaysDTO,
    "plate_kitchen_day_id",
    institution_join_path=[
        ("plate_info", "p", "pkd.plate_id = p.plate_id"),
        ("restaurant_info", "r", "p.restaurant_id = r.restaurant_id")
    ],
    institution_table_alias="r"  # institution_id is on restaurant_info
)
```

**Effort**: Medium (2-3 days)
- Modify `CRUDService.__init__` and `get_all()`, `get_by_id()`, `create()`, `update()`
- Add `_build_join_query_with_scope()` helper method
- Update `plate_kitchen_days_service` initialization
- Test with existing endpoints


### Option 2: Keep Manual Implementation (Status Quo)

**Approach**: Continue with manual JOIN queries in route handlers.

**Benefits**:
- ✅ No framework changes needed
- ✅ Full control over queries

**Drawbacks**:
- ❌ Code duplication
- ❌ Inconsistency with enriched endpoints
- ❌ Security risk (easy to miss scoping)
- ❌ Maintenance burden

**Effort**: None (already done) but not recommended

## Centralized Scoping Architecture

### Problem: Scoping Logic Scattered Across Routes

Currently, scoping determination is duplicated across routes:
- Each route manually calls `get_institution_scope(current_user)`
- Some routes have custom logic (e.g., `_get_scope_for_user()` in `plate_kitchen_days.py`)
- Base and enriched endpoints in the same route file duplicate scope determination
- No single source of truth for scoping rules per entity

**Example of Current Duplication**:
```python
# In plate_kitchen_days.py - base endpoint
scope = _get_scope_for_user(current_user)  # Custom logic

# In plate_kitchen_days.py - enriched endpoint  
scope = _get_scope_for_user(current_user)  # Same logic duplicated
```

### Solution: Entity-Based Scoping Service

Create a centralized `EntityScopingService` that:
1. **Determines scope based on entity type**: Each entity has its own scoping rules
2. **Handles special cases**: Customer blocking, role-based access, etc.
3. **Returns consistent scope**: Same scope for base and enriched endpoints
4. **Single source of truth**: All scoping rules in one place

**Architecture**:
```python
# app/security/entity_scoping.py
class EntityScopingService:
    """Centralized scoping determination for all entities"""
    
    @staticmethod
    def get_scope_for_entity(
        entity_type: str,
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Get institution scope for a specific entity type.
        
        Args:
            entity_type: Entity identifier (e.g., "plate_kitchen_days", "restaurant_balance")
            current_user: Current authenticated user
            **kwargs: Additional context (e.g., for user-level scoping)
            
        Returns:
            InstitutionScope or None (for global access)
        """
        # Entity-specific scoping rules
        rules = {
            "plate_kitchen_days": EntityScopingService._scope_plate_kitchen_days,
            "restaurant_balance": EntityScopingService._scope_restaurant_balance,
            "restaurant_transaction": EntityScopingService._scope_restaurant_transaction,
            # ... etc
        }
        
        rule = rules.get(entity_type)
        if rule:
            return rule(current_user, **kwargs)
        
        # Default: standard institution scoping
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_plate_kitchen_days(current_user: dict, **kwargs) -> Optional[InstitutionScope]:
        """Scoping rules for plate_kitchen_days"""
        role_type = current_user.get("role_type")
        
        # Block Customers
        if role_type == "Customer":
            raise HTTPException(403, "Forbidden: Customers cannot access plate kitchen days")
        
        # Employees: global access
        if role_type == "Employee":
            return None
        
        # Suppliers: institution-scoped
        if role_type == "Supplier":
            return get_institution_scope(current_user)
        
        return None
```

**Route Usage**:
```python
# Before (duplicated)
scope = _get_scope_for_user(current_user)  # Base endpoint
scope = _get_scope_for_user(current_user)  # Enriched endpoint

# After (centralized)
scope = EntityScopingService.get_scope_for_entity("plate_kitchen_days", current_user)
# Both base and enriched endpoints use the same scope
```

**Benefits**:
- ✅ Single source of truth for scoping rules
- ✅ Consistent scope for base and enriched endpoints
- ✅ Easy to update scoping rules (change in one place)
- ✅ Entity-specific rules (Customer blocking, etc.) centralized
- ✅ Routes become simpler (just call the service)

## Service Impact Analysis

### Services Requiring JOIN-Based Scoping

#### 1. **plate_kitchen_days_service** ⚠️ HIGH IMPACT
**Current Usage**:
- `app/routes/plate_kitchen_days.py`: GET /, GET /{id}, POST /, PUT /{id}, DELETE /{id}
- `app/routes/plate_selection.py`: Legacy endpoints (POST /kitchen-days/{plate_id}, GET /kitchen-days/{plate_id})
- `app/services/plate_selection_service.py`: `_fetch_plate_selection_context()` - fetches kitchen days for plate

**Required Changes**:
- ✅ Routes already have manual scoping (can be simplified after framework)
- ⚠️ Business logic service needs scope parameter: `plate_kitchen_days_service.get_all(db, scope=scope)`
- ⚠️ Legacy routes in `plate_selection.py` need scope support (or deprecate)

**Effort**: Medium (1 day)
- Update service calls in `plate_selection_service.py` to pass scope
- Update legacy routes or mark as deprecated
- Simplify new routes to use framework

#### 2. **plate_service** ✅ LOW IMPACT
**Current Usage**:
- `app/routes/plate_kitchen_days.py`: Validation only (`get_by_id()`)
- `app/services/plate_selection_service.py`: Business logic (`get_by_id()`)
- `app/services/plate_pickup_service.py`: Business logic (`get_by_id()`)

**Required Changes**:
- ✅ Mostly used for validation (no scoping needed)
- ✅ Already has `institution_scoped=True` in route factory
- ⚠️ Business logic services may need scope for future features

**Effort**: Low (0.5 day)
- Verify business logic doesn't need scoping (currently doesn't)
- Add scope parameter to service calls if needed in future

#### 3. **plate_pickup_live_service** ⚠️ MEDIUM IMPACT
**Current Usage**:
- `app/services/plate_pickup_service.py`: `_get_and_validate_pickup_record()`, `_update_pickup_record_arrival()`
- `app/routes/plate_pickup.py`: Uses business logic service (scoping handled in routes)

**Required Changes**:
- ⚠️ Business logic service uses `get_by_id()` - may need scope for validation
- ✅ Routes already handle user-level scoping (customers see own pickups)
- ⚠️ Need to verify institution scoping for Suppliers

**Effort**: Medium (1 day)
- Review if Suppliers need institution-scoped pickup access
- Add scope parameter to service calls if needed
- Update unit tests

#### 4. **restaurant_transaction_service** ⚠️ MEDIUM IMPACT
**Current Usage**:
- `app/services/plate_selection_service.py`: Creates transactions
- `app/services/plate_pickup_service.py`: Updates transactions on arrival
- `app/routes/restaurant_transaction.py`: Read-only routes (already has manual scoping)

**Required Changes**:
- ✅ Routes already have manual JOIN-based scoping (can be simplified)
- ⚠️ Business logic services create/update transactions - may need scope validation
- ⚠️ Need to ensure Suppliers can only see their institution's transactions

**Effort**: Medium (1 day)
- Simplify routes to use framework
- Review business logic for scope validation needs
- Update unit tests

#### 5. **restaurant_balance_service** ⚠️ MEDIUM IMPACT
**Current Usage**:
- `app/routes/restaurant_balance.py`: Read-only routes (already has manual scoping)
- `app/services/billing/institution_billing.py`: Business logic (creates/updates balances)

**Required Changes**:
- ✅ Routes already have manual JOIN-based scoping (can be simplified)
- ✅ Business logic creates balances automatically (no user scoping needed)
- ⚠️ Need to ensure Suppliers can only see their institution's balances

**Effort**: Medium (1 day)
- Simplify routes to use framework
- Verify business logic doesn't need changes
- Update unit tests

#### 6. **qr_code_service** ✅ LOW IMPACT
**Current Usage**:
- `app/routes/qr_code.py`: Already uses `scope` parameter! ✅
- `app/services/plate_selection_service.py`: Business logic (`get_by_restaurant_id()`)
- `app/services/plate_pickup_service.py`: Business logic (`_validate_qr_code_by_payload()`)

**Required Changes**:
- ✅ Routes already properly scoped
- ⚠️ Business logic services may need scope for validation
- ⚠️ `get_by_restaurant_id()` helper may need scope support

**Effort**: Low (0.5 day)
- Review business logic for scope needs
- Update helper functions if needed

### Unit Test Impact Analysis

#### Existing Unit Tests Requiring Updates

1. **test_plate_selection_service.py** (14 tests)
   - Tests `create_plate_selection_with_transactions()`
   - Uses `plate_kitchen_days_service.get_all()` - needs scope mocking
   - **Effort**: 0.5 day

2. **test_plate_pickup_service.py** (8 tests)
   - Tests `PlatePickupService` methods
   - Uses `plate_pickup_live_service.get_by_id()` - may need scope mocking
   - **Effort**: 0.5 day

3. **test_credit_loading_service.py** (10+ tests)
   - Tests restaurant transaction creation
   - May need scope validation tests
   - **Effort**: 0.5 day

4. **test_entity_service.py** (various tests)
   - Tests entity service functions
   - May need scope-related tests
   - **Effort**: 0.5 day

5. **New: test_crud_service.py** (NEW - needs creation)
   - Test JOIN-based scoping in `CRUDService`
   - Test backward compatibility
   - Test all CRUD operations with JOIN scoping
   - **Effort**: 1 day

**Total Unit Test Effort**: 3 days

## Recommended Approach: Option 1 with Centralized Scoping

### Implementation Plan

#### Phase 0: Create Centralized Scoping Service (1 day)
1. **Create `EntityScopingService`** (0.5 day)
   - Create `app/security/entity_scoping.py`
   - Implement `get_scope_for_entity(entity_type, current_user)` method
   - Add entity-specific scoping rules:
     - `plate_kitchen_days`: Block Customers, Employees global, Suppliers scoped
     - `restaurant_balance`: Standard institution scoping
     - `restaurant_transaction`: Standard institution scoping
     - `plate_pickup_live`: User-level scoping for Customers, institution for Suppliers
     - Default: Standard `get_institution_scope()` behavior
   - Document all scoping rules in docstrings

2. **Create scoping registry** (0.5 day)
   - Define entity type constants (e.g., `ENTITY_PLATE_KITCHEN_DAYS = "plate_kitchen_days"`)
   - Create mapping of entity types to scoping rules
   - Add validation for unknown entity types

3. **Update routes to use centralized scoping** (0.5 day)
   - Update `plate_kitchen_days.py` to use `EntityScopingService`
   - Update `restaurant_balance.py` to use `EntityScopingService`
   - Update `restaurant_transaction.py` to use `EntityScopingService`
   - Verify base and enriched endpoints use same scope

**Deliverable**: All routes use centralized scoping, base and enriched endpoints share scope

#### Phase 1: Extend CRUDService & Unit Tests (4-5 days)
1. **Add JOIN configuration to `CRUDService.__init__`** (0.5 day)
   - Add `institution_join_path: Optional[List[Tuple[str, str, str]]]`
   - Add `institution_table_alias: Optional[str]`
   - Update docstrings with examples

2. **Add JOIN query builder method** (0.5 day)
   - `_build_join_query_with_scope()`: Constructs JOIN query with scoping
   - Reuse logic from `EnrichedService._build_where_clause()`
   - Handle both direct column and JOIN-based scoping

3. **Modify CRUD methods to support JOIN scoping** (1 day)
   - `get_all()`: Check for `institution_join_path`, use JOIN query if present
   - `get_by_id()`: Check for `institution_join_path`, use JOIN query if present
   - `create()`: Validate via JOIN if `institution_join_path` exists
   - `update()`: Validate via JOIN if `institution_join_path` exists
   - `soft_delete()`: Validate via JOIN if `institution_join_path` exists

4. **Create comprehensive unit tests for CRUDService** (1 day)
   - Create `app/tests/services/test_crud_service.py`
   - Test JOIN-based scoping for all CRUD operations
   - Test backward compatibility (direct column scoping still works)
   - Test edge cases (no scope, global scope, supplier scope)
   - Test with multiple JOIN paths

5. **Update service initializations** (0.5 day)
   - `plate_kitchen_days_service`: Add JOIN configuration
   - `restaurant_transaction_service`: Add JOIN configuration
   - `restaurant_balance_service`: Add JOIN configuration
   - `plate_pickup_live_service`: Add JOIN configuration (if needed)
   - `qr_code_service`: Add JOIN configuration (already has routes scoped, verify)
   - `plate_service`: Verify if needed (already has direct scoping via route factory)

#### Phase 2: Refactor Existing Manual Implementations (2-3 days) ✅ **COMPLETE**
1. **Refactor `plate_kitchen_days` routes** (0.5 day) ✅
   - ✅ Removed manual JOIN queries (~70 lines → ~10 lines)
   - ✅ Use `plate_kitchen_days_service.get_all(db, scope=scope)`
   - ✅ Use `plate_kitchen_days_service.get_by_id(id, db, scope=scope)`
   - ✅ Simplified route handlers

2. **Refactor `restaurant_balance` routes** (0.5 day) ✅
   - ✅ Removed manual JOIN queries (~50 lines → ~10 lines)
   - ✅ Use `restaurant_balance_service.get_all(db, scope=scope)`
   - ✅ Use `restaurant_balance_service.get_by_id(id, db, scope=scope)`

3. **Refactor `restaurant_transaction` routes** (0.5 day) ✅
   - ✅ Removed manual JOIN queries (~50 lines → ~10 lines)
   - ✅ Use `restaurant_transaction_service.get_all(db, scope=scope)`
   - ✅ Use `restaurant_transaction_service.get_by_id(id, db, scope=scope)`

4. **Update business logic services** (1 day) ✅
   - ✅ `plate_selection_service.py`: Added scope parameter to `plate_kitchen_days_service.get_all()` call
   - ✅ `plate_pickup_service.py`: Reviewed - no scope needed (user-level scoping)
   - ✅ `credit_loading_service.py`: Reviewed - no scope needed (system-level operations)
   - ✅ Verified all service calls pass scope correctly

5. **Update legacy routes** (0.5 day) ✅
   - ✅ `app/routes/plate_selection.py`: Updated kitchen-days endpoints to use scope
   - ✅ Added deprecation notices for backward compatibility

#### Phase 3: Refactor Unit Tests & Integration Testing (2-3 days) 🟡 **IN PROGRESS**
1. **Refactor existing unit tests** (1.5 days) 🟡
   - ✅ `test_plate_selection_service.py`: Added scope mocking for `plate_kitchen_days_service.get_all()`
   - ⏳ `test_plate_pickup_service.py`: Add scope mocking if needed
   - ⏳ `test_credit_loading_service.py`: Add scope validation tests
   - ⏳ `test_entity_service.py`: Add scope-related tests
   - ✅ Updated mocks to support scope parameter

2. **Integration tests with Postman** (0.5 day)
   - Test `plate_kitchen_days` endpoints with scoping (Suppliers vs Employees)
   - Test `restaurant_balance` endpoints with scoping
   - Test `restaurant_transaction` endpoints with scoping
   - Verify backward compatibility (existing Postman collections still work)

3. **Documentation** (0.5 day)
   - Update `CRUDService` docstrings with JOIN-based scoping examples
   - Update `SCOPING_SYSTEM.md` with new pattern
   - Add migration guide for services using JOIN-based scoping
   - Document unit test patterns for scoped services

### Migration Strategy

**Backward Compatibility**:
- Existing services without `institution_join_path` continue to work
- Direct `institution_column` scoping remains unchanged
- No breaking changes

**Incremental Adoption**:
- Migrate one service at a time
- Test thoroughly before moving to next
- Can keep manual implementations during transition

### Security Benefits

1. **Consistency**: All endpoints use same scoping mechanism
2. **Reduced Risk**: Framework handles scoping, less chance of human error
3. **Auditability**: Scoping logic centralized, easier to review
4. **Maintainability**: Changes to scoping logic affect all endpoints automatically

### Code Reduction Estimate

**Before** (manual implementation):
- `plate_kitchen_days` routes: ~200 lines of scoping logic
- `restaurant_balance` routes: ~100 lines of scoping logic
- `restaurant_transaction` routes: ~100 lines of scoping logic
- Business logic services: ~50 lines of manual validation
- **Total**: ~450 lines

**After** (framework-based):
- `plate_kitchen_days` routes: ~50 lines (75% reduction)
- `restaurant_balance` routes: ~30 lines (70% reduction)
- `restaurant_transaction` routes: ~30 lines (70% reduction)
- Business logic services: ~10 lines (framework handles it)
- Framework code: +200 lines (one-time)
- **Total**: ~320 lines

**Net Result**: ~130 lines eliminated, better security, easier maintenance, consistent pattern

### Total Effort Estimate

| Phase | Tasks | Effort |
|-------|-------|--------|
| **Phase 0** | Create Centralized Scoping Service | 1 day |
| **Phase 1** | Extend CRUDService + Unit Tests | 4-5 days |
| **Phase 2** | Refactor Routes + Business Logic | 2-3 days | ✅ **COMPLETE** |
| **Phase 3** | Refactor Tests + Integration + Docs | 2-3 days | 🟡 **IN PROGRESS** |
| **Total** | | **9-12 days** |

## Decision Matrix

| Criteria | Option 1 | Option 2 |
|----------|----------|----------|
| **Code Reduction** | ⭐⭐⭐⭐⭐ | ⭐ |
| **Security** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Consistency** | ⭐⭐⭐⭐⭐ | ⭐ |
| **Maintainability** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Effort** | Medium (9-12 days) | None |
| **Backward Compat** | ✅ | ✅ |
| **Recommended** | ✅ | ❌ |

## Next Steps

1. **Review this roadmap** with team
2. **Approve Option 1** (extend CRUDService)
3. **Create implementation tickets** for Phase 1-3
4. **Start with Phase 1** (extend CRUDService)
5. **Migrate `plate_kitchen_days`** as proof of concept
6. **Migrate other services** incrementally

## Scoping Architecture Decision

### Should Routes Handle Scoping or Just Endpoint Handling?

**Recommendation**: **Routes should determine scope, endpoints should apply it**

**Rationale**:
1. **Routes are the entry point**: They have access to `current_user` and can determine appropriate scope
2. **Consistency**: Base and enriched endpoints in the same route file should use the same scope
3. **Separation of concerns**: 
   - Routes: Determine scope based on entity type and user role
   - Services (CRUDService/EnrichedService): Apply scope to queries
4. **Flexibility**: Routes can handle special cases (Customer blocking, etc.) before passing scope to services

**Architecture**:
```
Route Handler
    ↓
EntityScopingService.get_scope_for_entity(entity_type, current_user)
    ↓
Returns: InstitutionScope (or None for global)
    ↓
Pass to: CRUDService.get_all(db, scope=scope)  [Base endpoint]
    ↓
Pass to: EnrichedService.get_enriched(db, scope=scope)  [Enriched endpoint]
```

**Benefits**:
- ✅ Routes control scoping rules (can block Customers, etc.)
- ✅ Services just apply the scope they receive
- ✅ Base and enriched endpoints automatically share scope
- ✅ Centralized scoping rules in `EntityScopingService`

**Alternative Considered**: Services determine scope internally
- ❌ Services would need `current_user` parameter (breaks separation)
- ❌ Harder to handle special cases (Customer blocking, etc.)
- ❌ Less flexible for future requirements

## Questions to Resolve

1. **Priority**: Is this a high priority security improvement or nice-to-have?
2. **Timeline**: Can we allocate 9-12 days for this refactoring?
3. **Scope**: Should we migrate all affected services or just `plate_kitchen_days`?
4. **Testing**: Do we have sufficient test coverage to safely refactor?
5. **Unit Tests**: Should we refactor all existing unit tests in Phase 1 or Phase 3?
6. **Scoping Architecture**: Confirm routes determine scope, services apply it (recommended approach)

## Implementation Notes

### Unit Test Refactoring Strategy

**Approach**: Refactor unit tests in Phase 1 (alongside framework implementation) to ensure:
- Framework is properly tested before route refactoring
- Backward compatibility is verified
- Patterns are established for future tests

**Test Patterns to Establish**:
```python
# Example: Testing JOIN-based scoping in CRUDService
def test_get_all_with_join_scoping():
    # Test that JOIN-based scoping filters correctly
    # Test that global scope (Employees) sees all records
    # Test that supplier scope filters by institution
    pass

# Example: Testing service calls with scope
@patch('app.services.crud_service.plate_kitchen_days_service')
def test_plate_selection_with_scope(mock_service):
    # Mock service to accept scope parameter
    # Verify scope is passed correctly
    pass
```

### Service Migration Priority

1. **High Priority** (Security Critical):
   - `plate_kitchen_days_service` - New API, needs proper scoping
   - `restaurant_balance_service` - Financial data, needs scoping
   - `restaurant_transaction_service` - Financial data, needs scoping

2. **Medium Priority** (Business Logic):
   - `plate_pickup_live_service` - May need scoping for Suppliers
   - `qr_code_service` - Already scoped in routes, verify business logic

3. **Low Priority** (Validation Only):
   - `plate_service` - Mostly used for validation, already scoped in routes

### Centralized Scoping Benefits

**Before** (Current State):
- Each route manually determines scope
- Base and enriched endpoints duplicate scope logic
- Scoping rules scattered across route files
- Hard to maintain consistency

**After** (With EntityScopingService):
- Single function call: `EntityScopingService.get_scope_for_entity("plate_kitchen_days", current_user)`
- Base and enriched endpoints automatically share scope
- All scoping rules in one place (`entity_scoping.py`)
- Easy to update scoping rules (change once, affects all endpoints)
- Consistent behavior across platform

**Example Route Pattern**:
```python
@router.get("/", response_model=List[PlateKitchenDayResponseSchema])
def list_plate_kitchen_days(current_user: dict = Depends(get_current_user), ...):
    # Centralized scoping - same for base and enriched
    scope = EntityScopingService.get_scope_for_entity("plate_kitchen_days", current_user)
    return plate_kitchen_days_service.get_all(db, scope=scope)

@router.get("/enriched/", response_model=List[PlateKitchenDayEnrichedResponseSchema])
def list_enriched_plate_kitchen_days(current_user: dict = Depends(get_current_user), ...):
    # Same scope as base endpoint automatically
    scope = EntityScopingService.get_scope_for_entity("plate_kitchen_days", current_user)
    return get_enriched_plate_kitchen_days(db, scope=scope)
```

## Related Documents

- `docs/api/SCOPING_SYSTEM.md` - Current scoping system documentation
- `docs/api/ENRICHED_ENDPOINT_PATTERN.md` - Enriched endpoint pattern
- `app/services/crud_service.py` - Current CRUDService implementation
- `app/services/enriched_service.py` - EnrichedService with JOIN scoping

