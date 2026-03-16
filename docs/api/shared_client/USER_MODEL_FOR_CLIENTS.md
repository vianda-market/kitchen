# User Model for B2B/B2C Clients

This document describes the user model for mobile apps, web clients, and third-party integrations. Use it to coordinate B2B and B2C implementations.

## role_type Values

| Value | Description |
|-------|-------------|
| `Internal` | Vianda Enterprises staff (backoffice). Global access to all institutions. |
| `Supplier` | Restaurant/institution users. Institution-scoped (access only their institution). |
| `Customer` | End users (mobile apps). Self-scoped (access only their own data). |
| `Employer` | Benefit-program managers. Institution-scoped (access only their Employer institution). |

## role_name Values by role_type

| role_type | role_name Values |
|-----------|------------------|
| **Internal** | Admin, Super Admin, Global Manager, Manager, Operator |
| **Supplier** | Admin, Manager, Operator |
| **Customer** | Comensal only |
| **Employer** | Admin, Manager, Comensal |

## institution_type Values

| Value | Description |
|-------|-------------|
| `Internal` | Vianda Enterprises institution |
| `Customer` | Vianda Customers (B2C end users) |
| `Supplier` | Restaurant/supplier institution |
| `Employer` | Benefit-program institution |

Use "Employer" consistently for benefit-program institutions. Do not use "benefits-program" as the canonical term.

## employer_id (Assign Employer)

**Only Customer (Comensal) users can have `employer_id`.**

- Internal, Supplier, and Employer users **cannot** have `employer_id`
- `PUT /users/me/employer` is blocked for Internal, Supplier, and Employer role_types
- Only Customer users can assign themselves to an employer

## Breaking Changes (Employee → Internal Rename)

### role_type

- **Before**: `role_type === "Employee"`
- **After**: `role_type === "Internal"`

Update all client-side checks:

```javascript
// OLD
if (user.role_type === "Employee") { ... }

// NEW
if (user.role_type === "Internal") { ... }
```

### role_name "Employer" Removed from Customer

- **Before**: Customer users could have `role_name === "Employer"` (benefit-program managers)
- **After**: Employer users are now `role_type === "Employer"` with `role_name === "Admin"`, `"Manager"`, or `"Comensal"`

Update client-side checks:

```javascript
// OLD - Customer with Employer role_name
if (user.role_type === "Customer" && user.role_name === "Employer") { ... }

// NEW - Employer role_type
if (user.role_type === "Employer") { ... }
```

## Example Valid Combinations

| role_type | role_name | institution_type |
|-----------|-----------|------------------|
| Internal | Admin | Internal |
| Internal | Super Admin | Internal |
| Supplier | Admin | Supplier |
| Customer | Comensal | Customer or Employer |
| Employer | Admin | Employer |
| Employer | Manager | Employer |
| Employer | Comensal | Employer |
