# Restaurant Holiday API - Implementation Plan

## Overview

This document outlines the plan for implementing the `restaurant_holidays` API and integrating it into the restaurant validation flow. The goal is to allow restaurants to define their own closure days while preventing duplication with national holidays and ensuring comprehensive validation.

## Business Rules

### Core Principles

1. **National Holidays Take Precedence**: All orders are unavailable on national holidays, regardless of restaurant-specific settings
2. **No Duplication**: Restaurants cannot register holidays that are already national holidays
3. **Restaurant-Specific Closures**: Restaurants can define their own closure days (e.g., local festivals, maintenance, temporary closures)
4. **Comprehensive Validation**: Restaurant validation must check both national holidays and restaurant-specific holidays

### Validation Rules

1. **Restaurant Holiday Creation**:
   - ✅ Restaurant can create holidays for dates that are NOT national holidays
   - ❌ Restaurant cannot create holidays for dates that ARE national holidays (rejected with clear error)
   - ✅ Restaurant can create recurring holidays (e.g., "We're closed every Monday")
   - ⚠️ Recurring restaurant holidays that fall on national holidays should be handled carefully

2. **Vianda Selection Validation**:
   - ❌ Block if target date is a national holiday
   - ❌ Block if target date is a restaurant-specific holiday
   - ✅ Allow if target date is neither a national nor restaurant holiday

## Data Model Analysis

### Current Tables

**`national_holidays`**:
- `country_code` — ISO alpha-2 (`VARCHAR(3)` with length check)
- `holiday_date`, `holiday_name`, `is_recurring`, `recurring_month`, `recurring_day`, `status`, `is_archived`
- **`source`**: `'manual' | 'nager_date'` — Nager import rows are always non-recurring; manual rows may recur

**`restaurant_holidays`**:
- `restaurant_id UUID` — Foreign key to restaurant
- **`country_code`** — ISO alpha-2 (server-derived from restaurant address on create/update)
- `holiday_date DATE`, **`holiday_name`** NOT NULL
- `is_recurring`, **`recurring_month`**, **`recurring_day`** (integers, nullable)
- **`source`**: `'manual' | 'national_sync'` (API inserts use **`manual`** until national-sync automation exists)

### Data Consistency Considerations

**Issue**: Two separate tables with potentially overlapping data
- National holidays: Country-level, affects all restaurants
- Restaurant holidays: Restaurant-level, affects one restaurant

**Challenge**: Need to check both tables during validation, which could be inefficient

## Architecture Options

### Option 1: Separate Tables with Validation Logic (Recommended)

**Approach**: Keep `national_holidays` and `restaurant_holidays` as separate tables, validate against both during vianda selection.

**Pros**:
- ✅ Clear separation of concerns (national vs. restaurant)
- ✅ No data duplication
- ✅ Easy to query "all holidays for a restaurant" (union of both)
- ✅ Simple to understand and maintain
- Schema aligned: `restaurant_holidays` uses `country_code` + integer recurrence (see `schema.sql`)

**Cons**:
- ⚠️ Requires two queries during validation (national + restaurant)
- ⚠️ Slightly more complex validation logic

**Implementation**:
```python
def is_restaurant_holiday(restaurant_id: UUID, date: str, country_code: str, db) -> bool:
    # Check national holidays
    if _is_date_national_holiday(date, country_code, db):
        return True
    
    # Check restaurant holidays
    if _is_date_restaurant_holiday(date, restaurant_id, db):
        return True
    
    return False
```

**Performance**: Two queries, but both are indexed and fast. Acceptable for vianda selection validation.

---

### Option 2: Materialized View / Unified Query

**Approach**: Create a database view or use a unified query that combines both tables.

**Pros**:
- ✅ Single query for validation
- ✅ Potentially faster for complex queries
- ✅ Can add computed fields (e.g., `holiday_type: 'national' | 'restaurant'`)

