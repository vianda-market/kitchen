# Enum Migration Roadmap: VARCHAR with CHECK → PostgreSQL ENUM

## Executive Summary

This document outlines the migration strategy for converting VARCHAR columns with CHECK constraints to PostgreSQL ENUM types. The migration improves type safety, performance, and code clarity while maintaining backward compatibility.

**⚠️ IMPORTANT: Local Development Approach**
- **No migration scripts needed** - we're in local development, database will be torn down and rebuilt
- **Update `schema.sql` directly** - add enum types and update column definitions
- **Update `seed.sql`** - remove seed data for deleted tables, add enum casting to all enum values
- **Rebuild database** - tear down and rebuild with new schema
- **Use Postman collection** - populate data using Postman collection after rebuild

## Benefits of ENUM Migration

### 1. **Type Safety**
- ✅ **Compile-time validation**: PostgreSQL enforces enum values at the database level
- ✅ **API-level validation**: Pydantic can validate against enum types automatically
- ✅ **Driver-level support**: psycopg2 handles enum types natively (after registration)

### 2. **Performance**
- ✅ **Storage efficiency**: ENUMs use 4 bytes vs VARCHAR(20) = 20+ bytes
- ✅ **Index efficiency**: ENUM indexes are more compact
- ✅ **Query optimization**: PostgreSQL can optimize enum comparisons better

### 3. **Code Clarity**
- ✅ **Self-documenting**: Enum types clearly show valid values
- ✅ **IDE support**: Better autocomplete and type hints
- ✅ **Reduced validation code**: Less Pydantic validator boilerplate

### 4. **Maintainability**
- ✅ **Single source of truth**: Enum values defined once in Python enum class
- ✅ **Easier refactoring**: Type system catches invalid values
- ✅ **Better error messages**: Clear enum validation errors

## Architectural Principle: Operational Tables vs Enum System Lists

### **Clear Distinction**

**Operational Tables (Dynamic, Must Live in PostgreSQL):**
- ✅ **Business data that changes at runtime**: Users, orders, transactions, bills, etc.
- ✅ **Requires CRUD operations**: Create, read, update, delete via API
- ✅ **Requires audit trails**: History tables, triggers, change tracking
- ✅ **Examples**: `user_info`, `plate_info`, `client_bill_info`, `restaurant_transaction`

**Enum System Lists (Static, Must NOT Live in PostgreSQL):**
- ✅ **Fixed set of values defined at compile time**: Status values, role types, kitchen days, etc.
- ✅ **Never changes at runtime**: Values are part of the application code
- ✅ **Type-safe**: Enforced by PostgreSQL ENUM types and Python enum classes
- ✅ **Examples**: `status_enum`, `role_type_enum`, `kitchen_day_enum`, `pickup_type_enum`

### **Why This Distinction Matters**

1. **Type Safety**: Enum values are validated at compile time, not runtime
2. **Performance**: ENUMs are more efficient than VARCHAR with CHECK constraints
3. **Code Clarity**: Enum values are self-documenting in code
4. **Maintainability**: Single source of truth in Python enum classes
5. **No Runtime Changes**: Enum values are part of the application, not data

## Current State Analysis

### ✅ Already Using ENUM
- **`address_type_enum`**: Used for `address_info.address_type` (array type)
  - Values: `'Restaurant'`, `'Entity Billing'`, `'Entity Address'`, `'Customer Home'`, `'Customer Billing'`, `'Customer Employer'`
  - **Status**: ✅ Fully implemented with psycopg2 registration

### ❌ Should NOT Be ENUMs (Operational Data - Dynamic)
- **Business entities that require runtime CRUD operations**:
  - Users, products, plates, restaurants, bills, transactions
  - These are operational tables, not enum system lists
  - **Decision**: Keep as operational tables with proper foreign keys and constraints

### ✅ Should Be ENUMs (Enum System Lists - Static)

#### 1. **`kitchen_day`** - Priority: HIGH
- **Current**: `VARCHAR(20) CHECK (kitchen_day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'))`
- **Tables**: 
  - `plate_kitchen_days.kitchen_day`
  - `plate_kitchen_days_history.kitchen_day`
  - `plate_selection.kitchen_day`
- **Rationale**: Fixed set of weekdays, never changes
- **Estimated Impact**: Medium (3 tables, frequently queried)

#### 2. **`pickup_type`** - Priority: HIGH
- **Current**: `VARCHAR(20) CHECK (pickup_type IN ('self', 'for_others', 'by_others'))`
- **Tables**:
  - `pickup_preferences.pickup_type`
- **Rationale**: Fixed set of pickup types, core business logic
- **Estimated Impact**: Medium (1 table, core feature)

#### 3. **`operation`** - Priority: MEDIUM
- **Current**: `VARCHAR(10) CHECK (operation IN ('CREATE', 'UPDATE', 'ARCHIVE', 'DELETE'))`
- **Tables**:
  - `restaurant_holidays_history.operation`
  - `plate_kitchen_days_history.operation`
  - Other `_history` tables (via triggers)
- **Rationale**: Fixed set of audit operations, used in history tables
- **Estimated Impact**: Low (history tables, write-only)

#### 4. **`role_type` & `role_name`** - Priority: CRITICAL ⚠️ **CRITICAL**
- **Current**: 
  - `role_info.role_type`: `VARCHAR(20) NOT NULL` (no CHECK constraint)
  - `role_info.name`: `VARCHAR(50) NOT NULL` (no CHECK constraint)
  - `user_info.role_id` → `role_info.role_id` (foreign key)
- **Values**: 
  - `role_type`: `'Employee'`, `'Supplier'`, `'Customer'`
  - `role_name`: `'Admin'`, `'Super Admin'`, `'Comensal'`
- **Valid Combinations** (Fixed Set):
  - `Employee + Admin` = System administrator
  - `Employee + Super Admin` = Super administrator with approval powers
  - `Supplier + Admin` = Supplier administrator
  - `Customer + Comensal` = Regular end user
- **Rationale**: 
  - Role combinations are **fixed at compile time**, not operational data
  - **Remove `role_info` table entirely** - store enums directly on `user_info`
  - Core permission system - **MUST be enums**
- **New Architecture**:
  - Remove `role_info` table
  - Add `role_type role_type_enum NOT NULL` to `user_info`
  - Add `role_name role_name_enum NOT NULL` to `user_info`
  - Remove `role_id` foreign key from `user_info`
  - Validate combinations in Pydantic validators
- **Estimated Impact**: **CRITICAL** (permission system, access control infrastructure, login path)

#### 6. **`status`** - Priority: CRITICAL ⚠️ **CRITICAL**
- **Current**: `VARCHAR(20) NOT NULL DEFAULT 'Active'` (no CHECK constraint, managed via `status_info` table)
- **Tables**: **ALL `_info` tables and `_history` tables** (30+ tables)
  - `user_info.status`, `product_info.status`, `plate_info.status`, `restaurant_info.status`
  - `institution_info.status`, `role_info.status`, `plan_info.status`, etc.
  - All corresponding `_history` tables
- **Current Values** (from `status_info` seed data):
  - `'Pending'`, `'Arrived'`, `'Complete'`, `'Cancelled'` (order category)
  - `'Active'`, `'Inactive'` (general category)
  - `'Processed'` (transaction category)
- **Rationale**: 
  - Status is a **system enum list**, not operational data
  - Status values should be **fixed at compile time**, not managed dynamically
  - Current `status_info` table is **architectural mistake** - enum values don't belong in database
- **Estimated Impact**: **CRITICAL** (affects all tables, core system field)
- **Migration Complexity**: HIGH (requires deprecating `status_info` table and all references)

#### 7. **`holiday_status`** - Priority: MEDIUM
- **Current**: `VARCHAR(20) CHECK (status IN ('Active', 'Inactive', 'Cancelled'))`
- **Tables**:
  - `national_holidays.status`
  - `national_holidays_history.status`
  - `restaurant_holidays.status`
  - `restaurant_holidays_history.status`
- **Rationale**: Limited status set for holidays (subset of general status enum)
- **Note**: Will use same `status_enum` as other tables after migration
- **Estimated Impact**: Low (holiday tables, infrequent updates)

