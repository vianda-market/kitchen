# Bulk API Pattern

## Overview

Some FastAPI endpoints support **bulk operations** that allow creating, updating, or deleting multiple records in a single API call. All bulk operations are **atomic** - either all operations succeed or all fail (transactional).

## Bulk Operation Patterns

There are two patterns for bulk operations:

### Pattern 1: Array in POST Body (Single Endpoint)

**Endpoint**: `POST /api/v1/vianda-kitchen-days/`

The POST endpoint accepts an array in the request body, even for single items. The response is always an array.

**Example Request**:
```json
POST /api/v1/vianda-kitchen-days/
{
  "vianda_id": "uuid",
  "kitchen_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
}
```

**Example Response**:
```json
[
  {
    "vianda_kitchen_day_id": "uuid",
    "vianda_id": "uuid",
    "kitchen_day": "Monday",
    "is_archived": false,
    "created_date": "2025-11-19T12:00:00Z",
    "modified_by": "uuid",
    "modified_date": "2025-11-19T12:00:00Z"
  },
  {
    "vianda_kitchen_day_id": "uuid",
    "vianda_id": "uuid",
    "kitchen_day": "Tuesday",
    "is_archived": false,
    "created_date": "2025-11-19T12:00:00Z",
    "modified_by": "uuid",
    "modified_date": "2025-11-19T12:00:00Z"
  }
  // ... more items
]
```

**Single Item**: Even for a single day, use an array:
```json
POST /api/v1/vianda-kitchen-days/
{
  "vianda_id": "uuid",
  "kitchen_days": ["Monday"]  // Array with 1 item
}
```

**Response**: Always returns an array (even for 1 item):
```json
[
  {
    "vianda_kitchen_day_id": "uuid",
    "vianda_id": "uuid",
    "kitchen_day": "Monday",
    // ... other fields
  }
]
```

### Pattern 2: Separate Bulk Endpoint

**Endpoint**: `POST /api/v1/national-holidays/bulk`

Some APIs have a dedicated `/bulk` endpoint alongside the standard single-item endpoint.

**Example Request**:
```json
POST /api/v1/national-holidays/bulk
[
  {
    "country_code": "US",
    "holiday_name": "New Year's Day",
    "holiday_date": "2025-01-01",
    "is_recurring": true,
    "recurring_month": 1,
    "recurring_day": 1
  },
  {
    "country_code": "US",
    "holiday_name": "Independence Day",
    "holiday_date": "2025-07-04",
    "is_recurring": true,
    "recurring_month": 7,
    "recurring_day": 4
  }
]
```

**Example Response**:
```json
[
  {
    "national_holiday_id": "uuid",
    "country_code": "US",
    "holiday_name": "New Year's Day",
    "holiday_date": "2025-01-01",
    "is_recurring": true,
    "recurring_month": 1,
    "recurring_day": 1,
    "is_archived": false,
    "created_date": "2025-11-19T12:00:00Z",
    "modified_by": "uuid",
    "modified_date": "2025-11-19T12:00:00Z"
  },
  {
    "national_holiday_id": "uuid",
    "country_code": "US",
    "holiday_name": "Independence Day",
    "holiday_date": "2025-07-04",
    "is_recurring": true,
    "recurring_month": 7,
    "recurring_day": 4,
    "is_archived": false,
    "created_date": "2025-11-19T12:00:00Z",
    "modified_by": "uuid",
    "modified_date": "2025-11-19T12:00:00Z"
  }
]
```

## Available Bulk Endpoints

### 1. Vianda Kitchen Days
- **Endpoint**: `POST /api/v1/vianda-kitchen-days/`
- **Pattern**: Array in POST body (Pattern 1)
- **Schema**: `ViandaKitchenDayCreateSchema` with `kitchen_days: List[str]`
- **Returns**: `List[ViandaKitchenDayResponseSchema]`
- **Access**: Suppliers (institution-scoped), Employees (global)

**Use Case**: Assign multiple days of the week (Monday-Friday) to a vianda in one atomic operation.

**TypeScript Example**:
```typescript
interface CreateKitchenDaysRequest {
  vianda_id: string;
  kitchen_days: string[];  // ["Monday", "Tuesday", ...]
}

interface KitchenDayResponse {
  vianda_kitchen_day_id: string;
  vianda_id: string;
  kitchen_day: string;
  is_archived: boolean;
  created_date: string;
  modified_by: string;
  modified_date: string;
}

// Usage
const createKitchenDays = async (
  plateId: string,
  days: string[]
): Promise<KitchenDayResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/vianda-kitchen-days/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      vianda_id: plateId,
      kitchen_days: days  // Array of day names
    })
  });
  
  if (!response.ok) {
    throw new Error('Failed to create kitchen days');
  }
  
  return response.json();  // Always returns an array
};

// Single day (still use array)
await createKitchenDays(plateId, ["Monday"]);

// Multiple days
await createKitchenDays(plateId, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]);
```

