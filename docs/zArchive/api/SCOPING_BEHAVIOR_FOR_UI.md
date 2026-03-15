# Scoping Behavior for UI Development

## Overview

The backend automatically enforces data scoping based on the authenticated user's role. **The UI does NOT need to filter data client-side** - the backend handles all scoping automatically.

## Key Principle

**Backend enforces scoping → UI receives pre-filtered data → No client-side filtering needed**

If a user tries to access data outside their scope, the backend will return a `403 Forbidden` error.

---

## Role Types

- **Employee**: Global access (can see all data across all institutions)
- **Supplier**: Institution-scoped (can only see data from their institution)
- **Customer**: User-scoped (can only see their own data)

---

## Scoping Behavior by Resource Type

### Institution-Scoped Resources

**Behavior**: Suppliers see only their institution's data, Employees see all.

**Resources**:
- Restaurants
- Products
- Plates (for Suppliers - see special case below)
- QR Codes
- Institution Entities
- Institution Bank Accounts
- Institution Bills
- Institution Payment Attempts
- Restaurant Balance Info

**Example**:
- A Supplier from "Acme Restaurant" can only see restaurants, products, and plates from "Acme Restaurant"
- An Employee can see restaurants, products, and plates from all institutions

---

### User-Scoped Resources

**Behavior**: Customers see only their own data, Suppliers see their institution's users, Employees see all.

**Resources**:
- Users
- Addresses

**Example**:
- A Customer can only see their own user record and their own addresses
- A Supplier can see all users and addresses within their institution
- An Employee can see all users and addresses across all institutions

---

## Special Cases

### Plates API

**Behavior**: 
- **Customers**: Can GET all plates (no scoping) to browse available meals, but cannot create/modify them
- **Suppliers**: Can only see plates from their institution's restaurants
- **Employees**: Can see all plates

**Why**: Customers need to browse all available meals to make selections, but they cannot create or modify plates.

---

### Addresses API

**Behavior**:
- **Customers**: 
  - `user_id` is automatically set from their own `user_id` on creation (cannot be changed)
  - Can only GET/PUT/DELETE addresses where `user_id` matches their own
- **Suppliers**: 
  - Can assign `user_id` to any user within their institution
  - Can manage addresses for any user within their institution
- **Employees**: 
  - Can assign `user_id` to any user
  - Can manage addresses for any user

**Example**:
```typescript
// Customer creating an address
POST /addresses/
{
  "street_type": "Av.",
  "street_name": "Libertador",
  "building_number": "191",
  // user_id is automatically set from JWT - don't send it
}

// Supplier creating an address for a user in their institution
POST /addresses/
{
  "user_id": "uuid-of-user-in-same-institution",  // ✅ Allowed
  "street_type": "Av.",
  "street_name": "Libertador",
  "building_number": "191"
}
```

---

### Users API

**Behavior**:
- **Customers**: 
  - Can GET/PUT/DELETE their own user record only
  - Cannot POST (create users) - returns 403
- **Suppliers**: 
  - Can manage users within their institution
  - Cannot create users outside their institution
- **Employees**: 
  - Global access (can manage all users)

**Example**:
```typescript
// Customer trying to access their own user - ✅ Allowed
GET /users/{customer_user_id}

// Customer trying to access another user - ❌ 403 Forbidden
GET /users/{other_user_id}

// Customer trying to create a user - ❌ 403 Forbidden
POST /users/
```

---

### Institutions API

**Behavior**:
- **Suppliers**: 
  - Can GET/PUT/DELETE their own institution
  - Cannot POST (create new institutions) - returns 403
- **Employees**: 
  - Full access (can create, read, update, delete all institutions)

**Example**:
```typescript
// Supplier accessing their own institution - ✅ Allowed
GET /institutions/{supplier_institution_id}

// Supplier trying to create a new institution - ❌ 403 Forbidden
POST /institutions/

// Supplier trying to access another institution - ❌ 403 Forbidden
GET /institutions/{other_institution_id}
```