**Cons**:
- ⚠️ More complex to maintain
- ⚠️ Requires database view or complex UNION query
- ⚠️ May need to refresh materialized views
- ⚠️ Overhead for simple use cases

**Implementation**:
```sql
-- Option 2a: Database View
CREATE VIEW restaurant_all_holidays AS
SELECT 
    restaurant_id,
    holiday_date,
    'national' as holiday_type,
    country_code,
    holiday_name
FROM national_holidays nh
JOIN restaurant_info r ON nh.country_code = r.country_code
UNION ALL
SELECT 
    restaurant_id,
    holiday_date,
    'restaurant' as holiday_type,
    country,
    holiday_name
FROM restaurant_holidays;

-- Option 2b: Application-Level Union Query
SELECT holiday_date FROM (
    SELECT holiday_date FROM national_holidays 
    WHERE country_code = %s AND holiday_date = %s
    UNION
    SELECT holiday_date FROM restaurant_holidays 
    WHERE restaurant_id = %s AND holiday_date = %s
) AS all_holidays;
```

**Performance**: Single query, but UNION overhead. May not be significantly faster than two separate queries.

---

### Option 3: Denormalized Cache Table

**Approach**: Create a `restaurant_holiday_cache` table that pre-computes all holidays for each restaurant.

**Pros**:
- ✅ Fastest validation (single query, single table)
- ✅ Can include computed fields (holiday type, source)

**Cons**:
- ❌ Data duplication (national holidays duplicated per restaurant)
- ❌ Complex synchronization (must update cache when national holidays change)
- ❌ Storage overhead
- ❌ Risk of cache inconsistency

**Implementation**:
```sql
CREATE TABLE restaurant_holiday_cache (
    restaurant_id UUID,
    holiday_date DATE,
    holiday_type VARCHAR(10), -- 'national' or 'restaurant'
    source_id UUID, -- holiday_id from source table
    PRIMARY KEY (restaurant_id, holiday_date)
);
```

**Performance**: Fastest, but significant maintenance overhead.

---

## Recommended Approach: Option 1 (Separate Tables)

**Rationale**:
1. **Simplicity**: No schema changes, no cache maintenance
2. **Performance**: Two indexed queries are fast enough for validation
3. **Maintainability**: Clear separation, easy to understand
4. **Scalability**: Can optimize later if needed (e.g., add indexes, materialized view)

**Validation Query Pattern**:
```python
# Fast path: Check restaurant holidays first (more specific)
restaurant_holiday = check_restaurant_holiday(restaurant_id, date, db)
if restaurant_holiday:
    return True  # Restaurant-specific holiday

# Fallback: Check national holidays (broader scope)
national_holiday = check_national_holiday(country_code, date, db)
if national_holiday:
    return True  # National holiday

return False  # No holiday
```

## API Design Plan

### Endpoints

**Base Path**: `/restaurant-holidays`

1. **GET `/restaurant-holidays/`** - List restaurant holidays
   - Query params: `restaurant_id` (required for Suppliers), `include_archived` (default: false)
   - Access: Suppliers (own restaurants), Employees (all restaurants)
   - Returns: `List[RestaurantHolidayResponseSchema]`

2. **GET `/restaurant-holidays/{holiday_id}`** - Get single holiday
   - Access: Suppliers (own restaurants), Employees (all restaurants)
   - Returns: `RestaurantHolidayResponseSchema`

3. **POST `/restaurant-holidays/`** - Create restaurant holiday
   - Body: `RestaurantHolidayCreateSchema`
   - Access: Suppliers (own restaurants), Employees (all restaurants)
   - **Validation**: Reject if date is a national holiday
   - Returns: `RestaurantHolidayResponseSchema`

4. **POST `/restaurant-holidays/bulk`** - Create multiple holidays atomically
   - Body: `RestaurantHolidayBulkCreateSchema`
   - Access: Suppliers (own restaurants), Employees (all restaurants)
   - **Validation**: Reject entire batch if any date is a national holiday
   - Returns: `List[RestaurantHolidayResponseSchema]`