## Migration Strategy

### Phase 1: Preparation (Week 1)

**Important**: Since we're in local development, the migration approach is:
1. Update `schema.sql` directly (add enum types, update column definitions)
2. Update `seed.sql` (remove deleted table seed data, add enum casting)
3. Tear down and rebuild database
4. Use Postman collection to populate data

No migration scripts needed - just schema and seed file updates.

#### 1.1 Create Python Enum Classes
Create enum classes in `app/config/` for each enum type:

```python
# app/config/kitchen_days.py
from enum import Enum

class KitchenDay(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    
    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.values()

# app/config/pickup_types.py
class PickupType(str, Enum):
    SELF = "self"
    FOR_OTHERS = "for_others"
    BY_OTHERS = "by_others"
    # ... same pattern

# app/config/audit_operations.py
class AuditOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ARCHIVE = "ARCHIVE"
    DELETE = "DELETE"
    # ... same pattern

# app/config/role_types.py
class RoleType(str, Enum):
    EMPLOYEE = "Employee"
    SUPPLIER = "Supplier"
    CUSTOMER = "Customer"
    # ... same pattern

# app/config/holiday_status.py
class HolidayStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    CANCELLED = "Cancelled"
    # ... same pattern
```

#### 1.2 Update Pydantic Schemas
Update schemas to use enum types:

```python
# app/schemas/consolidated_schemas.py
from app.config.kitchen_days import KitchenDay
from app.config.pickup_types import PickupType
from app.config.status import Status  # NEW

class PlateKitchenDaysCreateSchema(BaseModel):
    plate_id: UUID
    kitchen_day: KitchenDay  # Changed from str
    # ... rest of schema

class PickupPreferencesCreateSchema(BaseModel):
    pickup_type: PickupType  # Changed from str
    # ... rest of schema

# Update ALL schemas that use status
class UserCreateSchema(BaseModel):
    # ... other fields
    status: Optional[Status] = Field(default=Status.ACTIVE)  # Changed from str

class UserUpdateSchema(BaseModel):
    # ... other fields
    status: Optional[Status] = None  # Changed from Optional[str]

# Repeat for all _info table schemas
```

#### 1.3 Update Service Layer
Update services to use enum types:

```python
# app/services/plate_service.py
from app.config.kitchen_days import KitchenDay

def get_plates_by_day(day: KitchenDay, db: connection):
    # Use enum value directly
    query = "SELECT * FROM plate_kitchen_days WHERE kitchen_day = %s"
    return db_read(query, (day.value,), connection=db)
```

### Phase 2: Database Schema Migration (Week 2)

#### 2.1 Create Enum Types in PostgreSQL
```sql
-- app/db/schema.sql additions
-- CRITICAL: Status enum (must be created first, used by all tables)
CREATE TYPE status_enum AS ENUM (
    'Active', 'Inactive',
    'Pending', 'Arrived', 'Complete', 'Cancelled',
    'Processed'
);

CREATE TYPE role_type_enum AS ENUM ('Employee', 'Supplier', 'Customer');
CREATE TYPE role_name_enum AS ENUM ('Admin', 'Super Admin', 'Comensal');
CREATE TYPE transaction_type_enum AS ENUM ('Order', 'Credit', 'Debit', 'Refund', 'Discretionary', 'Payment');
CREATE TYPE kitchen_day_enum AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday');
CREATE TYPE pickup_type_enum AS ENUM ('self', 'for_others', 'by_others');
CREATE TYPE audit_operation_enum AS ENUM ('CREATE', 'UPDATE', 'ARCHIVE', 'DELETE');
-- Note: holiday_status will use status_enum, no separate type needed
```

#### 2.2 Update Schema Directly (No Migration Scripts)
**Note**: Since we're in local development, we'll update `schema.sql` directly and rebuild the database. No migration scripts needed.

For each enum type, update the schema directly:

```sql
-- app/db/schema.sql

-- Step 1: Create enum type (add to schema.sql)
CREATE TYPE kitchen_day_enum AS ENUM ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday');

-- Step 2: Update table definitions directly
-- BEFORE
CREATE TABLE plate_kitchen_days (
    -- ... other fields
    kitchen_day VARCHAR(20) NOT NULL CHECK (kitchen_day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')),
    -- ... other fields
);

-- AFTER
CREATE TABLE plate_kitchen_days (
    -- ... other fields
    kitchen_day kitchen_day_enum NOT NULL,  -- CHANGE TO ENUM, REMOVE CHECK
    -- ... other fields
);

-- Repeat for all tables using kitchen_day:
-- - plate_kitchen_days
-- - plate_kitchen_days_history
-- - plate_selection
```

**Benefits of Direct Schema Update:**
- ✅ Simpler: No migration scripts to maintain
- ✅ Cleaner: Fresh database with correct schema
- ✅ Faster: No data migration overhead
- ✅ Safer: No risk of migration failures

### Phase 3: psycopg2 Enum Registration (Week 2)

#### 3.1 Update Enum Registration Function
Extend `_register_enum_types()` in `app/utils/db_pool.py`:

```python
def _register_enum_types(conn: psycopg2.extensions.connection):
    """
    Register all PostgreSQL enum types with psycopg2 for proper type handling.
    """
    enum_types = [
        'address_type_enum',      # Already implemented
        'status_enum',            # CRITICAL - used by all tables
        'role_type_enum',         # CRITICAL - permission system
        'role_name_enum',          # CRITICAL - permission system
        'transaction_type_enum',  # CRITICAL - transaction system
        'kitchen_day_enum',       # New
        'pickup_type_enum',       # New
        'audit_operation_enum',   # New
    ]
    
    registered_count = 0
    for enum_name in enum_types:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT oid, typarray 
                    FROM pg_type 
                    WHERE typname = %s
                """, (enum_name,))
                result = cursor.fetchone()
                
                if result:
                    enum_oid, array_oid = result
                    # Register the enum type
                    ENUM_TYPE = psycopg2.extensions.new_type(
                        (enum_oid,), f'{enum_name.upper()}', lambda value, cursor: value
                    )
                    psycopg2.extensions.register_type(ENUM_TYPE, conn)
                    
                    # Register the array type (if exists)
                    if array_oid:
                        ENUM_ARRAY_TYPE = psycopg2.extensions.new_array_type(
                            (array_oid,), f'{enum_name.upper()}_ARRAY', ENUM_TYPE
                        )
                        psycopg2.extensions.register_type(ENUM_ARRAY_TYPE, conn)
                    
                    registered_count += 1
                    log_info(f"✅ Registered {enum_name} and {enum_name}[] types with psycopg2")
        except Exception as e:
            log_warning(f"⚠️ Failed to register {enum_name}: {e}")
    
    if registered_count == len(enum_types):
        log_info(f"✅ Successfully registered {registered_count}/{len(enum_types)} enum types")
    else:
        log_warning(f"⚠️ Only registered {registered_count}/{len(enum_types)} enum types")
    
    return registered_count == len(enum_types)
```

#### 3.2 Update Value Preparation
Extend `_prepare_value_for_db()` in `app/utils/db.py` to handle all enum types:

