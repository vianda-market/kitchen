# Enum Service API Documentation

## Overview

The Enum Service API provides centralized access to all system enum values used throughout the platform. This API enables frontend applications to dynamically populate dropdown menus and validate form inputs against the backend's source of truth for enum values.

**Base Path**: `/api/v1/enums/`

**Language (Phase 1 i18n):** `GET /api/v1/enums` accepts **`?language=en|es|pt`** (default `en`) and returns each enum key as **`{ "values": string[], "labels": Record<string,string> }`** instead of a bare string array. **`GET /api/v1/enums/{enum_name}`** is still a flat JSON array of codes. Invalid `language` → **422**. Full client guide: [LANGUAGE_AND_LOCALE_FOR_CLIENTS.md](./LANGUAGE_AND_LOCALE_FOR_CLIENTS.md).

**Authentication**: Required (all authenticated users can access)

**Supported Roles**: Employee, Supplier, Customer (varies by endpoint; see Role access rules below)

---

## Role Access Rules

Who can read role enums (`role_type`, `role_name`):

| Actor | Can read roles? | How |
|-------|-----------------|-----|
| **Customer** | No | `role_type` and `role_name` are omitted from `GET /api/v1/enums/` and `GET /api/v1/enums/{enum_name}` responses. Requesting `role_type` or `role_name` returns **403 Forbidden**. |
| **Supplier** | Yes, subset only | Use `GET /api/v1/enums/roles/assignable` – returns only assignable roles (Supplier role_type; Admin, Manager, Operator role_names) |
| **Employee** | Yes, all | `GET /api/v1/enums/` includes role_type and role_name; `GET /api/v1/enums/roles/assignable` returns full set |

**Note**: `GET /api/v1/roles/` does not exist. Roles are enums; use the enum endpoints above.

---

## Why Use This API?

### Problems Solved

1. **Data Integrity**: Eliminates hardcoded enum values in frontend code
2. **Consistency**: Single source of truth for all enum values
3. **Maintainability**: Adding new enum values requires no frontend code changes
4. **Type Safety**: Enables dynamic TypeScript type generation
5. **UX Improvement**: Users select from valid options instead of guessing text values

### Benefits

- **For Frontend**: Dynamic dropdowns, automatic updates, reduced bugs
- **For Backend**: Centralized enum management, easier to add values
- **For Product**: Faster iteration, consistent data quality

---

## Available Enum Types

The API exposes the following enum types:

| Enum Type | Description | Example Values |
|-----------|-------------|----------------|
| `status` | General status (use context-scoped keys for forms) | Active, Pending, Inactive |
| `status_user` | **User status only** (e.g. user edit form) | Active, Inactive |
| `status_restaurant` | **Restaurant status only** (e.g. restaurant create/edit) | Active, Pending, Inactive |
| `status_discretionary` | Discretionary request lifecycle | Pending, Cancelled, Approved, Rejected |
| `status_plate_pickup` | Plate pickup / order status | Pending, Arrived, Completed, Cancelled |
| `status_bill` | Bill status | Pending, Processed, Cancelled |
| `address_type` | Address classification | Restaurant, Customer Home, Entity Billing |
| `role_type` | User role types | Employee, Supplier, Customer |
| `role_name` | Specific role names | Admin, Super Admin, Comensal |
| `subscription_status` | Subscription lifecycle status | Active, **On Hold**, Pending, Cancelled |
| `method_type` | Payment method types | Credit Card, Debit Card, Bank Transfer, Cash |
| `transaction_type` | Transaction categories | Order, Credit, Debit, Refund, Discretionary |
| `street_type` | Street type abbreviations | St, Ave, Blvd, Rd, Dr, Ln, Way, Ct, Pl, Cir |
| `kitchen_day` | Valid kitchen days | Monday, Tuesday, Wednesday, Thursday, Friday |
| `pickup_type` | Pickup classifications | self, for_others, by_others |
| `discretionary_reason` | Discretionary credit reasons | Marketing Campaign, Credit Refund, Full Order Refund |

