# Role Assignment Guide

## Overview

This guide explains how to assign roles to users in the Kitchen API. Roles are defined by two fields: `role_type` and `role_name`, which together determine a user's access level and scope.

## Role System

### Role Types

- **Employee**: `"Employee"` - Vianda Enterprises staff
- **Supplier**: `"Supplier"` - Restaurant/institution administrators
- **Customer**: `"Customer"` - End users

### Role Names

#### For Employee Role Type
- `"Admin"` - Global access
- `"Super Admin"` - Global access (with additional privileges)
- `"Manager"` - Institution-scoped access
- `"Operator"` - Self-only access

#### For Supplier Role Type
- `"Admin"` - Institution-scoped access

#### For Customer Role Type
- `"Comensal"` - Self-only access

## Valid Role Combinations

The API validates that `role_type` and `role_name` combinations are valid:

| Role Type | Valid Role Names |
|-----------|------------------|
| Employee | Admin, Super Admin, Manager, Operator |
| Supplier | Admin, Manager, Operator |
| Customer | Comensal, Employer |

**Invalid combinations will return a `422 Unprocessable Entity` error.**

## Role Assignment Rules (Who Can Assign Which Role)

When creating or updating a user, the current user must be allowed to assign the target `role_name`. The backend enforces these rules and returns **403 Forbidden** if violated:

| Target role_name | Who can assign |
|------------------|----------------|
| **Super Admin** | Only Super Admin (Employee) |
| **Admin** | Only Admin or Super Admin (Employee Admin, Employee Super Admin, Supplier Admin) |
| **Manager** | Only Admin, Super Admin, or Manager |
| **Operator** | Only Admin, Super Admin, or Manager |
| **Comensal** / **Employer** | Only Employee (Customer users) |

Additional rules:
- **Operator** (Employee or Supplier): Cannot create or update other users. Operator has no access to user management; they can only manage their own profile via `PUT /users/me`.
- **Super Admin** assignment: Only a Super Admin can create or promote another user to Super Admin.
- **Admin** assignment: Only an Admin (or Super Admin) can assign Admin. A Manager cannot promote someone to Admin.

**Editing hierarchy (prevents downgrades)**:
- **Manager** cannot edit (update, password reset, or delete) **Admin** or **Super Admin**. Attempts return **403 Forbidden**.
- **Admin** cannot edit (update, password reset, or delete) **Super Admin**. Attempts return **403 Forbidden**.

**Frontend**: Use `GET /api/v1/enums/roles/assignable` to get the list of assignable role_type and role_name values. The backend will enforce the rules above on create/update; consider hiding or disabling role options the current user cannot assign to avoid 403 on submit.

## Creating Users with Roles

### Endpoint

```
POST /users/
```

### Request Body

```json
{
  "institution_id": "33333333-3333-3333-3333-333333333333",
  "role_type": "Employee",
  "role_name": "Manager",
  "username": "john.doe",
  "email": "john.doe@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe",
  "cellphone": "1234567890"
}
```

### Required Fields

- `institution_id` (UUID): The institution the user belongs to
- `role_type` (string): One of "Employee", "Supplier", or "Customer"
- `role_name` (string): Valid role name for the role type
- `username` (string): Unique username (min 3, max 100 characters)
- `email` (EmailStr): Valid email address
- `password` (string): Password (min 8 characters)
- `cellphone` (string): Phone number (max 20 characters)

### Optional Fields

- `first_name` (string, max 50 characters)
- `last_name` (string, max 50 characters)
- `employer_id` (UUID): Link to employer record

### Example: Create Employee Admin

```http
POST /users/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "institution_id": "33333333-3333-3333-3333-333333333333",
  "role_type": "Employee",
  "role_name": "Admin",
  "username": "admin.user",
  "email": "admin@vianda.com",
  "password": "SecurePassword123!",
  "first_name": "Admin",
  "last_name": "User",
  "cellphone": "1234567890"
}
```

### Example: Create Employee Management

```http
POST /users/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "institution_id": "33333333-3333-3333-3333-333333333333",
  "role_type": "Employee",
  "role_name": "Manager",
  "username": "manager.user",
  "email": "manager@vianda.com",
  "password": "SecurePassword123!",
  "first_name": "Manager",
  "last_name": "User",
  "cellphone": "1234567890"
}
```

### Example: Create Employee Operator

```http
POST /users/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "institution_id": "33333333-3333-3333-3333-333333333333",
  "role_type": "Employee",
  "role_name": "Operator",
  "username": "operator.user",
  "email": "operator@vianda.com",
  "password": "SecurePassword123!",
  "first_name": "Operator",
  "last_name": "User",
  "cellphone": "1234567890"
}
```

### Example: Create Supplier Admin

```http
POST /users/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "institution_id": "11111111-1111-1111-1111-111111111111",
  "role_type": "Supplier",
  "role_name": "Admin",
  "username": "supplier.admin",
  "email": "supplier@restaurant.com",
  "password": "SecurePassword123!",
  "first_name": "Supplier",
  "last_name": "Admin",
  "cellphone": "1234567890"
}
```