```python
def _prepare_value_for_db(value: Any, table: str, column: str, connection=None) -> Any:
    """
    Prepare a value for database insertion, handling special types like enums.
    """
    # Handle enum types
    enum_mappings = {
        ('address_info', 'address_type'): 'address_type_enum',
        # Status enum - used by ALL _info and _history tables
        ('user_info', 'status'): 'status_enum',
        ('user_history', 'status'): 'status_enum',
        ('product_info', 'status'): 'status_enum',
        ('product_history', 'status'): 'status_enum',
        ('plate_info', 'status'): 'status_enum',
        ('plate_history', 'status'): 'status_enum',
        ('restaurant_info', 'status'): 'status_enum',
        ('restaurant_history', 'status'): 'status_enum',
        ('institution_info', 'status'): 'status_enum',
        ('institution_history', 'status'): 'status_enum',
        ('role_info', 'status'): 'status_enum',
        ('role_history', 'status'): 'status_enum',
        ('plan_info', 'status'): 'status_enum',
        ('plan_history', 'status'): 'status_enum',
        ('national_holidays', 'status'): 'status_enum',
        ('national_holidays_history', 'status'): 'status_enum',
        ('restaurant_holidays', 'status'): 'status_enum',
        ('restaurant_holidays_history', 'status'): 'status_enum',
        # ... add all other _info and _history tables
        ('plate_kitchen_days', 'kitchen_day'): 'kitchen_day_enum',
        ('plate_kitchen_days_history', 'kitchen_day'): 'kitchen_day_enum',
        ('plate_selection', 'kitchen_day'): 'kitchen_day_enum',
        ('pickup_preferences', 'pickup_type'): 'pickup_type_enum',
        ('restaurant_holidays_history', 'operation'): 'audit_operation_enum',
        ('plate_kitchen_days_history', 'operation'): 'audit_operation_enum',
        # Role enums - stored directly on user_info (no role_info table)
        ('user_info', 'role_type'): 'role_type_enum',
        ('user_info', 'role_name'): 'role_name_enum',
        ('user_history', 'role_type'): 'role_type_enum',
        ('user_history', 'role_name'): 'role_name_enum',
        # Transaction type enum - stored directly on transaction tables (no transaction_type_info table)
        ('restaurant_transaction', 'transaction_type'): 'transaction_type_enum',
    }
    
    enum_type = enum_mappings.get((table, column))
    if enum_type and isinstance(value, (str, Enum)):
        # Convert Enum to string if needed
        enum_value = value.value if isinstance(value, Enum) else value
        
        if _is_enum_registered(connection, enum_type):
            # Use psycopg2.extras.Array for array types, direct value for scalar
            if table == 'address_info' and column == 'address_type':
                return psycopg2.extras.Array([enum_value] if isinstance(enum_value, str) else enum_value)
            return enum_value
        else:
            log_warning(
                f"⚠️ Enum type {enum_type} not registered for connection - "
                f"using SQL casting fallback for {table}.{column}"
            )
            return enum_value  # Will be cast in SQL
    
    # Convert UUID to string
    if isinstance(value, UUID):
        return str(value)
    
    return value
```

### Phase 4: Testing & Validation (Week 3)

#### 4.1 Unit Tests
- Test enum validation in Pydantic schemas
- Test enum registration in psycopg2
- Test fallback SQL casting

#### 4.2 Integration Tests
- Test CRUD operations with enum types
- Test history table triggers with enum types
- Test API endpoints with enum values

#### 4.3 Data Validation
- Verify all existing data migrates correctly
- Check for any invalid enum values in production data
- Validate enum constraints are enforced

## Failure Points & Mitigation Strategies

### Failure Point 1: Enum Registration Fails at Connection Time
**Symptoms**: 
- Warning logs: "⚠️ Failed to register enum types"
- Fallback SQL casting used for all enum operations

**Root Causes**:
- Database connection issues
- Enum type doesn't exist in database
- psycopg2 version incompatibility

**Mitigation**:
- ✅ **Already implemented**: Fallback SQL casting with warning logs
- ✅ **Monitoring**: Track warning log frequency
- ✅ **Validation**: Check enum types exist in database on startup

**Detection**:
```python
# Add to startup checks
def validate_enum_types_exist(db: connection) -> bool:
    """Validate all required enum types exist in database"""
    required_enums = [
        'address_type_enum',
        'status_enum',            # CRITICAL - used by all tables
        'role_type_enum',        # CRITICAL - permission system
        'role_name_enum',         # CRITICAL - permission system
        'transaction_type_enum',  # CRITICAL - transaction system
        'kitchen_day_enum',
        'pickup_type_enum',
        'audit_operation_enum',
    ]
    
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT typname FROM pg_type 
            WHERE typname = ANY(%s)
        """, (required_enums,))
        existing = {row[0] for row in cursor.fetchall()}
    
    missing = set(required_enums) - existing
    if missing:
        log_error(f"❌ Missing enum types: {missing}")
        return False
    
    log_info(f"✅ All {len(required_enums)} enum types exist in database")
    return True
```

### Failure Point 2: Data Migration Fails (Invalid Values)
**Symptoms**:
- Migration script fails with: `invalid input value for enum`
- Existing data contains values not in enum definition

**Root Causes**:
- Data corruption
- Manual database modifications
- Legacy data with old values

**Mitigation**:
- ✅ **Pre-migration validation**: Check for invalid values before migration
- ✅ **Data cleanup script**: Identify and fix invalid values
- ✅ **Rollback plan**: Keep old columns until migration verified

**Detection**:
```sql
-- Pre-migration validation query
SELECT DISTINCT kitchen_day 
FROM plate_kitchen_days 
WHERE kitchen_day NOT IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday');
-- Should return 0 rows
```

### Failure Point 3: API Schema Validation Fails
**Symptoms**:
- Pydantic validation errors when creating/updating records
- API returns 422 Unprocessable Entity

**Root Causes**:
- Client sending string values instead of enum values
- Enum values don't match between Python and PostgreSQL
- Case sensitivity issues

**Mitigation**:
- ✅ **Pydantic validators**: Validate enum values in schemas
- ✅ **Error messages**: Clear error messages with valid enum values
- ✅ **Backward compatibility**: Accept string values and convert to enum

**Example**:
```python
class PlateKitchenDaysCreateSchema(BaseModel):
    kitchen_day: KitchenDay
    
    @validator('kitchen_day', pre=True)
    def validate_kitchen_day(cls, v):
        if isinstance(v, str):
            # Try to convert string to enum
            try:
                return KitchenDay(v)
            except ValueError:
                valid_values = ', '.join(KitchenDay.values())
                raise ValueError(f"Invalid kitchen_day '{v}'. Must be one of: {valid_values}")
        return v
```

### Failure Point 4: History Table Triggers Fail
**Symptoms**:
- History records not created
- Trigger errors in database logs

**Root Causes**:
- Trigger functions not updated for enum types
- Enum casting in trigger functions

**Mitigation**:
- ✅ **Update triggers**: Ensure triggers handle enum types correctly
- ✅ **Test triggers**: Test all trigger operations with enum values
- ✅ **Monitor logs**: Watch for trigger errors

**Example**:
```sql
-- Trigger function must handle enum types
CREATE OR REPLACE FUNCTION plate_kitchen_days_history_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    -- Enum values are handled automatically by PostgreSQL
    INSERT INTO plate_kitchen_days_history (
        kitchen_day,  -- Enum type, no casting needed
        -- ... other fields
    ) VALUES (
        COALESCE(NEW.kitchen_day, OLD.kitchen_day),
        -- ... other values
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Failure Point 5: Seed Data Fails
**Symptoms**:
- Database rebuild fails
- Seed data insertion errors

**Root Causes**:
- Seed SQL files use string literals instead of enum casting
- Enum values in seed data don't match enum definition

**Mitigation**:
- ✅ **Update seed files**: Add `::enum_type` casting to all enum values
- ✅ **Validate seed data**: Check seed data matches enum definitions
- ✅ **Test rebuild**: Test full database rebuild process

**Example**:
```sql
-- app/db/seed.sql
INSERT INTO plate_kitchen_days (plate_id, kitchen_day, ...) VALUES
('uuid1', 'Monday'::kitchen_day_enum, ...),
('uuid2', 'Tuesday'::kitchen_day_enum, ...);
```

### Failure Point 6: psycopg2 Array Handling for Enums
**Symptoms**:
- Array enum values fail to insert
- Type mismatch errors

**Root Causes**:
- Array enum types not registered
- psycopg2.extras.Array not used correctly

**Mitigation**:
- ✅ **Already implemented**: Array handling in `_prepare_value_for_db()`
- ✅ **Test arrays**: Test array enum operations
- ✅ **Fallback**: SQL casting for array enums

## Status System Deprecation Plan

### **Problem Statement**

The current `status_info` table is an **architectural mistake**. Status values are **enum system lists** (static, compile-time constants), not operational data (dynamic, runtime-managed). 

**Current Issues:**
- ❌ Status values stored in database table (`status_info`)
- ❌ Status values can be modified at runtime (should be fixed)
- ❌ No type safety (VARCHAR instead of ENUM)
- ❌ Requires JOINs to validate status values
- ❌ History table (`status_history`) tracks changes to enum values (unnecessary)

**Correct Architecture:**
- ✅ Status values defined in Python enum class (`app/config/status.py`)
- ✅ Status values enforced by PostgreSQL ENUM type
- ✅ Status values validated at compile time, not runtime
- ✅ **Status stored directly on each table** - each table that needs status gets `status status_enum` column
- ✅ **No centralization needed** - status is a property of each entity, not a separate entity
- ✅ No database table needed for enum values

**Key Insight: Status is NOT Centralized**
- Each table that needs status gets its own `status status_enum` column
- No foreign key to a central status table
- Status is a property of the entity (user, product, plate, etc.), not a separate entity
- This is the correct approach - status belongs to the entity, not a lookup table

### **Deprecation Strategy**

#### Phase 1: Create Status Enum (Week 1)
1. **Create Python Enum Class**:
```python
# app/config/status.py
from enum import Enum

