# Enum Service API Documentation

## Overview

The Enum Service API provides centralized access to all system enum values used throughout the platform. This API enables frontend applications to dynamically populate dropdown menus and validate form inputs against the backend's source of truth for enum values.

**Base Path**: `/api/v1/enums/`

**Authentication**: Required (all authenticated users can access)

**Supported Roles**: Employee, Supplier, Customer

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
| `status` | General entity status | Active, Inactive, Pending, Cancelled |
| `address_type` | Address classification | Restaurant, Customer Home, Entity Billing |
| `role_type` | User role types | Employee, Supplier, Customer |
| `role_name` | Specific role names | Admin, Super Admin, Comensal |
| `subscription_status` | Subscription lifecycle status | Active, On Hold, Pending, Expired, Cancelled |
| `method_type` | Payment method types | Credit Card, Debit Card, Bank Transfer, Cash |
| `account_type` | Bank account types | Checking, Savings, Business |
| `transaction_type` | Transaction categories | Order, Credit, Debit, Refund, Discretionary |
| `street_type` | Street type abbreviations | St, Ave, Blvd, Rd, Dr, Ln |
| `kitchen_day` | Valid kitchen days | Monday, Tuesday, Wednesday, Thursday, Friday |
| `pickup_type` | Pickup classifications | self, for_others, by_others |
| `discretionary_reason` | Discretionary credit reasons | Marketing Campaign, Credit Refund, Full Order Refund |

---

## Endpoints

### 1. Get All Enums

Retrieve all system enum values in a single request.

**Endpoint**: `GET /api/v1/enums/`

**Authorization**: Bearer token (any authenticated user)

**Response**: `200 OK`

```json
{
  "status": ["Active", "Inactive", "Pending", "Arrived", "Complete", "Cancelled", "Processed"],
  "address_type": ["Restaurant", "Entity Billing", "Entity Address", "Customer Home", "Customer Billing", "Customer Employer"],
  "role_type": ["Employee", "Supplier", "Customer"],
  "role_name": ["Admin", "Super Admin", "Management", "Operator", "Comensal"],
  "subscription_status": ["Active", "On Hold", "Pending", "Expired", "Cancelled"],
  "method_type": ["Credit Card", "Debit Card", "Bank Transfer", "Cash", "Mercado Pago"],
  "account_type": ["Checking", "Savings", "Business"],
  "transaction_type": ["Order", "Credit", "Debit", "Refund", "Discretionary", "Payment"],
  "street_type": ["St", "Ave", "Blvd", "Rd", "Dr", "Ln", "Way", "Ct", "Pl", "Cir"],
  "kitchen_day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "pickup_type": ["self", "for_others", "by_others"],
  "discretionary_reason": ["Marketing Campaign", "Credit Refund", "Order incorrectly marked as not collected", "Full Order Refund"]
}
```

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

**Authorization**: Bearer token (any authenticated user)

**Response**: `200 OK`

```json
["Active", "Inactive", "Pending", "Arrived", "Complete", "Cancelled", "Processed"]
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

**Use Case**: Targeted refetch of a specific enum type

---

## Request Examples

### cURL

```bash
# Get all enums
curl -X GET "http://localhost:8000/api/v1/enums/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get specific enum
curl -X GET "http://localhost:8000/api/v1/enums/status" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### JavaScript (Fetch API)

```javascript
// Get all enums
const response = await fetch('http://localhost:8000/api/v1/enums/', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const enums = await response.json();

// Get specific enum
const statusResponse = await fetch('http://localhost:8000/api/v1/enums/status', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const statusValues = await statusResponse.json();
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

# Get specific enum
status_response = requests.get(
    'http://localhost:8000/api/v1/enums/status',
    headers={'Authorization': f'Bearer {access_token}'}
)
status_values = status_response.json()
```

---

## Frontend Integration Guide

### 1. Fetch Enums on App Startup

```typescript
// services/enumService.ts
import { api } from './api';

interface EnumValues {
  status: string[];
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

```tsx
// components/StatusDropdown.tsx
import React, { useEffect, useState } from 'react';
import { getEnumValues } from '../services/enumService';

interface StatusDropdownProps {
  value: string;
  onChange: (value: string) => void;
}

export function StatusDropdown({ value, onChange }: StatusDropdownProps) {
  const [statusOptions, setStatusOptions] = useState<string[]>([]);

  useEffect(() => {
    getEnumValues('status').then(setStatusOptions);
  }, []);

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select status...</option>
      {statusOptions.map(status => (
        <option key={status} value={status}>{status}</option>
      ))}
    </select>
  );
}
```

### 3. Generate TypeScript Types

```typescript
// types/enums.ts (auto-generated from API response)
export type Status = 
  | 'Active' 
  | 'Inactive' 
  | 'Pending' 
  | 'Arrived' 
  | 'Complete' 
  | 'Cancelled' 
  | 'Processed';

export type SubscriptionStatus = 
  | 'Active' 
  | 'On Hold' 
  | 'Pending' 
  | 'Expired' 
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

Import the Postman collection from `docs/postman/ENUM_SERVICE.postman_collection.json` to test:

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
- [Frontend Integration Guide](./client/ENUM_SERVICE_CLIENT.md) - Frontend-specific docs

---

## Changelog

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

1. Check [Postman collection](../postman/ENUM_SERVICE.postman_collection.json) for working examples
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
