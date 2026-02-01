# User Self-Update API Pattern

## Overview

This document describes the **new `/me` endpoint pattern** for user self-updates and the **deprecation of legacy `/{user_id}` endpoints** for self-operations.

## ⚠️ Important: API Pattern Change

**As of December 2024**, the API has introduced new `/me` endpoints for secure self-updates. The legacy `/{user_id}` endpoints are **deprecated for self-operations** and will be removed in a future version.

---

## New Pattern: `/me` Endpoints

### Available Endpoints

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `GET /users/me` | GET | Get current user's profile (enriched) | `UserEnrichedResponseSchema` |
| `PUT /users/me` | PUT | Update current user's profile | `UserResponseSchema` |
| `PUT /users/me/terminate` | PUT | Terminate current user's account (archive) | `{detail: string}` |
| `PUT /users/me/employer` | PUT | Assign employer to current user | `UserResponseSchema` |

### Key Benefits

1. **Security**: No path parameter manipulation risk - `user_id` extracted from JWT token
2. **Clarity**: Explicitly indicates self-operation
3. **Consistency**: All users (Customers, Suppliers, Employees) use same pattern for self-updates
4. **Future-proof**: Legacy endpoints will be removed for self-operations

---

## Deprecated Pattern: `/{user_id}` Endpoints

### ⚠️ Deprecated Endpoints (Self-Operations Only)

| Endpoint | Status | Use Instead |
|----------|--------|-------------|
| `GET /users/{user_id}` | ⚠️ **DEPRECATED** for self-reads | `GET /users/me` |
| `PUT /users/{user_id}` | ⚠️ **DEPRECATED** for self-updates | `PUT /users/me` |
| `GET /users/enriched/{user_id}` | ⚠️ **DEPRECATED** for self-reads | `GET /users/me` |

### Important Notes

- **Still Available for Admin Operations**: These endpoints remain available for **Admins managing OTHER users** (not themselves)
- **Deprecation Warnings**: Using these endpoints for self-operations will log warnings
- **OpenAPI/Swagger**: These endpoints are marked as `deprecated=True` in API documentation
- **Future Removal**: Self-update access via `/{user_id}` will be removed in 6-12 months

---

## Usage Patterns by Role

### Customers

**Self-Updates**: ✅ **MUST use `/me` endpoints**
- `GET /users/me` - View own profile
- `PUT /users/me` - Update own profile
- `PUT /users/me/terminate` - Terminate account
- `PUT /users/me/employer` - Assign employer

**Admin Operations**: ❌ **Not applicable** (Customers cannot manage other users)

### Employee Operators

**Self-Updates**: ✅ **MUST use `/me` endpoints**
- `GET /users/me` - View own profile
- `PUT /users/me` - Update own profile
- `PUT /users/me/terminate` - Terminate account
- `PUT /users/me/employer` - Assign employer

**Admin Operations**: ❌ **Not applicable** (Operators cannot manage other users)

### Employee Management / Employee Admin / Supplier Admin

**Self-Updates**: ✅ **MUST use `/me` endpoints**
- `GET /users/me` - View own profile
- `PUT /users/me` - Update own profile
- `PUT /users/me/terminate` - Terminate account
- `PUT /users/me/employer` - Assign employer

**Admin Operations**: ✅ **Use `/{user_id}` endpoints** (for managing OTHER users)
- `GET /users/{user_id}` - Get other user's profile
- `PUT /users/{user_id}` - Update other user's profile
- `GET /users/enriched/{user_id}` - Get other user's enriched profile

---

## TypeScript Examples

### ✅ Correct: Using `/me` Endpoints

