# Enum Maintenance Guide

**Purpose**: This is a reference guide for maintaining enums. Keep it handy when adding or modifying enum values—there are no pending implementation plans.

---

## Single Source of Truth

**`app/config/enums/`** is the single source of truth for all enum values. Enum classes live in `app/config/enums/{enum_name}.py` and are exported through `app/config/enums/__init__.py` (and re-exported from `app/config/__init__.py` for convenience).

## Adding a New Enum Value

When you need to add a new value to an existing enum (e.g., add `"Saturday"` to `KitchenDay`), you must update **3 places**:

### 1. Python Enum Class (Required)
**File**: `app/config/enums/{enum_name}.py`

```python
# app/config/enums/kitchen_days.py
class KitchenDay(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    # ... existing values
    SATURDAY = "Saturday"  # ← ADD NEW VALUE HERE
```

**Why**: This is the single source of truth for the application. All code references this enum class.

---

### 2. PostgreSQL ENUM Type (Required)
**File**: `app/db/schema.sql`

**Option A: If database is being rebuilt** (local development):
```sql
-- app/db/schema.sql
CREATE TYPE kitchen_day_enum AS ENUM (
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
    'Saturday'  -- ← ADD NEW VALUE HERE
);
```

**Option B: If database is in production** (requires migration):
```sql
-- Migration script or direct SQL
ALTER TYPE kitchen_day_enum ADD VALUE 'Saturday';
```

**Why**: PostgreSQL enforces enum values at the database level. The database enum must match the Python enum.

**⚠️ Important**: 
- In PostgreSQL, you **cannot remove** enum values once added (without recreating the type)
- You **can add** new values to the end of the enum
- Adding values in the middle requires recreating the type (complex migration)

---

### 3. Seed Data (If Applicable)
**File**: `app/db/seed.sql`

If seed data uses the enum value, update it:
```sql
-- app/db/seed.sql
INSERT INTO plate_kitchen_days (..., kitchen_day, ...) VALUES 
(..., 'Saturday'::kitchen_day_enum, ...);  -- ← Use new value with enum casting
```

**Why**: Seed data must use valid enum values with proper casting.

---

## What You DON'T Need to Update

You **do NOT need to update**:

- ✅ **psycopg2 enum registration** (`app/utils/db_pool.py`) - Automatically handles all enum types
- ✅ **Value preparation mappings** (`app/utils/db.py`) - Uses table/column mappings, not specific values
- ✅ **Pydantic schemas** - Already use enum types, will automatically accept new values
- ✅ **Application code** - Already uses enum classes, will automatically work with new values

---

## Example: Adding "Saturday" to KitchenDay

### Step 1: Update Python Enum
```python
# app/config/enums/kitchen_days.py
class KitchenDay(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"  # ← NEW
```

### Step 2: Update PostgreSQL Enum
```sql
-- app/db/schema.sql (if rebuilding)
CREATE TYPE kitchen_day_enum AS ENUM (
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'
);

-- OR (if in production)
ALTER TYPE kitchen_day_enum ADD VALUE 'Saturday';
```

### Step 3: Update Seed Data (if needed)
```sql
-- app/db/seed.sql
INSERT INTO plate_kitchen_days (plate_id, kitchen_day, ...) VALUES
('uuid', 'Saturday'::kitchen_day_enum, ...);
```

### Step 4: Rebuild Database (local dev) or Run Migration (production)
```bash
# Local development
./app/db/build_kitchen_db.sh

# Production (requires migration script)
# Run ALTER TYPE command above
```

---

## Special Cases

### Adding a New Status Value

Status is used by **30+ tables**. When adding a new status:

1. **Update Python enum**: `app/config/enums/status.py`
2. **Update PostgreSQL enum**: `app/db/schema.sql` (or `ALTER TYPE status_enum ADD VALUE ...`)
3. **No schema changes needed**: All tables already use `status status_enum`, so they automatically accept the new value
4. **Update seed data**: If seed data uses status values, add enum casting

### Adding a New Role Combination

Role combinations are **validated in Pydantic schemas**. When adding a new valid combination:

1. **Update Python enums**: `app/config/enums/role_types.py` and/or `app/config/enums/role_names.py`
2. **Update PostgreSQL enums**: `app/db/schema.sql` (or `ALTER TYPE ... ADD VALUE`)
3. **Update role combination validator**: `app/schemas/consolidated_schemas.py` - add new combination to `valid_combinations` dict
4. **Update `get_valid_for_role_type()`**: `app/config/enums/role_names.py` - add new combination

Example:
```python
# app/config/enums/role_names.py
@classmethod
def get_valid_for_role_type(cls, role_type: RoleType) -> list[str]:
    valid_combinations = {
        RoleType.EMPLOYEE: [cls.ADMIN, cls.SUPER_ADMIN, cls.MANAGER],  # ← NEW
        # ...
    }
```

---

## Best Practices

1. **Always update Python enum first** - This is the source of truth
2. **Keep Python and PostgreSQL enums in sync** - They must match exactly
3. **Test locally first** - Rebuild database and test before deploying
4. **Document breaking changes** - If removing an enum value, document migration path
5. **Use enum casting in seed data** - Always use `'Value'::enum_type` syntax

---

## Troubleshooting

### Error: "invalid input value for enum"
**Cause**: PostgreSQL enum doesn't have the value you're trying to use.

**Fix**: 
- Check if value exists in PostgreSQL: `SELECT unnest(enum_range(NULL::kitchen_day_enum));`
- Add missing value: `ALTER TYPE kitchen_day_enum ADD VALUE 'Saturday';`

### Error: "Enum type not registered"
**Cause**: psycopg2 hasn't registered the enum type for this connection.

**Fix**: 
- Check `app/utils/db_pool.py` - enum should be in `_register_enum_types()` list
- Restart application to re-register types

### Error: Pydantic validation fails
**Cause**: Python enum doesn't have the value.

**Fix**: 
- Check `app/config/enums/{enum_name}.py` - value must exist in enum class
- Import and use enum: `from app.config.enums import KitchenDay` (or `from app.config.enums.kitchen_days import KitchenDay`)

