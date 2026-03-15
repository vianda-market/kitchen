# Enriched Endpoints - UI Implementation Guide

## Context

The FastAPI backend has implemented **enriched endpoints** for multiple entities that return data with denormalized related entity names (e.g., role names, institution names, restaurant names). This eliminates the need for the UI to make multiple API calls or perform N+1 queries.

**All enriched endpoints use a centralized `EnrichedService` implementation**, ensuring consistency, maintainability, and automatic scoping behavior across all endpoints.

## Problem Solved

Previously, to display entity lists with related entity names, the UI would need to:
1. Call the base endpoint (e.g., `GET /users/`) to get entities (with only foreign key UUIDs)
2. For each entity, make additional API calls to fetch related entity names

**Example for Users:**
- Call `GET /users/` → get users with `role_id` and `institution_id` UUIDs
- For each user, call `GET /roles/{role_id}` → get role name
- For each user, call `GET /institutions/{institution_id}` → get institution name
- **Result**: 1 + N + N = 2N + 1 API calls for N users

**Now**, the UI can call `GET /users/enriched/` once and get all the data needed in a single query.

This pattern applies to all enriched endpoints across the system.

## Available Enriched Endpoints

The backend provides enriched endpoints for multiple entities. All follow the same pattern:

### Pattern
- `GET /{entity}/enriched/` - List all enriched records
- `GET /{entity}/enriched/{id}` - Get single enriched record

### Examples

**Users:**
- `GET /users/enriched/` - List enriched users
- `GET /users/enriched/{user_id}` - Get single enriched user

**Restaurants:**
- `GET /restaurants/enriched/` - List enriched restaurants
- `GET /restaurants/enriched/{restaurant_id}` - Get single enriched restaurant

**Plates:**
- `GET /plates/enriched/` - List enriched plates
- `GET /plates/enriched/{plate_id}` - Get single enriched plate

**And many more...** See [ENRICHED_ENDPOINT_PATTERN.md](./ENRICHED_ENDPOINT_PATTERN.md) for the complete list.

---

## Detailed Example: Users Enriched Endpoints

### 1. List Enriched Users
```
GET /users/enriched/

Query Parameters:
  - include_archived: boolean (optional, default: false)
    - If true, includes archived users in the response
    - If false (or omitted), only returns active users (is_archived = FALSE)
    - **Recommendation**: Omit this parameter to use the safe default behavior

Headers:
  - Authorization: Bearer <token> (required)

Response: 200 OK
[
  {
    "user_id": "uuid",
    "institution_id": "uuid",
    "institution_name": "Acme Corporation",  // ← Included!
    "role_id": "uuid",
    "role_name": "Admin",                    // ← Included!
    "role_type": "Employee",                 // ← Included!
    "username": "john.doe",
    "email": "john.doe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "full_name": "John Doe",                 // ← Pre-concatenated!
    "cellphone": "+1234567890",
    "employer_id": "uuid" | null,
    "is_archived": false,
    "status": "Active",
    "created_date": "2024-01-15T10:30:00Z",
    "modified_date": "2024-01-20T14:45:00Z"
  },
  // ... more users
]

Error Responses:
  - 401 Unauthorized: Missing or invalid token
  - 403 Forbidden: User doesn't have permission
  - 500 Internal Server Error: Server error
```

### 2. Get Single Enriched User
```
GET /users/enriched/{user_id}

Path Parameters:
  - user_id: UUID (required)

Query Parameters:
  - include_archived: boolean (optional, default: false)
    - If true, includes archived users in the response
    - If false (or omitted), only returns active users (is_archived = FALSE)
    - **Recommendation**: Omit this parameter to use the safe default behavior

Headers:
  - Authorization: Bearer <token> (required)

Response: 200 OK
{
  "user_id": "uuid",
  "institution_id": "uuid",
  "institution_name": "Acme Corporation",  // ← Included!
  "role_id": "uuid",
  "role_name": "Admin",                      // ← Included!
  "role_type": "Employee",                   // ← Included!
  "username": "john.doe",
  "email": "john.doe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "full_name": "John Doe",                   // ← Pre-concatenated!
  "cellphone": "+1234567890",
  "employer_id": "uuid" | null,
  "is_archived": false,
  "status": "Active",
  "created_date": "2024-01-15T10:30:00Z",
  "modified_date": "2024-01-20T14:45:00Z"
}

Error Responses:
  - 401 Unauthorized: Missing or invalid token
  - 404 Not Found: User doesn't exist or is outside user's scope
  - 403 Forbidden: User doesn't have permission
  - 500 Internal Server Error: Server error
```

## TypeScript Interface

```typescript
interface UserEnrichedResponse {
  user_id: string;
  institution_id: string;
  institution_name: string;  // ← New field
  role_id: string;
  role_name: string;        // ← New field
  role_type: string;        // ← New field
  username: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;        // ← Pre-concatenated! Handles NULL values gracefully
  cellphone: string;
  employer_id: string | null;
  is_archived: boolean;
  status: string;
  created_date: string;     // ISO 8601 datetime
  modified_date: string;    // ISO 8601 datetime
}
```