class Status(str, Enum):
    """System status values - fixed at compile time"""
    # General statuses
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    
    # Order statuses
    PENDING = "Pending"
    ARRIVED = "Arrived"
    COMPLETE = "Complete"
    CANCELLED = "Cancelled"
    
    # Transaction statuses
    PROCESSED = "Processed"
    
    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.values()
    
    @classmethod
    def get_by_category(cls, category: str) -> list[str]:
        """Get status values by category (for backward compatibility)"""
        category_map = {
            'general': [cls.ACTIVE, cls.INACTIVE],
            'order': [cls.PENDING, cls.ARRIVED, cls.COMPLETE, cls.CANCELLED],
            'transaction': [cls.PROCESSED],
        }
        return [s.value for s in category_map.get(category, [])]
```

2. **Create PostgreSQL ENUM Type**:
```sql
CREATE TYPE status_enum AS ENUM (
    'Active', 'Inactive',
    'Pending', 'Arrived', 'Complete', 'Cancelled',
    'Processed'
);
```

#### Phase 2: Update Schema to Use Status Enum (Week 2)
**Note**: Since we're in local development, we'll update `schema.sql` directly and rebuild the database. No migration scripts needed.

1. **Update All Status Columns in `schema.sql`**:
   - All `_info` tables: Change `status VARCHAR(20) NOT NULL DEFAULT 'Active'` to `status status_enum NOT NULL DEFAULT 'Active'::status_enum`
   - All `_history` tables: Change `status VARCHAR(20) NOT NULL` to `status status_enum NOT NULL`
   - Total: ~30+ tables

2. **Schema Update Pattern**:
```sql
-- app/db/schema.sql
-- BEFORE
CREATE TABLE user_info (
    -- ... other fields
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    -- ... other fields
);

-- AFTER
CREATE TABLE user_info (
    -- ... other fields
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    -- ... other fields
);

-- Repeat for all _info and _history tables
```

3. **No Data Migration Needed**:
   - Database will be torn down and rebuilt
   - Seed data will use enum casting: `'Active'::status_enum`
   - Postman collection will create new data with enum values

#### Phase 3: Remove status_info Infrastructure (Week 4)

**3.1 Remove Foreign Key References**:
```sql
-- Check for any foreign keys referencing status_info
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND ccu.table_name = 'status_info';
```

**3.2 Remove status_info from PRIMARY_KEY_MAPPING**:
```python
# app/utils/db.py
PRIMARY_KEY_MAPPING = {
    # ... other mappings
    # "status_info": "status_id",  # REMOVE THIS LINE
    # ... rest of mappings
}
```

**3.3 Drop status_info Table**:
```sql
-- Drop triggers first
DROP TRIGGER IF EXISTS status_history_trigger ON status_info;

-- Drop history table
DROP TABLE IF EXISTS status_history CASCADE;

-- Drop main table
DROP TABLE IF EXISTS status_info CASCADE;
```

**3.4 Update Seed Data**:
```sql
-- app/db/seed.sql
-- REMOVE these lines:
-- INSERT INTO status_info (status_id, status_name, description, category, modified_by) VALUES ...

-- UPDATE: All status values in seed data must use enum casting
-- BEFORE
INSERT INTO user_info (..., status, ...) VALUES (..., 'Active', ...);

-- AFTER
INSERT INTO user_info (..., status, ...) VALUES (..., 'Active'::status_enum, ...);

-- Repeat for all INSERT statements that set status values
```

**3.5 Remove CRUD Routes** (if any exist):
- Remove any API routes for `status_info` CRUD operations
- Remove from route factory registrations
- Remove schemas for status_info

**3.6 Update Documentation**:
- Remove `status_info` from table naming patterns docs
- Update API documentation to reflect enum-based status

#### Phase 4: Update Application Code (Week 4-5)

**4.1 Update Pydantic Schemas**:
```python
# app/schemas/consolidated_schemas.py
from app.config.status import Status

class UserCreateSchema(BaseModel):
    # ... other fields
    status: Optional[Status] = Field(default=Status.ACTIVE)  # Changed from str

class UserUpdateSchema(BaseModel):
    # ... other fields
    status: Optional[Status] = None  # Changed from Optional[str]
```

**4.2 Update Service Layer**:
```python
# app/services/user_service.py
from app.config.status import Status

def create_user(user_data: dict, db: connection):
    # Status is now enum, not string
    if 'status' not in user_data:
        user_data['status'] = Status.ACTIVE.value
    # ... rest of function
```

**4.3 Remove status_info Queries**:
- Search for: `SELECT * FROM status_info`
- Search for: `status_info` table references
- Replace with enum validation

**4.4 Update Validation Logic**:
```python
# Before (wrong):
def validate_status(status_name: str, category: str, db: connection):
    query = "SELECT status_id FROM status_info WHERE status_name = %s AND category = %s"
    result = db_read(query, (status_name, category), connection=db)
    return result is not None

# After (correct):
from app.config.status import Status

def validate_status(status_value: str):
    return Status.is_valid(status_value)
```

### **Failure Points for Status Migration**

#### Failure Point 7: Invalid Status Values in Production Data
**Symptoms**: Migration fails with `invalid input value for enum status_enum`

**Root Causes**:
- Data contains status values not in enum definition
- Manual database modifications
- Legacy data with old/removed status values

**Mitigation**:
- ✅ **Pre-migration audit**: Query all unique status values before migration
- ✅ **Data cleanup**: Fix invalid status values before migration
- ✅ **Validation script**: Create script to identify all invalid values

**Detection**:
```sql
-- Pre-migration audit: Find all unique status values
SELECT DISTINCT status, COUNT(*) as count
FROM user_info
GROUP BY status
UNION ALL
SELECT DISTINCT status, COUNT(*) as count
FROM product_info
GROUP BY status
-- ... repeat for all tables
ORDER BY status;

