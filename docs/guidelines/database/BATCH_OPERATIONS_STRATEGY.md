# Database Batch Operations Strategy

## Overview

This document describes the batch operations strategy for database functions, focusing on the insert operations pattern that can be extended to other operations.

## Architecture Pattern

### Design Philosophy

The batch operations strategy follows a **hybrid approach** that balances:
- **DRY (Don't Repeat Yourself)**: Shared logic extracted to helper functions
- **Separation of Concerns**: Single vs batch operations remain distinct
- **Backward Compatibility**: Existing single operations unchanged
- **Atomicity**: Batch operations are transactional (all succeed or all fail)

### Core Components

**Insert Operations**:
1. **Shared Helper Function**: `_build_insert_sql()`
2. **Single Operation Function**: `db_insert()`
3. **Batch Operation Function**: `db_batch_insert()`

**Update Operations**:
1. **Shared Helper Function**: `_build_update_sql()`
2. **Single Operation Function**: `db_update()`
3. **Batch Operation Function**: `db_batch_update()`

**Delete Operations**:
1. **Shared Helper Function**: `_build_delete_sql()`
2. **Single Operation Function**: `db_delete()`
3. **Batch Operation Function**: `db_batch_delete()`

---

## Insert Operations

### Helper Function: `_build_insert_sql()`

**Purpose**: Extract common SQL construction logic shared by both single and batch inserts.

**Location**: `app/utils/db.py`

**Signature**:
```python
def _build_insert_sql(table: str, data: dict) -> Tuple[str, tuple, str]:
    """
    Build SQL statement, values tuple, and primary key for insert.
    
    Args:
        table: Table name
        data: Dictionary of column names to values
    
    Returns:
        Tuple of (sql, values, primary_key)
    """
```

**Responsibilities**:
- Build SQL INSERT statement with column names and placeholders
- Convert UUID objects to strings for database compatibility
- Look up primary key column name from `PRIMARY_KEY_MAPPING`
- Return SQL, values tuple, and primary key name

**Benefits**:
- Eliminates code duplication between `db_insert` and `db_batch_insert`
- Centralizes SQL construction logic
- Ensures consistent behavior across single and batch operations

---

### Single Insert: `db_insert()`

**Purpose**: Insert a single record with immediate commit.

**Behavior**:
- Commits immediately after insert
- Suitable for single-record operations that should be atomic on their own
- Returns the primary key ID of the inserted record

**Use Cases**:
- Creating a single user
- Creating a single product
- Creating a single address
- Any operation where immediate commit is desired

**Example**:
```python
data = {
    "plate_id": "uuid1",
    "kitchen_day": "Monday",
    "is_archived": False
}
inserted_id = db_insert("plate_kitchen_days", data, connection)
```

**Transaction Behavior**:
- Each call is a separate transaction
- If called multiple times, each insert commits independently
- No rollback if subsequent operations fail

---

### Batch Insert: `db_batch_insert()`

**Purpose**: Insert multiple records atomically in a single transaction.

**Behavior**:
- Validates all data before executing any inserts (fail-fast)
- Executes all inserts in a single transaction
- Commits once at the end (atomicity)
- Rolls back all operations if any insert fails

**Use Cases**:
- Creating multiple kitchen days for a plate
- Bulk user creation
- Bulk address creation
- Bulk product creation
- Any operation requiring atomic batch creation

**Example**:
```python
data_list = [
    {"plate_id": "uuid1", "kitchen_day": "Monday"},
    {"plate_id": "uuid1", "kitchen_day": "Tuesday"},
    {"plate_id": "uuid1", "kitchen_day": "Wednesday"}
]
inserted_ids = db_batch_insert("plate_kitchen_days", data_list, connection)
# Returns: [uuid1, uuid2, uuid3]
```

**Transaction Behavior**:
- All inserts are part of a single transaction
- If any insert fails, all operations are rolled back
- Guarantees atomicity: all succeed or all fail

**Validation**:
- Validates `data_list` is not empty
- Validates each item is a dictionary
- Validates each dictionary is not empty
- All validation happens before any database operations

---

## Implementation Details

### Code Reuse Pattern

```
_build_insert_sql()  (shared helper)
    ↓                    ↓
db_insert()      db_batch_insert()
(single)          (batch)
```

Both functions use `_build_insert_sql()` to construct SQL, ensuring:
- Consistent SQL generation
- Consistent UUID handling
- Consistent primary key lookup
- Minimal code duplication

### Transaction Management

**Single Insert**:
```python
try:
    cursor.execute(sql, values)
    inserted_id = cursor.fetchone()[0]
    connection.commit()  # Immediate commit
    return inserted_id
except:
    connection.rollback()
    raise
```

**Batch Insert**:
```python
try:
    for data in data_list:
        sql, values, pk = _build_insert_sql(table, data)
        cursor.execute(sql, values)
        inserted_ids.append(cursor.fetchone()[0])
    connection.commit()  # Single commit at end
    return inserted_ids
except:
    connection.rollback()  # Rollback all on any error
    raise
```

### Error Handling

Both functions:
- Use `handle_database_exception()` for consistent error formatting
- Log errors with context (table name, operation type)
- Rollback on any exception
- Re-raise exceptions for caller handling

---

## Usage Guidelines

### When to Use `db_insert()`

✅ **Use for**:
- Single record operations
- Operations that should commit immediately
- Operations where partial success is acceptable
- Simple CRUD operations

❌ **Don't use for**:
- Multiple related records that must be atomic
- Operations where partial failure is unacceptable

### When to Use `db_batch_insert()`

✅ **Use for**:
- Multiple related records that must be atomic
- Operations where all must succeed or all must fail
- Bulk operations
- Operations requiring transactional integrity

❌ **Don't use for**:
- Single record operations (use `db_insert()` instead)
- Operations where partial success is acceptable

---

## Performance Considerations

### Single Insert
- **Overhead**: One transaction per insert
- **Best for**: Small numbers of inserts (< 10)
- **Trade-off**: Higher transaction overhead, but simpler code

### Batch Insert
- **Overhead**: One transaction for all inserts
- **Best for**: Multiple inserts (10+)
- **Trade-off**: Lower transaction overhead, but requires all data upfront

### Performance Comparison

| Operation | Single Insert (10 records) | Batch Insert (10 records) |
|-----------|----------------------------|--------------------------|
| Transactions | 10 | 1 |
| Commits | 10 | 1 |
| Network Round-trips | 10 | 1 |
| **Total Time** | ~100ms | ~20ms |

*Note: Actual times depend on database latency and record size*

---

## Update Operations

### Helper Function: `_build_update_sql()`

**Purpose**: Extract common SQL construction logic shared by both single and batch updates.

**Location**: `app/utils/db.py`

**Signature**:
```python
def _build_update_sql(table: str, data: dict, where: dict) -> Tuple[str, tuple]:
    """
    Build SQL statement and values tuple for update operation.
    
    Args:
        table: Table name
        data: Dictionary of column names to values for SET clause
        where: Dictionary of column names to values for WHERE clause
    
    Returns:
        Tuple of (sql, values)
    """
```

**Responsibilities**:
- Build SQL UPDATE statement with SET and WHERE clauses
- Convert UUID objects to strings for database compatibility
- Return SQL and values tuple

---

### Single Update: `db_update()`

**Purpose**: Update records matching a WHERE clause with immediate commit.

**Behavior**:
- Commits immediately after update
- Suitable for single-record operations that should be atomic on their own
- Returns number of rows affected

**Use Cases**:
- Updating a single record
- Simple field updates
- Status changes

**Example**:
```python
data = {"status": "archived"}
where = {"id": "uuid1"}
row_count = db_update("table", data, where, connection)
```

---

### Batch Update: `db_batch_update()`

**Purpose**: Update multiple records atomically in a single transaction.

**Behavior**:
- Supports two patterns:
  - **Pattern 1**: Same update, different WHERE clauses
  - **Pattern 2**: Different updates per record
- Validates all data before executing any updates (fail-fast)
- Executes all updates in a single transaction
- Commits once at the end (atomicity)
- Rolls back all operations if any update fails

**Pattern 1 Example** (Same update, different WHERE clauses):
```python
updates = {"status": "archived"}
where_list = [
    {"id": "uuid1"},
    {"id": "uuid2"},
    {"id": "uuid3"}
]
count = db_batch_update("table", updates, where_list, connection)
```

**Pattern 2 Example** (Different updates per record):
```python
updates = [
    {"id": "uuid1", "status": "active", "modified_by": "user1"},
    {"id": "uuid2", "status": "inactive", "modified_by": "user1"}
]
count = db_batch_update("table", updates, connection=connection)
```

**Use Cases**:
- Bulk status updates
- Bulk field updates
- Archival operations
- Any operation requiring atomic batch updates

---

## Delete Operations

### Helper Function: `_build_delete_sql()`

**Purpose**: Extract common SQL construction logic shared by both single and batch deletes.

**Location**: `app/utils/db.py`

**Signature**:
```python
def _build_delete_sql(table: str, where: dict, soft: bool = False, soft_update_fields: Optional[dict] = None) -> Tuple[str, tuple]:
    """
    Build SQL statement and values tuple for delete operation.
    
    Args:
        table: Table name
        where: Dictionary of column names to values for WHERE clause
        soft: If True, perform soft delete (UPDATE is_archived) instead of hard delete
        soft_update_fields: Optional dictionary of additional fields to update during soft delete
    
    Returns:
        Tuple of (sql, values)
    """
```

**Responsibilities**:
- Build SQL DELETE or UPDATE statement (for soft delete)
- Convert UUID objects to strings for database compatibility
- Support additional fields for soft delete (modified_by, modified_date)

---

### Single Delete: `db_delete()`

**Purpose**: Delete records matching a WHERE clause with immediate commit.

**Behavior**:
- Supports hard delete (DELETE FROM) and soft delete (UPDATE is_archived)
- Commits immediately after delete
- Returns number of rows affected

**Use Cases**:
- Deleting a single record
- Soft deleting (archiving) a single record

**Example**:
```python
# Hard delete
row_count = db_delete("table", {"id": "uuid1"}, connection)

# Soft delete
row_count = db_delete("table", {"id": "uuid1"}, connection, soft=True, 
                     soft_update_fields={"modified_by": user_id})
```

---

### Batch Delete: `db_batch_delete()`

**Purpose**: Delete multiple records atomically in a single transaction.

**Behavior**:
- Supports hard delete and soft delete
- Validates all WHERE clauses before executing any deletes (fail-fast)
- Executes all deletes in a single transaction
- Commits once at the end (atomicity)
- Rolls back all operations if any delete fails

**Example**:
```python
where_list = [
    {"id": "uuid1"},
    {"id": "uuid2"},
    {"id": "uuid3"}
]

# Hard delete
count = db_batch_delete("table", where_list, connection)

# Soft delete (archival)
count = db_batch_delete("table", where_list, connection, soft=True,
                       soft_update_fields={"modified_by": user_id, "modified_date": datetime.now()})
```

**Use Cases**:
- Bulk archival operations
- Bulk cleanup operations
- Any operation requiring atomic batch deletion

---

## Implementation Status

| Operation | Helper Function | Single Function | Batch Function | Status |
|-----------|----------------|-----------------|----------------|--------|
| **Insert** | `_build_insert_sql()` | `db_insert()` | `db_batch_insert()` | ✅ Implemented |
| **Update** | `_build_update_sql()` | `db_update()` | `db_batch_update()` | ✅ Implemented |
| **Delete** | `_build_delete_sql()` | `db_delete()` | `db_batch_delete()` | ✅ Implemented |
| **Upsert** | N/A | N/A | `db_batch_upsert()` | ⚠️ Future Consideration |

---

## Future Extensions

**Potential Future Operations**:

1. **Batch Upsert**: `db_batch_upsert()` - Insert or update multiple records
   - Less common use case
   - Can be achieved with conditional logic + existing batch functions
   - Consider only if specific use case emerges

See `BATCH_OPERATIONS_ANALYSIS.md` for detailed analysis of potential batch operations.

---

## Testing Strategy

### Unit Tests
- Test `_build_insert_sql()` with various data types
- Test `db_insert()` with single record
- Test `db_batch_insert()` with multiple records
- Test error handling and rollback behavior

### Integration Tests
- Test atomicity (verify rollback on failure)
- Test performance with large batches
- Test with various data types (UUIDs, strings, numbers, dates)

### Edge Cases
- Empty data list
- Invalid data types
- Database constraint violations
- Connection failures mid-batch

---

## Migration Guide

### Migrating from Single to Batch

**Before** (multiple single inserts):
```python
for day in kitchen_days:
    data = {"plate_id": plate_id, "kitchen_day": day}
    db_insert("plate_kitchen_days", data, connection)
    # Each insert commits separately
```

**After** (single batch insert):
```python
data_list = [
    {"plate_id": plate_id, "kitchen_day": day}
    for day in kitchen_days
]
db_batch_insert("plate_kitchen_days", data_list, connection)
# All inserts commit atomically
```

**Benefits**:
- Atomicity: All succeed or all fail
- Performance: Single transaction vs multiple
- Simplicity: One function call vs loop

---

## Related Documentation

- `app/utils/db.py` - Implementation
- `docs/api/BATCH_TRANSACTION_HANDLING_ANALYSIS.md` - Design analysis
- `docs/api/DB_INSERT_REFACTORING_ANALYSIS.md` - Refactoring rationale