5. **PUT `/restaurant-holidays/{holiday_id}`** - Update holiday
   - Body: `RestaurantHolidayUpdateSchema`
   - Access: Suppliers (own restaurants), Employees (all restaurants)
   - **Validation**: Reject if new date is a national holiday
   - Returns: `RestaurantHolidayResponseSchema`

6. **DELETE `/restaurant-holidays/{holiday_id}`** - Soft delete holiday
   - Access: Suppliers (own restaurants), Employees (all restaurants)
   - Returns: 204 No Content

### Access Control

- **Suppliers**: Can manage holidays for restaurants in their institution only
- **Employees**: Can manage holidays for all restaurants (global access)
- **Customers**: No access (403 Forbidden)

### Institution Scoping

- Uses `EntityScopingService` with `ENTITY_RESTAURANT_HOLIDAY`
- Scoping path: `restaurant_holidays` → `restaurant_info` → `institution_id`

## Validation Logic Plan

### 1. Restaurant Holiday Creation Validation

**Location**: `app/routes/restaurant_holidays.py` → `create_restaurant_holiday()`

**Validation Steps**:
1. Validate restaurant exists and belongs to user's institution (if Supplier)
2. **Check if date is a national holiday**:
   ```python
   # Get restaurant's country code
   restaurant = restaurant_service.get_by_id(restaurant_id, db)
   address = address_service.get_by_id(restaurant.address_id, db)
   country_code = get_country_code_from_address(address.country)  # Convert name to code
   
   # Check national holidays
   if _is_date_national_holiday(holiday_date, country_code, db):
       raise HTTPException(
           status_code=409,
           detail=f"Date {holiday_date} is already a national holiday. Restaurants cannot register holidays on national holidays."
       )
   ```
3. Check for duplicate restaurant holiday (same restaurant + same date)
4. Validate recurring holiday format (if `is_recurring=True`)

**Error Messages**:
- National holiday conflict: "Date {date} is already a national holiday. Restaurants cannot register holidays on national holidays."
- Duplicate restaurant holiday: "Restaurant already has a holiday registered for {date}"

### 2. Restaurant Holiday Update Validation

**Location**: `app/routes/restaurant_holidays.py` → `update_restaurant_holiday()`

**Validation Steps**:
1. Validate restaurant exists and belongs to user's institution (if Supplier)
2. If `holiday_date` is being updated, check if new date is a national holiday
3. Check for duplicate restaurant holiday (excluding current record)

### 3. Vianda Selection Validation Integration

**Location**: `app/services/vianda_selection_validation.py`

**Current Function**: `validate_restaurant_status()` (status only)

**Proposed Enhancement**: Extend to `validate_restaurant()` with holiday checking

**New Function Signature**:
```python
def validate_restaurant(
    restaurant: RestaurantDTO,
    target_date: Optional[str] = None,  # YYYY-MM-DD format
    country_code: Optional[str] = None,
    db=None
) -> None:
    """
    Comprehensive restaurant validation including status and holidays.
    
    1. Status validation (current implementation)
    2. National holiday validation (if target_date provided)
    3. Restaurant holiday validation (if target_date provided)
    """
```

**Implementation Flow**:
```python
def validate_restaurant(
    restaurant: RestaurantDTO,
    target_date: Optional[str] = None,
    country_code: Optional[str] = None,
    db=None
) -> None:
    # 1. Status validation (always check)
    if restaurant.status != 'Active':
        raise HTTPException(...)
    
    # 2. Holiday validation (only if target_date provided)
    if target_date and country_code and db:
        # Check national holidays
        if _is_date_national_holiday(target_date, country_code, db):
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' cannot accept orders on {target_date} due to a national holiday. Please select another date."
            )
        
        # Check restaurant holidays
        if _is_date_restaurant_holiday(target_date, restaurant.restaurant_id, db):
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' is closed on {target_date} due to a restaurant holiday. Please select another date."
            )
```

