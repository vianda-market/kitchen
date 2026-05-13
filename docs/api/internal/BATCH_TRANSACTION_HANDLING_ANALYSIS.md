# Batch Transaction Handling - Design Analysis

## Problem Statement

The current `db_insert` function commits immediately after each insert operation. For batch operations (e.g., creating multiple kitchen days), we need atomicity - all operations must succeed or all must fail.

**Current Behavior**:
```python
db_insert(table, data, connection)  # Commits immediately
db_insert(table, data2, connection)  # Commits immediately
# If second fails, first is already committed ❌
```

**Required Behavior**:
```python
# All operations in one transaction
db_batch_insert([data1, data2, data3], connection)  # Commits once at end
# If any fails, all rollback ✅
```

## Options Analysis

### Option 1: Modify `db_insert` with `commit` Parameter ⚠️ RISKY

**Approach**: Add optional `commit: bool = True` parameter to `db_insert`

```python
def db_insert(table: str, data: dict, connection=None, commit: bool = True):
    # ... execute insert ...
    if commit:
        connection.commit()
    else:
        # Don't commit, caller will commit
        pass
```

**Pros**:
- ✅ Reuses existing function
- ✅ Minimal code changes

**Cons**:
- ❌ **High regression risk** - Changes behavior of widely-used function
- ❌ **Easy to misuse** - Forgetting to commit could cause data loss
- ❌ **Breaking change** - All callers need to be aware
- ❌ **Confusing API** - Same function, different behaviors
- ❌ **Testing complexity** - Must test both commit modes

**Risk Assessment**: 🔴 **HIGH RISK** - Not recommended

---

### Option 2: Create `db_batch_insert` Function ✅ RECOMMENDED

**Approach**: Create new specialized function for batch operations

```python
def db_batch_insert(table: str, data_list: List[dict], connection=None):
    """
    Insert multiple records into a table in a single atomic transaction.
    
    Args:
        table: Table name
        data_list: List of dictionaries, each representing one row
        connection: Database connection (if None, creates new connection)
    
    Returns:
        List of inserted primary key IDs
    
    Raises:
        Exception: If any insert fails, all operations are rolled back
    """
    # Validate all data first
    # Execute all inserts
    # Commit once at end
    # Rollback on any error
```

**Pros**:
- ✅ **No regression risk** - Existing `db_insert` unchanged
- ✅ **Clear intent** - Function name indicates batch operation
- ✅ **Future-proof** - Can be reused for other batch operations
- ✅ **Atomic by design** - Transaction handling built-in
- ✅ **Easy to test** - Isolated function
- ✅ **Clear API** - Explicit batch operation

**Cons**:
- ⚠️ Additional function to maintain
- ⚠️ Some code duplication (but minimal)

**Risk Assessment**: 🟢 **LOW RISK** - Recommended

---

### Option 3: Raw SQL in Endpoint ⚠️ NOT RECOMMENDED

**Approach**: Use raw SQL with explicit transaction management in the endpoint

```python
def create_vianda_kitchen_days(...):
    with connection.cursor() as cursor:
        try:
            for day in kitchen_days:
                cursor.execute("INSERT INTO ...", ...)
            connection.commit()
        except:
            connection.rollback()
            raise
```

**Pros**:
- ✅ Full control over transaction
- ✅ No changes to utility functions

**Cons**:
- ❌ **Code duplication** - SQL logic repeated
- ❌ **Not reusable** - Can't use for other batch operations
- ❌ **Bypasses utilities** - Doesn't use existing `db_insert` logic
- ❌ **Maintenance burden** - SQL scattered across endpoints

**Risk Assessment**: 🟡 **MEDIUM RISK** - Not recommended

---

### Option 4: Transaction Context Manager ✅ GOOD ALTERNATIVE

**Approach**: Create a transaction context manager, use existing `db_insert` within it

```python
@contextmanager
def transaction(connection):
    """Context manager for database transactions"""
    try:
        yield connection
        connection.commit()
    except:
        connection.rollback()
        raise

# Usage:
with transaction(connection):
    db_insert(table, data1, connection, commit=False)  # Still need commit param
    db_insert(table, data2, connection, commit=False)
```

**Pros**:
- ✅ Clean transaction management
- ✅ Reusable pattern

**Cons**:
- ❌ **Still requires modifying `db_insert`** - Need `commit=False` parameter
- ❌ **Same risks as Option 1** - Regression risk

**Risk Assessment**: 🟡 **MEDIUM RISK** - Better than Option 1, but still risky

---

## Recommended Solution: `db_batch_insert` ✅

### Implementation

