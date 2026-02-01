# Batch Operations Analysis

## Overview

This document analyzes which database functions could benefit from batch operation variants, similar to the `db_batch_insert()` pattern.

## Current Database Functions

| Function | Type | Batch Variant | Status |
|----------|------|---------------|--------|
| `db_insert()` | Single | `db_batch_insert()` | ✅ Implemented |
| `db_update()` | Single | `db_batch_update()` | ❌ Not implemented |
| `db_delete()` | Single | `db_batch_delete()` | ❌ Not implemented |
| `db_read()` | Generic | N/A | ✅ Already handles multiple results |

---

## Analysis by Function

### 1. `db_update()` - Batch Update Potential

**Current Implementation**:
- Updates records matching a WHERE clause
- Commits immediately after update
- Returns number of affected rows

**Batch Use Cases**:
1. **Bulk Status Updates**: Update status for multiple records
   ```python
   # Current: Multiple calls
   for record_id in record_ids:
       db_update("table", {"status": "archived"}, {"id": record_id}, connection)
   
   # Potential: Single batch call
   db_batch_update("table", {"status": "archived"}, [{"id": id} for id in record_ids], connection)
   ```

2. **Bulk Field Updates**: Update same field for multiple records
   ```python
   # Update modified_date for multiple records
   db_batch_update("table", {"modified_date": now}, where_list, connection)
   ```

3. **Different Updates Per Record**: Update different values for different records
   ```python
   updates = [
       {"id": "uuid1", "status": "active", "modified_by": "user1"},
       {"id": "uuid2", "status": "inactive", "modified_by": "user1"}
   ]
   db_batch_update("table", updates, connection)
   ```

**Complexity**: 🟡 **MEDIUM**
- Need to handle two patterns:
  - Same update, different WHERE clauses (simpler)
  - Different updates per record (more complex)

**Recommendation**: ✅ **YES - High Value**
- Common use case: bulk status updates, archival operations
- Performance benefit: single transaction vs multiple
- Atomicity benefit: all succeed or all fail

**Implementation Pattern**:
```python
def db_batch_update(
    table: str,
    updates: Union[dict, List[dict]],
    where_list: Optional[List[dict]] = None,
    connection=None
) -> int:
    """
    Update multiple records atomically.
    
    Pattern 1: Same update, different WHERE clauses
        updates = {"status": "archived"}
        where_list = [{"id": "uuid1"}, {"id": "uuid2"}]
    
    Pattern 2: Different updates per record
        updates = [
            {"id": "uuid1", "status": "active"},
            {"id": "uuid2", "status": "inactive"}
        ]
    """
```

---

### 2. `db_delete()` - Batch Delete Potential

**Current Implementation**:
- Deletes records matching a WHERE clause
- Commits immediately after delete
- Returns number of affected rows

**Batch Use Cases**:
1. **Bulk Soft Delete**: Soft delete multiple records
   ```python
   # Current: Multiple calls
   for record_id in record_ids:
       db_update("table", {"is_archived": True}, {"id": record_id}, connection)
   
   # Potential: Single batch call
   db_batch_delete("table", [{"id": id} for id in record_ids], soft=True, connection)
   ```

2. **Bulk Hard Delete**: Hard delete multiple records
   ```python
   # Delete multiple records atomically
   db_batch_delete("table", [{"id": id} for id in record_ids], connection)
   ```

3. **Cascade Deletes**: Delete related records
   ```python
   # Delete all related records atomically
   db_batch_delete("child_table", [{"parent_id": parent_id} for parent_id in parent_ids], connection)
   ```

**Complexity**: 🟢 **LOW**
- Simpler than update (only WHERE clauses needed)
- Can reuse `_build_where_clause()` pattern from insert

**Recommendation**: ✅ **YES - High Value**
- Common use case: bulk archival, cleanup operations
- Performance benefit: single transaction vs multiple
- Atomicity benefit: all succeed or all fail
- Safety benefit: can validate all records exist before deleting any