-- Expected values only:
-- 'Active', 'Inactive', 'Pending', 'Arrived', 'Complete', 'Cancelled', 'Processed'
```

#### Failure Point 8: Foreign Key References to status_info
**Symptoms**: Cannot drop `status_info` table due to foreign key constraints

**Root Causes**:
- Some table has `status_id` foreign key (shouldn't exist, but check)
- Application code references `status_info.status_id`

**Mitigation**:
- ✅ **Audit foreign keys**: Check for any FK references before dropping
- ✅ **Remove references**: Update any code that uses `status_id` foreign keys
- ✅ **Cascade drop**: Use `CASCADE` when dropping table

#### Failure Point 9: Application Code Still Uses status_info
**Symptoms**: Application errors when trying to query `status_info` table

**Root Causes**:
- Code still has `SELECT * FROM status_info` queries
- Services still validate against `status_info` table
- API routes still expose `status_info` CRUD operations

**Mitigation**:
- ✅ **Code search**: Search entire codebase for `status_info` references
- ✅ **Update all references**: Replace with enum validation
- ✅ **Remove CRUD routes**: Remove any status_info API endpoints
- ✅ **Test thoroughly**: Test all status-related operations

## Role System Deprecation Plan

### **Problem Statement**

The current `role_info` table is an **architectural mistake**. Role combinations are **enum system lists** (static, compile-time constants), not operational data (dynamic, runtime-managed).

**Current Issues:**
- ❌ `role_type` and `name` stored in database table (`role_info`)
- ❌ Role combinations can potentially be modified at runtime (should be fixed)
- ❌ No type safety (VARCHAR instead of ENUM)
- ❌ Requires JOIN on login (performance impact on critical path)
- ❌ Unnecessary indirection (users → role_id → role_info → role_type/name)

**Valid Role Combinations (Fixed Set):**
- `Employee + Admin` = System administrator
- `Employee + Super Admin` = Super administrator with approval powers
- `Supplier + Admin` = Supplier administrator
- `Customer + Comensal` = Regular end user

**Correct Architecture:**
- ✅ `role_type` and `role_name` defined in Python enum classes
- ✅ Both enforced by PostgreSQL ENUM types
- ✅ Values validated at compile time, not runtime
- ✅ **Remove `role_info` table entirely** - store enums directly on `user_info`
- ✅ Validate combinations in Pydantic validators

### **Key Insight: Remove `role_info` Table Entirely**

**Why Remove `role_info` Table:**
1. **Role combinations are fixed**: Only 4 valid combinations exist, unlikely to change
2. **No operational data**: `role_info` only stores enum values (`role_type`, `name`) and descriptions
3. **Simpler schema**: Store `role_type` and `role_name` directly on `user_info` as enum fields
4. **Better performance**: No JOIN needed during login (critical path)
5. **Type safety**: Enums enforce valid combinations at application level
6. **Clearer data model**: Role information directly on user, no indirection

**New Architecture:**
- ✅ Remove `role_info` table entirely
- ✅ Add `role_type role_type_enum NOT NULL` to `user_info`
- ✅ Add `role_name role_name_enum NOT NULL` to `user_info`
- ✅ Remove `role_id` foreign key from `user_info`
- ✅ Validate combinations in Pydantic validators
- ✅ Remove `role_history` table (role changes are rare, track in `user_history`)

**What We Lose:**
- ❌ Role descriptions (can be moved to application constants if needed)
- ❌ Ability to "disable" role combinations via database (can be handled in code)
- ❌ Separate history tracking for role changes (role changes are rare, can track in `user_history`)

**What We Gain:**
- ✅ Simpler schema (one less table, no JOIN on login)
- ✅ Better performance (no JOIN on critical login path)
- ✅ Type safety (enums on user table, validated at compile time)
- ✅ Clearer data model (role info directly on user, no indirection)
- ✅ Easier to understand (no need to look up role to understand user permissions)

### **Deprecation Strategy**

#### Phase 1: Create Role Enums (Week 1)
1. **Create Python Enum Classes**:
```python
# app/config/role_types.py
from enum import Enum

class RoleType(str, Enum):
    """Role types - fixed at compile time"""
    EMPLOYEE = "Employee"
    SUPPLIER = "Supplier"
    CUSTOMER = "Customer"
    
    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.values()

# app/config/role_names.py
class RoleName(str, Enum):
    """Role names - fixed at compile time"""
    ADMIN = "Admin"
    SUPER_ADMIN = "Super Admin"
    COMENSAL = "Comensal"
    
    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.values()
    
    @classmethod
    def get_valid_for_role_type(cls, role_type: RoleType) -> list[str]:
        """Get valid role names for a given role type"""
        valid_combinations = {
            RoleType.EMPLOYEE: [cls.ADMIN, cls.SUPER_ADMIN],
            RoleType.SUPPLIER: [cls.ADMIN],
            RoleType.CUSTOMER: [cls.COMENSAL],
        }
        return [rn.value for rn in valid_combinations.get(role_type, [])]
```

2. **Create PostgreSQL ENUM Types**:
```sql
CREATE TYPE role_type_enum AS ENUM ('Employee', 'Supplier', 'Customer');
CREATE TYPE role_name_enum AS ENUM ('Admin', 'Super Admin', 'Comensal');
```

#### Phase 2: Update Schema to Use Role Enums (Week 2)
**Note**: Since we're in local development, we'll update `schema.sql` directly and rebuild the database. No migration scripts needed.

1. **Update `schema.sql`**:
```sql
-- app/db/schema.sql

-- Step 1: Create enum types (add to schema.sql)
CREATE TYPE role_type_enum AS ENUM ('Employee', 'Supplier', 'Customer');
CREATE TYPE role_name_enum AS ENUM ('Admin', 'Super Admin', 'Comensal');

-- Step 2: Update user_info table definition
-- BEFORE
CREATE TABLE user_info (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    role_id UUID NOT NULL,  -- REMOVE THIS
    -- ... other fields
);

-- AFTER
CREATE TABLE user_info (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,  -- ADD THIS
    role_name role_name_enum NOT NULL,  -- ADD THIS
    -- ... other fields
    -- Remove: FOREIGN KEY (role_id) REFERENCES role_info(role_id)
);

-- Step 3: Update user_history table definition
-- BEFORE
CREATE TABLE user_history (
    -- ... fields
    role_id UUID NOT NULL,  -- REMOVE THIS
    -- ... other fields
);

-- AFTER
CREATE TABLE user_history (
    -- ... fields
    role_type role_type_enum NOT NULL,  -- ADD THIS
    role_name role_name_enum NOT NULL,  -- ADD THIS
    -- ... other fields
);

-- Step 4: Remove role_info and role_history table definitions entirely
-- DELETE these sections from schema.sql:
-- CREATE TABLE role_info ...
-- CREATE TABLE role_history ...
```

2. **No Data Migration Needed**:
   - Database will be torn down and rebuilt
   - Seed data will be updated to use enum values directly
   - Postman collection will create new data with enum values

#### Phase 3: Update Application Code (Week 3)
1. **Remove role_info References**:
   - Remove `role_service` usage from `app/auth/routes.py`
   - Remove `role_id` from user schemas
   - Remove `role_info` from `PRIMARY_KEY_MAPPING`
   - Remove CRUD routes for `role_info` (found in `app/routes/crud_routes.py`)

2. **Update Login Flow**:
```python
# app/auth/routes.py - BEFORE
role = role_service.get_by_id(user.role_id, db)
role_type = role.role_type
role_name = role.name

# app/auth/routes.py - AFTER
role_type = user.role_type.value  # Direct from user, enum value
role_name = user.role_name.value  # Direct from user, enum value
```

3. **Update User Schemas**:
```python
# app/schemas/consolidated_schemas.py
from app.config.role_types import RoleType
from app.config.role_names import RoleName

class UserCreateSchema(BaseModel):
    # Remove role_id
    # Add role_type and role_name
    role_type: RoleType
    role_name: RoleName
    
    @validator('role_name')
    def validate_role_combination(cls, v, values):
        """Validate that role_type and role_name combination is valid"""
        role_type = values.get('role_type')
        if not role_type:
            return v
        
        valid_combinations = {
            RoleType.EMPLOYEE: [RoleName.ADMIN, RoleName.SUPER_ADMIN],
            RoleType.SUPPLIER: [RoleName.ADMIN],
            RoleType.CUSTOMER: [RoleName.COMENSAL],
        }
        
        if v not in valid_combinations.get(role_type, []):
            raise ValueError(
                f"Invalid role combination: {role_type.value} + {v.value}. "
                f"Valid combinations: {[rn.value for rn in valid_combinations.get(role_type, [])]}"
            )
        return v
```

4. **Update User Signup Service**:
```python
# app/services/user_signup_service.py
# Remove CUSTOMER_ROLE constant (no longer needed)
# Update signup to set role_type and role_name directly
from app.config.role_types import RoleType
from app.config.role_names import RoleName

user_data = {
    "role_type": RoleType.CUSTOMER.value,
    "role_name": RoleName.COMENSAL.value,
    # ... other fields
}
```

5. **Update Seed Data**:
   - Remove `role_info` seed data
   - Update user seed data to include `role_type` and `role_name` directly with enum casting:
```sql
-- app/db/seed.sql
-- REMOVE these lines:
-- INSERT INTO role_info (role_id, role_type, name, description, modified_by) VALUES ...