```python
def db_batch_insert(table: str, data_list: List[dict], connection=None):
    """
    Insert multiple records into a table in a single atomic transaction.
    
    This function is designed for batch operations where all inserts must
    succeed or all must fail (atomicity). It validates all data before
    executing any inserts, then executes all inserts in a single transaction.
    
    Args:
        table: Table name
        data_list: List of dictionaries, each representing one row to insert
        connection: Database connection (if None, creates and manages connection)
    
    Returns:
        List of inserted primary key IDs in the same order as data_list
    
    Raises:
        ValueError: If data_list is empty
        Exception: If any insert fails, all operations are rolled back
    
    Example:
        data_list = [
            {"vianda_id": "uuid1", "kitchen_day": "Monday"},
            {"vianda_id": "uuid1", "kitchen_day": "Tuesday"}
        ]
        ids = db_batch_insert("vianda_kitchen_days", data_list, connection)
        # Returns: [uuid1, uuid2] (primary key IDs)
    """
    if not data_list:
        raise ValueError("data_list cannot be empty")
    
    # Get the primary key column for the given table
    primary_key = PRIMARY_KEY_MAPPING.get(table, "id")
    
    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True
    
    start_time = time.time()
    inserted_ids = []
    
    try:
        cursor = connection.cursor()
        
        # Validate all data first (before any inserts)
        for i, data in enumerate(data_list):
            if not isinstance(data, dict):
                raise ValueError(f"data_list[{i}] must be a dictionary")
            if not data:
                raise ValueError(f"data_list[{i}] cannot be empty")
        
        # Execute all inserts
        for i, data in enumerate(data_list):
            columns = ', '.join(data.keys())
            placeholders = ', '.join('%s' for _ in data)
            sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING {primary_key}"
            
            # Convert UUID objects to their string representation
            values = tuple(v if not isinstance(v, UUID) else str(v) for v in data.values())
            
            log_info(f"Executing batch INSERT {i+1}/{len(data_list)}: {sql} with values {values}")
            cursor.execute(sql, values)
            inserted_id = cursor.fetchone()[0]
            inserted_ids.append(inserted_id)
        
        # Commit all inserts atomically
        connection.commit()
        execution_time = time.time() - start_time
        
        log_info(f"Successfully batch inserted {len(inserted_ids)} records into '{table}'")
        log_info(f"📊 BATCH INSERT executed in {execution_time:.3f}s")
        
        if execution_time > 1.0:
            log_warning(f"🐌 Slow BATCH INSERT detected: {execution_time:.3f}s - {table}")
        
        return inserted_ids
        
    except Exception as e:
        # Rollback all inserts on any error
        connection.rollback()
        log_error(f"Batch insert failed for '{table}': {e}. All operations rolled back.")
        raise handle_database_exception(e, f"batch insert into {table}")
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after BATCH INSERT execution.")
```

### Usage in Endpoint

```python
@router.post("/", response_model=List[ViandaKitchenDayResponseSchema])
def create_vianda_kitchen_days(
    payload: ViandaKitchenDayCreateSchema,  # kitchen_days: List[str]
    ...
):
    def create_operation(connection: psycopg2.extensions.connection):
        # Validate vianda exists
        vianda = vianda_service.get_by_id(payload.vianda_id, connection)
        if not vianda:
            raise HTTPException(status_code=404, detail=f"Vianda not found: {payload.vianda_id}")
        
        # Validate all days before creating any
        for day in payload.kitchen_days:
            if _check_unique_constraint(payload.vianda_id, day, connection):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vianda {payload.vianda_id} is already assigned to {day}"
                )
        
        # Prepare data for batch insert
        data_list = []
        for day in payload.kitchen_days:
            data_list.append({
                "vianda_id": str(payload.vianda_id),
                "kitchen_day": day,
                "is_archived": False,
                "modified_by": current_user["user_id"]
            })
        
        # Batch insert all days atomically
        from app.utils.db import db_batch_insert
        inserted_ids = db_batch_insert("vianda_kitchen_days", data_list, connection)
        
        # Fetch created records to return
        created_days = []
        for inserted_id in inserted_ids:
            kitchen_day = vianda_kitchen_days_service.get_by_id(
                UUID(inserted_id), connection, scope=scope
            )
            if kitchen_day:
                created_days.append(kitchen_day)
        
        log_info(f"Created {len(created_days)} kitchen days for vianda {payload.vianda_id}")
        return created_days
    
    return handle_business_operation(create_operation, db, "create vianda kitchen days")
```

## Future Use Cases

The `db_batch_insert` function can be reused for:

1. **Bulk user creation** - Create multiple users at once
2. **Bulk address creation** - Create multiple addresses
3. **Bulk product creation** - Create multiple products
4. **Bulk vianda creation** - Create multiple viandas
5. **Any other bulk operations** - Future needs

## Comparison Table

| Criteria | Modify `db_insert` | `db_batch_insert` | Raw SQL | Context Manager |
|----------|-------------------|-------------------|---------|----------------|
| **Regression Risk** | 🔴 High | 🟢 None | 🟢 None | 🟡 Medium |
| **Reusability** | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Code Clarity** | ⚠️ Mixed | ✅ Clear | ⚠️ Scattered | ✅ Clear |
| **Maintainability** | ❌ Complex | ✅ Simple | ❌ Complex | ⚠️ Medium |
| **Future-Proof** | ⚠️ Limited | ✅ Excellent | ❌ No | ⚠️ Limited |
| **Testing** | ❌ Complex | ✅ Simple | ⚠️ Medium | ⚠️ Medium |

## Recommendation

✅ **Implement `db_batch_insert` function**

**Rationale**:
1. **Zero regression risk** - Existing code unchanged
2. **Future-proof** - Reusable for other batch operations
3. **Clear intent** - Function name indicates batch operation
4. **Atomic by design** - Transaction handling built-in
5. **Easy to test** - Isolated, testable function
6. **Industry standard** - Common pattern (e.g., `bulk_create` in Django ORM)

## Implementation Checklist

- [ ] Create `db_batch_insert` function in `app/utils/db.py`
- [ ] Add unit tests for `db_batch_insert`
- [ ] Update endpoint to use `db_batch_insert`
- [ ] Test atomicity (verify rollback on error)
- [ ] Document function in code and docs

## Alternative: Use CRUDService Pattern

If we want to keep using CRUDService, we could also add a `batch_create` method to `CRUDService`:

```python
class CRUDService:
    def batch_create(
        self,
        data_list: List[dict],
        db: psycopg2.extensions.connection,
        *,
        scope: Optional[InstitutionScope] = None
    ) -> List[T]:
        """Create multiple records atomically"""
        # Uses db_batch_insert internally
        # Validates scope for all records
        # Returns list of DTOs
```

This would be even cleaner, but requires more changes. The `db_batch_insert` approach is simpler and can be used directly or wrapped by CRUDService later.

