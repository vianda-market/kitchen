# Batch Operations Services Roadmap

## Overview

This roadmap tracks the adoption of batch database operations across services in the codebase. Batch operations (`db_batch_insert()`, `db_batch_update()`, `db_batch_delete()`) provide significant performance improvements and atomicity guarantees for bulk operations.

## Implementation Status

### ✅ Completed Implementations

1. **Plate Kitchen Days Service** (`app/routes/plate_kitchen_days.py`)
   - **Operation**: Batch Insert
   - **Use Case**: Creating multiple kitchen day assignments for a plate
   - **Status**: ✅ Implemented
   - **Benefits**: Atomic creation of multiple days, single transaction

2. **Archival Service** (`app/services/archival.py`)
   - **Operation**: Batch Delete (Soft Delete)
   - **Use Case**: Bulk archival of records
   - **Status**: ✅ Implemented
   - **Benefits**: Atomic archival, sets `modified_by` and `modified_date` in single transaction
   - **Implementation**: Uses `db_batch_delete()` with `soft=True` and `soft_update_fields`

---

## 🔄 Pending Optimizations

### High Priority

#### 1. Billing Service - Restaurant Balance Reset

**Location**: `app/services/billing/institution_billing.py`

**Current Implementation** (Lines 745-779):
```python
for row in results:
    restaurant_id = row[0]
    current_balance = Decimal(str(row[1]))
    currency_code = row[2]
    credit_currency_id = row[3]
    
    try:
        # Reset balance to 0
        update_balance_with_monetary_amount(
            restaurant_id=restaurant_id,
            amount=-float(current_balance),  # Negative amount to reduce to 0
            currency_code=currency_code,
            db=connection
        )
        reset_count += 1
        total_reset_amount += current_balance
    except Exception as e:
        log_error(f"Error resetting balance for restaurant {restaurant_id}: {e}")
        continue
```

**Issue**:
- Loops through restaurants and calls `update_balance_with_monetary_amount()` individually
- Each call is a separate transaction
- If one fails, others continue (no atomicity)
- Performance overhead: N transactions for N restaurants

**Proposed Solution**:
- **Option A**: Use `db_batch_update()` if `update_balance_with_monetary_amount()` can be refactored
  - Requires analyzing `update_balance_with_monetary_amount()` to understand its logic
  - May need to extract balance calculation logic
  - Use Pattern 1 (same update, different WHERE clauses) if all balances reset to 0
  - Use Pattern 2 (different updates) if balances need different reset values

- **Option B**: Create specialized batch balance reset function
  - Similar to `update_balance_with_monetary_amount()` but accepts list of restaurants
  - Handles balance calculation and transaction creation atomically
  - Maintains existing business logic while adding batch capability

**Complexity**: 🟡 **MEDIUM**
- Need to understand `update_balance_with_monetary_amount()` implementation
- May require refactoring balance update logic
- Need to ensure transaction creation logic is preserved

**Estimated Effort**: 4-6 hours
- Analyze current implementation (1 hour)
- Design batch approach (1 hour)
- Implement and test (2-3 hours)
- Integration testing (1 hour)

**Benefits**:
- **Performance**: Single transaction vs N transactions (80%+ reduction)
- **Atomicity**: All balances reset or none (critical for billing)
- **Reliability**: No partial resets if one restaurant fails

**Risk Assessment**: 🟡 **MEDIUM**
- Balance updates are critical financial operations
- Need thorough testing to ensure correctness
- Must preserve existing business logic

**Recommendation**: 
- **Phase 1**: Analyze `update_balance_with_monetary_amount()` to understand dependencies
- **Phase 2**: Design batch approach that preserves business logic
- **Phase 3**: Implement with comprehensive testing
- **Phase 4**: Gradual rollout with monitoring

---

### Medium Priority

#### 2. Other Services with Loop-Based Updates

**Potential Candidates** (to be analyzed):

1. **User Service** - Bulk user status updates
2. **Product Service** - Bulk product updates
3. **Restaurant Service** - Bulk restaurant updates
4. **Subscription Service** - Bulk subscription updates

**Analysis Required**:
- Identify services with loop-based database operations
- Assess frequency and volume of operations
- Evaluate performance impact
- Prioritize based on business value

**Estimated Effort**: 2-4 hours per service
- Code analysis (30 min)
- Implementation (1-2 hours)
- Testing (1 hour)

---

## Implementation Guidelines

### When to Use Batch Operations

✅ **Use batch operations for**:
- Operations on 10+ records
- Operations requiring atomicity (all succeed or all fail)
- Bulk status updates
- Bulk archival operations
- Operations where performance is critical

❌ **Don't use batch operations for**:
- Single record operations (use single functions)
- Operations where partial success is acceptable
- Operations with complex business logic that can't be batched
- Operations where data isn't available upfront

### Migration Checklist

When migrating a service to use batch operations:

- [ ] Analyze current implementation
- [ ] Identify batch operation pattern (insert/update/delete)
- [ ] Determine appropriate batch pattern (Pattern 1 vs Pattern 2 for updates)
- [ ] Ensure data validation before batch operation
- [ ] Add error handling and rollback logic
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update service documentation
- [ ] Monitor performance improvements
- [ ] Verify atomicity in production

---

## Performance Monitoring

### Metrics to Track

1. **Transaction Count**: Reduction in number of transactions
2. **Execution Time**: Time saved per operation
3. **Error Rate**: Ensure batch operations don't increase errors
4. **Atomicity**: Verify all-or-nothing behavior

### Expected Improvements

| Operation | Records | Before (ms) | After (ms) | Improvement |
|-----------|---------|------------|------------|-------------|
| Balance Reset | 100 | ~1000 | ~200 | 80% |
| Archival | 1000 | ~5000 | ~1000 | 80% |
| Kitchen Days | 5 | ~50 | ~10 | 80% |

*Note: Actual improvements depend on database latency and record complexity*

---

## Related Documentation

- `app/db/BATCH_OPERATIONS_STRATEGY.md` - Batch operations strategy and patterns
- `app/db/BATCH_OPERATIONS_ANALYSIS.md` - Detailed analysis of batch operations
- `app/utils/db.py` - Implementation of batch functions

---

## Next Steps

1. **Immediate**: Analyze `update_balance_with_monetary_amount()` in billing service
2. **Short-term**: Design batch balance reset approach
3. **Medium-term**: Implement and test batch balance reset
4. **Long-term**: Identify and optimize other loop-based operations

---

## Last Updated

- **Date**: 2025-11-19
- **Status**: Phase 1 & 2 (Insert & Update) Complete, Phase 1 (Delete) Complete
- **Next Review**: After billing service analysis

