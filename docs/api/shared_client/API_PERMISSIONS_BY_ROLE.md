# API Permissions by Role Type

This document provides a comprehensive reference for API endpoint permissions organized by role type. Each API section includes a permission matrix showing which operations are allowed for each role.

## Role Type Definitions

**Enum Values** (from `role_type_enum`):
- **Employee** (`'Employee'`): Vianda Enterprises staff with global access (includes Super Admin and Admin)
- **Supplier** (`'Supplier'`): Restaurant/institution administrators, scoped to their `institution_id`
- **Customer** (`'Customer'`): End users accessing via iOS/Android apps

**Role Name Definitions** (from `role_name_enum`):
- **Admin** (`'Admin'`): Administrator (Employee or Supplier)
- **Super Admin** (`'Super Admin'`): Super administrator with Employee role_type and special approval permissions
- **Manager** (`'Manager'`): Management role (Employee or Supplier)
- **Operator** (`'Operator'`): Operator role (Employee or Supplier)
- **Comensal** (`'Comensal'`): Customer role name for end users
- **Employer** (`'Employer'`): Customer role name for employer users

**Note**: Super Admin is NOT a separate role_type. Super Admins have `role_type='Employee'` and `role_name='Super Admin'`.

**Supplier role_name and permissions**: For Supplier users, `role_name` further restricts access. Many APIs allow **Admin** and **Manager** to read and/or mutate; **Operator** is often read-only or has no access. Exception: Institution Bank Accounts and Institution Entities require **Supplier Admin** or **Employee Admin/Super Admin** (Supplier Manager/Operator and Employee Manager/Operator have no access). See per-API tables below.

## Permission Legend