## Implementation Example

### React Component Example

```typescript
import { useState, useEffect } from 'react';

interface UserEnrichedResponse {
  user_id: string;
  institution_id: string;
  institution_name: string;
  role_id: string;
  role_name: string;
  role_type: string;
  username: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  cellphone: string;
  employer_id: string | null;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}

const UsersPage = () => {
  const [users, setUsers] = useState<UserEnrichedResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEnrichedUsers = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('authToken');
        
        const response = await fetch('http://localhost:8000/users/enriched/', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          if (response.status === 401) {
            throw new Error('Unauthorized - please login again');
          }
          if (response.status === 403) {
            throw new Error('Forbidden - insufficient permissions');
          }
          throw new Error(`Failed to fetch users: ${response.statusText}`);
        }

        const data = await response.json();
        setUsers(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchEnrichedUsers();
  }, []);

  if (loading) return <div>Loading users...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h1>Users</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Username</th>
            <th>Email</th>
            <th>Status</th>
            <th>Role Name</th>
            <th>Institution</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.user_id}>
              <td>{user.full_name}</td>  {/* ← Pre-concatenated! No client-side logic needed */}
              <td>{user.username}</td>
              <td>{user.email}</td>
              <td>{user.status}</td>
              <td>{user.role_name}</td>  {/* ← No additional API call needed! */}
              <td>{user.institution_name}</td>  {/* ← No additional API call needed! */}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default UsersPage;
```

### API Service Function Example

```typescript
// services/userService.ts

const API_BASE_URL = 'http://localhost:8000';

export const fetchEnrichedUsers = async (
  includeArchived: boolean = false
): Promise<UserEnrichedResponse[]> => {
  const token = localStorage.getItem('authToken');
  
  // Note: By default, includeArchived=false means archived records are excluded
  // Only set the parameter if explicitly including archived records
  const params = new URLSearchParams();
  if (includeArchived) {
    params.append('include_archived', 'true');
  }
  // If includeArchived=false, omit parameter to use safe default

  const response = await fetch(
    `${API_BASE_URL}/users/enriched/?${params.toString()}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }
  );

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Unauthorized');
    }
    if (response.status === 403) {
      throw new Error('Forbidden');
    }
    throw new Error(`Failed to fetch enriched users: ${response.statusText}`);
  }

  return response.json();
};

