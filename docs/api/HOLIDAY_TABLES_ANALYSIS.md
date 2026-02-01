# Holiday Tables Analysis: `national_holidays` vs `restaurant_holidays`

## Overview

The system has two separate holiday tables that serve different purposes, though there is some conceptual overlap. This document explains their use cases, differences, and current implementation status.

---

## Table Comparison

### `national_holidays`

**Purpose**: Country-wide holidays that affect all restaurants in a country.

**Schema**:
```sql
CREATE TABLE national_holidays (
    holiday_id UUID PRIMARY KEY,
    country_code VARCHAR(3) NOT NULL,        -- ISO country code (e.g., 'AR', 'PE', 'US')
    holiday_name VARCHAR(100) NOT NULL,
    holiday_date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month INTEGER,                 -- For recurring holidays (1-12)
    recurring_day INTEGER,                    -- For recurring holidays (1-31)
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ,
    modified_by UUID,
    modified_date TIMESTAMPTZ
);
```

**Key Characteristics**:
- **Scope**: Country-level (affects all restaurants in that country)
- **Granularity**: One record per country per holiday date
- **Recurring Support**: Uses `recurring_month` and `recurring_day` (integer fields)
- **Country Code**: Uses ISO 3-letter country codes (`VARCHAR(3)`)

**Example Records**:
- `country_code='AR'`, `holiday_name='Día de la Independencia'`, `holiday_date='2025-07-09'`
- `country_code='US'`, `holiday_name='Independence Day'`, `is_recurring=TRUE`, `recurring_month=7`, `recurring_day=4`

---

### `restaurant_holidays`

**Purpose**: Restaurant-specific holidays that only affect individual restaurants.

**Schema**:
```sql
CREATE TABLE restaurant_holidays (
    holiday_id UUID PRIMARY KEY,
    restaurant_id UUID NOT NULL,             -- Foreign key to restaurant_info
    country VARCHAR(100) NOT NULL,            -- Country name (not code)
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(100),                -- Optional
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_month_day VARCHAR(10),          -- Format: "MM-DD" (e.g., "12-25")
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMPTZ,
    modified_by UUID,
    modified_date TIMESTAMPTZ,
    UNIQUE(restaurant_id, holiday_date)      -- One holiday per restaurant per date
);
```

**Key Characteristics**:
- **Scope**: Restaurant-level (affects only that specific restaurant)
- **Granularity**: One record per restaurant per holiday date
- **Recurring Support**: Uses `recurring_month_day` (string format "MM-DD")
- **Country**: Uses country name (`VARCHAR(100)`) instead of code

**Example Records**:
- `restaurant_id='...'`, `country='Argentina'`, `holiday_date='2025-12-25'`, `holiday_name='Christmas'`
- `restaurant_id='...'`, `country='Argentina'`, `is_recurring=TRUE`, `recurring_month_day='12-25'`

---

## Use Cases

### `national_holidays` Use Cases

1. **Plate Selection Validation** (`app/services/plate_selection_validation.py`)
   - **Purpose**: Prevents customers from selecting plates on national holidays
   - **Function**: `_is_date_national_holiday(date_str, country_code, db)`
   - **Logic**: 
     - Checks if a specific date is a national holiday for the customer's country
     - Supports both exact date matches and recurring holidays
     - Used in `_find_next_available_kitchen_day_in_week()` to skip holidays when finding the next available kitchen day
   - **Example**: If July 9th is Argentina's Independence Day, customers cannot order plates for that day

2. **Billing Service** (`app/services/billing/institution_billing.py`)
   - **Purpose**: Skips billing operations on national holidays
   - **Function**: `is_holiday(country, date, db)`
   - **Logic**: 
     - Checks if a date is a national holiday before processing bills
     - Used in `create_bills_for_entities()` to skip entity billing on holidays
   - **Example**: If a billing date falls on a national holiday, that entity's billing is skipped for that day

3. **API Management** (`app/routes/national_holidays.py`)
   - **Purpose**: Employee-only CRUD API for managing national holidays
   - **Endpoints**:
     - `GET /national-holidays/` - List holidays (filterable by country_code)
     - `GET /national-holidays/{holiday_id}` - Get single holiday
     - `POST /national-holidays/` - Create single holiday
     - `POST /national-holidays/bulk` - Create multiple holidays atomically
     - `PUT /national-holidays/{holiday_id}` - Update holiday
     - `DELETE /national-holidays/{holiday_id}` - Soft delete holiday
   - **Access**: Employees only (via `get_employee_user` dependency)

---

### `restaurant_holidays` Use Cases

**Current Status**: ⚠️ **NOT CURRENTLY USED**

- **Table exists**: ✅ Schema defined in `app/db/schema.sql`
- **DTO exists**: ✅ `RestaurantHolidaysDTO` in `app/dto/models.py`
- **Service exists**: ✅ `restaurant_holidays_service` in `app/services/crud_service.py`
- **Schema exists**: ✅ `RestaurantHolidayCreateSchema`, `RestaurantHolidayUpdateSchema`, `RestaurantHolidayResponseSchema` in `app/schemas/restaurant_holidays.py`
- **Routes exist**: ❌ **NO API ROUTES IMPLEMENTED**
- **Used in services**: ❌ **NOT USED IN ANY SERVICE LOGIC**