---

## Filtering Status by Context

Status values are **context-specific**. The backend exposes a single `status_enum` in the database but different entities only accept a **subset** of statuses. Use the right key or query so your form dropdown shows only valid options and the API accepts the value.

### Why filter status?

- **User** entity: only `Active` and `Inactive` are valid. Showing "Arrived" or "Processed" in the user edit form would be wrong and can be rejected by the API.
- **Restaurant** entity: only `Active`, `Pending`, and `Inactive` are valid. Use `status_restaurant` or `GET /api/v1/enums/status?context=restaurant` for the restaurant status dropdown.
- **Discretionary** requests: Pending, Cancelled, Approved, Rejected.
- **Plate pickup / orders**: Pending, Arrived, Completed, Cancelled.
- **Bills**: Pending, Processed, Cancelled.

### Option 1: Use context-scoped keys from GET /enums/

When you call `GET /api/v1/enums/`, the response includes both the full list and context-scoped lists:

| Use case | Key to use | Values |
|----------|------------|--------|
| User create/edit (status field) | `status_user` | `["Active", "Inactive"]` |
| Restaurant create/edit (status field) | `status_restaurant` | `["Active", "Pending", "Inactive"]` |
| Discretionary request forms | `status_discretionary` | `["Pending", "Cancelled", "Approved", "Rejected"]` |
| Plate pickup / order status | `status_plate_pickup` | `["Pending", "Arrived", "Completed", "Cancelled"]` |
| Bill status | `status_bill` | `["Pending", "Processed", "Cancelled"]` |
| Generic / unknown entity | `status` | `["Active", "Pending", "Inactive"]` |

**Example**: For the user edit form, use `enums.status_user` (or `enums['status_user']`) for the status dropdown, not `enums.status`.

### Option 2: Use the `context` query parameter (GET single enum)

For a single enum fetch, you can request status filtered by context:

**Endpoint**: `GET /api/v1/enums/status?context={context}`

**Query parameter**: `context` (optional). Valid values: `user`, `restaurant`, `discretionary`, `plate_pickup`, `bill`.

| Request | Response |
|---------|----------|
| `GET /api/v1/enums/status` | `["Active", "Pending", "Inactive"]` |
| `GET /api/v1/enums/status?context=user` | `["Active", "Inactive"]` |
| `GET /api/v1/enums/status?context=restaurant` | `["Active", "Pending", "Inactive"]` |
| `GET /api/v1/enums/status?context=plate_pickup` | `["Pending", "Arrived", "Completed", "Cancelled"]` |
| `GET /api/v1/enums/status?context=bill` | `["Pending", "Processed", "Cancelled"]` |
| `GET /api/v1/enums/status?context=discretionary` | `["Pending", "Cancelled", "Approved", "Rejected"]` |

Use this when you only need status values for one context and want to avoid loading all enums.

**Summary**: Prefer **Option 1** when you already load all enums (e.g. on app startup). Use **Option 2** when you fetch a single enum and need status for a specific form (e.g. user edit: `GET /enums/status?context=user`).

---

## Subscription status and On Hold

The **`subscription_status`** enum describes the lifecycle of a subscription record. Use `GET /api/v1/enums/` or `GET /api/v1/enums/subscription_status` to get the list; use it for subscription create/edit forms and for displaying subscription state.

### Values

| Value | Description |
|-------|-------------|
| **Active** | Subscription is active; user can use the service. |
| **On Hold** | Subscription is temporarily paused. When set, the subscription record includes **`hold_start_date`** (when the hold started) and optionally **`hold_end_date`** (when it will resume; `null` = indefinite). |
| **Pending** | Subscription is pending (e.g. awaiting payment or activation). |
| **Cancelled** | Subscription has been cancelled. |

### On Hold and hold dates

- When **`subscription_status`** is **`"On Hold"`**, the API includes:
  - **`hold_start_date`** (ISO 8601): when the subscription was put on hold.
  - **`hold_end_date`** (ISO 8601 or `null`): when the subscription is expected to resume; `null` means indefinite hold.