**Helper Functions Needed**:
```python
def _is_date_restaurant_holiday(
    date_str: str,
    restaurant_id: UUID,
    db: psycopg2.extensions.connection
) -> bool:
    """
    Check if a specific date is a restaurant holiday.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        restaurant_id: Restaurant ID
        db: Database connection
        
    Returns:
        True if the date is a restaurant holiday, False otherwise
    """
    # Check exact date match
    query = """
    SELECT COUNT(*) FROM restaurant_holidays 
    WHERE restaurant_id = %s 
    AND holiday_date = %s 
    AND is_archived = FALSE
    """
    result = db_read(query, (str(restaurant_id), date_str), connection=db, fetch_one=True)
    
    if result and result.get('count', 0) > 0:
        return True
    
    from datetime import datetime
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        month = date_obj.month
        day = date_obj.day

        query = """
        SELECT COUNT(*) FROM restaurant_holidays
        WHERE restaurant_id = %s
        AND recurring_month = %s
        AND recurring_day = %s
        AND is_recurring = TRUE
        AND is_archived = FALSE
        """
        result = db_read(
            query, (str(restaurant_id), month, day), connection=db, fetch_one=True
        )

        return result and result.get('count', 0) > 0
    except ValueError:
        return False
```

### 4. Integration into Vianda Selection Flow

**Location**: `app/services/vianda_selection_service.py`

**Current Flow**:
1. Fetch context (vianda, restaurant, address, etc.)
2. Validate restaurant status
3. Determine target kitchen day
4. Validate credits
5. Create selection

**Enhanced Flow**:
1. Fetch context (vianda, restaurant, address, etc.)
2. Determine target kitchen day
3. **Calculate target date from target kitchen day**
4. **Validate restaurant (status + holidays for target date)**
5. Validate credits
6. Create selection

**Date Calculation**:
```python
# After determining target_day, calculate actual date
from datetime import datetime, timedelta
from app.services.date_service import get_effective_current_day

current_day = get_effective_current_day()
days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

current_index = days_of_week.index(current_day)
target_index = days_of_week.index(target_day)
days_ahead = target_index - current_index
if days_ahead < 0:
    days_ahead += 7  # Next week

target_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

# Now validate restaurant with target date
validate_restaurant(
    restaurant=context["restaurant"],
    target_date=target_date,
    country_code=context["address"].country,  # Need to convert to country_code
    db=db
)
```

## Data Consistency Strategy

### Preventing Duplication

**Approach**: Validation at creation/update time

1. **During Restaurant Holiday Creation**:
   - Query `national_holidays` for the restaurant's country
   - Check exact date match
   - Check recurring holidays (if restaurant holiday is recurring)
   - Reject if match found

2. **During Restaurant Holiday Update**:
   - If `holiday_date` is being changed, re-validate against national holidays
   - Reject if new date is a national holiday

3. **Bulk Creation**:
   - Validate all dates before creating any
   - If any date is a national holiday, reject entire batch (atomic)

### Handling Recurring Holidays

**Challenge**: Recurring restaurant holidays might overlap with national holidays on specific dates.

**Solution Options**:

**Option A: Allow Recurring, Validate on Use** (Recommended)
- Allow restaurants to create recurring holidays (e.g., "Closed every Monday")
- During vianda selection, check if the specific date is both:
  - A recurring restaurant holiday match
  - NOT a national holiday
- If it's a national holiday, national holiday takes precedence (no need to check restaurant holiday)

**Option B: Validate Recurring Against All National Holidays**
- When creating recurring restaurant holiday, check against all recurring national holidays
- Reject if recurring pattern matches (e.g., restaurant "Closed every July 4th" vs. national "Independence Day")
- **Problem**: Complex validation, might reject valid use cases

**Recommendation**: **Option A** - Simpler, more flexible, national holidays naturally take precedence.

## Implementation Phases

