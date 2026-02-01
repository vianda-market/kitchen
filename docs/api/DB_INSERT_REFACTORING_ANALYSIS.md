# `db_insert` Refactoring Analysis

## Current State

- **`db_insert` calls**: Only 2 locations
  - `app/services/crud_service.py` (line 559)
  - `app/routes/admin/archival_config.py` (line 129)
- **Function complexity**: ~40 lines
- **Common logic**: SQL construction, UUID conversion, connection management, logging

## Option 1: DRY with Shared Function + Refactor

### Approach
```python
# Extract common logic
def _build_insert_sql(table: str, data: dict) -> tuple[str, tuple]:
    """Build SQL and values for insert"""
    columns = ', '.join(data.keys())
    placeholders = ', '.join('%s' for _ in data)
    primary_key = PRIMARY_KEY_MAPPING.get(table, "id")
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING {primary_key}"
    values = tuple(v if not isinstance(v, UUID) else str(v) for v in data.values())
    return sql, values

def db_single_insert(table: str, data: dict, connection=None):
    """Insert single record (commits immediately)"""
    sql, values = _build_insert_sql(table, data)
    # ... connection management, execute, commit, return ID

def db_batch_insert(table: str, data_list: List[dict], connection=None):
    """Insert multiple records (commits once at end)"""
    # Validate all data
    # Execute all inserts using _build_insert_sql
    # Commit once
    # Return list of IDs
```

### Pros
- ✅ **True DRY** - Shared logic extracted
- ✅ **Clear separation** - Single vs batch explicit
- ✅ **Type safety** - `db_single_insert` only accepts dict
- ✅ **Future-proof** - Easy to extend

### Cons
- ⚠️ **Refactoring required** - 2 call sites need updates
- ⚠️ **Breaking change** - Function name changes
- ⚠️ **More functions** - 3 functions instead of 1

### Risk Assessment
🟡 **LOW-MEDIUM RISK** - Only 2 call sites, easy to update

---

## Option 2: Make `db_insert` Handle Both (User's Question)

### Approach
```python
def db_insert(table: str, data: Union[dict, List[dict]], connection=None):
    """
    Insert single record or multiple records.
    
    If data is dict: Insert and commit immediately (current behavior)
    If data is list: Insert all, commit once at end (atomic)
    """
    # Detect if single or batch
    is_batch = isinstance(data, list)
    data_list = [data] if not is_batch else data
    
    # Process all inserts
    # Commit once at end
    # Return single ID or list of IDs
```

### Pros
- ✅ **Zero refactoring** - Existing calls unchanged
- ✅ **Backward compatible** - Single dict still works
- ✅ **Single function** - One function for all inserts
- ✅ **Flexible** - Can handle both cases

### Cons
- ❌ **Violates Single Responsibility Principle** - Function does two things
- ❌ **Type confusion** - Return type is `Union[UUID, List[UUID]]`
- ❌ **Less clear API** - Not obvious it handles batches
- ❌ **Runtime type checking** - Must check `isinstance` at runtime
- ❌ **Error handling complexity** - Different error paths
- ❌ **Testing complexity** - Must test both modes

### Risk Assessment
🟡 **MEDIUM RISK** - Works but violates design principles

---

## Option 3: Hybrid - Keep `db_insert`, Add `db_batch_insert` with Shared Helpers

### Approach
```python
# Shared helper (private)
def _build_insert_sql(table: str, data: dict) -> tuple[str, tuple]:
    """Build SQL and values for insert"""
    columns = ', '.join(data.keys())
    placeholders = ', '.join('%s' for _ in data)
    primary_key = PRIMARY_KEY_MAPPING.get(table, "id")
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING {primary_key}"
    values = tuple(v if not isinstance(v, UUID) else str(v) for v in data.values())
    return sql, values

# Keep existing function (unchanged)
def db_insert(table: str, data: dict, connection=None):
    """Insert single record (commits immediately)"""
    sql, values = _build_insert_sql(table, data)
    # ... existing logic unchanged

# New function (uses shared helper)
def db_batch_insert(table: str, data_list: List[dict], connection=None):
    """Insert multiple records (commits once at end)"""
    # Validate all data
    # Execute all inserts using _build_insert_sql
    # Commit once
    # Return list of IDs
```

### Pros
- ✅ **Zero breaking changes** - `db_insert` unchanged
- ✅ **DRY achieved** - Shared SQL building logic
- ✅ **Clear API** - Separate functions for separate purposes
- ✅ **Type safety** - Each function has clear types
- ✅ **Easy to test** - Each function tested independently

### Cons
- ⚠️ **Slight code duplication** - Connection management, logging (but minimal)

### Risk Assessment
🟢 **LOW RISK** - Best of both worlds

---

## Detailed Risk Analysis: Option 2 (Unified Function)

### Risk 1: Return Type Confusion
```python
# Caller must handle both cases
result = db_insert("table", data)
if isinstance(result, list):
    # Batch mode
    ids = result
else:
    # Single mode
    id = result
```
**Impact**: 🔴 **HIGH** - Every caller needs type checking

### Risk 2: Backward Compatibility Edge Cases
```python
# What if someone passes a list with one item?
db_insert("table", [data])  # Returns list or single ID?
# Inconsistent behavior
```
**Impact**: 🟡 **MEDIUM** - Confusing API

### Risk 3: Error Handling Complexity
```python
try:
    result = db_insert("table", data_list)
except Exception:
    # Which insert failed? How many succeeded?
    # Partial success handling?
```
**Impact**: 🟡 **MEDIUM** - Harder to debug

### Risk 4: Type Hints Become Complex
```python
def db_insert(
    table: str, 
    data: Union[dict, List[dict]], 
    connection=None
) -> Union[UUID, List[UUID]]:
    # Type checker can't help much
```
**Impact**: 🟡 **MEDIUM** - Less type safety