---

## What the UI Should Do

### ✅ DO

1. **Trust the backend**: Backend already filters data based on user's role
2. **Handle 403 errors gracefully**: Show user-friendly messages when access is denied
3. **Use appropriate endpoints**: Use enriched endpoints when you need related entity names
4. **Omit `include_archived`**: Let backend exclude archived records by default
5. **Auto-set fields for Customers**: Don't send `user_id` when creating addresses as a Customer (backend sets it automatically)

### ❌ DON'T

1. **Don't filter client-side**: Backend already filters - filtering again is redundant and can cause issues
2. **Don't try to access out-of-scope data**: The backend will return 403
3. **Don't send `user_id` for Customers**: When creating addresses as a Customer, let the backend set it automatically
4. **Don't assume all data is available**: Check permissions first (see `API_PERMISSIONS_BY_ROLE.md`)

---

## Error Handling

### 403 Forbidden

**When it occurs**:
- User tries to access data outside their scope
- User tries to perform an operation not allowed for their role

**What to do**:
```typescript
if (response.status === 403) {
  // Show user-friendly message
  showError("You don't have permission to access this resource");
  // Optionally redirect or hide UI elements
}
```

**Example scenarios**:
- Customer trying to access another user's record
- Supplier trying to create a new institution
- Customer trying to create a user
- Supplier trying to access another institution's data

### 401 Unauthorized

**When it occurs**:
- Missing or invalid authentication token
- Token expired

**What to do**:
```typescript
if (response.status === 401) {
  // Redirect to login
  redirectToLogin();
}
```

---

## Implementation Examples

### Example 1: Users List Page

```typescript
// ✅ GOOD: Backend handles scoping automatically
const fetchUsers = async () => {
  const response = await fetch('/users/enriched/', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  if (response.status === 403) {
    throw new Error('Access denied');
  }
  
  const users = await response.json();
  // Users are already filtered by backend:
  // - Customers: Only their own user
  // - Suppliers: Users from their institution
  // - Employees: All users
  
  return users;
};
```

### Example 2: Address Creation (Customer)

```typescript
// ✅ GOOD: Don't send user_id - backend sets it automatically
const createAddress = async (addressData) => {
  // Remove user_id if present (for Customers)
  const { user_id, ...data } = addressData;
  
  const response = await fetch('/addresses/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)  // user_id not included
  });
  
  return response.json();
};
```

### Example 3: Address Creation (Supplier)

```typescript
// ✅ GOOD: Supplier can assign user_id to users in their institution
const createAddress = async (addressData) => {
  const response = await fetch('/addresses/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(addressData)  // user_id can be included
  });
  
  if (response.status === 403) {
    // User might be outside supplier's institution
    throw new Error('Cannot assign address to this user');
  }
  
  return response.json();
};
```

### Example 4: Plates Browsing (Customer)

```typescript
// ✅ GOOD: Customers can GET all plates (no scoping for browsing)
const fetchPlates = async () => {
  const response = await fetch('/plates/enriched/', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const plates = await response.json();
  // Customers see all plates (for browsing)
  // Suppliers see only their institution's plates
  // Employees see all plates
  
  return plates;
};
```

---

## Testing Scoping Behavior

When testing your UI:

1. **Test as different roles**: 
   - Test as Customer, Supplier, and Employee
   - Verify each role sees the correct data

2. **Test error handling**:
   - Try to access out-of-scope data
   - Verify 403 errors are handled gracefully

3. **Test edge cases**:
   - Customer trying to create a user
   - Supplier trying to create an institution
   - Customer trying to access another user's address

---

## Related Documentation

- **API Permissions**: See `API_PERMISSIONS_BY_ROLE.md` for detailed permission matrices
- **Enriched Endpoints**: See `ENRICHED_ENDPOINT_PATTERN.md` for using enriched endpoints
- **Archived Records**: See `ARCHIVED_RECORDS_PATTERN.md` for handling archived records

---

*Last Updated: 2025-11-17*