export const fetchEnrichedUserById = async (
  userId: string,
  includeArchived: boolean = false
): Promise<UserEnrichedResponse> => {
  const token = localStorage.getItem('authToken');
  
  // Note: By default, includeArchived=false means archived records are excluded
  // Only set the parameter if explicitly including archived records
  const params = new URLSearchParams();
  if (includeArchived) {
    params.append('include_archived', 'true');
  }
  // If includeArchived=false, omit parameter to use safe default

  const response = await fetch(
    `${API_BASE_URL}/users/enriched/${userId}?${params.toString()}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }
  );

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Unauthorized');
    }
    if (response.status === 404) {
      throw new Error('User not found');
    }
    if (response.status === 403) {
      throw new Error('Forbidden');
    }
    throw new Error(`Failed to fetch enriched user: ${response.statusText}`);
  }

  return response.json();
};
```

## Key Benefits

1. **Single API Call**: Get all user data including role and institution names in one request
2. **Better Performance**: Eliminates N+1 queries (1 call instead of 2N+1 calls)
3. **Simpler Code**: No need to fetch roles and institutions separately
4. **Consistent Data**: All data comes from the same query, ensuring consistency

## Migration from Base Endpoints

If you're currently using the base `/users/` endpoints:

**Before:**
```typescript
// Multiple API calls needed
const users = await fetchUsers();
const roles = await Promise.all(users.map(u => fetchRole(u.role_id)));
const institutions = await Promise.all(users.map(u => fetchInstitution(u.institution_id)));

// Combine data manually
const enrichedUsers = users.map((user, i) => ({
  ...user,
  role_name: roles[i].name,
  institution_name: institutions[i].name
}));
```

**After:**
```typescript
// Single API call
const enrichedUsers = await fetchEnrichedUsers();
// role_name and institution_name are already included!
```

## Full Name Field

**Important**: The enriched endpoints automatically include a `full_name` field that concatenates `first_name` and `last_name`:

- **User Enriched Endpoints**: Include `full_name` field
- **Address Enriched Endpoints**: Include `user_full_name` field

### Benefits

- ✅ **No client-side concatenation**: UI can directly use `user.full_name` without string manipulation
- ✅ **Handles NULL values**: Gracefully handles cases where `first_name` or `last_name` is NULL
- ✅ **Consistent formatting**: All clients get the same name format
- ✅ **Edge case handling**: Returns empty string if both names are NULL, only the non-NULL name if one is missing

### Usage Example

```typescript
// ✅ GOOD: Use pre-concatenated full_name
<td>{user.full_name}</td>

// ❌ AVOID: Client-side concatenation (unnecessary)
<td>{user.first_name} {user.last_name}</td>
```

### Full Name Behavior

The `full_name` field is computed server-side using PostgreSQL's `CONCAT_WS` function:

- **Both names present**: `"John Doe"` (space-separated)
- **Only first name**: `"John"` (no trailing space)
- **Only last name**: `"Doe"` (no leading space)
- **Both NULL**: `""` (empty string)

**Note**: The `full_name` field is always a non-null string, even when `first_name` and `last_name` are both NULL. This ensures the UI never needs to handle NULL values for the full name display.

## Scoping Behavior

Enriched endpoints automatically filter results based on the authenticated user's role type. **The UI does not need to implement any filtering logic** - the backend handles this automatically.

### Standard Institution Scoping (Most Entities)

For most enriched endpoints (users, restaurants, products, addresses, etc.):

- **Employees** (`role_type = "Employee"`): See all records across all institutions (global access)
- **Suppliers** (`role_type = "Supplier"`): See only records from their institution (`institution_id` match)
- **Customers** (`role_type = "Customer"`): See only records from their institution (if applicable)

**Example**: `/users/enriched/`
- Employee logs in → sees all users from all institutions
- Supplier logs in → sees only users from their institution
- Customer logs in → sees only users from their institution

### User-Level Scoping (Special Cases)

For certain enriched endpoints that track user-specific data (e.g., plate pickups, subscriptions):

- **Employees** (`role_type = "Employee"`): See all records across all institutions (global access)
- **Suppliers** (`role_type = "Supplier"`): See records for restaurants in their institution (filtered by restaurant's `institution_id`)
- **Customers** (`role_type = "Customer"`): See only their own records (filtered by `user_id`)

**Example**: `/plate-pickup/enriched/`
- Employee logs in → sees all plate pickups from all restaurants
- Supplier logs in → sees plate pickups for restaurants belonging to their institution
- Customer logs in → sees only their own plate pickups

### Important for UI Development

1. **No Client-Side Filtering Required**: The backend automatically applies the correct scoping based on the authenticated user's JWT token
2. **Consistent Behavior**: The same user will always see the same filtered results for the same endpoint
3. **Role-Based Access**: Different users with different roles will see different data sets automatically
4. **No Additional Parameters**: Scoping is handled automatically - no need to pass `institution_id` or `user_id` parameters

### Implementation Example

```typescript
// ✅ GOOD: Just call the endpoint - scoping is automatic
const fetchPlatePickups = async () => {
  const token = localStorage.getItem('authToken');
  const response = await fetch('/plate-pickup/enriched/', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  // Results are automatically filtered based on user's role
  return response.json();
};

// ❌ AVOID: Don't try to filter on the client side
const fetchPlatePickups = async () => {
  const token = localStorage.getItem('authToken');
  const user = getCurrentUser(); // Don't do this
  const response = await fetch(`/plate-pickup/enriched/?user_id=${user.id}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  // Backend already handles this - redundant filtering
  return response.json();
};
```

## Notes

- The enriched endpoints respect the same **scoping rules** as base endpoints
- Users with global roles (Employee) see all records across all institutions
- Users with institution-scoped roles (Supplier) see only records from their institution
- Users with customer roles see their own records (for user-scoped resources) or institution records (for standard resources)
- The `include_archived` parameter works the same way as base endpoints
- **By default, archived records are excluded** - omit `include_archived` parameter to use safe default
- All authentication and authorization rules apply

## Archived Records Handling

**Important**: All endpoints exclude archived records by default (`include_archived=false`).

### ✅ Recommended Approach (Omit Parameter)

```typescript
// ✅ GOOD: Uses default behavior (excludes archived)
const users = await fetchEnrichedUsers();
// Only active users are returned automatically
```

### ✅ Alternative (Explicit)

```typescript
// ✅ GOOD: Explicitly excludes archived
const users = await fetchEnrichedUsers(false);
```

### ⚠️ Only When Needed

```typescript
// ⚠️ Only use when you specifically need archived records
const allUsers = await fetchEnrichedUsers(true);
```

**See**: [Archived Records Pattern Documentation](./ARCHIVED_RECORDS_PATTERN.md) for complete details.

## Testing

Test the endpoints using:
- Postman: Import the API collection and use the enriched endpoints
- Browser DevTools: Check Network tab to verify single API call
- React DevTools: Verify data structure matches the enriched response interfaces

## Implementation Status

✅ **All enriched endpoints are fully implemented and use the centralized `EnrichedService`**

This ensures:
- Consistent behavior across all enriched endpoints
- Automatic scoping based on user role type
- Reliable error handling
- Maintainable codebase

The backend implementation is complete and production-ready.