- ✅ = Allowed
- ❌ = Not Allowed (returns 403)
- 🔒 = Not Applicable (endpoint doesn't exist)

---

## 1. Plans API (`/plans/`)

**Description**: Subscription plan management for credit packages.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅ | ❌ | ❌ | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- GET operations available to Customers and Employees (for viewing plans in mobile app and backoffice)
- POST/PUT/DELETE restricted to Employees only (system configuration)
- Suppliers cannot access plans API

**Dependencies**: `get_client_or_employee_user()` for GET, `get_employee_user()` for POST/PUT/DELETE

---

## 2. Credit Currency API (`/credit-currencies/`)

**Description**: Credit currency configuration (conversion rates, currency codes).

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- All operations Employee-only (system configuration)
- Backend can still cross-query credit_currency for plate calculations, but Suppliers cannot directly access the API

**Dependencies**: `get_employee_user()` for all operations

---

## 3. Discretionary Credit API

### 3.1 Admin Discretionary Routes (`/admin/discretionary/`)

**Description**: Create and manage discretionary credit requests.

**Enum Requirements**: `role_type='Employee'` (any `role_name`)

| Role Type | Role Name | GET | POST | PUT | DELETE |
|-----------|-----------|-----|------|-----|--------|
| **Employee** | Any (`'Admin'`, `'Super Admin'`, etc.) | ✅ | ✅ | ✅ | ✅ |
| **Customer** | Any | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | Any | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- Any Employee (regardless of role_name) can create and manage discretionary requests
- Used for requesting discretionary credits for customers
- This is separate from approval routes (see 3.2)

**Dependencies**: `get_employee_user()` for all operations (requires `role_type='Employee'`)

### 3.2 Super Admin Discretionary Routes (`/super-admin/discretionary/`)

**Description**: Approve/reject discretionary credit requests.

**Enum Requirements**:
- **GET Operations**: `role_type='Employee'` AND `role_name IN ('Admin', 'Super Admin')`
- **Approve/Reject Operations**: `role_type='Employee'` AND `role_name='Super Admin'`

| Role Type | Role Name | GET Pending | GET All | GET Details | Approve | Reject |
|-----------|-----------|-------------|---------|-------------|---------|--------|
| **Employee** | `'Super Admin'` | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Employee** | `'Admin'` | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Customer** | Any | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | Any | ❌ | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- GET operations (pending requests, request details, all requests) available to Admin and Super Admin Employees
- Approve/Reject operations restricted to Super Admin Employees only (`role_name='Super Admin'`)
- Admins can view and create discretionary requests, but only Super Admins can approve/reject them

**Dependencies**: 
- `get_admin_user()` for GET endpoints (allows `role_type='Employee'` AND `role_name IN ('Admin', 'Super Admin')`)
- `get_super_admin_user()` for POST endpoints (approve/reject) (requires `role_type='Employee'` AND `role_name='Super Admin'`)

**Endpoints**:
- `GET /api/v1/super-admin/discretionary/pending-requests/` - List pending requests (Admin + Super Admin)
- `GET /api/v1/super-admin/discretionary/requests/` - List all requests (Admin + Super Admin)
- `GET /api/v1/super-admin/discretionary/requests/{request_id}` - Get request details (Admin + Super Admin)
- `POST /api/v1/super-admin/discretionary/requests/{request_id}/approve` - Approve request (Super Admin only)
- `POST /api/v1/super-admin/discretionary/requests/{request_id}/reject` - Reject request (Super Admin only)

---

## 4. Users API (`/users/`)

**Description**: User account management.

| Role | GET | POST (create) | PUT (update) | PUT .../password (admin reset) | DELETE |
|------|-----|----------------|--------------|--------------------------------|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅* | ❌ | ✅* (self) | ❌ | ✅* (self) |
| **Supplier** | ✅* | ✅* | ✅* | ✅* | ✅* |

**Supplier role_name (within Supplier)**:
| Supplier role_name | GET | POST (create) | PUT (update) | PUT .../password (admin reset) |
|--------------------|-----|----------------|--------------|--------------------------------|
| **Admin** | ✅ | ✅ | ✅ | ✅ |
| **Manager** | ✅ | ✅ | ✅ | ✅ |
| **Operator** | ✅ | ❌ | ❌ | ❌ |

**Employee role_name (within Employee)**:
| Employee role_name | GET | POST (create) | PUT (update other) | PUT .../password (admin reset) |
|--------------------|-----|----------------|--------------------|--------------------------------|
| **Super Admin** | ✅ | ✅ | ✅ | ✅ |
| **Admin** | ✅ | ✅ | ✅ | ✅ |
| **Manager** | ✅ | ✅ | ✅ | ✅ |
| **Operator** | ✅* | ❌ | ❌ | ❌ |

*Employee Operator can only GET and update their own record via `PUT /users/me`; cannot manage other users.

**Role assignment rules** (who can assign which role_name when creating or editing a user):

| Target role_name | Who can assign |
|------------------|----------------|
| **Super Admin** | Only Super Admin (Employee) |
| **Admin** | Only Admin or Super Admin (Employee Admin, Employee Super Admin, Supplier Admin) |
| **Manager** | Only Admin, Super Admin, or Manager |
| **Operator** | Only Admin, Super Admin, or Manager |
| **Comensal** / **Employer** | Only Employee (Customer users) |

**Editing hierarchy** (prevents downgrades):
- **Manager** cannot edit (update, password reset, or delete) **Admin** or **Super Admin**
- **Admin** cannot edit (update, password reset, or delete) **Super Admin**
- Attempts return **403 Forbidden**

**Notes**:
- **Customers**: Can GET, PUT, DELETE only their own user record (scoped by `user_id`). Change own password via `PUT /users/me/password`.
- **Suppliers**: Institution scoping. Only **Admin** and **Manager** can create users, update users, or reset another user's password. **Operator** can GET users within their institution only (read-only). Supplier Admin can assign Admin; Admin or Manager can assign Manager or Operator.
- **Employees**: Global access. **Operator** cannot create or update other users. **Super Admin** can assign Super Admin; **Admin** or Super Admin can assign Admin; **Admin**, Super Admin, or **Manager** can assign Manager or Operator.
- **Operator** (Employee or Supplier): No access to adjust other users, including role assignments.

**Dependencies**: `get_current_user()`, `ensure_operator_cannot_create_users()`, `ensure_supplier_can_create_edit_users()` on POST/PUT for Suppliers, `ensure_can_assign_role_name()` on create/update when role_name is set, `ensure_can_edit_user()` on PUT/DELETE and password reset, `ensure_supplier_can_reset_user_password()` on admin password reset. User scoping for Customers, institution scoping for Suppliers.

---

## 5. Restaurants API (`/restaurants/`)

**Description**: Restaurant information and management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Notes**:
- Institution scoping applies: Suppliers can only access restaurants within their institution
- Employees have global access
- Customers cannot access restaurant management API

**Dependencies**: `get_current_user()` with institution scoping

---

## 6. Products API (`/products/`)

**Description**: Product catalog management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Notes**:
- Institution scoping applies: Suppliers can only access products within their institution
- Employees have global access
- Customers cannot access product management API

**Dependencies**: `get_current_user()` with institution scoping

---

## 7. Plates API (`/plates/`)

**Description**: Plate (meal) offerings management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Notes**:
- **Customers**: Can GET plates to browse and book meals (no scoping - can see all available plates)
- **Suppliers**: Can access plates within their institution (institution scoping)
- **Employees**: Have global access
- POST/PUT/DELETE restricted to Suppliers and Employees (plate management)

**Dependencies**: `get_client_or_employee_user()` for GET, `get_current_user()` with institution scoping for POST/PUT/DELETE

---

## 8. QR Codes API (`/qr-code/`)

**Description**: QR code generation and management for restaurants.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Notes**:
- Institution scoping applies: Suppliers can only access QR codes within their institution
- Employees have global access
- Customers cannot access QR code management API (they scan QR codes via plate pickup API)

**Dependencies**: `get_current_user()` with institution scoping

---

## 9. Addresses API (`/addresses/`)

**Description**: Address management for users and institutions.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅* | ✅* | ✅* | ✅* |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Supplier role_name (within Supplier)**:
| Supplier role_name | GET | POST | PUT | DELETE |
|--------------------|-----|------|-----|--------|
| **Admin** | ✅ | ✅ | ✅ | ✅ |
| **Manager** | ✅ | ✅ | ✅ | ✅ |
| **Operator** | ✅ | ❌ | ❌ | ❌ |

**Notes**:
- **Customers**: Can GET, POST, PUT, DELETE only their own addresses (scoped by `user_id`)
- **Suppliers**: Institution scoping; only **Admin** and **Manager** can create/edit/delete addresses. **Operator** is read-only (GET only).
- **Employees**: Have global access

**Dependencies**: `get_current_user()`, `ensure_supplier_can_create_edit_addresses()` on POST/PUT/DELETE for Suppliers

---

## 10. Institution Entities API (`/institution-entities/`)

**Description**: Institution entity records (legal entities within an institution for billing, etc.).

**Access**: **Supplier Admin** and **Employee Admin/Super Admin** can access. All other roles receive 403 Forbidden.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee Admin / Super Admin** | ✅ | ✅ | ✅ | ✅ |
| **Employee Manager / Operator** | ❌ | ❌ | ❌ | ❌ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier Admin** | ✅ | ✅ | ✅ | ✅ |
| **Supplier Manager** | ❌ | ❌ | ❌ | ❌ |
| **Supplier Operator** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- **Supplier Admin** and **Employee Admin/Super Admin** can access institution entities (GET, POST, PUT, DELETE).
- **Supplier Manager**, **Supplier Operator**, **Employee Manager/Operator**, and **Customers** receive 403 on all endpoints.

**Dependencies**: `get_current_user()`, `require_supplier_admin_or_employee_admin()` dependency on router. Institution scoping for Supplier Admin; global scope for Employee Admin/Super Admin.

---

## 11. Institutions API (`/institutions/`)

**Description**: Institution (company/organization) management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅* | ✅* | ✅* |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ❌ | ❌ | ❌ |

**Employee role_name (for POST, PUT, DELETE)**:
| Employee role_name | POST (create) | PUT (update) | DELETE |
|--------------------|---------------|--------------|--------|
| **Super Admin** | ✅ | ✅ | ✅ |
| **Admin** | ✅ | ✅ | ✅ |
| **Manager** | ❌ | ❌ | ❌ |
| **Operator** | ❌ | ❌ | ❌ |

**Notes**:
- **Suppliers**: Can GET their own institution only (read-only). Cannot create, update, or delete institutions.
- **Employees**: Only **Admin** and **Super Admin** can POST (create), PUT (update), or DELETE institutions. **Manager** and **Operator** are read-only (GET only).
- **Customers**: Cannot access institution management API

**Dependencies**: `get_current_user()` with institution scoping for GET. POST, PUT, DELETE use `get_admin_user()` to restrict to Employee Admin and Super Admin only.

---

## 12. Plate Selection API (`/plate-selection/`)

**Description**: Customer plate selection and ordering.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ❌ | ❌ |
| **Customer** | ✅ | ✅ | ❌ | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- Customers and Employees can view and create plate selections
- Plate selections are immutable (no PUT/DELETE)
- Suppliers cannot access plate selection API

**Dependencies**: `get_current_user()` with user context

---

## 13. Plate Pickup API (`/plate-pickup/`)

**Description**: QR code scanning and pickup confirmation.

| Role | GET Pending | POST Scan QR | POST Complete |
|------|-------------|--------------|---------------|
| **Employee** | ✅ | ❌ | ❌ |
| **Customer** | ✅ | ✅ | ❌ |
| **Supplier** | ✅* | ❌ | ✅* |

**Notes**:
- Customers can scan QR codes to confirm arrival
- Suppliers can view pending pickups and complete orders (restaurant staff)
- Employees can view pending pickups for monitoring
- Institution scoping applies for Suppliers

**Dependencies**: `get_current_user()` with institution scoping

---

## 14. Subscriptions API (`/subscriptions/`)

**Description**: User subscription management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅* | ✅* | ✅* | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- Customers can manage their own subscriptions (scoped by user_id)
- Employees have global access
- Suppliers cannot access subscriptions API

**Dependencies**: `get_current_user()` with user context

---

## 16. Payment Methods API (`/payment-methods/`)

**Description**: User payment method management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅* | ✅* | ✅* | ✅* |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- Customers can manage their own payment methods (scoped by user_id)
- Employees have global access
- Suppliers cannot access payment methods API

**Dependencies**: `get_current_user()` with user context

---

## 16. Institution Bills API (`/institution-bills/`)

**Description**: Institution billing and payment management.

| Role | GET | POST Generate | POST Record Payment | POST Cancel |
|------|-----|---------------|-------------------|-------------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ❌ | ✅* | ✅* |

**Notes**:
- Suppliers can view and manage bills for their institution
- Employees have global access and can generate bills
- Customers cannot access institution bills API

**Dependencies**: `get_current_user()` with institution scoping

---

## Summary Matrix

### System Configuration APIs (Employee-Only)

| API | Employee | Customer | Supplier |
|-----|----------|---------|----------|
| **Plans** (POST/PUT/DELETE) | ✅ | ❌ | ❌ |
| **Credit Currency** (All) | ✅ | ❌ | ❌ |
| **Discretionary** (All) | ✅ | ❌ | ❌ |
| **Fintech Link** (POST/PUT/DELETE) | ✅ | ❌ | ❌ |

### View-Only APIs (Customer + Employee)

| API | Employee | Customer | Supplier |
|-----|----------|---------|----------|
| **Plans** (GET) | ✅ | ✅ | ❌ |
| **Fintech Link** (GET) | ✅ | ✅ | ❌ |

### Institution-Scoped APIs

| API | Employee | Customer | Supplier (by role_name) |
|-----|----------|---------|------------------------|
| **Users** | ✅ (Global) | ✅ (Own) | Admin/Manager: full; Operator: read-only |
| **Restaurants** | ✅ (Global) | ❌ | ✅ (Scoped) |
| **Products** | ✅ (Global) | ❌ | ✅ (Scoped) |
| **Plates** | ✅ (Global) | ✅ (View All) | ✅ (Scoped) |
| **QR Codes** | ✅ (Global) | ❌ | ✅ (Scoped) |
| **Addresses** | ✅ (Global) | ✅ (Own) | Admin/Manager: full; Operator: read-only |
| **Institution Bank Accounts** | ✅ (Admin/Super Admin) | ❌ | Supplier Admin (full); Manager/Operator: 403 |
| **Institution Entities** | ✅ (Admin/Super Admin) | ❌ | Supplier Admin (full); Manager/Operator: 403 |
| **Institutions** | ✅ (Global, Admin/Super Admin create/edit/delete) | ❌ | ✅ (Own, read-only) |

### User-Scoped APIs

| API | Employee | Customer | Supplier |
|-----|----------|---------|----------|
| **Subscriptions** | ✅ (Global) | ✅ (Own) | ❌ |
| **Payment Methods** | ✅ (Global) | ✅ (Own) | ❌ |
| **Plate Selection** | ✅ | ✅ | ❌ |

---

## Permission Dependency Functions

The following dependency functions are used to enforce these permissions:

- `get_current_user()`: Base authentication, returns user with `role_type`, `institution_id`, `role_name`
- `get_employee_user()`: Verifies `role_type == "Employee"` (for system configuration APIs)
- `get_client_user()`: Verifies `role_type == "Customer"` (for customer-only operations)
- `get_client_or_employee_user()`: Verifies `role_type in ["Customer", "Employee"]` (for shared access)
- `get_super_admin_user()`: Verifies `role_type == "Employee" AND role_name == "Super Admin"` (for approval operations)
- `get_admin_user()`: Verifies `role_type == "Employee" AND role_name in ["Admin", "Super Admin"]` (for discretionary view, institution create/update/delete)

**Supplier role checks** (from `app/security/field_policies.py`): These are called inside routes after `get_current_user()` to restrict by role:
- `ensure_operator_cannot_create_users(current_user)` — POST /users: Operator (Employee or Supplier) 403
- `ensure_supplier_can_create_edit_users(current_user)` — POST/PUT users (Supplier): Admin + Manager only; Operator 403
- `ensure_can_assign_role_name(actor_role_type, actor_role_name, target_role_type, target_role_name)` — Create/update user when role_name is set: Super Admin only by Super Admin; Admin only by Admin/Super Admin; Manager/Operator only by Admin/Super Admin/Manager
- `ensure_can_edit_user(actor_role_type, actor_role_name, target_role_type, target_role_name)` — PUT/DELETE users and password reset: Manager cannot edit Admin or Super Admin; Admin cannot edit Super Admin
- `ensure_supplier_can_reset_user_password(current_user)` — PUT `/users/{id}/password`: Admin + Manager only; Operator 403
- `ensure_supplier_can_create_edit_addresses(current_user)` — POST/PUT/DELETE addresses: Admin + Manager only; Operator 403
- `ensure_can_access_institution_bank_and_entities(current_user)` — Institution bank accounts and institution entities: Supplier Admin and Employee Admin/Super Admin can access; Supplier Manager/Operator and Employee Manager/Operator 403

## Scoping System

Access control is enforced through a centralized scoping system. See [SCOPING_SYSTEM.md](../SCOPING_SYSTEM.md) (internal doc) for detailed documentation.

### InstitutionScope

Applied via `InstitutionScope` service, which restricts Suppliers to their `institution_id` while allowing Employees global access.

**Usage**: For institution-scoped resources (restaurants, products, plates, QR codes, etc.)

**Behavior**:
- **Employees**: Global access (can see all institutions)
- **Suppliers**: Scoped to their `institution_id` only
- **Customers**: Not typically used (customers use UserScope instead)

### UserScope

Applied via `UserScope` service, which restricts Customers to their own `user_id` while allowing Suppliers to access users within their institution and Employees global access.

**Usage**: For user-scoped resources (user records, addresses, etc.)

**Behavior**:
- **Employees**: Global access (can see all users)
- **Suppliers**: Can access users within their institution (requires database validation)
- **Customers**: Can only access their own `user_id`

**Special Address Logic**:
- **Customers**: Auto-set `user_id` from `current_user` on creation; can only manage addresses where `user_id == their own user_id`
- **Suppliers**: Can assign `user_id` to any user within their institution; validated via `enforce_user_assignment()`
- **Employees**: Global access

**Implementation**: See `app/security/scoping.py` for the full `UserScope` implementation.

---

## Notes

- **Institution Scoping**: Suppliers are automatically scoped to their `institution_id` for all institution-scoped APIs. Employees bypass this restriction.
- **User Scoping**: Customers are automatically scoped to their own `user_id` for user-scoped APIs (Users, Addresses). Employees can access all users.
- **Supplier role_name**: For Supplier users, `role_name` (Admin, Manager, Operator) further restricts access. APIs that enforce this: Users (create/edit/reset password), Addresses (create/edit/delete). Institution Bank Accounts and Institution Entities require **Supplier Admin** or **Employee Admin/Super Admin** (Supplier Manager/Operator and Employee Manager/Operator: 403).
- **Role assignment rules (user management)**:
  - **Super Admin**: Only Super Admin (Employee) can assign Super Admin to another user.
  - **Admin**: Only Admin or Super Admin can assign Admin.
  - **Manager**: Only Admin, Super Admin, or Manager can assign Manager.
  - **Operator**: Only Admin, Super Admin, or Manager can assign Operator.
  - **Operator** (Employee or Supplier): Cannot create or update other users (including role assignments).
- **Editing hierarchy (prevents downgrades)**:
  - **Manager** cannot edit (update, password reset, or delete) **Admin** or **Super Admin** (403 Forbidden).
  - **Admin** cannot edit (update, password reset, or delete) **Super Admin** (403 Forbidden).
- **Institution Bank Accounts and Institution Entities**: **Supplier Admin** and **Employee Admin/Super Admin** can access (GET, POST, PUT, DELETE). **Supplier Manager**, **Supplier Operator**, **Employee Manager/Operator**, and **Customers** receive 403 on all endpoints.
- **Institution Creation and Management**: Only **Employee Admin** and **Super Admin** can create, update, or delete institutions. Suppliers, Employee Manager, and Employee Operator are read-only (GET only) for institutions.
- **Plate Browsing**: Customers can GET all plates (no scoping) to browse available meals for booking. They use the Plate Selection API to actually book plates.
- **Super Admin**: Super Admin is NOT a separate role type. Super Admins have `role_type='Employee'` (from `role_type_enum`) and `role_name='Super Admin'` (from `role_name_enum`).
- **Admin vs Super Admin (Employee)**: 
  - **Admin** (`role_type='Employee'`, `role_name='Admin'`): Can view and create discretionary requests, manage system configuration
  - **Super Admin** (`role_type='Employee'`, `role_name='Super Admin'`): Can do everything Admin can do, PLUS approve/reject discretionary requests
- **Archived Records**: Most GET endpoints support `is_archived` query parameter (defaults to `false` to exclude archived records).

---

*Last Updated: 2026-02-10*

