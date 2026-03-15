# Role and API Area Access – Backend Feedback

This document informs the backend team of the **API area types** used by the client (vianda-platform frontend) and the expected **403** behavior so permissions can be aligned. It also requests a small change to the roles API for field-level compliance.

## 1. API area types

The client groups APIs into three areas based on who may access them:

| Area | Who can access | Description |
|------|----------------|-------------|
| **Core** | Employees only (Super Admin for some endpoints) | Platform-wide configuration. Suppliers must receive **403** on all Core endpoints. |
| **Supplier** | Employees and Suppliers (institution-scoped for Suppliers) | Institution, Restaurants, Products, Plates, QR Codes, etc. (current “Supplier” menu). |
| **Customer** | Employees and Customers (not Suppliers) | Customer-facing data. **Suppliers must receive 403** on all Customer-area endpoints. |

### Core area (Suppliers → 403)

- Markets: `/api/v1/markets/`, `/api/v1/markets/enriched/`
- Credit Currencies: `/api/v1/credit-currencies/`, enriched
- Discretionary: `/api/v1/admin/discretionary/requests/`, `/api/v1/super-admin/discretionary/*`
- Fintech Links (Core): `/api/v1/fintech-links/`, enriched
- National Holidays: `/api/v1/national-holidays/`
- Plans: `/api/v1/plans/`, `/api/v1/plans/enriched/`

### Customer area (Suppliers → 403)

- Employers: `/api/v1/employers/`, `/api/v1/employers/enriched/`
- Fintech Link Assignments: endpoint used for the “Fintech Link Assignments” page (e.g. `/api/v1/fintech-link-assignment/enriched/` or equivalent)
- Payment Methods: `/api/v1/payment-methods/`, `/api/v1/payment-methods/enriched/`
- Subscriptions: `/api/v1/subscriptions/`, `/api/v1/subscriptions/enriched/`

## 2. Explicit 403 expectations for Suppliers

**Request:** For callers with role type **Supplier**, the backend should return **403 Forbidden** on:

1. **All Customer-area endpoints** (list and write):
   - GET/POST/PUT/DELETE on Employers (base and enriched)
   - GET (and any write) on Fintech Link Assignments (the endpoint that serves the Fintech Link Assignments page)
   - GET/POST/PUT/DELETE on Payment Methods (base and enriched)
   - GET/POST/PUT/DELETE on Subscriptions (base and enriched)

2. **All Core-area endpoints** (as already documented in ROLE_AND_FIELD_ACCESS_CLIENT.md):
   - Markets, Credit Currencies, Discretionary, Fintech Links (Core), National Holidays, Plans

The client already hides the Customers section from Suppliers and shows “Access denied” when it receives 403. Confirming or implementing 403 for Supplier on the Customer-area endpoints above will ensure correct behavior when a Supplier opens those URLs directly.

## 3. Roles API – expose `role_type` per role

**Request:** So the client can restrict the **User** create/edit form for Suppliers (they may only assign role_type **Supplier** or **Employee**, not **Customer**), the roles list used for the dropdown must expose a **role_type** (or equivalent) per role.

- **Endpoint:** `GET /api/v1/roles/` (or the endpoint used for the user form role dropdown)
- **Ask:** Include a field such as `role_type` with values `Employee`, `Supplier`, or `Customer` for each role.
- **Use case:** When the current user is a Supplier, the client will filter the dropdown to only roles where `role_type` is `Supplier` or `Employee`, and will not offer Customer roles.

If this field already exists under another name, please share the field name so the client can use it.

## 4. Reference

- **Route-level and field-level rules:** [docs/backend/ROLE_AND_FIELD_ACCESS_CLIENT.md](../ROLE_AND_FIELD_ACCESS_CLIENT.md) — who can call what, address_type and user role_type restrictions, and error handling.