```typescript
// Get current user's profile
async function getMyProfile(): Promise<UserEnrichedResponseSchema> {
  const response = await fetch('/api/v1/users/me', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
}

// Update current user's profile
async function updateMyProfile(updates: UserUpdateSchema): Promise<UserResponseSchema> {
  const response = await fetch('/api/v1/users/me', {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  return response.json();
}

// Terminate current user's account
async function terminateMyAccount(): Promise<{detail: string}> {
  const response = await fetch('/api/v1/users/me/terminate', {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
}

// Assign employer to current user
async function assignMyEmployer(employerId: string): Promise<UserResponseSchema> {
  const response = await fetch(`/api/v1/users/me/employer?employer_id=${employerId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
}
```

### ⚠️ Deprecated: Using `/{user_id}` for Self-Updates

```typescript
// ❌ DEPRECATED: Don't use this for self-updates
async function updateMyProfileDeprecated(userId: string, updates: UserUpdateSchema): Promise<UserResponseSchema> {
  // This will log a deprecation warning
  const response = await fetch(`/api/v1/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  return response.json();
}

// ✅ CORRECT: Use /me endpoint instead
async function updateMyProfile(updates: UserUpdateSchema): Promise<UserResponseSchema> {
  const response = await fetch('/api/v1/users/me', {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  return response.json();
}
```

### ✅ Correct: Using `/{user_id}` for Admin Operations

```typescript
// ✅ CORRECT: Admins can use /{user_id} for managing OTHER users
async function updateOtherUser(userId: string, updates: UserUpdateSchema): Promise<UserResponseSchema> {
  // This is fine - admin operation on another user
  const response = await fetch(`/api/v1/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  return response.json();
}
```

---

## Migration Guide

### Step 1: Identify Self-Update Calls

Find all API calls where `user_id` in the URL matches the current user's ID:

```typescript
// Before: Deprecated pattern
const currentUserId = getCurrentUserId(); // From JWT token
await fetch(`/api/v1/users/${currentUserId}`, { method: 'PUT', ... });

// After: New pattern
await fetch('/api/v1/users/me', { method: 'PUT', ... });
```

### Step 2: Update API Service Functions

```typescript
// Before
class UserService {
  async updateUser(userId: string, updates: UserUpdateSchema) {
    return fetch(`/api/v1/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  }
}

// After
class UserService {
  async updateMyProfile(updates: UserUpdateSchema) {
    return fetch('/api/v1/users/me', {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  }
  
  // Keep for admin operations
  async updateOtherUser(userId: string, updates: UserUpdateSchema) {
    return fetch(`/api/v1/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(updates)
    });
  }
}
```

### Step 3: Update React Components

```typescript
// Before
function ProfileEditForm() {
  const { userId } = useAuth();
  const updateProfile = async (updates: UserUpdateSchema) => {
    await userService.updateUser(userId, updates); // ❌ Deprecated
  };
}

// After
function ProfileEditForm() {
  const updateProfile = async (updates: UserUpdateSchema) => {
    await userService.updateMyProfile(updates); // ✅ Correct
  };
}
```

---

## What to Expect During Migration

### Deprecation Warnings

When using deprecated endpoints for self-updates, you may see:

1. **Log Warnings**: Backend logs will include deprecation warnings
2. **OpenAPI/Swagger**: Endpoints marked as `deprecated=True`
3. **No Breaking Changes**: Endpoints still work during migration period

### Error Handling

```typescript
// Handle potential deprecation responses (future)
try {
  const response = await fetch('/api/v1/users/me', { ... });
  if (response.status === 410) {
    // Gone - endpoint removed (future)
    throw new Error('Endpoint removed. Use /me endpoints.');
  }
} catch (error) {
  // Handle error
}
```

---

## Best Practices

### ✅ DO

- Use `/me` endpoints for all self-updates (all user types)
- Use `/{user_id}` endpoints only for admin operations (managing other users)
- Extract `user_id` from JWT token for `/me` endpoints (don't pass it)
- Update all self-update code to use `/me` pattern

### ❌ DON'T

- Don't use `/{user_id}` endpoints for self-updates
- Don't pass `user_id` to `/me` endpoints (extracted from token)
- Don't filter client-side - backend handles scoping
- Don't ignore deprecation warnings

---

## Security Benefits

### Why `/me` Endpoints Are More Secure

1. **No Path Parameter Manipulation**: `user_id` comes from JWT token, not URL
2. **Explicit Intent**: Clear that this is a self-operation
3. **Reduced Attack Surface**: No risk of accidentally updating wrong user
4. **Consistent Pattern**: All users follow same pattern

### Example: Path Parameter Manipulation Risk

```typescript
// ❌ RISKY: user_id in URL can be manipulated
PUT /users/{user_id}  // What if attacker changes user_id?

// ✅ SAFE: user_id from JWT token (cannot be manipulated)
PUT /users/me  // Always refers to authenticated user
```

---

## Summary

| Operation | Endpoint | Who Can Use |
|-----------|----------|-------------|
| **Get my profile** | `GET /users/me` | All users |
| **Update my profile** | `PUT /users/me` | All users |
| **Terminate my account** | `PUT /users/me/terminate` | All users |
| **Assign my employer** | `PUT /users/me/employer` | All users |
| **Get other user's profile** | `GET /users/{user_id}` | Admins only |
| **Update other user's profile** | `PUT /users/{user_id}` | Admins only |

**Key Rule**: Use `/me` for self-operations, `/{user_id}` for admin operations (managing other users).

---

## Related Documentation

- `API_PERMISSIONS_BY_ROLE.md` - Role-based access control
- `SCOPING_BEHAVIOR_FOR_UI.md` - Scoping behavior
- `ENRICHED_ENDPOINT_PATTERN.md` - Enriched endpoint pattern

---

**Last Updated**: December 2024