### 2. National Holidays
- **Endpoint**: `POST /api/v1/national-holidays/bulk`
- **Pattern**: Separate bulk endpoint (Pattern 2)
- **Schema**: `NationalHolidayBulkCreateSchema` containing `List[NationalHolidayCreateSchema]`
- **Returns**: `List[NationalHolidayResponseSchema]`
- **Access**: Employees only

**Use Case**: Create multiple national holidays for a country in one atomic operation.

**TypeScript Example**:
```typescript
interface NationalHolidayCreate {
  country_code: string;
  holiday_name: string;
  holiday_date: string;  // YYYY-MM-DD
  is_recurring: boolean;
  recurring_month?: number;
  recurring_day?: number;
}

// Usage
const createHolidays = async (
  holidays: NationalHolidayCreate[]
): Promise<NationalHolidayResponse[]> => {
  const response = await fetch(`${API_BASE_URL}/national-holidays/bulk`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(holidays)  // Array directly in body
  });
  
  if (!response.ok) {
    throw new Error('Failed to create holidays');
  }
  
  return response.json();  // Always returns an array
};

// Bulk create
await createHolidays([
  {
    country_code: "US",
    holiday_name: "New Year's Day",
    holiday_date: "2025-01-01",
    is_recurring: true,
    recurring_month: 1,
    recurring_day: 1
  },
  {
    country_code: "US",
    holiday_name: "Independence Day",
    holiday_date: "2025-07-04",
    is_recurring: true,
    recurring_month: 7,
    recurring_day: 4
  }
]);
```

## Key Characteristics

### Atomicity
All bulk operations are **atomic** - either all records are created/updated/deleted successfully, or none are. If any validation fails, the entire operation is rolled back.

**Example**: If you try to create 5 kitchen days and one already exists:
```json
{
  "error": "Vianda {vianda_id} is already assigned to Wednesday",
  "status_code": 409
}
```
**Result**: None of the 5 days are created. The operation is rolled back.

### Validation
All records are validated **before** any are created/updated/deleted. This ensures fail-fast behavior and prevents partial updates.

### Response Format
- **Pattern 1** (Array in POST body): Always returns an array, even for single items
- **Pattern 2** (Separate bulk endpoint): Always returns an array

### Error Handling
If any record in the bulk operation fails validation:
1. The entire operation is rolled back
2. A `422 Unprocessable Entity` or `409 Conflict` error is returned
3. The error message indicates which record failed and why

**Example Error Response**:
```json
{
  "detail": "Vianda {vianda_id} is already assigned to Wednesday"
}
```

## Best Practices

### When to Use Bulk Operations
- ✅ **Creating multiple related records** (e.g., assigning multiple days to a vianda)
- ✅ **Importing data** (e.g., bulk holiday creation)
- ✅ **Atomic requirements** (all must succeed or all must fail)
- ✅ **Performance** (fewer HTTP requests)

### When NOT to Use Bulk Operations
- ❌ **Single record operations** - Use the standard endpoint
- ❌ **Unrelated records** - Use separate API calls
- ❌ **Very large datasets** (> 1000 records) - Consider pagination or streaming

### Error Handling Strategy
```typescript
try {
  const results = await createBulkOperation(items);
  console.log(`Successfully created ${results.length} items`);
} catch (error) {
  if (error.status === 409) {
    // Conflict - some records already exist
    console.error('Duplicate detected:', error.message);
  } else if (error.status === 422) {
    // Validation error
    console.error('Validation failed:', error.message);
  } else {
    // Other error
    console.error('Unexpected error:', error);
  }
  // No partial success - all items rolled back
}
```

### TypeScript Pattern
Always expect an array response:
```typescript
// ✅ Correct
const results: KitchenDayResponse[] = await createKitchenDays(plateId, days);
results.forEach(item => console.log(item.vianda_kitchen_day_id));

// ❌ Incorrect - don't assume single item
const result: KitchenDayResponse = await createKitchenDays(plateId, ["Monday"]);
// ^ This will fail - response is always an array
```

## Implementation Status

| Endpoint | Pattern | Status | Access Control |
|----------|---------|--------|----------------|
| `POST /api/v1/vianda-kitchen-days/` | Pattern 1 (Array in body) | ✅ Implemented | Suppliers (institution-scoped), Employees (global) |
| `POST /api/v1/national-holidays/bulk` | Pattern 2 (Separate endpoint) | ✅ Implemented | Employees only |

## Future Considerations

Additional bulk operations may be added in the future following these patterns. Check `API_PERMISSIONS_BY_ROLE.md` for the latest list of available endpoints.

---

*Last Updated: 2025-11-19*