-- UPDATE: INSERT INTO user_info to include role_type and role_name with enum casting
INSERT INTO user_info (
    user_id, username, hashed_password, first_name, last_name, 
    institution_id, role_type, role_name, email, cellphone, 
    is_archived, status, created_date, modified_by, modified_date
) VALUES (
    'uuid', 'admin', 'hash', 'John', 'Doe',
    'inst-uuid', 
    'Employee'::role_type_enum,      -- Enum casting
    'Admin'::role_name_enum,         -- Enum casting
    'admin@example.com', '1234567890', FALSE, 
    'Active'::status_enum,            -- Status enum casting
    NOW(), 'uuid', NOW()
);
```

#### Phase 4: Update Permission Checks and JWT (Week 4)
1. **Update Permission Checks**:
```python
# app/auth/dependencies.py
from app.config.role_types import RoleType
from app.config.role_names import RoleName

def get_super_admin_user(current_user: dict = Depends(get_current_user)):
    """Verify user is Super Admin"""
    if current_user.get("role_type") != RoleType.EMPLOYEE.value:
        raise HTTPException(status_code=403, detail="Employee access required")
    if current_user.get("role_name") != RoleName.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return current_user
```

2. **Update JWT Token Creation** (Already done in Phase 3):
```python
# app/auth/routes.py
# role_type and role_name come directly from user object (enums)
access_token = create_access_token(
    data={
        "sub": str(user.user_id),
        "role_type": user.role_type.value,  # Direct from user, enum value
        "role_name": user.role_name.value,  # Direct from user, enum value
        "institution_id": str(user.institution_id)
    }
)
```

3. **Update Enriched User Queries**:
```python
# app/services/entity_service.py
# Remove JOIN with role_info
# role_type and role_name are now direct columns on user_info
query = """
    SELECT 
        u.user_id,
        u.institution_id,
        u.role_type,      -- Direct column, no JOIN needed
        u.role_name,     -- Direct column, no JOIN needed
        u.username,
        u.email,
        -- ... other fields
    FROM user_info u
    -- No JOIN with role_info needed
"""
```

### **Failure Points for Role Migration**

#### Failure Point 10: Invalid Role Combinations in Production Data
**Symptoms**: Migration fails or creates invalid combinations

**Root Causes**:
- Users have `role_id` pointing to invalid role combinations
- Data contains role combinations not in valid set

**Mitigation**:
- ✅ **Pre-migration audit**: Check all role combinations before migration
- ✅ **Data cleanup**: Fix invalid combinations before migration
- ✅ **Validation**: Ensure all combinations are valid

**Detection**:
```sql
-- Pre-migration audit: Check all role combinations
SELECT r.role_type, r.name, COUNT(*) as user_count
FROM role_info r
JOIN user_info u ON u.role_id = r.role_id
GROUP BY r.role_type, r.name
ORDER BY r.role_type, r.name;

-- Expected combinations only:
-- Employee + Admin
-- Employee + Super Admin
-- Supplier + Admin
-- Customer + Comensal
```

#### Failure Point 11: Orphaned role_id References
**Symptoms**: Migration fails because users reference non-existent roles

**Root Causes**:
- Users have `role_id` that doesn't exist in `role_info`
- Data integrity issues

**Mitigation**:
- ✅ **Pre-migration validation**: Check for orphaned references
- ✅ **Data cleanup**: Fix orphaned references before migration

**Detection**:
```sql
-- Check for orphaned role_id references
SELECT u.user_id, u.role_id
FROM user_info u
LEFT JOIN role_info r ON u.role_id = r.role_id
WHERE r.role_id IS NULL;
-- Should return 0 rows
```

#### Failure Point 12: Application Code Still Uses role_id or role_info
**Symptoms**: Application errors after migration

**Root Causes**:
- Code still queries `role_info` table
- Code still uses `role_id` foreign key
- Services still fetch role from `role_info`

**Mitigation**:
- ✅ **Code search**: Search entire codebase for `role_info` and `role_id` references
- ✅ **Update all references**: Replace with direct enum fields
- ✅ **Remove CRUD routes**: Remove any role_info API endpoints
- ✅ **Test thoroughly**: Test all role-dependent operations

**Detection**:
```bash
# Search for role_info references
grep -r "role_info" app/
grep -r "role_id" app/
grep -r "role_service" app/
# Update all found references
```

## Transaction Type System Deprecation Plan

### **Problem Statement**

The current `transaction_type_info` table is an **architectural mistake**. Transaction types are **enum system lists** (static, compile-time constants), not operational data (dynamic, runtime-managed).

**Current Issues:**
- ❌ Transaction types stored in database table (`transaction_type_info`)
- ❌ Transaction types can potentially be modified at runtime (should be fixed)
- ❌ No type safety (VARCHAR instead of ENUM)
- ❌ **Table is completely unused** - no foreign keys reference it!
- ❌ `restaurant_transaction.transaction_type` is VARCHAR, not a foreign key
- ❌ Code hardcodes values: "Order", "Discretionary" (not validated against table)

**Current Values (from seed data and code):**
- `'Order'` - Customer order transaction (restaurant)
- `'Credit'` - Credit addition transaction (client)
- `'Debit'` - Credit deduction transaction (client)
- `'Refund'` - Refund transaction (client)
- `'Payment'` - Payment transaction (institution)
- `'Discretionary'` - Discretionary credit transaction (used in code, not in seed!)

**Correct Architecture:**
- ✅ Transaction types defined in Python enum class (`app/config/transaction_types.py`)
- ✅ Transaction types enforced by PostgreSQL ENUM type
- ✅ Values validated at compile time, not runtime
- ✅ **Remove `transaction_type_info` table entirely** - store enum directly on transaction tables
- ✅ Validate transaction types in Pydantic validators

### **Key Insight: Remove `transaction_type_info` Table Entirely**

**Why Remove `transaction_type_info` Table:**
1. **Transaction types are fixed**: Only 6 valid types exist, unlikely to change
2. **No operational data**: `transaction_type_info` only stores enum values (`type_name`) and descriptions
3. **Table is unused**: No foreign keys reference it - transactions use VARCHAR directly
4. **Simpler schema**: Store `transaction_type` directly on transaction tables as enum field
5. **Type safety**: Enums enforce valid transaction types at application level
6. **Clearer data model**: Transaction type directly on transaction, no indirection

**New Architecture:**
- ✅ Remove `transaction_type_info` table entirely
- ✅ Add `transaction_type transaction_type_enum NOT NULL` to `restaurant_transaction`
- ✅ Consider adding `transaction_type` to `client_transaction` (currently uses `source` field)
- ✅ Remove `transaction_type_id` foreign key (doesn't exist, but ensure no references)
- ✅ Validate transaction types in Pydantic validators
- ✅ Remove `transaction_type_history` table (transaction type changes are rare)

**What We Lose:**
- ❌ Transaction type descriptions (can be moved to application constants if needed)
- ❌ Ability to "disable" transaction types via database (can be handled in code)
- ❌ Separate history tracking for transaction type changes (rare, can track in transaction history)

**What We Gain:**
- ✅ Simpler schema (one less table)
- ✅ Type safety (enums on transaction tables, validated at compile time)
- ✅ Clearer data model (transaction type directly on transaction, no indirection)
- ✅ Better validation (code can't use invalid transaction types)

### **Deprecation Strategy**

#### Phase 1: Create Transaction Type Enum (Week 1)
1. **Create Python Enum Class**:
```python
# app/config/transaction_types.py
from enum import Enum

class TransactionType(str, Enum):
    """Transaction types - fixed at compile time"""
    # Restaurant transaction types
    ORDER = "Order"
    
    # Client transaction types
    CREDIT = "Credit"
    DEBIT = "Debit"
    REFUND = "Refund"
    DISCRETIONARY = "Discretionary"  # Note: Used in code but not in seed data
    
    # Institution transaction types
    PAYMENT = "Payment"
    
    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.values()
    
    @classmethod
    def get_by_category(cls, category: str) -> list[str]:
        """Get transaction types by category (for backward compatibility)"""
        category_map = {
            'restaurant': [cls.ORDER],
            'client': [cls.CREDIT, cls.DEBIT, cls.REFUND, cls.DISCRETIONARY],
            'institution': [cls.PAYMENT],
        }
        return [tt.value for tt in category_map.get(category, [])]
