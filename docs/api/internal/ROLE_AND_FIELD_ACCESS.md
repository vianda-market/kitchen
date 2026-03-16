# Role and Field Access

This document describes the two-layer access model: **route-level** (who can call an endpoint) and **field-level** (which values are allowed in the payload for shared APIs).

## Route-level access

Route access is enforced by dependencies in `app/auth/dependencies.py`. Each route (or router) uses one dependency that allows only certain `role_type` (and optionally `role_name`).

| Route group | Dependency | Effect |
|-------------|------------|--------|
| Markets (`/api/v1/markets/`, `/enriched/`) GET (list, get by id) | `get_current_user` | Any authenticated user (Employee, Supplier, Customer) – for country dropdown when creating addresses. Public endpoint moved to Leads: `GET /api/v1/leads/markets` (no auth). |
| Markets POST, PUT, DELETE | `get_employee_user` | Employee only |
| Credit currencies, National holidays, Fintech admin | `get_employee_user` | Employee only |
| Plans (GET) | `get_client_or_employee_user` | Employee or Customer; Supplier gets 403 |
| Payment methods (client), Fintech link (client) | `get_employee_or_customer_user` | Employee or Customer; Supplier gets 403 |
| Admin discretionary | `get_employee_user` | Employee only |
| Super Admin discretionary (approve/reject) | `get_super_admin_user` | Employee with role_name Super Admin only |
| Addresses, Users | `get_current_user` | Any authenticated; scope and field rules apply. **Supplier role_name** further restricts: Address create/update/delete = Admin only; User create/update/delete = Admin, Manager only. All Supplier roles can GET within institution scope. |

Adding a new route: choose the dependency that matches the intended audience. Blocking a role (e.g. Supplier) is done by using a dependency that does not include that role.

## Field-level rules

Field rules apply only to **shared APIs** where multiple role types can call the same endpoint but are restricted in which values they can send. They live in `app/security/field_policies.py`.

### 1. Address create/update/delete (Supplier role_name)

- **Supplier Admin**: May create, update, and delete addresses (subject to address_type rules below).
- **Supplier Manager, Operator**: Cannot create, update, or delete addresses. Returns **403** with detail "Only Supplier Admin can create or edit addresses. Supplier Manager and Operator have read-only access to addresses."

**Call sites**: `app/routes/address.py` (create, update, delete), `app/routes/employer.py` (add_employer_address, create_employer), `app/services/route_factory.py` (payment_method creation with address_data). Uses `ensure_supplier_can_create_edit_addresses()`.

### 2. Address address_type

- **Supplier** (Admin only, per above): May only send `address_type` values: **Restaurant**, **Entity Billing**, **Entity Address**. Sending Customer Home, Customer Billing, or Customer Employer returns **403** with detail "Suppliers may only use address types: Restaurant, Entity Billing, Entity Address. Disallowed: ...".
- **Employer address** (`POST /api/v1/employers/{id}/addresses`): When adding an address to an employer, **Customer Employer** is also allowed for Suppliers.
- **Customer**: No restriction (optional future: restrict to Customer Home, Customer Billing, Customer Employer).
- **Employee**: No restriction.

**Call sites**: `app/routes/address.py` (create, update), `app/routes/employer.py` (add_employer_address).

### 3. Supplier user creation – institution scope

- **Supplier**: When creating a user (`POST /users/`), `institution_id` must equal the Supplier's own `institution_id`. Otherwise **403** with detail "Suppliers can only add users to their own institution. The institution_id must match your institution."

**Call sites**: `app/routes/user.py` (create). Uses `ensure_supplier_user_institution_only()`.

### 4. User create/update/delete (Supplier role_name)

- **Supplier Admin, Manager**: May create, update, and delete users (subject to role_type and role_name rules below).
- **Supplier Operator**: Cannot create, update, or delete users. Returns **403** with detail "Only Supplier Admin and Manager can create or edit users. Supplier Operator has read-only access to users within their institution."

**Call sites**: `app/routes/user.py` (create, update, delete). Uses `ensure_supplier_can_create_edit_users()`.

### 5. User role_type and institution_id (create only, immutable)

- **role_type is immutable**: Set on user creation only. Cannot be changed on update. Sending `role_type` on `PUT /users/{id}` returns **400** with detail "role_type is immutable and cannot be changed after user creation."
- **institution_id is immutable**: Set on user creation only. Cannot be changed on update. Sending `institution_id` on `PUT /users/{id}` or `PUT /users/me` returns **400** with detail "institution_id is immutable and cannot be changed after user creation."
- **Supplier** (on create): May only create a user with `role_type` **Supplier** (cannot assign Employee or Customer). Sending `role_type: Employee` or `role_type: Customer` returns **403** with detail "Suppliers cannot create or update users to Employee or Customer. Allowed role types: Supplier only.".
- **Employee**: May set any `role_type`.
- **Customer**: Cannot create users (route returns 403 before field check).

**Call sites**: `app/routes/user.py` (create, update when role_type is in payload).

### 6. User role_name on create/update

- **Supplier**: May only assign `role_name` **Admin**, **Manager**, or **Operator** (cannot assign Super Admin or Comensal). Sending `role_name: Super Admin` returns **403** with detail "Suppliers cannot assign Super Admin or Comensal. Allowed role names: Admin, Manager, Operator.".
- **Employee**: May set any `role_name`.
- **Customer**: Cannot create users (route returns 403 before field check).

**Call sites**: `app/routes/user.py` (create, update when role_name is in payload).

## How to add a new rule

- **New route / change who can call**: Change or add the dependency on that route (e.g. switch to `get_employee_user` to block Supplier).
- **New field rule**: Add a function in `app/security/field_policies.py` (e.g. `ensure_xyz_allowed(...)`) and call it from the route handler that builds the create/update payload, before calling the service layer.

## Related docs

- ROLE_BASED_ACCESS_CONTROL.md – scope matrix, /me pattern
- api/client/API_PERMISSIONS_BY_ROLE.md – permission matrix by endpoint
- api/client/ROLE_AND_FIELD_ACCESS_CLIENT.md – client integration (payload rules, 403 handling)
