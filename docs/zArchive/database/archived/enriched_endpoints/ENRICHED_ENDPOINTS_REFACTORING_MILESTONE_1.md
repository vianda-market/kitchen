# Enriched Endpoints Refactoring - Milestone 1

## Goal
Create `EnrichedService` class and migrate 2-3 endpoints as proof of concept.

## Success Criteria
- ✅ `EnrichedService` class implemented and tested
- ✅ 2-3 existing endpoints migrated to use `EnrichedService`
- ✅ All tests pass
- ✅ No regression in functionality
- ✅ Code reduction of 70-80% per migrated endpoint

## Timeline
**Estimated: 3-5 days**

## Step-by-Step Implementation

### Step 1: Design `EnrichedService` Class Interface (Day 1, Morning)

**File**: `app/services/enriched_service.py` (new file)

**Key Design Decisions**:
1. **Similar to `CRUDService` pattern** - class-based, generic
2. **Configuration-based** - pass in table names, aliases, JOINs, fields
3. **Flexible** - support custom JOINs, computed fields, special filtering
4. **Type-safe** - use generics for schema types

**Core Methods**:
- `get_enriched()` - List endpoint
- `get_enriched_by_id()` - Single item endpoint
- `_build_where_clause()` - Internal helper for condition building
- `_build_query()` - Internal helper for SQL construction
- `_convert_uuids()` - Internal helper for UUID conversion
- `_execute_query()` - Internal helper for query execution

### Step 2: Implement Core `EnrichedService` Class (Day 1, Afternoon)

**Implementation Checklist**:
- [ ] Create class structure with `__init__` method
- [ ] Implement `_build_where_clause()` for condition building
- [ ] Implement `_build_query()` for SQL construction
- [ ] Implement `_convert_uuids()` for UUID conversion
- [ ] Implement `_execute_query()` for query execution with error handling
- [ ] Implement `get_enriched()` method
- [ ] Implement `get_enriched_by_id()` method
- [ ] Add comprehensive docstrings

**Key Features to Support**:
- Institution scoping (global vs. institution-scoped)
- `include_archived` filtering
- Custom WHERE conditions
- Custom JOINs
- Custom SELECT fields
- UUID conversion
- Schema validation
- Error handling

### Step 3: Unit Tests for `EnrichedService` (Day 2, Morning)

**Test Coverage**:
- [ ] Test condition building (archived, scope)
- [ ] Test query building with JOINs
- [ ] Test UUID conversion
- [ ] Test error handling
- [ ] Test with different configurations

### Step 4: Migrate First Endpoint - `get_enriched_institution_bank_accounts` (Day 2, Afternoon)

**Why this one?**
- Relatively simple (fewer JOINs)
- Recently worked on (fresh in mind)
- Good representative of common patterns

**Migration Steps**:
1. [ ] Create `EnrichedService` instance configuration for institution bank accounts
2. [ ] Replace function body with `EnrichedService` call
3. [ ] Test endpoint manually
4. [ ] Verify response matches original
5. [ ] Check code reduction

**Expected Result**:
- Function goes from ~90 lines to ~15-20 lines
- Same functionality
- All tests pass

### Step 5: Migrate Second Endpoint - `get_enriched_institution_bills` (Day 3, Morning)

**Why this one?**
- Similar complexity to first
- Uses similar patterns
- Validates the service works for multiple endpoints

**Migration Steps**:
1. [ ] Create `EnrichedService` instance configuration for institution bills
2. [ ] Replace function body with `EnrichedService` call
3. [ ] Test endpoint manually
4. [ ] Verify response matches original
5. [ ] Check code reduction

### Step 6: Migrate Third Endpoint - `get_enriched_users` (Day 3, Afternoon)

**Why this one?**
- More complex (multiple JOINs, computed fields)
- Tests service with more complex scenarios
- Validates computed fields (full_name)

**Migration Steps**:
1. [ ] Create `EnrichedService` instance configuration for users
2. [ ] Handle computed field (`full_name`)
3. [ ] Replace function body with `EnrichedService` call
4. [ ] Test endpoint manually
5. [ ] Verify response matches original
6. [ ] Check code reduction

### Step 7: Integration Testing (Day 4)

**Test Checklist**:
- [ ] All 3 migrated endpoints work correctly
- [ ] Scoping works (Employee vs. Supplier)
- [ ] `include_archived` works
- [ ] Error handling works
- [ ] Performance is acceptable (no regression)
- [ ] Response schemas match original

### Step 8: Documentation and Review (Day 5)

**Documentation Tasks**:
- [ ] Update `ENRICHED_ENDPOINTS_DRY_ROADMAP.md` with lessons learned
- [ ] Document `EnrichedService` usage patterns
- [ ] Create migration guide for remaining endpoints
- [ ] Code review and refactoring if needed

## Deliverables

1. **`app/services/enriched_service.py`** - New `EnrichedService` class
2. **Migrated endpoints** - 3 endpoints using new service
3. **Unit tests** - Tests for `EnrichedService`
4. **Documentation** - Usage guide and migration patterns

## Future Considerations

### Role-Based Field Masking (Future Enhancement)

**Note**: Currently, all Employee roles (Super Admin, Admin, regular Employee) see the same data. In the future, we may need to implement field masking for non-Admin/Super Admin roles to hide sensitive fields (e.g., `account_number`, `routing_number` in bank accounts).

**Implementation Approach** (when needed):
- Add `field_masks` parameter to `EnrichedService.__init__()`
- Apply field masks post-query in `get_enriched()` and `get_enriched_by_id()`
- Estimated work: ~1 hour

**Status**: Not implemented - keeping current approach for now.

## Next Steps After Milestone 1

Once Milestone 1 is complete:
1. Review and refine `EnrichedService` based on learnings
2. Create migration plan for remaining 10 endpoints
3. Migrate remaining endpoints incrementally (2-3 at a time)
4. Build all new enriched endpoints using `EnrichedService`

## Risk Mitigation

- **Incremental migration**: Only migrate 2-3 endpoints at a time
- **Keep old code**: Don't delete old functions until new ones are proven
- **Comprehensive testing**: Test each migrated endpoint thoroughly
- **Rollback plan**: Can revert to old functions if issues arise

