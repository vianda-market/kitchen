# Enriched Endpoints DRY Refactoring Roadmap

## Overview

This document outlines opportunities to apply the DRY (Don't Repeat Yourself) principle to the enriched endpoint functions in `app/services/entity_service.py`. Currently, there are 12+ enriched endpoint functions that share significant structural similarities.

## Current State Analysis

### Enriched Endpoint Functions Identified

1. `get_enriched_users()` / `get_enriched_user_by_id()`
2. `get_enriched_institution_entities()` / `get_enriched_institution_entity_by_id()`
3. `get_enriched_addresses()` / `get_enriched_address_by_id()`
4. `get_enriched_restaurants()` / `get_enriched_restaurant_by_id()`
5. `get_enriched_qr_codes()` / `get_enriched_qr_code_by_id()`
6. `get_enriched_products()` / `get_enriched_product_by_id()`
7. `get_enriched_plates()` / `get_enriched_plate_by_id()`
8. `get_enriched_plans()` / `get_enriched_plan_by_id()`
9. `get_enriched_subscriptions()` / `get_enriched_subscription_by_id()`
10. `get_enriched_institution_bills()`
11. `get_enriched_plate_pickups()`

### Common Patterns Identified

#### 1. **Condition Building Pattern** (Repeated 13+ times)
```python
conditions = []
params: List[Any] = []

# Filter by archived status
if not include_archived:
    conditions.append("table.is_archived = FALSE")

# Apply institution scoping
if scope and not scope.is_global and scope.institution_id:
    conditions.append("table.institution_id = %s")
    params.append(scope.institution_id)

where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
```

#### 2. **Query Execution Pattern** (Repeated 13+ times)
```python
results = db_read(
    query,
    tuple(params) if params else None,
    connection=db,
    fetch_one=False  # or True for by_id functions
)

if not results:
    return []
```

#### 3. **UUID Conversion Pattern** (Repeated 6+ times)
```python
# Convert UUID objects to strings for Pydantic validation
for row in results:
    row_dict = dict(row)
    for key, value in row_dict.items():
        if isinstance(value, UUID):
            row_dict[key] = str(value)
    enriched_items.append(Schema(**row_dict))
```

#### 4. **Error Handling Pattern** (Repeated 13+ times)
```python
try:
    # ... query logic ...
except HTTPException:
    raise
except Exception as e:
    log_error(f"Error getting enriched {entity}: {e}")
    raise HTTPException(status_code=500, detail=f"Failed to get enriched {entity}")
```

#### 5. **Scope Filtering Pattern** (Repeated 10+ times)
```python
# Apply institution scoping (for Suppliers - filter by institution)
if scope and not scope.is_global and scope.institution_id:
    conditions.append("table.institution_id = %s::uuid")
    params.append(str(scope.institution_id))
```

#### 6. **Schema Validation Pattern** (Repeated 13+ times)
```python
enriched_items = [EnrichedSchema(**result) for result in results]
```

#### 7. **List vs Single Item Pattern** (Repeated 13+ times)
- List functions: `fetch_one=False`, return `List[Schema]`
- By-ID functions: `fetch_one=True`, return `Optional[Schema]`

## DRY Violations Summary

### High Priority (Affects 10+ functions)

1. **Condition Building Logic**: Repeated condition/params/where_clause building
2. **UUID Conversion**: Repeated UUID-to-string conversion logic
3. **Error Handling**: Identical try/except blocks
4. **Query Execution**: Repeated db_read calls with similar patterns

### Medium Priority (Affects 5-9 functions)

1. **Scope Filtering**: Similar but slightly different scope application logic
2. **Schema Validation**: Direct schema instantiation (could be abstracted)
3. **Empty Result Handling**: Repeated `if not results: return []`

### Low Priority (Affects 2-4 functions)

1. **User-level Filtering**: Only in `get_enriched_plate_pickups()`
2. **Special JOIN Logic**: Some endpoints have unique JOIN requirements

## Proposed Refactoring Strategy

### Phase 1: Extract Common Utilities (Low Risk)

**Goal**: Create helper functions for repeated patterns without changing function signatures.

#### 1.1 Create `build_where_clause()` Helper
```python
def build_where_clause(
    include_archived: bool = False,
    scope: Optional[InstitutionScope] = None,
    table_alias: str = "t",
    institution_column: str = "institution_id",
    additional_conditions: Optional[List[Tuple[str, Any]]] = None
) -> Tuple[str, List[Any]]:
    """
    Build WHERE clause and parameters for enriched queries.
    
    Args:
        include_archived: Whether to include archived records
        scope: Optional institution scope for filtering
        table_alias: Table alias used in query (e.g., "u", "r", "iba")
        institution_column: Column name for institution_id
        additional_conditions: List of (condition, param) tuples
        
    Returns:
        Tuple of (where_clause, params)
    """
```

#### 1.2 Create `convert_uuids_to_strings()` Helper
```python
def convert_uuids_to_strings(row_dict: dict) -> dict:
    """
    Convert UUID objects to strings in a row dictionary.
    
    Args:
        row_dict: Dictionary from database query
        
    Returns:
        Dictionary with UUIDs converted to strings
    """
```

#### 1.3 Create `execute_enriched_query()` Helper
```python
def execute_enriched_query(
    query: str,
    params: Optional[List[Any]],
    db: psycopg2.extensions.connection,
    fetch_one: bool = False
) -> Optional[List[dict]]:
    """
    Execute enriched query with standard error handling.
    
    Args:
        query: SQL query string
        params: Query parameters
        db: Database connection
        fetch_one: Whether to fetch single result
        
    Returns:
        List of dictionaries or None if fetch_one and no result
    """
```

### Phase 2: Create Generic Enriched Query Builder (Medium Risk)

**Goal**: Create a generic function that handles the common enriched query pattern.

#### 2.1 Create `build_enriched_query()` Function
```python
def build_enriched_query(
    base_table: str,
    table_alias: str,
    select_fields: List[str],
    joins: List[Tuple[str, str, str]],  # (table, alias, join_condition)
    where_conditions: Optional[List[str]] = None,
    where_params: Optional[List[Any]] = None,
    order_by: str = "created_date DESC"
) -> str:
    """
    Build a complete enriched SQL query.
    
    Args:
        base_table: Main table name
        table_alias: Alias for main table
        select_fields: List of SELECT fields
        joins: List of JOIN clauses
        where_conditions: Additional WHERE conditions
        where_params: Parameters for WHERE conditions
        order_by: ORDER BY clause
        
    Returns:
        Complete SQL query string
    """
```

### Phase 3: Create Generic Enriched Service (High Risk, High Reward)

**Goal**: Create a generic enriched service class similar to `CRUDService`.

#### 3.1 Create `EnrichedService` Class
```python
class EnrichedService:
    """
    Generic service for enriched endpoint queries.
    Handles common patterns: condition building, query execution, UUID conversion, error handling.
    """
    
    def __init__(
        self,
        base_table: str,
        table_alias: str,
        schema_class: Type[BaseModel],
        institution_column: Optional[str] = None
    ):
        self.base_table = base_table
        self.table_alias = table_alias
        self.schema_class = schema_class
        self.institution_column = institution_column
    
    def get_enriched(
        self,
        db: psycopg2.extensions.connection,
        *,
        scope: Optional[InstitutionScope] = None,
        include_archived: bool = False,
        select_fields: List[str],
        joins: List[Tuple[str, str, str]],
        additional_conditions: Optional[List[Tuple[str, Any]]] = None,
        order_by: str = "created_date DESC"
    ) -> List[BaseModel]:
        """
        Generic enriched query execution.
        """
```

## Phase Dependency Analysis

### Can We Jump to Phase 3?

**Short Answer**: Yes, but with trade-offs.

**Phase 3 would incorporate Phase 1 & 2 logic internally** (similar to how `CRUDService` has all logic built-in rather than using separate helpers). So:

- **If we do Phase 1 & 2 first**: We build helpers that existing functions use, then Phase 3 could either:
  - Use those helpers internally (reuse), OR
  - Have its own implementation (deprecate helpers)
  
- **If we jump to Phase 3**: We build the service class with all logic built-in (like `CRUDService`), and Phase 1 & 2 helpers are never created.

### Sequential vs. Direct Approach

#### Sequential Approach (Phase 1 → 2 → 3)
**Pros**:
- ✅ **Lower risk**: Each phase is independently testable
- ✅ **Incremental value**: Phase 1 gives immediate benefits (~30-40% code reduction)
- ✅ **Learning curve**: Understand patterns before building the big solution
- ✅ **Incremental migration**: Can migrate endpoints one phase at a time
- ✅ **Rollback safety**: If Phase 3 fails, Phase 1/2 improvements remain

**Cons**:
- ❌ **More total work**: Building helpers that may be replaced
- ❌ **Slower overall**: Three separate refactoring cycles
- ❌ **Potential deprecation**: Phase 1/2 helpers might be replaced by Phase 3

#### Direct Approach (Jump to Phase 3)
**Pros**:
- ✅ **Faster overall**: One refactoring cycle instead of three
- ✅ **More cohesive**: All logic in one place (like `CRUDService`)
- ✅ **No wasted work**: Don't build helpers that get replaced
- ✅ **Cleaner architecture**: Service class is the single abstraction

**Cons**:
- ❌ **Higher risk**: Bigger change, harder to test incrementally
- ❌ **All-or-nothing**: Can't get partial benefits if Phase 3 has issues
- ❌ **Larger migration**: Need to migrate all endpoints at once (or in bigger chunks)

### Recommendation

**For this codebase, recommend jumping to Phase 3** because:

1. **You already have `CRUDService` pattern**: The team is familiar with class-based generic services
2. **Enriched endpoints are similar enough**: The patterns are consistent enough to abstract
3. **Faster delivery**: Get maximum benefit in one go
4. **Cleaner long-term**: One service class is easier to maintain than helpers + service

**However, use incremental migration strategy**:
- Build Phase 3 service class
- Migrate 2-3 endpoints as proof of concept
- Test thoroughly
- Migrate remaining endpoints incrementally

This gives you the benefits of Phase 3 (cohesive design) with the safety of incremental migration.

## Implementation Roadmap

### Option A: Sequential Approach (Phase 1 → 2 → 3)

#### Phase 1: Extract Common Utilities (Estimated: 2-3 hours)
- [ ] Create `build_where_clause()` helper function
- [ ] Create `convert_uuids_to_strings()` helper function
- [ ] Create `execute_enriched_query()` helper function
- [ ] Refactor 2-3 enriched endpoints to use helpers (proof of concept)
- [ ] Test refactored endpoints
- [ ] Refactor remaining enriched endpoints incrementally

**Benefits**:
- Immediate code reduction (~30-40% per function)
- Low risk (no signature changes)
- Easy to test incrementally

#### Phase 2: Generic Query Builder (Estimated: 4-6 hours)
- [ ] Create `build_enriched_query()` function
- [ ] Refactor 2-3 enriched endpoints to use query builder
- [ ] Test and validate
- [ ] Refactor remaining endpoints

**Benefits**:
- Further code reduction (~50-60% per function)
- Standardized query structure
- Easier to maintain SQL patterns

#### Phase 3: Generic Enriched Service (Estimated: 8-12 hours)
- [ ] Design `EnrichedService` class interface
- [ ] Implement core functionality
- [ ] Create migration plan for existing endpoints
- [ ] Migrate 2-3 endpoints as proof of concept
- [ ] Test thoroughly
- [ ] Migrate remaining endpoints incrementally

**Benefits**:
- Maximum code reduction (~70-80% per function)
- Single source of truth for enriched query logic
- Easier to add new enriched endpoints
- Consistent behavior across all endpoints

### Option B: Direct Approach (Jump to Phase 3)

#### Phase 3: Generic Enriched Service (Estimated: 10-14 hours)
- [ ] Design `EnrichedService` class interface (incorporating Phase 1 & 2 logic)
- [ ] Implement core functionality:
  - Condition building (Phase 1 logic)
  - Query building (Phase 2 logic)
  - UUID conversion
  - Error handling
  - Schema validation
- [ ] Create migration plan for existing endpoints
- [ ] Migrate 2-3 endpoints as proof of concept
- [ ] Test thoroughly
- [ ] Migrate remaining endpoints incrementally

**Benefits**:
- Maximum code reduction (~70-80% per function) in one go
- Single source of truth for enriched query logic
- Cleaner architecture (one service class)
- Faster overall delivery
- No intermediate helpers to maintain

**Timeline**: 10-14 hours (vs. 14-21 hours for sequential approach)

## Considerations

### What to Keep Unique

1. **Entity-Specific JOINs**: Each entity has unique relationships
2. **Custom Field Calculations**: Some endpoints have computed fields (e.g., `has_image`, `full_name`)
3. **Special Filtering Logic**: Some endpoints have unique filtering requirements (e.g., user-level filtering)

### Migration Strategy

1. **Incremental Approach**: Refactor 2-3 endpoints at a time
2. **Maintain Backward Compatibility**: Keep existing function signatures
3. **Comprehensive Testing**: Test each refactored endpoint thoroughly
4. **Documentation**: Update docstrings and comments

### Risk Assessment

- **Phase 1**: Low risk - helper functions are easy to test and rollback
- **Phase 2**: Medium risk - query builder needs careful testing
- **Phase 3**: High risk - major architectural change, requires comprehensive testing

## Success Metrics

- **Code Reduction**: Target 50-70% reduction in enriched endpoint code
- **Maintainability**: Easier to add new enriched endpoints
- **Consistency**: All enriched endpoints follow same patterns
- **Test Coverage**: Maintain or improve test coverage

## Timeline Estimate

### Sequential Approach (Phase 1 → 2 → 3)
- **Phase 1**: 1-2 days
- **Phase 2**: 2-3 days
- **Phase 3**: 1-2 weeks (including testing and migration)
- **Total**: 2-3 weeks

### Direct Approach (Jump to Phase 3)
- **Phase 3**: 1.5-2 weeks (including testing and migration)
- **Total**: 1.5-2 weeks

**Time Savings**: ~1 week by jumping to Phase 3

## Decision Matrix

| Factor | Sequential (1→2→3) | Direct (Jump to 3) |
|--------|-------------------|-------------------|
| **Total Time** | 2-3 weeks | 1.5-2 weeks |
| **Risk Level** | Low (incremental) | Medium (bigger change) |
| **Immediate Value** | Yes (Phase 1) | No (all at once) |
| **Code Reduction** | Gradual (30% → 60% → 80%) | All at once (80%) |
| **Maintainability** | Helpers + Service | Service only |
| **Rollback Safety** | High (can stop at any phase) | Medium (all-or-nothing) |
| **Team Familiarity** | New pattern each phase | One pattern (like CRUDService) |

## Strategic Decision: When to Refactor?

### Scenario: Time to Market is NOT an Issue

**Recommendation: Jump to Phase 3 NOW, then build new endpoints with the new method.**

#### Why Refactor Before Building More Endpoints?

1. **Avoid Technical Debt Accumulation**
   - Each new enriched endpoint built the old way = more code to migrate later
   - Current: 13 endpoints to migrate
   - If you build 5 more: 18 endpoints to migrate
   - **Cost**: ~40% more migration work

2. **New Endpoints Start Clean**
   - New endpoints use the clean pattern from day one
   - No need to refactor them later
   - Consistent architecture across all endpoints

3. **Less Total Work Overall**
   - Refactor 13 endpoints now: ~1.5-2 weeks
   - Build 5 new endpoints old way + migrate 18 later: ~2-3 weeks
   - **Savings**: ~1 week of work

4. **Better Developer Experience**
   - Developers learn the new pattern once
   - All future endpoints follow the same pattern
   - Easier onboarding for new developers

#### When to Continue Building Old Way

Only if:
- **Time to market is critical** (not your case)
- **You need endpoints immediately** and can't wait 1-2 weeks
- **You have a hard deadline** that prevents refactoring

### Recommended Approach (Time to Market NOT an Issue)

**Jump to Phase 3 NOW** with this strategy:

1. **Phase 1: Build `EnrichedService` class** (1-2 days)
   - Design the service class interface
   - Implement core functionality
   - Test with unit tests

2. **Phase 2: Migrate existing endpoints** (1 week)
   - Migrate 2-3 endpoints as proof of concept
   - Test thoroughly
   - Migrate remaining 10-11 endpoints incrementally (2-3 at a time)

3. **Phase 3: Build new endpoints with new method** (ongoing)
   - All new enriched endpoints use `EnrichedService` from the start
   - No technical debt accumulation
   - Consistent architecture

**Total Time**: 1.5-2 weeks to refactor existing + establish pattern for future

### Alternative: Continue Building Old Way

If you choose to continue building old way (not recommended if time allows):

1. **Short-term**: Build new endpoints using current pattern
2. **Medium-term**: Accumulate technical debt (more endpoints to migrate)
3. **Long-term**: Larger refactoring effort (more endpoints = more work)

**Cost**: ~40% more migration work for each new endpoint built

## Recommended Approach

**Jump to Phase 3 NOW** with incremental migration strategy:

1. Build `EnrichedService` class (incorporating Phase 1 & 2 logic internally)
2. Migrate 2-3 existing endpoints as proof of concept
3. Test thoroughly
4. Migrate remaining existing endpoints incrementally (2-3 at a time)
5. **Build all new enriched endpoints using `EnrichedService` from the start**

This gives you:
- ✅ Faster delivery (1.5-2 weeks vs. 2-3 weeks)
- ✅ Cleaner architecture (one service class)
- ✅ Safety (incremental migration)
- ✅ Familiar pattern (similar to existing `CRUDService`)
- ✅ **No technical debt accumulation** (new endpoints start clean)
- ✅ **Less total work** (fewer endpoints to migrate)

## Next Steps

1. Review and approve this roadmap
2. **Recommended**: Jump to Phase 3 NOW (since time to market is not an issue)
3. **Alternative**: Start with Phase 1 if you prefer lower-risk incremental approach
4. Design `EnrichedService` class interface
5. Implement and test with 2-3 existing endpoints
6. Migrate remaining existing endpoints incrementally
7. **Build all future enriched endpoints using `EnrichedService`**