**Implementation Pattern**:
```python
def db_batch_delete(
    table: str,
    where_list: List[dict],
    connection=None,
    soft: bool = False
) -> int:
    """
    Delete multiple records atomically.
    
    Args:
        table: Table name
        where_list: List of WHERE clause dictionaries
        connection: Optional database connection
        soft: If True, perform soft delete (update is_archived) instead of hard delete
    
    Returns:
        Total number of records deleted
    """
```

**Special Considerations**:
- **Soft Delete**: If `soft=True`, should use `db_batch_update()` internally
- **Validation**: Should validate all records exist before deleting any
- **Cascade**: May need to handle foreign key constraints

---

### 3. `db_read()` - Batch Read Analysis

**Current Implementation**:
- Generic query function
- Already handles multiple results via `fetch_one=False`
- Returns list of dictionaries

**Batch Potential**: ❌ **NOT NEEDED**
- Already handles multiple results efficiently
- No transaction concerns (read-only)
- Can use `IN` clauses for batch filtering:
  ```python
  query = "SELECT * FROM table WHERE id IN (%s, %s, %s)"
  results = db_read(query, (id1, id2, id3))
  ```

**Recommendation**: ✅ **NO ACTION NEEDED**
- Current implementation is sufficient
- SQL `IN` clause handles batch reads efficiently

---

## Additional Batch Operations

### 4. `db_batch_upsert()` - Insert or Update

**Use Cases**:
- Bulk import with conflict resolution
- Sync operations (insert if new, update if exists)
- Idempotent operations

**Complexity**: 🔴 **HIGH**
- Requires `ON CONFLICT` handling (PostgreSQL-specific)
- Need to handle different conflict strategies
- More complex than simple insert/update

**Recommendation**: ⚠️ **MAYBE - Low Priority**
- Less common use case
- Can be achieved with conditional logic + `db_batch_insert()` + `db_batch_update()`
- Consider only if specific use case emerges

**Implementation Pattern** (if needed):
```python
def db_batch_upsert(
    table: str,
    data_list: List[dict],
    conflict_column: str,
    connection=None
) -> List:
    """
    Insert or update multiple records atomically.
    
    Uses PostgreSQL ON CONFLICT for atomic upsert.
    """
    # Build INSERT ... ON CONFLICT ... DO UPDATE SQL
```

---

## Priority Assessment

### High Priority (Implement Soon)

1. ✅ **`db_batch_delete()`** - High value, low complexity
   - Common use case: bulk archival, cleanup
   - Simple implementation (similar to batch insert)
   - Clear atomicity benefits

2. ✅ **`db_batch_update()`** - High value, medium complexity
   - Common use case: bulk status updates
   - Two patterns to support (same update vs different updates)
   - Clear performance and atomicity benefits

### Medium Priority (Consider Later)

3. ⚠️ **`db_batch_upsert()`** - Medium value, high complexity
   - Less common use case
   - Can be achieved with existing functions
   - Consider only if specific use case emerges

### Low Priority (Not Needed)

4. ✅ **`db_batch_read()`** - Not needed
   - Current `db_read()` with `IN` clause is sufficient
   - No transaction concerns for reads

---

## Implementation Recommendations

### Phase 1: Batch Delete (Recommended First)

**Why First**:
- Simplest to implement (similar to batch insert)
- High value use case (bulk archival)
- Clear pattern to follow

**Implementation Steps**:
1. Create `_build_delete_sql()` helper (similar to `_build_insert_sql()`)
2. Create `db_batch_delete()` function
3. Add soft delete support (optional)
4. Add unit tests
5. Update archival service to use batch delete

**Estimated Effort**: 2-3 hours

---

### Phase 2: Batch Update (Recommended Second)

**Why Second**:
- More complex than delete (two patterns)
- High value use case (bulk status updates)
- Can reuse patterns from batch insert/delete

**Implementation Steps**:
1. Create `_build_update_sql()` helper
2. Create `db_batch_update()` function
3. Support both patterns (same update vs different updates)
4. Add unit tests
5. Update services to use batch update