- Clients should use **On Hold** (not a generic “Inactive”) so that UI can show hold dates and a “Resume” or “Cancel” action correctly.
- Subscription list and detail responses return `subscription_status`, `hold_start_date`, and `hold_end_date`; see subscription API docs for the exact response shape.

### TypeScript

```typescript
export type SubscriptionStatus =
  | 'Active'
  | 'On Hold'
  | 'Pending'
  | 'Cancelled';
```

---

### Where is the filtering for the User page?

The filtering is in the **backend response**: `GET /api/v1/enums/` must return the key **`status_user`** with value `["Active", "Inactive"]`. The User (create/edit) form should use **`enums.status_user`** for the Status dropdown so only Active and Inactive are shown.

- **If the backend returns `status_user`**: Use it directly; no fallback needed.
- **If the backend returns only `status` (no `status_user`)**: Client can derive user options from `status` by keeping only `"Active"` and `"Inactive"`, or use a hardcoded fallback `["Active", "Inactive"]` and log a console warning so you know the backend needs updating.
- **If the enums request fails**: Use the same fallback and existing console.warn.

**Backend**: The backend always injects `status_user`, `status_discretionary`, `status_plate_pickup`, and `status_bill` into the response. If your response doesn’t include them, ensure the server was restarted after the latest code and test with browser cache disabled (e.g. DevTools → Network → "Disable cache") or a hard refresh.

---

## Endpoints

### 1. Get All Enums

Retrieve all system enum values in a single request.

**Endpoint**: `GET /api/v1/enums/`

**Authorization**: Bearer token (any authenticated user)

**Response**: `200 OK`

**Role enums and Customers**: When the authenticated user is a Customer, `role_type` and `role_name` are omitted from the response.

```json
{
  "status": ["Active", "Pending", "Inactive"],
  "status_user": ["Active", "Inactive"],
  "status_restaurant": ["Active", "Pending", "Inactive"],
  "status_discretionary": ["Pending", "Cancelled", "Approved", "Rejected"],
  "status_plate_pickup": ["Pending", "Arrived", "Completed", "Cancelled"],
  "status_bill": ["Pending", "Processed", "Cancelled"],
  "address_type": ["Restaurant", "Entity Billing", "Entity Address", "Customer Home", "Customer Billing", "Customer Employer"],
  "role_type": ["Employee", "Supplier", "Customer"],
  "role_name": ["Admin", "Super Admin", "Manager", "Operator", "Comensal"],
  "subscription_status": ["Active", "On Hold", "Pending", "Cancelled"],
  "method_type": ["Credit Card", "Debit Card", "Bank Transfer", "Cash", "Mercado Pago"],
  "transaction_type": ["Order", "Credit", "Debit", "Refund", "Discretionary", "Payment"],
  "street_type": ["St", "Ave", "Blvd", "Rd", "Dr", "Ln", "Way", "Ct", "Pl", "Cir"],
  "kitchen_day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "pickup_type": ["self", "for_others", "by_others"],
  "discretionary_reason": ["Marketing Campaign", "Credit Refund", "Order incorrectly marked as not collected", "Full Order Refund"]
}
```