### Risk 5: Function Signature Bloat
```python
# Future: What if we need batch-specific options?
def db_insert(
    table: str,
    data: Union[dict, List[dict]],
    connection=None,
    batch_timeout: Optional[int] = None,  # Only for batch
    batch_size: Optional[int] = None,      # Only for batch
    ...
):
    # Function becomes complex
```
**Impact**: 🟡 **MEDIUM** - Harder to maintain

---

## Code Duplication Analysis

### What's Actually Duplicated?

**Option 3 (Hybrid) duplicates**:
- Connection management (~5 lines)
- Logging (~5 lines)
- Error handling (~3 lines)
- **Total: ~13 lines of duplication**

**Option 1 (Full refactor) eliminates**:
- All duplication
- But requires refactoring 2 call sites

**Option 2 (Unified) eliminates**:
- All duplication
- But creates design debt

### Is 13 Lines of Duplication Bad?

**Answer: NO** - This is acceptable duplication because:
1. **Different concerns**: Single insert vs batch insert have different:
   - Transaction boundaries (immediate commit vs deferred commit)
   - Error handling (single failure vs partial failure)
   - Return types (single ID vs list of IDs)
   - Performance characteristics

2. **DRY Principle applies to logic, not code**: The logic is similar but not identical

3. **Maintainability**: Two clear functions are easier to maintain than one complex function

---

## Recommendation: **Option 3 (Hybrid)**

### Rationale

1. **Zero breaking changes** - Existing code unchanged
2. **DRY where it matters** - SQL building logic shared
3. **Clear separation** - Single vs batch explicit
4. **Type safety** - Each function has clear types
5. **Minimal duplication** - Only ~13 lines (acceptable)
6. **Future-proof** - Easy to extend either function independently

### Implementation

```python
# app/utils/db.py

def _build_insert_sql(table: str, data: dict) -> tuple[str, tuple, str]:
    """
    Build SQL statement, values tuple, and primary key for insert.
    
    Returns:
        (sql, values, primary_key)
    """
    columns = ', '.join(data.keys())
    placeholders = ', '.join('%s' for _ in data)
    primary_key = PRIMARY_KEY_MAPPING.get(table, "id")
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING {primary_key}"
    values = tuple(v if not isinstance(v, UUID) else str(v) for v in data.values())
    return sql, values, primary_key

def db_insert(table: str, data: dict, connection=None):
    """Insert single record (commits immediately)"""
    sql, values, primary_key = _build_insert_sql(table, data)
    
    # Connection management
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True
    
    start_time = time.time()
    try:
        cursor = connection.cursor()
        log_info(f"Executing SQL: {sql} with values {values}")
        cursor.execute(sql, values)
        inserted_id = cursor.fetchone()[0]
        connection.commit()
        execution_time = time.time() - start_time
        
        log_info(f"Successfully inserted record into '{table}' with ID {inserted_id}")
        log_info(f"📊 INSERT executed in {execution_time:.3f}s")
        
        if execution_time > 1.0:
            log_warning(f"🐌 Slow INSERT detected: {execution_time:.3f}s - {table}")
        
        return inserted_id
    except Exception as e:
        connection.rollback()
        raise handle_database_exception(e, f"insert into {table}")
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after INSERT execution.")

def db_batch_insert(table: str, data_list: List[dict], connection=None):
    """Insert multiple records atomically (commits once at end)"""
    if not data_list:
        raise ValueError("data_list cannot be empty")
    
    # Connection management (duplicated but acceptable)
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True
    
    start_time = time.time()
    inserted_ids = []
    
    try:
        cursor = connection.cursor()
        
        # Validate all data first
        for i, data in enumerate(data_list):
            if not isinstance(data, dict):
                raise ValueError(f"data_list[{i}] must be a dictionary")
            if not data:
                raise ValueError(f"data_list[{i}] cannot be empty")
        
        # Execute all inserts using shared helper
        for i, data in enumerate(data_list):
            sql, values, primary_key = _build_insert_sql(table, data)
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
        connection.rollback()
        log_error(f"Batch insert failed for '{table}': {e}. All operations rolled back.")
        raise handle_database_exception(e, f"batch insert into {table}")
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after BATCH INSERT execution.")
```

---

## Comparison Table

| Criteria | Option 1 (Refactor) | Option 2 (Unified) | Option 3 (Hybrid) |
|----------|-------------------|-------------------|------------------|
| **Breaking Changes** | 🔴 Yes (2 call sites) | 🟢 No | 🟢 No |
| **DRY Achievement** | ✅ 100% | ✅ 100% | ✅ ~70% (acceptable) |
| **Code Clarity** | ✅ Excellent | ⚠️ Mixed | ✅ Excellent |
| **Type Safety** | ✅ Excellent | ⚠️ Complex | ✅ Excellent |
| **Maintainability** | ✅ Good | ⚠️ Complex | ✅ Excellent |
| **Risk Level** | 🟡 Low-Medium | 🟡 Medium | 🟢 Low |
| **Future-Proof** | ✅ Yes | ⚠️ Limited | ✅ Yes |

---

## Final Recommendation

✅ **Implement Option 3 (Hybrid Approach)**

**Why**:
1. **Zero risk** - No breaking changes
2. **DRY where it matters** - SQL building logic shared
3. **Clear API** - Separate functions for separate purposes
4. **Acceptable duplication** - ~13 lines is fine for different concerns
5. **Easy to maintain** - Each function is simple and focused

**When to consider Option 1**:
- If we have 10+ call sites (we only have 2)
- If we're doing a major refactoring anyway
- If the duplication becomes significant (currently minimal)

**When to avoid Option 2**:
- Always - it violates design principles for minimal benefit