### Example: Create Customer

```http
POST /users/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "institution_id": "44444444-4444-4444-4444-444444444444",
  "role_type": "Customer",
  "role_name": "Comensal",
  "username": "customer.user",
  "email": "customer@example.com",
  "password": "SecurePassword123!",
  "first_name": "Customer",
  "last_name": "User",
  "cellphone": "1234567890"
}
```

## Updating User Roles

### Endpoint

```
PUT /users/{user_id}
```

### Request Body

You can update `role_type` and `role_name` together:

```json
{
  "role_type": "Employee",
  "role_name": "Manager"
}
```

**Note**: Both fields must be provided together, and the combination must be valid.

### Example: Promote Employee Operator to Management

```http
PUT /users/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "role_type": "Employee",
  "role_name": "Manager"
}
```

### Example: Demote Employee Management to Operator

```http
PUT /users/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "role_type": "Employee",
  "role_name": "Operator"
}
```

## Validation Errors

### Invalid Role Combination

**Request**:
```json
{
  "role_type": "Employee",
  "role_name": "Comensal"
}
```

**Response**:
```json
{
  "detail": [
    {
      "loc": ["body", "role_name"],
      "msg": "Invalid role combination: Employee + Comensal. Valid combinations: ['Admin', 'Super Admin', 'Manager', 'Operator']",
      "type": "value_error"
    }
  ]
}
```

**Status Code**: `422 Unprocessable Entity`

### Missing Role Fields

**Request**:
```json
{
  "username": "test.user",
  "email": "test@example.com",
  "password": "SecurePassword123!",
  "cellphone": "1234567890"
}
```

**Response**:
```json
{
  "detail": [
    {
      "loc": ["body", "role_type"],
      "msg": "field required",
      "type": "value_error.missing"
    },
    {
      "loc": ["body", "role_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Status Code**: `422 Unprocessable Entity`

## Access Control for Role Assignment

### Who Can Assign Roles?

- ✅ **Employee Admin/Super Admin**: Can assign any role to any user
- ✅ **Employee Management**: Can assign roles to users within their institution
- ❌ **Employee Operator**: Cannot assign roles (cannot manage other users)
- ❌ **Supplier Admin**: Can assign roles to users within their institution (typically Supplier Admin or Customer)
- ❌ **Customer**: Cannot assign roles

### Example: Employee Management Assigning Role

**Request**:
```http
PUT /users/{user_id_in_same_institution}
Authorization: Bearer <employee_management_token>
Content-Type: application/json

{
  "role_type": "Employee",
  "role_name": "Operator"
}
```

**Response**: `200 OK` (if user is in same institution)

**Cross-Institution Attempt**:
```http
PUT /users/{user_id_in_different_institution}
Authorization: Bearer <employee_management_token>
Content-Type: application/json

{
  "role_type": "Employee",
  "role_name": "Operator"
}
```

**Response**: `403 Forbidden` (user exists but is outside scope)

## Database Schema

Roles are stored as PostgreSQL ENUMs in the database:

### `role_type_enum`
```sql
CREATE TYPE role_type_enum AS ENUM (
    'Employee',
    'Supplier',
    'Customer'
);
```

### `role_name_enum`
```sql
CREATE TYPE role_name_enum AS ENUM (
    'Admin',
    'Super Admin',
    'Comensal',
    'Manager',
    'Operator'
);
```

### User Table Structure
```sql
CREATE TABLE user_info (
    user_id UUID PRIMARY KEY,
    institution_id UUID NOT NULL,
    role_type role_type_enum NOT NULL,
    role_name role_name_enum NOT NULL,
    -- ... other fields
);
```

## Migration from Old System

The API previously used a `role_id` (UUID) system with a `role_info` table. This has been migrated to the enum-based system:

- ❌ **Old**: `role_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"`
- ✅ **New**: `role_type: "Employee"`, `role_name: "Admin"`

**All API requests must now use the new format.**

## Best Practices

1. **Always validate role combinations before sending**
   - Check the valid combinations table above
   - Invalid combinations will return 422 errors

2. **Assign appropriate roles based on responsibilities**
   - Employee Admin: System administrators with global access
   - Employee Management: Institution managers who manage users within their institution
   - Employee Operator: Support staff who only manage their own profile
   - Supplier Admin: Restaurant administrators
   - Customer: End users

3. **Use institution-scoped roles when possible**
   - Employee Management is more secure than Employee Admin for most use cases
   - Limits access to only the relevant institution

4. **Test role assignments in a development environment first**
   - Ensure the role combination is valid
   - Verify access control works as expected

## Related Documentation

- [Role-Based Access Control](./ROLE_BASED_ACCESS_CONTROL.md) - How roles affect API access
- [Scoping System](./SCOPING_SYSTEM.md) - Technical details on scope implementation