Use `status_user`, `status_restaurant`, `status_discretionary`, `status_plate_pickup`, or `status_bill` for entity-specific status dropdowns (see [Filtering Status by Context](#filtering-status-by-context)).

**Headers**:
- `Cache-Control: public, max-age=3600` - Frontend should cache for 1 hour
- `X-Content-Type-Options: nosniff` - Security header

**Use Case**: Initial page load, cache all enums for the session

---

### 2. Get Specific Enum

Retrieve values for a single enum type.

**Endpoint**: `GET /api/v1/enums/{enum_name}`

**Path Parameters**:
- `enum_name` (required): Name of the enum type (e.g., `status`, `role_type`, `subscription_status`)

**Query Parameters** (optional):
- `context`: For `enum_name=status` only. Restricts to a subset: `user`, `restaurant`, `discretionary`, `plate_pickup`, `bill`. Omit for the full status list.

**Authorization**: Bearer token (any authenticated user)

**Response**: `200 OK`

Example without context (full status list):
```json
["Active", "Pending", "Inactive"]
```

Example with `?context=user` (user edit form):
```json
["Active", "Inactive"]
```

**Error Responses**:

- **404 Not Found**: Unknown enum type
  ```json
  {
    "detail": "Unknown enum type: invalid_name"
  }
  ```

- **401 Unauthorized**: Missing or invalid authentication token
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

**Use Case**: Targeted refetch of a specific enum type. For status, add `?context=user` (or other context) to get only values valid for that form.

**Role enums and Customers**: When the authenticated user is a Customer, requesting `role_type` or `role_name` returns **403 Forbidden** with detail "Customers cannot read role enums".

---

### 3. Get Assignable Roles (User Create/Edit Form)

Retrieve role_type and role_name values that the current user can assign when creating or editing users.

**Endpoint**: `GET /api/v1/enums/roles/assignable`

**Authorization**: Employee and Supplier only. Customers get **403 Forbidden**.

**Response** (Supplier):
```json
{
  "role_type": ["Supplier"],
  "role_name_by_role_type": {
    "Supplier": ["Admin", "Manager", "Operator"]
  }
}
```

**Response** (Employee): Full set per valid role combinations (Employee, Supplier, Customer for role_type; role_name varies by role_type).

**Use Case**: Populate the Role dropdown in user create/edit forms. Use `role_type` and `role_name_by_role_type[selected_role_type]` for cascading dropdowns.

**Cascading**: When the user selects a `role_type`, populate the `role_name` dropdown from `role_name_by_role_type[selected_role_type]`.

---

### 4. Get Assignable Institution Types (Institution Create/Edit Form)

Retrieve institution types the current user can create/assign when creating or editing institutions.

**Endpoint**: `GET /api/v1/enums/institution-types/assignable`

**Authorization**: All authenticated users. Response filtered by role.

**Response** (Super Admin):
```json
{
  "institution_type": ["Employee", "Supplier", "Customer", "Employer"]
}
```

**Response** (Admin):
```json
{
  "institution_type": ["Supplier", "Employer"]
}
```

**Response** (Supplier / Customer): `{"institution_type": []}` (cannot create institutions).

**Use Case**: Populate the institution type dropdown in institution create/edit forms. **Do not hardcode** — use this endpoint so Employer (benefits-program institutions) is included and Employee/Customer are correctly restricted to Super Admin only.

---

## Request Examples

### cURL

```bash
# Get all enums (includes status_user, status_plate_pickup, etc.)
curl -X GET "http://localhost:8000/api/v1/enums/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get full status list
curl -X GET "http://localhost:8000/api/v1/enums/status" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get status for user form only (Active, Inactive)
curl -X GET "http://localhost:8000/api/v1/enums/status?context=user" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### JavaScript (Fetch API)

```javascript
// Get all enums (use enums.status_user for user edit form)
const response = await fetch('http://localhost:8000/api/v1/enums/', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const enums = await response.json();
// User status dropdown: enums.status_user → ["Active", "Inactive"]

// Get status for a specific context (e.g. user form)
const statusResponse = await fetch('http://localhost:8000/api/v1/enums/status?context=user', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const statusValues = await statusResponse.json(); // ["Active", "Inactive"]
```

### Python (requests)

```python
import requests

# Get all enums
response = requests.get(
    'http://localhost:8000/api/v1/enums/',
    headers={'Authorization': f'Bearer {access_token}'}
)
enums = response.json()

# Get full status list
status_response = requests.get(
    'http://localhost:8000/api/v1/enums/status',
    headers={'Authorization': f'Bearer {access_token}'}
)
status_values = status_response.json()

# Get status for user form only (Active, Inactive)
user_status_response = requests.get(
    'http://localhost:8000/api/v1/enums/status',
    params={'context': 'user'},
    headers={'Authorization': f'Bearer {access_token}'}
)
user_status_values = user_status_response.json()  # ["Active", "Inactive"]
```

---

## Frontend Integration Guide

### 1. Fetch Enums on App Startup

```typescript
// services/enumService.ts
import { api } from './api';

interface EnumValues {
  status: string[];
  status_user: string[];
  status_discretionary: string[];
  status_plate_pickup: string[];
  status_bill: string[];
  address_type: string[];
  role_type: string[];
  // ... other enum types
}

let cachedEnums: EnumValues | null = null;
let cacheTimestamp: number = 0;
const CACHE_DURATION = 3600000; // 1 hour in milliseconds

export async function getEnums(): Promise<EnumValues> {
  const now = Date.now();
  
  // Return cached values if still valid
  if (cachedEnums && (now - cacheTimestamp) < CACHE_DURATION) {
    return cachedEnums;
  }
  
  // Fetch fresh values
  const response = await api.get('/api/v1/enums/');
  cachedEnums = response.data;
  cacheTimestamp = now;
  
  return cachedEnums;
}

export async function getEnumValues(enumName: string): Promise<string[]> {
  const enums = await getEnums();
  return enums[enumName as keyof EnumValues] || [];
}
```

### 2. Use in Form Components

Use **context-scoped** status so the dropdown only shows valid values for that entity (e.g. user = Active/Inactive only).

```tsx
// components/StatusDropdown.tsx – use status_user for user edit form
import React, { useEffect, useState } from 'react';
import { getEnums } from '../services/enumService';

type StatusContext = 'user' | 'discretionary' | 'plate_pickup' | 'bill';

interface StatusDropdownProps {
  value: string;
  onChange: (value: string) => void;
  /** Which entity: use 'user' for user edit form so only Active/Inactive are shown */
  context?: StatusContext;
}

export function StatusDropdown({ value, onChange, context = 'user' }: StatusDropdownProps) {
  const [statusOptions, setStatusOptions] = useState<string[]>([]);

  useEffect(() => {
    getEnums().then((enums) => {
      const key = context === 'user' ? 'status_user' : `status_${context}` as const;
      setStatusOptions((enums as Record<string, string[]>)[key] ?? []);
    });
  }, [context]);

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select status...</option>
      {statusOptions.map((status) => (
        <option key={status} value={status}>{status}</option>
      ))}
    </select>
  );
}
```

Alternative: fetch status for one context only via query param:
```tsx
// GET /api/v1/enums/status?context=user
const res = await api.get('/api/v1/enums/status', { params: { context: 'user' } });
const statusOptions = res.data; // ["Active", "Inactive"]
```

### 3. Generate TypeScript Types

Use context-specific types for status where applicable so forms only allow valid values:

```typescript
// types/enums.ts (align with API; use context-scoped for forms)
export type Status = 
  | 'Active' 
  | 'Inactive' 
  | 'Pending' 
  | 'Arrived' 
  | 'Completed' 
  | 'Cancelled' 
  | 'Processed';

/** User entity status only – use for user create/edit status field */
export type UserStatus = 'Active' | 'Inactive';

/** Restaurant entity status only – use for restaurant create/edit status field */
export type RestaurantStatus = 'Active' | 'Pending' | 'Inactive';

/** Plate pickup / order status */
export type PlatePickupStatus = 'Pending' | 'Arrived' | 'Completed' | 'Cancelled';

/** Bill status */
export type BillStatus = 'Pending' | 'Processed';

export type SubscriptionStatus = 
  | 'Active' 
  | 'On Hold' 
  | 'Pending' 
  | 'Cancelled';

export type RoleType = 
  | 'Employee' 
  | 'Supplier' 
  | 'Customer';

// ... other enum types
```

---

## Caching Strategy

### Recommended Approach

1. **Initial Load**: Fetch all enums on app startup
2. **Cache Duration**: 1 hour (matches server `Cache-Control` header)
3. **Storage**: In-memory cache or localStorage
4. **Invalidation**: On version change or manual refresh

### Implementation Example

```typescript
class EnumCache {
  private cache: Map<string, { data: any; timestamp: number }> = new Map();
  private readonly TTL = 3600000; // 1 hour

  async get<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
    const cached = this.cache.get(key);
    const now = Date.now();

    if (cached && (now - cached.timestamp) < this.TTL) {
      return cached.data as T;
    }

    const data = await fetcher();
    this.cache.set(key, { data, timestamp: now });
    return data;
  }

  invalidate(key?: string) {
    if (key) {
      this.cache.delete(key);
    } else {
      this.cache.clear();
    }
  }
}

export const enumCache = new EnumCache();
```

---

## Error Handling

### Common Errors

| Status Code | Error | Cause | Solution |
|-------------|-------|-------|----------|
| 401 | Unauthorized | Missing or invalid token | Re-authenticate user |
| 404 | Not Found | Invalid enum name | Check spelling, use valid enum type |
| 500 | Server Error | Backend error | Retry with exponential backoff |

### Recommended Error Handling

```typescript
async function fetchEnums() {
  try {
    const response = await fetch('/api/v1/enums/', {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Token expired, redirect to login
        window.location.href = '/login';
        return;
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to fetch enums:', error);
    // Fall back to hardcoded defaults or show error message
    return getDefaultEnums();
  }
}
```

---

## Extensibility

### Adding a New Enum Type

To add a new enum type to the API:

1. **Create Python Enum Class** (`app/config/enums/new_enum.py`)
   ```python
   from enum import Enum

   class NewEnum(str, Enum):
       VALUE_ONE = "Value One"
       VALUE_TWO = "Value Two"

       @classmethod
       def values(cls) -> list[str]:
           return [item.value for item in cls]
   ```

2. **Export in `__init__.py`** (`app/config/enums/__init__.py`)
   ```python
   from app.config.enums.new_enum import NewEnum
   
   __all__ = [..., "NewEnum"]
   ```

3. **Add to Enum Service** (`app/services/enum_service.py`)
   ```python
   def get_all_enums() -> Dict[str, List[str]]:
       return {
           # ... existing enums ...
           "new_enum": NewEnum.values(),
       }
   ```

4. **Update Response Schema** (`app/schemas/consolidated_schemas.py`)
   ```python
   class EnumsResponseSchema(BaseModel):
       # ... existing fields ...
       new_enum: List[str] = Field(..., description="Valid new enum values")
   ```

**Result**: Frontend automatically receives the new enum values on next API call (no frontend code changes required).

---

## Testing

### Postman Collection

Import the Postman collection from `docs/postman/collections/ENUM_SERVICE.postman_collection.json` to test:

- ✅ Get all enums (authenticated)
- ✅ Get specific enum (authenticated)
- ✅ Invalid enum name (404)
- ✅ Unauthorized access (401)
- ✅ Cache headers verification
- ✅ Customer access verification

### Unit Tests

Run backend unit tests:

```bash
pytest app/tests/services/test_enum_service.py -v
```

**Test Coverage**:
- ✅ Enum service returns dictionary
- ✅ All enums have values
- ✅ Specific enum retrieval
- ✅ Invalid enum raises ValueError
- ✅ Status enum values
- ✅ Subscription status values
- ✅ Enum keys match specification
- ✅ Role type values
- ✅ Kitchen day values
- ✅ Payment method type values
- ✅ Street type values
- ✅ Singleton consistency

---

## Performance Considerations

### Response Size

- **All Enums**: ~2-3 KB uncompressed
- **Single Enum**: ~100-200 bytes uncompressed
- **Compression**: Use gzip compression for ~70% size reduction

### Response Time

- **Target**: < 100ms
- **Typical**: 20-50ms (cached in Python memory)
- **No Database Calls**: Enums are loaded from Python classes, not database

### Load Impact

- **With Caching**: Minimal (1 request per user per hour)
- **Without Caching**: Potentially high (1 request per form render)

---

## Security

### Access Control

- **Authentication Required**: All endpoints require valid JWT token
- **Authorization**: All authenticated users (Employee, Supplier, Customer) can read enums
- **No Modification**: Enums are read-only via API
- **Modification Access**: Only via code deployment (Super Admin level)

### Data Exposure

- **Enum Values**: Not sensitive data, safe to expose to all authenticated users
- **System Architecture**: Reveals some system structure, but acceptable for efficiency
- **No PII**: Enum values contain no personally identifiable information

---

## Related Documentation

- [ABAC Policies](../config/abac_policies.yaml) - Access control policies
- [Enum Classes](../../app/config/enums/) - Python enum definitions
- [Consolidated Schemas](../../app/schemas/consolidated_schemas.py) - Pydantic schemas
- [Postman collection](../../postman/collections/ENUM_SERVICE.postman_collection.json) for testing

---

## Changelog

### 2026-02-21 - Subscription status: On Hold and hold dates

- **`subscription_status`** enum includes **`"On Hold"`** (with Pending, Cancelled, Active). Use it for subscription lifecycle and forms.
- When a subscription is On Hold, the record includes **`hold_start_date`** and **`hold_end_date`** (optional; `null` = indefinite). See [Subscription status and On Hold](#subscription-status-and-on-hold).
- Documented subscription_status values and hold-date semantics for clients in this doc.

### 2026-02-21 - Restaurant status context

- Added **`status_restaurant`** to GET /enums/ response: `["Active", "Pending", "Inactive"]` for restaurant create/edit forms.
- Added **`context=restaurant`** to GET /enums/status query parameter. Use for restaurant status dropdown so only Active, Pending, and Inactive are shown. See [RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md](RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md) for business rules.

### 2026-02-10 - Status context filtering

- Added context-scoped status keys: `status_user`, `status_restaurant`, `status_discretionary`, `status_plate_pickup`, `status_bill` in GET /enums/ response.
- Added optional query parameter `context` to GET /enums/status (values: `user`, `restaurant`, `discretionary`, `plate_pickup`, `bill`) to return only status values valid for that context.
- Documented how to filter status fields by context so user edit forms show only Active/Inactive and restaurant forms show only Active, Pending, Inactive (see [Filtering Status by Context](#filtering-status-by-context)).

### 2026-02-08 - Initial Release

- Added 12 enum types
- Implemented GET /api/v1/enums/ endpoint
- Implemented GET /api/v1/enums/{enum_name} endpoint
- Added caching headers (1 hour TTL)
- Added authentication requirement
- Created Postman collection
- Created unit tests

---

## Support

For questions or issues:

1. Check [Postman collection](../postman/collections/ENUM_SERVICE.postman_collection.json) for working examples
2. Run [unit tests](../../app/tests/services/test_enum_service.py) to verify functionality
3. Review [enum service code](../../app/services/enum_service.py) for implementation details
4. Contact backend team for assistance

---

## Frequently Asked Questions

**Q: Why do I get 401 Unauthorized?**  
A: Ensure you're sending a valid Bearer token in the Authorization header. Re-authenticate if token expired.

**Q: Can I modify enum values via API?**  
A: No, enum values are read-only via API. Modifications require code deployment.

**Q: How often should I refetch enums?**  
A: Cache for 1 hour (as indicated by Cache-Control header). Refetch on app startup or version change.

**Q: What if I need a new enum type?**  
A: Submit a backend feature request following the "Extensibility" section above.

**Q: Can Customers see all enum values?**  
A: Yes, all authenticated users (Employee, Supplier, Customer) can read all enum values.

**Q: Why is `audit_operation_enum` not exposed?**  
A: It's an internal enum used only by database triggers, not needed in frontend.

**Q: Why does the user edit form show "Arrived" or "Processed" in the status dropdown?**  
A: Use the context-scoped key or query param so the dropdown only shows valid values. For user edit, use `enums.status_user` from GET /enums/ or GET /enums/status?context=user. Only Active and Inactive are valid for users; the API will reject other status values.

