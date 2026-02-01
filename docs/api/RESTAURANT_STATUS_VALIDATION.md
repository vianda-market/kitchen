# Restaurant Validation in Plate Selection

## Overview

Restaurant validation has been added to the plate selection flow to prevent customers from booking plates from restaurants that are not currently operational. This includes:

1. **Restaurant Status** - Restaurant must be 'Active' to accept orders
2. **Holiday Validation** - Restaurant cannot accept orders on holidays (national and restaurant-specific) - *See Future Considerations*

## Implementation

### Restaurant Validation Function

**Location**: `app/services/plate_selection_validation.py`

**Function**: `validate_restaurant_status(restaurant: RestaurantDTO) -> None`

**Purpose**: Validates that a restaurant is available for plate selection. Currently implements status validation; holiday validation is planned for future implementation.

**Behavior**:
- Only restaurants with status `'Active'` can accept plate selections
- Restaurants with other statuses (e.g., 'Inactive', 'Closed', 'Suspended', 'Maintenance') are blocked
- Raises `HTTPException` with status code `403 Forbidden` if restaurant is not active
- Provides user-friendly error messages based on the restaurant's status

**Error Messages**:
- `'Inactive'` → "Restaurant '{name}' is currently inactive and cannot accept new orders. Please try another restaurant."
- `'Closed'` → "Restaurant '{name}' is currently closed and cannot accept new orders. Please try another restaurant."
- `'Suspended'` → "Restaurant '{name}' is currently suspended and cannot accept new orders. Please try another restaurant."
- `'Maintenance'` → "Restaurant '{name}' is under maintenance and cannot accept new orders. Please try another restaurant."
- Other statuses → "Restaurant '{name}' has status '{status}' and cannot accept new orders. Please try another restaurant."

### Integration Point

**Location**: `app/services/plate_selection_service.py`

**Function**: `_fetch_plate_selection_context()`

**Integration**: Restaurant status validation is called immediately after fetching the restaurant and before any other operations:

```python
# Fetch restaurant
restaurant = restaurant_service.get_by_id(plate.restaurant_id, db)
if not restaurant:
    raise HTTPException(status_code=404, detail=f"Restaurant not found...")

# Validate restaurant status - must be 'Active' to accept plate selections
validate_restaurant_status(restaurant)  # ← NEW VALIDATION

# Continue with other validations...
```

### Validation Flow

1. **Route**: `POST /plate-selections/` receives plate selection request
2. **Service**: `create_plate_selection_with_transactions()` orchestrates the process
3. **Context Fetching**: `_fetch_plate_selection_context()` fetches all required data
4. **Restaurant Status Check**: `validate_restaurant_status()` validates restaurant is 'Active'
5. **Early Exit**: If restaurant is not 'Active', validation fails before any records are created

### Benefits

1. **Early Validation**: Restaurant status is checked before any database writes, preventing partial state
2. **User-Friendly Messages**: Clear error messages explain why the restaurant cannot accept orders
3. **Consistent Behavior**: All plate selections go through the same validation path
4. **Logging**: Failed attempts are logged with restaurant ID and name for monitoring
5. **Extensible**: Ready for holiday validation integration when restaurant holidays API is implemented

### Restaurant Status Values

The `restaurant_info` table has a `status VARCHAR(20) NOT NULL DEFAULT 'Active'` field.

**Valid Status Values** (based on common patterns):
- `'Active'` - Restaurant is operational and can accept orders ✅
- `'Inactive'` - Restaurant is temporarily inactive ❌
- `'Closed'` - Restaurant is closed ❌
- `'Suspended'` - Restaurant is suspended ❌
- `'Maintenance'` - Restaurant is under maintenance ❌

**Note**: Only `'Active'` status allows plate selections. All other statuses block plate selection.

### Error Response

When a customer tries to select a plate from a non-active restaurant:

**HTTP Status**: `403 Forbidden`

**Response Body**:
```json
{
  "detail": "Restaurant 'Restaurant Name' is currently inactive and cannot accept new orders. Please try another restaurant."
}
```

### Testing Scenarios

1. **Active Restaurant**: ✅ Plate selection succeeds
2. **Inactive Restaurant**: ❌ Returns 403 with appropriate message
3. **Closed Restaurant**: ❌ Returns 403 with appropriate message
4. **Suspended Restaurant**: ❌ Returns 403 with appropriate message
5. **Maintenance Restaurant**: ❌ Returns 403 with appropriate message
6. **Unknown Status**: ❌ Returns 403 with generic message

### Related Validations

This validation works alongside other plate selection validations:

1. **Restaurant Status** (NEW) - Restaurant must be 'Active'
2. **Plate Availability** - Plate must exist and not be archived
3. **Kitchen Days** - Plate must be available on the target day
4. **National Holidays** - Target day must not be a national holiday
5. **Credit Balance** - Customer must have sufficient credits
6. **Week Constraints** - Orders only allowed for remainder of current week

## Holiday Validation (Future Implementation)

### National Holidays

National holidays are currently checked during kitchen day selection (see `_find_next_available_kitchen_day_in_week()` in `plate_selection_validation.py`), which skips holidays when finding the next available day. However, restaurant-specific holiday validation is not yet implemented.

**Current Behavior**:
- National holidays are considered when determining the next available kitchen day
- If a target day falls on a national holiday, the system automatically skips to the next available day
- This prevents customers from selecting plates on national holidays

**Location**: `app/services/plate_selection_validation.py` → `_find_next_available_kitchen_day_in_week()`

### Restaurant Holidays (Planned)

When the `restaurant_holidays` API is implemented, restaurant-specific holiday validation should be added to the restaurant validation flow.

**Proposed Implementation**:
1. Add `validate_restaurant_holidays()` function to check restaurant-specific holidays
2. Integrate into `validate_restaurant_status()` or create a unified `validate_restaurant()` function
3. Check restaurant holidays for the target date after status validation
4. Provide user-friendly error messages for restaurant-specific closures

**Integration Point**:
```python
# Future implementation in validate_restaurant_status() or new validate_restaurant()
def validate_restaurant(
    restaurant: RestaurantDTO,
    target_date: Optional[str] = None,
    country_code: Optional[str] = None,
    db=None
) -> None:
    # 1. Status validation (current implementation)
    if restaurant.status != 'Active':
        # ... raise exception
    
    # 2. National holiday validation (if target_date provided)
    if target_date and country_code and db:
        if _is_date_national_holiday(target_date, country_code, db):
            # ... raise exception
    
    # 3. Restaurant holiday validation (future - when API is implemented)
    if target_date and db:
        if _is_date_restaurant_holiday(target_date, restaurant.restaurant_id, db):
            # ... raise exception
```

**Related Tables**:
- `national_holidays` - ✅ Currently used for kitchen day selection
- `restaurant_holidays` - ⚠️ Schema exists but API not yet implemented

**See Also**: `docs/api/HOLIDAY_TABLES_ANALYSIS.md` for details on holiday table structure and use cases.

---

*Last Updated: 2025-11-22*