**Intended Use Case** (based on schema design):
- Allow individual restaurants to define their own holidays (e.g., restaurant closure days, local festivals)
- These holidays would be restaurant-specific and not affect other restaurants
- Could be used to:
  - Block plate selection for specific restaurants on their custom holidays
  - Skip billing for specific restaurants on their custom holidays
  - Allow restaurants to close on days that aren't national holidays

---

## Key Differences

| Aspect | `national_holidays` | `restaurant_holidays` |
|--------|---------------------|----------------------|
| **Scope** | Country-wide | Restaurant-specific |
| **Country Field** | `country_code` (VARCHAR(3), ISO code) | `country` (VARCHAR(100), name) |
| **Restaurant Link** | None (country-level) | `restaurant_id` (FK) |
| **Recurring Format** | `recurring_month` (INT) + `recurring_day` (INT) | `recurring_month_day` (VARCHAR(10), "MM-DD") |
| **Implementation Status** | ✅ Fully implemented | ⚠️ Schema only, not used |
| **API Endpoints** | ✅ Full CRUD API | ❌ None |
| **Used in Services** | ✅ Plate selection, Billing | ❌ None |
| **Access Control** | Employee-only | N/A (not implemented) |

---

## Overlap Analysis

### Potential Overlap

There is **conceptual overlap** between the two tables:

1. **Same Purpose**: Both track holidays that affect kitchen operations
2. **Same Fields**: Both have `holiday_date`, `holiday_name`, `is_recurring`
3. **Different Granularity**: 
   - `national_holidays`: Country-level (affects all restaurants)
   - `restaurant_holidays`: Restaurant-level (affects one restaurant)

### Why Both Exist

The design suggests a **two-tier holiday system**:

1. **National Holidays** (`national_holidays`):
   - Managed centrally by employees
   - Apply to all restaurants in a country
   - Used for country-wide business logic (plate selection, billing)

2. **Restaurant Holidays** (`restaurant_holidays`):
   - Would be managed by restaurant owners/suppliers
   - Apply only to specific restaurants
   - Would allow restaurants to close on days that aren't national holidays
   - **Currently not implemented** - likely planned for future use

### Design Rationale

This separation allows:
- **Centralized Management**: National holidays managed by system administrators
- **Flexibility**: Restaurants can define their own closure days
- **Granularity**: Different logic can apply national vs. restaurant holidays
- **Scalability**: Can implement restaurant-specific holiday logic without affecting national holiday logic

---

## Current Implementation Details

### Services Using `national_holidays`

1. **`plate_selection_validation.py`**:
   ```python
   def _is_date_national_holiday(date_str: str, country_code: str, db) -> bool:
       # Checks exact date match
       # Checks recurring holidays (month + day)
       # Returns True if date is a national holiday
   ```
   - Used in: `_find_next_available_kitchen_day_in_week()`
   - Purpose: Skip holidays when finding next available kitchen day

2. **`crud_service.py`**:
   ```python
   def is_holiday(country: str, date, db) -> bool:
       # Checks if date is a national holiday
       # Uses: SELECT * FROM national_holiday_info WHERE country = %s AND holiday_date = %s
   ```
   - Used in: `institution_billing.py`
   - Purpose: Skip billing on national holidays

3. **`institution_billing.py`**:
   ```python
   if is_holiday(entity_country, bill_date, connection):
       log_info(f"Date {bill_date} is a national holiday for {entity_country}, skipping entity")
       continue
   ```
   - Purpose: Skip entity billing on national holidays

### Services Using `restaurant_holidays`

**None** - The table exists but is not used in any service logic.

---

## Recommendations

### Current State

1. **`national_holidays`**: ✅ Fully functional and integrated
2. **`restaurant_holidays`**: ⚠️ Schema exists but not implemented

### Future Considerations

If `restaurant_holidays` is to be implemented:

1. **Create API Routes**:
   - Similar to `national_holidays.py` routes
   - Access control: Suppliers (for their restaurants) + Employees (global)
   - Institution scoping for Suppliers

2. **Update Service Logic**:
   - Modify `plate_selection_validation.py` to check both national and restaurant holidays
   - Modify `institution_billing.py` to check both national and restaurant holidays
   - Consider priority: Restaurant holidays override national holidays? Or both block operations?

3. **Consistency Improvements**:
   - Consider standardizing `country_code` vs `country` (use ISO codes in both?)
   - Consider standardizing recurring format (use integers in both?)

4. **Documentation**:
   - Document the relationship between national and restaurant holidays
   - Define behavior when both exist for the same date

---

## Summary

- **`national_holidays`**: ✅ **Active** - Used for country-wide holiday management, fully integrated into plate selection and billing services
- **`restaurant_holidays`**: ⚠️ **Dormant** - Schema exists but no API or service logic implemented

The overlap is **intentional** - they serve different granularities (country vs. restaurant), but `restaurant_holidays` is not yet implemented in the business logic.

---

*Last Updated: 2025-11-21*

