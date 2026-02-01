# API Permissions by Role Type

This document provides a comprehensive reference for API endpoint permissions organized by role type. Each API section includes a permission matrix showing which operations are allowed for each role.

## Role Type Definitions

- **Employee**: Vianda Enterprises staff with global access (includes Super Admin and Admin)
- **Supplier**: Restaurant/institution administrators, scoped to their `institution_id`
- **Customer**: End users accessing via iOS/Android apps

## Permission Legend

- ✅ = Allowed
- ❌ = Not Allowed (returns 403)
- 🔒 = Not Applicable (endpoint doesn't exist)

---

## 1. Plans API (`/api/v1/plans/`)

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

## 2. Credit Currency API (`/api/v1/credit-currencies/`)

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

## 3. Discretionary Credit API (`/api/v1/admin/discretionary/`)

### 3.1 Admin Discretionary Routes (`/admin/discretionary/`)

**Description**: Create and manage discretionary credit requests.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- Any Employee can create and manage discretionary requests
- Used for requesting discretionary credits for customers

**Dependencies**: `get_employee_user()` for all operations

### 3.2 Super Admin Discretionary Routes (`/super-admin/discretionary/`)

**Description**: Approve/reject discretionary credit requests.

| Role | GET Pending | GET All | Approve | Reject |
|------|-------------|---------|---------|--------|
| **Super Admin Employee** | ✅ | ✅ | ✅ | ✅ |
| **Admin Employee** | ✅ | ✅ | ❌ | ❌ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- GET operations (pending requests, request details, all requests) available to Admin and Super Admin Employees
- Approve/Reject operations restricted to Super Admin Employees only

**Dependencies**: `get_admin_user()` for GET, `get_super_admin_user()` for POST (approve/reject)

---

## 4. Fintech Link API (`/api/v1/fintech-link/`)

**Description**: Payment provider links for subscription plans.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅ | ❌ | ❌ | ❌ |
| **Supplier** | ❌ | ❌ | ❌ | ❌ |

**Notes**:
- GET operations available to Customers (for viewing payment links in mobile app) and Employees (for backoffice management)
- POST/PUT/DELETE restricted to Employees only (system configuration)
- Suppliers cannot access fintech link API

**Dependencies**: `get_client_or_employee_user()` for GET, `get_employee_user()` for POST/PUT/DELETE

**Endpoints**:
- `GET /fintech-link/` - List all fintech links
- `GET /fintech-link/{fintech_link_id}` - Get fintech link by ID
- `GET /fintech-link/by_plan/{plan_id}` - Get fintech links by plan
- `GET /fintech-link/enriched/` - List enriched fintech links
- `GET /fintech-link/enriched/{fintech_link_id}` - Get enriched fintech link by ID
- `POST /fintech-link/` - Create fintech link (Employee-only)
- `PUT /fintech-link/{fintech_link_id}` - Update fintech link (Employee-only)
- `DELETE /fintech-link/{fintech_link_id}` - Delete fintech link (Employee-only)

---

## 5. Users API (`/api/v1/users/`)

**Description**: User account management.

### 5.1 Self-Update Endpoints (`/api/v1/users/me`)

**⚠️ NEW PATTERN (December 2024)**: Use `/me` endpoints for all self-updates.

| Endpoint | Method | Purpose | All Roles |
|----------|--------|---------|-----------|
| `GET /api/v1/users/me` | GET | Get current user's profile (enriched) | ✅ |
| `PUT /api/v1/users/me` | PUT | Update current user's profile | ✅ |
| `PUT /api/v1/users/me/terminate` | PUT | Terminate current user's account | ✅ |
| `PUT /api/v1/users/me/employer` | PUT | Assign employer to current user | ✅ |

**Notes**:
- **All users** (Customers, Suppliers, Employees) MUST use `/me` endpoints for self-updates
- `user_id` is automatically extracted from JWT token (don't pass it)
- Returns enriched data (role_name, role_type, institution_name) for `GET /users/me`

### 5.2 Admin Endpoints (`/users/{user_id}`)

**⚠️ DEPRECATED for self-updates**: Use `/me` endpoints instead for self-operations.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Notes**:
- **Customers**: Cannot use `/{user_id}` endpoints (must use `/me` for self-updates)
- **Suppliers**: Can access users within their institution (institution scoping) - use for managing OTHER users
- **Employees**: Have global access (can see all users) - use for managing OTHER users
- **POST (Create)**: Restricted to Employees and Suppliers (admin user creation)
- **⚠️ Deprecation Warning**: Using `/{user_id}` for self-updates will log warnings and be removed in future versions

**Endpoints**:
- `GET /api/v1/users/{user_id}` - ⚠️ **DEPRECATED** for self-reads (use `GET /api/v1/users/me`)
- `PUT /api/v1/users/{user_id}` - ⚠️ **DEPRECATED** for self-updates (use `PUT /api/v1/users/me`)
- `GET /api/v1/users/enriched/{user_id}` - ⚠️ **DEPRECATED** for self-reads (use `GET /api/v1/users/me`)
- `DELETE /users/{user_id}` - Admin-only (delete other users)

**Dependencies**: `get_current_user()` with user scoping for Customers, institution scoping for Suppliers

**See Also**: `USER_SELF_UPDATE_PATTERN.md` for detailed migration guide

---

## 6. Restaurants API (`/api/v1/restaurants/`)

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

## 7. Products API (`/api/v1/products/`)

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

## 8. Plates API (`/api/v1/plates/`)

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

## 9. QR Codes API (`/api/v1/qr-codes/`)

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

## 10. Addresses API (`/api/v1/addresses/`)

**Description**: Address management for users and institutions.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ✅* | ✅* | ✅* | ✅* |
| **Supplier** | ✅* | ✅* | ✅* | ✅* |

**Notes**:
- **Customers**: Can GET, POST, PUT, DELETE only their own addresses (scoped by `user_id`)
- **Suppliers**: Can access addresses within their institution (institution scoping)
- **Employees**: Have global access

**Dependencies**: `get_current_user()` with user scoping for Customers, institution scoping for Suppliers

---

## 11. Institutions API (`/institutions/`)

**Description**: Institution (company/organization) management.

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Employee** | ✅ | ✅ | ✅ | ✅ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |
| **Supplier** | ✅* | ❌ | ✅* | ✅* |

**Notes**:
- **Suppliers**: Can GET, PUT, DELETE their own institution only (institution scoping)
- **Suppliers**: Cannot POST (create new institutions) - this is restricted to Employees only
- **Employees**: Have global access and can create new institutions
- **Customers**: Cannot access institution management API

**Dependencies**: `get_current_user()` with institution scoping. POST endpoint uses `get_employee_user()` to restrict creation to Employees only.

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

## 15. Payment Methods API (`/payment-methods/`)

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

| API | Employee | Customer | Supplier |
|-----|----------|---------|----------|
| **Users** | ✅ (Global) | ✅ (Own) | ✅ (Scoped) |
| **Restaurants** | ✅ (Global) | ❌ | ✅ (Scoped) |
| **Products** | ✅ (Global) | ❌ | ✅ (Scoped) |
| **Plates** | ✅ (Global) | ✅ (View All) | ✅ (Scoped) |
| **QR Codes** | ✅ (Global) | ❌ | ✅ (Scoped) |
| **Addresses** | ✅ (Global) | ✅ (Own) | ✅ (Scoped) |
| **Institutions** | ✅ (Global) | ❌ | ✅ (Own Only, No POST) |

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
- `get_admin_user()`: Verifies `role_type == "Employee" AND role_name in ["Admin", "Super Admin"]` (for view operations)

## Scoping System

Access control is enforced through a centralized scoping system. See [SCOPING_SYSTEM.md](./SCOPING_SYSTEM.md) for detailed documentation.

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
- **Institution Creation**: Only Employees can create new institutions. Suppliers can manage their existing institution but cannot create new ones.
- **Plate Browsing**: Customers can GET all plates (no scoping) to browse available meals for booking. They use the Plate Selection API to actually book plates.
- **Super Admin**: Super Admin is NOT a separate role type. Super Admins have `role_type='Employee'` and `name='Super Admin'`.
- **Archived Records**: Most GET endpoints support `is_archived` query parameter (defaults to `false` to exclude archived records).

---

*Last Updated: 2025-11-17*

