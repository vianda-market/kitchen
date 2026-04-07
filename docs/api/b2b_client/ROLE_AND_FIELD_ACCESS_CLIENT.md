# Role and Field Access – Client Integration

This guide tells client apps (web backoffice, mobile, or other agents) how to integrate with **route-level** and **field-level** access so that users only see and submit allowed actions and values.

## Who can call what (route-level)

| API area | Employee | Supplier | Customer |
|----------|----------|----------|----------|
| **Markets** (`/api/v1/markets/`, `/enriched/`) | Yes | **403** | **403** |
| **Plans** (GET) | Yes | **403** | Yes |
| **Payment methods** (client), Fintech link (client) | Yes | **403** | Yes |
| **Addresses** (create, update, delete, list, get) | Yes | **Admin only** for create/update/delete; all can GET | Yes (own only) |
| **Users** (create, update, delete, list, get) | Yes | **Admin, Manager** for create/update/delete; all can GET | **403** on create |
| **Admin discretionary** | Yes | **403** | **403** |
| **Super Admin discretionary** (approve/reject) | Super Admin only | **403** | **403** |

- **Suppliers** get **403** on Markets and Payment methods (and Plans write). Do not show these menus or call these endpoints when the user is a Supplier.
- **Customers** get **403** on user creation and on admin-only endpoints. The client app (e.g. app-store app) typically only exposes customer flows; user creation is done by Employees or Suppliers in the backoffice.

## Field-level rules (shared APIs)

### Addresses API

When the user is a **Supplier**:

- **Create/update/delete**: Only **Supplier Admin** can create, update, or delete addresses. Supplier Manager and Operator get **403** with detail "Only Supplier Admin can create or edit addresses. Supplier Manager and Operator have read-only access to addresses."
- **Get/list**: All Supplier roles can GET and list addresses within their institution scope.
- **Allowed `address_type` values** (when Admin): `Restaurant`, `Entity Billing`, `Entity Address` only.
- **Do not send**: `Customer Home`, `Customer Billing`, `Customer Employer` on `POST /api/v1/addresses/` or `PUT /api/v1/addresses/{id}`.
- **Exception**: When adding an address to an employer (`POST /api/v1/employers/{employer_id}/addresses`), the backend may include `Customer Employer`; the Supplier is allowed to submit that in this context.

When the user is a **Customer**:

- Typically only their own addresses (scope). No extra `address_type` restriction at this time.

When the user is an **Employee**:

- Any `address_type` is allowed.

**If you send disallowed types as Supplier**: the API returns **403** with a body like:

```json
{
  "detail": "Suppliers may only use address types: Restaurant, Entity Billing, Entity Address. Disallowed: Customer Home."
}
```

**Client recommendation**: For Supplier users, only show or allow selecting address types: Restaurant, Entity Billing, Entity Address (and, on the employer-address screen, the employer address type as needed).

---

### Users API

When the user is a **Supplier**:

- **Create/update/delete**: Only **Supplier Admin** and **Supplier Manager** can create, update, or delete users. Supplier Operator gets **403** with detail "Only Supplier Admin and Manager can create or edit users. Supplier Operator has read-only access to users within their institution."
- **Get/list**: All Supplier roles can GET and list users within their institution scope.
- **Institution on create**: Suppliers may only create users for **their own institution**. Sending a different `institution_id` returns **403** with detail "Suppliers can only add users to their own institution. The institution_id must match your institution."
- **`city_id` on create**: Employee and Supplier users get **Global city** by default when `city_id` is not provided. Customer (Comensal) requires a real city; do not use the Global city for B2C customers.
- **Allowed `role_type` on create only** (when Admin or Manager): `Supplier` only (cannot assign Employee or Customer). **`role_type` is immutable** – it cannot be changed after user creation. Sending `role_type` on `PUT /users/{id}` returns **400** with detail "role_type is immutable and cannot be changed after user creation."
- **`institution_id` is immutable** – set on create only. Sending `institution_id` on `PUT /users/{id}` or `PUT /users/me` returns **400** with detail "institution_id is immutable and cannot be changed after user creation."
- **Employer**: Only **Customer** users have an employer. Supplier and Employee users must not be sent `employer_id` on create or update (returns **400**). In API responses, `employer_id` is always **null** for Supplier and Employee. `PUT /users/me/employer` is allowed only for Customers; Supplier and Employee get **403**.
- **Allowed `role_name` on create/update**: `Admin`, `Manager`, `Operator` only (cannot assign Super Admin or Comensal).
- **To populate Role dropdown**: Use `GET /api/v1/enums/roles/assignable` – returns filtered values for cascading dropdowns.

When the user is an **Employee** (admin):

- Any `role_type` and `role_name` is allowed.
- To populate Role dropdown: Use `GET /api/v1/enums/roles/assignable` or `GET /api/v1/enums/` (includes role_type, role_name).
- **`city_id` on create:** Employee and Supplier users get the Global city by default when `city_id` is not provided. Customer (Comensal) created via B2B requires `city_id` (must not be Global).

When the user is a **Customer**:

- Cannot create users; `POST /api/v1/users/` returns **403** (`"Forbidden: customers cannot create users"`).
- Cannot read role enums; `GET /api/v1/enums/` omits role_type and role_name.

**If you send `role_type: Employee` or `role_type: Customer` as Supplier**: the API returns **403** with a body like:

