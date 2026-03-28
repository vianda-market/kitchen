# Role-Based Access Control (RBAC) API Guide

## Overview

This document provides a comprehensive guide to role-based access control in the Kitchen API. It explains how different roles access endpoints, what scopes they have, and how to use the API correctly based on your role.

## Role Structure

The API uses a two-tier role system: `role_type` and `role_name`. Together, these determine a user's access level and scope.

### Role Types

- **Employee**: Vianda Enterprises staff members
- **Supplier**: Restaurant/institution administrators
- **Customer**: End users accessing via mobile apps

### Role Names

#### Employee Roles
- **Admin**: Global access to all institutions and users
- **Super Admin**: Global access (same as Admin, with additional system privileges)
- **Management**: Institution-scoped access (can manage users within their institution)
- **Operator**: Self-only access (can only manage their own profile)

#### Supplier Roles
- **Admin**: Institution-scoped access (can manage resources within their institution)

#### Customer Roles
- **Comensal**: Self-only access (can only manage their own profile)

## Scope Matrix

| Role Type | Role Name | Scope | Can Manage Others | Self-Updates |
|-----------|-----------|-------|-------------------|--------------|
| Employee | Admin | Global | ✅ Yes (any user/institution) | `/me` endpoints |
| Employee | Super Admin | Global | ✅ Yes (any user/institution) | `/me` endpoints |
| Employee | Management | Institution | ✅ Yes (institution users only) | `/me` endpoints |
| Employee | Operator | None | ❌ No | `/me` endpoints only |
| Supplier | Admin | Institution | ✅ Yes (institution users only) | `/me` endpoints |
| Customer | Comensal | None | ❌ No | `/me` endpoints only |

## Endpoint Access Patterns

### Self-Update Endpoints (`/me`)

All roles should use `/me` endpoints for updating their own profile:

- `GET /users/me` - Get current user's profile
- `PUT /users/me` - Update current user's profile

**Who can use**: All roles (Employee Admin, Management, Operator, Supplier Admin, Customer)

**Example Request**:
```http
PUT /users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "mobile_number": "+14155552671"
}
```

### Admin Endpoints (`/{user_id}`)

These endpoints allow managing other users. Access depends on role:

- `GET /users/{user_id}` - Get user by ID
- `PUT /users/{user_id}` - Update user by ID
- `DELETE /users/{user_id}` - Delete user by ID
- `GET /users/enriched/{user_id}` - Get enriched user data

**Who can use**:
- ✅ **Employee Admin/Super Admin**: Can access any user (global scope)
- ✅ **Employee Management**: Can access users within their institution
- ✅ **Supplier Admin**: Can access users within their institution
- ❌ **Employee Operator**: Cannot access other users (403 Forbidden)
- ❌ **Customer**: Cannot access other users (403 Forbidden)

**Example Request**:
```http
GET /users/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer <employee_admin_token>
```

**Error Responses**:
- `403 Forbidden`: User exists but is outside your scope (cross-institution access)
- `404 Not Found`: User does not exist

### List Endpoints (`/users/`)

- `GET /users/` - List all users
- `GET /users/enriched/` - List all users with enriched data

**Who can use**:
- ✅ **Employee Admin/Super Admin**: See all users (global scope)
- ✅ **Employee Management**: See users within their institution only
- ✅ **Supplier Admin**: See users within their institution only
- ❌ **Employee Operator**: Should use `/me` endpoint instead
- ❌ **Customer**: Should use `/me` endpoint instead

**Example Request**:
```http
GET /users/?include_archived=false
Authorization: Bearer <employee_management_token>
```

**Response**: Filtered list based on your institution scope

## Common Scenarios

### Scenario 1: Employee Operator Updating Their Profile

**Correct Approach**:
```http
PUT /users/me
Authorization: Bearer <employee_operator_token>
```

**Incorrect Approach** (will return 403):
```http
PUT /users/{their_own_user_id}
Authorization: Bearer <employee_operator_token>
```

### Scenario 2: Employee Management Accessing Cross-Institution User

**Request**:
```http
GET /users/{user_id_from_different_institution}
Authorization: Bearer <employee_management_token>
```

**Response**:
```json
{
  "detail": "Forbidden: You do not have access to this user"
}
```
**Status Code**: `403 Forbidden` (not 404, because the user exists)

### Scenario 3: Employee Admin Accessing Any User

**Request**:
```http
GET /users/{any_user_id}
Authorization: Bearer <employee_admin_token>
```

**Response**: User data (regardless of institution)

## Address Management

Address endpoints follow similar patterns:

### Self-Only Roles (Employee Operator, Customer)

- Can only create/update/delete addresses for themselves
- `user_id` is automatically set from the JWT token
- Attempting to manage addresses for others returns `403 Forbidden`

### Admin Roles (Employee Admin, Management, Supplier Admin)

- Can create/update/delete addresses for users within their scope
- Must provide `user_id` in request body
- Cross-institution access returns `403 Forbidden`

**Example - Employee Operator Creating Address**:
```http
POST /addresses/
Authorization: Bearer <employee_operator_token>
Content-Type: application/json

{
  "institution_id": "33333333-3333-3333-3333-333333333333",
  "address_type": ["Customer Home"],
  "country": "Argentina",
  "province": "Buenos Aires",
  "city": "Buenos Aires",
  "postal_code": "1414",
  "street_type": "Street",
  "street_name": "Example Street",
  "building_number": "123"
}
```

Note: `user_id` is automatically set from the token. If you try to set a different `user_id`, you'll get `403 Forbidden`.

## Error Handling

### 401 Unauthorized
- **Cause**: Missing or invalid authentication token
- **Solution**: Ensure you're logged in and using a valid token

### 403 Forbidden
- **Cause**: You don't have permission to access this resource
- **Common Scenarios**:
  - Employee Operator trying to access another user
  - Employee Management trying to access cross-institution user
  - Customer trying to access another user's data
- **Solution**: Use `/me` endpoints for self-updates, or ensure you have the correct role for admin operations

### 404 Not Found
- **Cause**: Resource doesn't exist
- **Note**: For user endpoints, if a user exists but is outside your scope, you'll get `403` instead of `404`

## Best Practices

1. **Always use `/me` endpoints for self-updates**
   - More secure (no path parameter manipulation)
   - Works for all roles
   - Recommended by the API

2. **Check your role before making admin requests**
   - Employee Operators and Customers cannot manage others
   - Use `/me` endpoints instead

3. **Handle 403 errors gracefully**
   - A 403 means the resource exists but you don't have access
   - A 404 means the resource doesn't exist
   - This distinction helps with security (prevents enumeration attacks)

4. **Use appropriate tokens**
   - Each role should use its own authentication token
   - Don't mix tokens between roles

## Related Documentation

- [API Permissions by Role](./API_PERMISSIONS_BY_ROLE.md) - Detailed endpoint permission matrix
- [Scoping System](./SCOPING_SYSTEM.md) - Technical details on scoping implementation
- [Role Assignment Guide](./ROLE_ASSIGNMENT_GUIDE.md) - How to assign roles to users

