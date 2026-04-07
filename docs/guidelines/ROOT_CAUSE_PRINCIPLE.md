# Root Cause Resolution Principle

Always fix issues at the root cause. Never apply downstream transformations as a primary fix.

## Why This Matters

- **Type safety:** Root cause fixes ensure correct type handling throughout the stack
- **Maintainability:** One fix at the source vs. workarounds scattered across consumers
- **Consistency:** All code paths use the same correct approach
- **Future-proofing:** Prevents the same class of issue from appearing elsewhere

## Concrete Example: Enum Array Type Mismatch

**Problem:** Inserting `address_type` arrays into PostgreSQL — psycopg2 sends them as `TEXT[]` instead of `address_type_enum[]`, causing type errors.

**❌ Wrong (downstream workaround):**
```python
def _build_insert_sql(table, data):
    for col in data.keys():
        if table == 'address_info' and col == 'address_type':
            placeholders.append('%s::address_type_enum[]')  # SQL casting everywhere
```

**✅ Correct (root cause fix):**
```python
# Register enum type once at connection time
def _register_enum_types(conn):
    cursor.execute("SELECT oid, typarray FROM pg_type WHERE typname = 'address_type_enum'")
    oid, array_oid = cursor.fetchone()
    psycopg2.extensions.register_type(psycopg2.extensions.new_type((oid,), 'ADDRESS_TYPE_ENUM', ...), conn)
    psycopg2.extensions.register_type(psycopg2.extensions.new_array_type((array_oid,), ...), conn)

# Then use Array() — driver handles type automatically
def _prepare_value_for_db(value, table, column, connection=None):
    if table == 'address_info' and column == 'address_type' and isinstance(value, list):
        return psycopg2.extras.Array(value)
```

## Decision Framework

| Scenario | Root Cause Fix |
|---|---|
| Type mismatch in API layer | Fix Pydantic validation / type conversion at input |
| Type mismatch in DB layer | Fix driver type registration / adapters at connection time |
| Validation error | Fix validation logic, not add try/except workarounds |
| Performance issue | Fix query or index, not add caching everywhere |
| Data transformation needed | Fix data source, not transform in every consumer |

## When Fallbacks Are Acceptable

Fallbacks are acceptable only for:
1. Root cause fix in progress but not yet deployed
2. Rare edge cases in external dependencies (connection pool failures, etc.)
3. Temporary workarounds with a clear TODO and timeline for removal

**All fallbacks must:**
- Log a `warning` when the fallback path is taken
- Explain why in the log message
- Have a TODO comment with removal timeline

```python
def _prepare_value_for_db(value, table, column, connection=None):
    if table == 'address_info' and column == 'address_type' and isinstance(value, list):
        if _is_enum_registered(connection):
            return psycopg2.extras.Array(value)   # root cause fix
        else:
            log_warning(
                "⚠️ address_type_enum not registered — falling back to SQL casting. "
                "Investigate enum registration in db_pool.py."
            )
            return value  # SQL will cast with %s::address_type_enum[]
```

## Current Enum State in This Codebase

- `address_type_enum` — registered at connection time in `app/utils/db_pool.py`, uses `psycopg2.extras.Array()`
- `status` fields — stored as `VARCHAR` with CHECK constraints (not enums) because values are managed dynamically in `status_info` table