**Estimated Effort**: 4-6 hours

---

## Code Reuse Strategy

### Shared Helpers Pattern

Following the insert pattern, create shared helpers:

```python
# Shared helpers
def _build_insert_sql(table: str, data: dict) -> Tuple[str, tuple, str]
def _build_update_sql(table: str, data: dict, where: dict) -> Tuple[str, tuple]
def _build_delete_sql(table: str, where: dict) -> Tuple[str, tuple]

# Single operations
def db_insert(table: str, data: dict, connection=None)
def db_update(table: str, data: dict, where: dict, connection=None)
def db_delete(table: str, where: dict, connection=None)

# Batch operations
def db_batch_insert(table: str, data_list: List[dict], connection=None)
def db_batch_update(table: str, updates: Union[dict, List[dict]], where_list: Optional[List[dict]], connection=None)
def db_batch_delete(table: str, where_list: List[dict], connection=None, soft: bool = False)
```

### Benefits

- **Consistency**: Same pattern across all operations
- **DRY**: Shared SQL building logic
- **Maintainability**: Easy to understand and extend
- **Testing**: Can test helpers independently

---

## Use Case Examples

### Example 1: Bulk Archival

**Current** (multiple transactions):
```python
for record_id in record_ids:
    db_update("table", {"is_archived": True}, {"id": record_id}, connection)
    # Each update commits separately
```

**With Batch Update** (single transaction):
```python
db_batch_update(
    "table",
    {"is_archived": True},
    [{"id": id} for id in record_ids],
    connection
)
# All updates commit atomically
```

### Example 2: Bulk Soft Delete

**Current** (multiple transactions):
```python
for record_id in record_ids:
    db_update("table", {"is_archived": True}, {"id": record_id}, connection)
```

**With Batch Delete** (single transaction):
```python
db_batch_delete("table", [{"id": id} for id in record_ids], soft=True, connection)
# All soft deletes commit atomically
```

### Example 3: Bulk Status Update

**Current** (multiple transactions):
```python
for record_id in record_ids:
    db_update("table", {"status": "active"}, {"id": record_id}, connection)
```

**With Batch Update** (single transaction):
```python
db_batch_update(
    "table",
    {"status": "active"},
    [{"id": id} for id in record_ids],
    connection
)
# All status updates commit atomically
```

---

## Performance Impact

### Transaction Overhead Reduction

| Operation | Single (10 records) | Batch (10 records) | Improvement |
|-----------|---------------------|---------------------|-------------|
| **Update** | 10 transactions | 1 transaction | ~80% reduction |
| **Delete** | 10 transactions | 1 transaction | ~80% reduction |
| **Network Round-trips** | 10 | 1 | ~90% reduction |

### Estimated Performance Gains

- **Small batches (10-50 records)**: 2-5x faster
- **Medium batches (50-200 records)**: 5-10x faster
- **Large batches (200+ records)**: 10-20x faster

*Note: Actual gains depend on database latency and record size*

---

## Summary

### Recommended Implementations

1. ✅ **`db_batch_delete()`** - High priority
   - High value, low complexity
   - Common use case (bulk archival)
   - Clear atomicity benefits

2. ✅ **`db_batch_update()`** - High priority
   - High value, medium complexity
   - Common use case (bulk status updates)
   - Clear performance benefits

3. ⚠️ **`db_batch_upsert()`** - Low priority
   - Medium value, high complexity
   - Less common use case
   - Can be achieved with existing functions

4. ✅ **`db_batch_read()`** - Not needed
   - Current implementation sufficient
   - SQL `IN` clause handles batch reads

### Implementation Order

1. **Phase 1**: `db_batch_delete()` (2-3 hours)
2. **Phase 2**: `db_batch_update()` (4-6 hours)
3. **Phase 3**: Evaluate `db_batch_upsert()` based on actual use cases

### Total Estimated Effort

- **Phase 1 + Phase 2**: 6-9 hours
- **Benefits**: Significant performance improvements, better atomicity, cleaner code