```

2. **Create PostgreSQL ENUM Type**:
```sql
CREATE TYPE transaction_type_enum AS ENUM (
    'Order',
    'Credit',
    'Debit',
    'Refund',
    'Discretionary',
    'Payment'
);
```

#### Phase 2: Update Schema to Use Transaction Type Enum (Week 2)
**Note**: Since we're in local development, we'll update `schema.sql` directly and rebuild the database. No migration scripts needed.

1. **Update `schema.sql`**:
```sql
-- app/db/schema.sql

-- Step 1: Create enum type (add to schema.sql)
CREATE TYPE transaction_type_enum AS ENUM (
    'Order',
    'Credit',
    'Debit',
    'Refund',
    'Discretionary',
    'Payment'
);

-- Step 2: Update restaurant_transaction table definition
-- BEFORE
CREATE TABLE restaurant_transaction (
    -- ... other fields
    transaction_type VARCHAR(20) NOT NULL,  -- CHANGE THIS
    -- ... other fields
);

-- AFTER
CREATE TABLE restaurant_transaction (
    -- ... other fields
    transaction_type transaction_type_enum NOT NULL,  -- CHANGE TO ENUM
    -- ... other fields
);

-- Step 3: Remove transaction_type_info and transaction_type_history table definitions entirely
-- DELETE these sections from schema.sql:
-- CREATE TABLE transaction_type_info ...
-- CREATE TABLE transaction_type_history ...
```

2. **No Data Migration Needed**:
   - Database will be torn down and rebuilt
   - Seed data will be updated to use enum values directly
   - Postman collection will create new data with enum values

#### Phase 3: Remove transaction_type_info Infrastructure (Week 3)
1. **Remove transaction_type_info from PRIMARY_KEY_MAPPING**:
```python
# app/utils/db.py
PRIMARY_KEY_MAPPING = {
    # ... other mappings
    # "transaction_type_info": "transaction_type_id",  # REMOVE THIS LINE
    # ... rest of mappings
}
```

2. **Drop transaction_type_info Table**:
```sql
-- Drop triggers first
DROP TRIGGER IF EXISTS transaction_type_history_trigger ON transaction_type_info;

-- Drop history table
DROP TABLE IF EXISTS transaction_type_history CASCADE;

-- Drop main table
DROP TABLE IF EXISTS transaction_type_info CASCADE;
```

3. **Update Seed Data**:
```sql
-- app/db/seed.sql
-- REMOVE these lines:
-- INSERT INTO transaction_type_info (transaction_type_id, type_name, description, category, modified_by) VALUES ...

-- UPDATE: All transaction_type values in seed data must use enum casting
-- If seed.sql creates restaurant_transaction records:
-- BEFORE
INSERT INTO restaurant_transaction (..., transaction_type, ...) VALUES (..., 'Order', ...);

-- AFTER
INSERT INTO restaurant_transaction (..., transaction_type, ...) VALUES (..., 'Order'::transaction_type_enum, ...);
```

4. **Remove CRUD Routes** (if any exist):
- Remove any API routes for `transaction_type_info` CRUD operations
- Remove from route factory registrations
- Remove schemas for transaction_type_info

5. **Update Documentation**:
- Remove `transaction_type_info` from table naming patterns docs
- Update API documentation to reflect enum-based transaction types

#### Phase 4: Update Application Code (Week 3-4)
1. **Update Service Layer**:
```python
# app/services/plate_selection_service.py
from app.config.transaction_types import TransactionType

# BEFORE
"transaction_type": "Order",

# AFTER
"transaction_type": TransactionType.ORDER.value,
```

2. **Update Credit Loading Service**:
```python
# app/services/credit_loading_service.py
from app.config.transaction_types import TransactionType

# BEFORE
"transaction_type": "Discretionary",

# AFTER
"transaction_type": TransactionType.DISCRETIONARY.value,
```

3. **Update Pydantic Schemas**:
```python
# app/schemas/consolidated_schemas.py
from app.config.transaction_types import TransactionType

class RestaurantTransactionCreateSchema(BaseModel):
    # ... other fields
    transaction_type: TransactionType  # Changed from str
    
class RestaurantTransactionUpdateSchema(BaseModel):
    # ... other fields
    transaction_type: Optional[TransactionType] = None  # Changed from Optional[str]
```

4. **Remove transaction_type_info Queries**:
- Search for: `SELECT * FROM transaction_type_info`
- Search for: `transaction_type_info` table references
- Replace with enum validation

5. **Update Validation Logic**:
```python
# Before (wrong):
def validate_transaction_type(type_name: str, category: str, db: connection):
    query = "SELECT transaction_type_id FROM transaction_type_info WHERE type_name = %s AND category = %s"
    result = db_read(query, (type_name, category), connection=db)
    return result is not None

# After (correct):
from app.config.transaction_types import TransactionType

def validate_transaction_type(type_value: str):
    return TransactionType.is_valid(type_value)
```

### **Failure Points for Transaction Type Migration**

#### Failure Point 13: Invalid Transaction Type Values in Production Data
**Symptoms**: Migration fails with `invalid input value for enum transaction_type_enum`

**Root Causes**:
- Data contains transaction types not in enum definition
- Code uses "Discretionary" but seed data doesn't have it
- Manual database modifications

**Mitigation**:
- ✅ **Pre-migration audit**: Query all unique transaction_type values before migration
- ✅ **Data cleanup**: Fix invalid transaction types before migration
- ✅ **Validation script**: Create script to identify all invalid values

**Detection**:
```sql
-- Pre-migration audit: Find all unique transaction_type values
SELECT DISTINCT transaction_type, COUNT(*) as count
FROM restaurant_transaction
GROUP BY transaction_type
ORDER BY transaction_type;

-- Expected values only:
-- 'Order', 'Discretionary', 'Payment' (for restaurant_transaction)
-- Note: 'Discretionary' is used in code but not in seed data - need to add to enum
```

#### Failure Point 14: Application Code Still Uses transaction_type_info
**Symptoms**: Application errors when trying to query `transaction_type_info` table

**Root Causes**:
- Code still has `SELECT * FROM transaction_type_info` queries
- Services still validate against `transaction_type_info` table
- API routes still expose `transaction_type_info` CRUD operations

**Mitigation**:
- ✅ **Code search**: Search entire codebase for `transaction_type_info` references
- ✅ **Update all references**: Replace with enum validation
- ✅ **Remove CRUD routes**: Remove any transaction_type_info API endpoints
- ✅ **Test thoroughly**: Test all transaction-related operations

## Migration Priority & Timeline

### Priority 1: Critical Infrastructure Fields (Week 1-5)
1. **`status`** ⚠️ **CRITICAL** - Affects all tables, core system field
   - Week 1: Create enum, update schemas
   - Week 2: Update `schema.sql` (add status_enum, update all 30+ status columns), remove status_info table
   - Week 3: Update `seed.sql` (remove status_info seed data, add enum casting to all status values)
   - Week 4: Update application code, remove status_info references
   - Week 5: Rebuild DB, test all operations

2. **`role_type` & `role_name`** ⚠️ **CRITICAL** - Permission system, access control
   - Week 1: Create enums, update schemas
   - Week 2: Update `schema.sql` (add role enums, update user_info/user_history, remove role_info table)
   - Week 3: Update `seed.sql` (remove role_info seed data, update user seed with enum casting)
   - Week 3: Update login flow (remove JOIN), update permission checks, update JWT handling
   - Week 4: Rebuild DB, test all permission endpoints

3. **`transaction_type`** ⚠️ **CRITICAL** - Transaction system, financial records
   - Week 1: Create enum, update schemas
   - Week 2: Update `schema.sql` (add transaction_type_enum, update restaurant_transaction, remove transaction_type_info table)
   - Week 3: Update `seed.sql` (remove transaction_type_info seed data, add enum casting)
   - Week 3: Update application code, remove transaction_type_info references
   - Week 4: Rebuild DB, test all transaction operations

### Priority 2: High Impact, Low Risk (Week 6-7)
3. **`kitchen_day`** - Core business logic, frequently queried
4. **`pickup_type`** - Core feature, user-facing

### Priority 3: Medium Impact, Low Risk (Week 8-9)
5. **`operation`** - History tables, write-only

### Priority 4: Low Impact, Low Risk (Week 10)
6. **`holiday_status`** - Holiday tables, infrequent updates (will use same status_enum)

## Rollback Plan

### If Schema Update Fails
Since we're in local development with database rebuilds:

1. **Immediate**: Revert `schema.sql` changes (git revert)
2. **Code**: Revert enum changes in Python code (git revert)
3. **Seed**: Revert `seed.sql` changes (git revert)
4. **Rebuild**: Tear down and rebuild database with previous schema

**No Data Loss Risk**: Since database is rebuilt from scratch, no production data to worry about.

### Rollback Process (Git Revert)
Since we're updating schema.sql directly, rollback is simple:

```bash
# Revert all changes
git checkout HEAD -- app/db/schema.sql
git checkout HEAD -- app/db/seed.sql
git checkout HEAD -- app/config/
git checkout HEAD -- app/schemas/
git checkout HEAD -- app/services/
git checkout HEAD -- app/utils/db.py
git checkout HEAD -- app/utils/db_pool.py