### Phase 1: API Foundation
- [ ] Create `RestaurantHolidayCreateSchema`, `RestaurantHolidayUpdateSchema`, `RestaurantHolidayResponseSchema`
- [ ] Create `RestaurantHolidayBulkCreateSchema` for bulk operations
- [ ] Create routes file `app/routes/restaurant_holidays.py`
- [ ] Implement basic CRUD endpoints
- [ ] Add institution scoping
- [ ] Register routes in `application.py`

### Phase 2: National Holiday Validation
- [ ] Add helper function to get country code from country name
- [ ] Implement national holiday check in `create_restaurant_holiday()`
- [ ] Implement national holiday check in `update_restaurant_holiday()`
- [ ] Implement national holiday check in `create_restaurant_holidays_bulk()`
- [ ] Add appropriate error messages
- [ ] Test rejection of national holiday dates

### Phase 3: Restaurant Holiday Validation Functions
- [ ] Implement `_is_date_restaurant_holiday()` helper function
- [ ] Support both exact date and recurring holiday checks
- [ ] Add unit tests for holiday checking logic

### Phase 4: Integration into Vianda Selection
- [ ] Extend `validate_restaurant_status()` to `validate_restaurant()` with holiday parameters
- [ ] Add date calculation logic in vianda selection service
- [ ] Integrate holiday validation into vianda selection flow
- [ ] Update error messages to distinguish national vs. restaurant holidays
- [ ] Test vianda selection blocking on restaurant holidays

### Phase 5: Testing & Documentation
- [ ] Create Postman collection for restaurant holidays API
- [ ] Test all validation scenarios
- [ ] Update `RESTAURANT_VALIDATION.md` with implementation details
- [ ] Document API in `API_PERMISSIONS_BY_ROLE.md`

## Performance Considerations

### Query Optimization

**Indexes Needed**:
```sql
-- Already exists for national_holidays
CREATE INDEX idx_national_holidays_country_date 
ON national_holidays(country_code, holiday_date) 
WHERE NOT is_archived;

-- Need for restaurant_holidays
CREATE INDEX idx_restaurant_holidays_restaurant_date 
ON restaurant_holidays(restaurant_id, holiday_date) 
WHERE NOT is_archived;

CREATE INDEX idx_restaurant_holidays_recurring
ON restaurant_holidays(restaurant_id, recurring_month, recurring_day)
WHERE is_recurring AND NOT is_archived;
```

### Caching Strategy (Future)

If performance becomes an issue:
- Cache restaurant holidays per restaurant (invalidate on create/update/delete)
- Cache national holidays per country (invalidate on create/update/delete)
- Use Redis or in-memory cache for frequently accessed data

## Open Questions

1. **Country code**: **`restaurant_holidays.country_code`** is stored on the row and **derived** from `restaurant_info` → `address_info.country_code` (with name→code fallback when needed), same alpha-2 space as `national_holidays`.

2. **Recurring Holiday Overlap**: Should we prevent recurring restaurant holidays that might overlap with national holidays?
   - **Recommendation**: No - validate on specific dates during vianda selection, national holidays take precedence

3. **Bulk Operations**: Should bulk creation allow partial success if some dates are national holidays?
   - **Recommendation**: No - atomic rejection (all or nothing) for data consistency

## Summary

**Architecture Decision**: **Option 1 - Separate Tables with Validation Logic**
- Keep `national_holidays` and `restaurant_holidays` as separate tables
- Validate against both during vianda selection
- Two queries are fast enough and maintain clear separation

**Key Validations**:
1. Restaurant holiday creation: Reject if date is a national holiday
2. Vianda selection: Block if date is either national or restaurant holiday
3. National holidays take precedence (already enforced by validation)

**Implementation Priority**:
1. API foundation (CRUD endpoints)
2. National holiday validation (prevent duplication)
3. Restaurant holiday checking functions
4. Integration into vianda selection validation

---

*Last Updated: 2025-11-22*