```json
{
  "detail": "Suppliers cannot create or update users to Employee or Customer. Allowed role types: Supplier only."
}
```

**Client recommendation**: When the current user is a Supplier, use `GET /api/v1/enums/roles/assignable` to populate the Role dropdown; only offer Supplier for role_type and Admin, Manager, Operator for role_name (cascading by selected role_type).

---

### Institution API

Institution updates (`PUT /api/v1/institutions/{id}`) require **Internal Admin or Super Admin**.

**Institution type restrictions**:
- **Internal** and **Customer** types: Only **Super Admin** can create or update these. Admin attempting this gets **403**.
- **Employer** type: Included in assignable types for Admin and Super Admin.

**Client recommendation**: For institution create/edit, use `GET /api/v1/enums/institution-types/assignable` for the institution type dropdown.

### Supplier Terms API

Supplier-specific deal terms (`no_show_discount`, `payment_frequency`, invoice compliance) are managed via dedicated endpoints:

- `GET /api/v1/supplier-terms/{institution_id}` — Supplier Admin (own, read-only) / Internal
- `PUT /api/v1/supplier-terms/{institution_id}` — Internal Manager, Global Manager, Admin, Super Admin only

When the user is a **Supplier**:
- **Cannot** edit supplier terms. PUT returns **403** with detail "Only Internal users with Manager, Global Manager, Admin, or Super Admin role can edit supplier terms."
- Can read their own terms via GET.

`no_show_discount` is **no longer on the institution payload**. It is now on `supplier_terms`. See [SUPPLIER_TERMS_B2B.md](./SUPPLIER_TERMS_B2B.md) for full API contract.

**Client recommendation**: Show a "Supplier Terms" tab on institution detail (Supplier type only). For Suppliers, show terms as read-only. After creating a Supplier institution, call `PUT /supplier-terms/{id}` to configure terms.

---

## Error handling

- **403** on an endpoint: the role is not allowed to call that route. Hide or disable that flow for that role.
- **403** with `detail` mentioning **"Suppliers may only use address types"** or **"Disallowed: ..."**: the payload contained a disallowed `address_type`. Show the message to the user and restrict the form to allowed types.
- **403** with `detail` mentioning **"Suppliers cannot create or update users to Employee or Customer"**: the payload had `role_type: Employee` or `role_type: Customer` for a Supplier. Restrict the role dropdown to Supplier only when the actor is a Supplier.
- **403** with `detail` mentioning **"Suppliers cannot assign Super Admin or Comensal"**: the payload had `role_name: Super Admin` or `role_name: Comensal` for a Supplier. Restrict role_name dropdown to Admin, Manager, Operator.
- **403** with `detail` mentioning **"Only Supplier Admin can create or edit addresses"**: the user is Supplier Manager or Operator. Hide or disable address create/edit/delete buttons for these roles.
- **403** with `detail` mentioning **"Only Supplier Admin and Manager can create or edit users"**: the user is Supplier Operator. Hide or disable user create/edit/delete buttons for Operator.
- **400** with `detail` **"role_type is immutable and cannot be changed after user creation"**: the client sent `role_type` on a user update. Do not include `role_type` in edit forms; it is set on create only.
- **400** with `detail` **"institution_id is immutable and cannot be changed after user creation"**: the client sent `institution_id` on a user update. Do not include institution in edit forms; it is set on create only.
- **403** with `detail` **"Suppliers can only add users to their own institution"**: a Supplier sent `institution_id` different from their own when creating a user. Only allow the Supplier's institution in the create form.
- **403** with `detail` **"Only Super Admin can create Employee or Customer-type institutions."** or **"Only Super Admin can set institution_type to Employee or Customer."**: an Admin (non-Super Admin) attempted to create or update an institution with `institution_type: "Employee"` or `"Customer"`. Use `GET /api/v1/enums/institution-types/assignable` so Admin does not see Employee or Customer in the dropdown.
- **400** with `detail` **"Employer is not applicable to Supplier or Employee users"**: the client sent `employer_id` when creating or updating a user with `role_type` Supplier or Employee. Omit employer for non-Customer users; only show Employer field for Customers.
- **403** on `PUT /users/me/employer` for Supplier or Employee: only Customer users can assign an employer to themselves.

## Quick reference

| Actor | Address types allowed | User role_types allowed (create/update) | User role_names allowed |
|-------|------------------------|----------------------------------------|-------------------------|
| **Supplier** | Restaurant, Entity Billing, Entity Address (+ Customer Employer on employer address) | Supplier only | Admin, Manager, Operator |
| **Customer** | No extra restriction | Cannot create users | N/A |
| **Employee** | All | All | All |

## Postman / automated tests

Use the **Role and Field Access** collection (`docs/postman/collections/ROLE_AND_FIELD_ACCESS.postman_collection.json`) to verify:

- Login as Supplier → POST address with `address_type: ["Restaurant"]` → 201; with `["Customer Home"]` → 403.
- Login as Supplier → POST user with `role_type: "Supplier"` → 201; with `role_type: "Employee"` or `role_type: "Customer"` → 403.
- Login as Customer → POST user → 403.

Set collection variables `supplierUsername` and `supplierPassword` if you have a Supplier user in your DB. Customer: `customer` / `customer_password`. See `docs/postman/README.md` for the collection list.