# Rebuild database with previous schema
./app/db/build_kitchen_db_dev.sh
```

## Success Metrics

### Technical Metrics
- ✅ All enum types registered successfully (100% registration rate)
- ✅ Zero fallback SQL casting warnings in production
- ✅ All migrations complete without errors
- ✅ All tests passing

### Performance Metrics
- ✅ Storage reduction: ~60% for enum columns (4 bytes vs 20+ bytes)
- ✅ Query performance: No degradation (enums are optimized)
- ✅ Index size: Reduced for enum columns

### Code Quality Metrics
- ✅ Reduced Pydantic validator boilerplate
- ✅ Better type hints and IDE support
- ✅ Clearer error messages

## Seed File Update Requirements

### **Critical: Update `app/db/seed.sql`**

Since we're removing `status_info`, `role_info`, and `transaction_type_info` tables, the seed file must be updated:

#### 1. **Remove Seed Data for Deleted Tables**
```sql
-- app/db/seed.sql

-- REMOVE these sections entirely:
-- INSERT INTO status_info (status_id, status_name, description, category, modified_by) VALUES ...
-- INSERT INTO role_info (role_id, role_type, name, description, modified_by) VALUES ...
-- INSERT INTO transaction_type_info (transaction_type_id, type_name, description, category, modified_by) VALUES ...
```

#### 2. **Update All Enum Value Insertions**
All INSERT statements that use enum values must include enum casting:

```sql
-- app/db/seed.sql

-- Status enum casting
INSERT INTO user_info (..., status, ...) VALUES 
(..., 'Active'::status_enum, ...);  -- Add ::status_enum casting

-- Role enum casting
INSERT INTO user_info (..., role_type, role_name, status, ...) VALUES 
(..., 
    'Employee'::role_type_enum,     -- Add ::role_type_enum casting
    'Admin'::role_name_enum,         -- Add ::role_name_enum casting
    'Active'::status_enum,           -- Add ::status_enum casting
    ...
);

-- Transaction type enum casting
INSERT INTO restaurant_transaction (..., transaction_type, status, ...) VALUES 
(..., 
    'Order'::transaction_type_enum,  -- Add ::transaction_type_enum casting
    'Pending'::status_enum,          -- Add ::status_enum casting
    ...
);

-- Kitchen day enum casting
INSERT INTO plate_kitchen_days (..., kitchen_day, ...) VALUES 
(..., 'Monday'::kitchen_day_enum, ...);  -- Add ::kitchen_day_enum casting

-- Pickup type enum casting
INSERT INTO pickup_preferences (..., pickup_type, ...) VALUES 
(..., 'self'::pickup_type_enum, ...);  -- Add ::pickup_type_enum casting
```

#### 3. **Update User Seed Data**
```sql
-- app/db/seed.sql

-- BEFORE
INSERT INTO user_info (
    user_id, username, hashed_password, first_name, last_name, 
    institution_id, role_id, email, cellphone, 
    is_archived, status, created_date, modified_by, modified_date
) VALUES (
    'uuid', 'admin', 'hash', 'John', 'Doe',
    'inst-uuid', 'role-uuid',  -- role_id reference
    'admin@example.com', '1234567890', FALSE, 'Active',
    NOW(), 'uuid', NOW()
);

-- AFTER
INSERT INTO user_info (
    user_id, username, hashed_password, first_name, last_name, 
    institution_id, role_type, role_name, email, cellphone, 
    is_archived, status, created_date, modified_by, modified_date
) VALUES (
    'uuid', 'admin', 'hash', 'John', 'Doe',
    'inst-uuid', 
    'Employee'::role_type_enum,      -- Direct enum value
    'Admin'::role_name_enum,         -- Direct enum value
    'admin@example.com', '1234567890', FALSE, 
    'Active'::status_enum,            -- Status enum casting
    NOW(), 'uuid', NOW()
);
```

#### 4. **Checklist for Seed File Updates**
- [ ] Remove `INSERT INTO status_info ...`
- [ ] Remove `INSERT INTO role_info ...`
- [ ] Remove `INSERT INTO transaction_type_info ...`
- [ ] Update all `status` values to use `::status_enum` casting
- [ ] Update all `role_type` values to use `::role_type_enum` casting
- [ ] Update all `role_name` values to use `::role_name_enum` casting
- [ ] Update all `transaction_type` values to use `::transaction_type_enum` casting
- [ ] Update all `kitchen_day` values to use `::kitchen_day_enum` casting
- [ ] Update all `pickup_type` values to use `::pickup_type_enum` casting
- [ ] Update all `operation` values to use `::audit_operation_enum` casting
- [ ] Update all `address_type` array values to use `::address_type_enum[]` casting

## Next Steps

1. **Review & Approve**: Review this roadmap with team
2. **Create Enums**: Create Python enum classes (Phase 1.1)
3. **Update Schemas**: Update Pydantic schemas (Phase 1.2)
4. **Update Database Schema**: Update `schema.sql` with enum types and column definitions (Phase 2)
5. **Update Seed Data**: Update `seed.sql` to remove deleted table seed data and add enum casting (see Seed File Update Requirements above)
6. **Tear Down & Rebuild**: Drop database and rebuild with new schema
7. **Test Locally**: Test enum handling, verify seed data loads correctly
8. **Update Postman Collection**: Ensure Postman collection uses enum values (if needed)
9. **Verify**: Test all CRUD operations with enum types

## Post-Migration Cleanup Tasks

### Enum Array Utility Cleanup and Generalization

**Status**: ⏳ Pending (After E2E Postman Collection is Working)

**Current State**:
- Enum array handling for `address_type` is implemented with SQL casting in `_build_insert_sql()`
- Custom `EnumArrayAdapter` class exists but is unused
- Solution works but is specific to `address_type` only

**Tasks**:
1. **Review and Remove Unused Code**:
   - Remove or repurpose `EnumArrayAdapter` class in `app/utils/db.py` (currently unused)
   - Clean up any other unused enum array handling code

2. **Generalize Enum Array Handling**:
   - Create a reusable utility function for enum array handling
   - Support all enum array types (not just `address_type_enum`)
   - Consider if SQL casting approach should be generalized or if psycopg2 registration can be improved

3. **Update Other Services**:
   - Audit codebase for other services/calls that rely on arrays with enums
   - Apply the enum array utility to those cases
   - Ensure consistent handling across the codebase

4. **Documentation**:
   - Document the enum array handling pattern
   - Add examples for future enum array implementations

**Files to Review**:
- `app/utils/db.py` - `EnumArrayAdapter` class, `_build_insert_sql()`, `_prepare_value_for_db()`
- `app/utils/db_pool.py` - Enum array type registration
- Search codebase for other enum array usage patterns

**Priority**: Low (functional but needs cleanup and generalization)

## References

- **Address Type Enum Implementation**: `app/config/address_types.py`
- **Enum Registration**: `app/utils/db_pool.py::_register_enum_types()`
- **Value Preparation**: `app/utils/db.py::_prepare_value_for_db()`
- **Root Cause Resolution**: `docs/CLAUDE.md` (Root Cause Resolution Principle)

