# Vianda Employer Benefits Program – Roadmap

**Status**: Roadmap (foundation in place)  
**Last Updated**: 2026-02  
**Purpose**: Enable Employer institutions to offer Vianda subscriptions as benefits and onboard their employees via a dedicated path, distinct from the standard B2C customer subscription flow.

---

## 1. Context and goals

- **Employer institutions**: Companies that participate in the benefits program get their own institution with `institution_type = 'Employer'`. The Employer user (Customer, role_name Employer) represents that company.
- **Benefits-program employees**: Employees who join through their employer are onboarded **under the employer’s institution** (same `institution_id`), so they are in scope for that institution. No need to derive “employees” via `employer_info` + `user_info.employer_id` for listing; institution-scoped APIs naturally include them.
- **Standard B2C path**: Customers who subscribe on their own (e.g. via kitchen-mobile) are assigned to the shared “Vianda Customers” institution (`institution_type = 'Customer'`) and use the normal signup/subscription flow.
- **This roadmap**: Define the **different route** for benefits-program onboarding so that new customers get the correct `institution_id` (employer’s institution) and, later, any institution-scoped behavior (e.g. subscription list, reporting) works without extra employer-specific logic.

---

## 2. What is in place (foundation)

- **`institution_type_enum`**: Extended with `'Employer'` (in addition to Employee, Customer, Supplier). Employer institutions are distinct from Supplier (restaurant) and Customer (e.g. Vianda Customers pool).
- **User–institution validation**: Customer users may be assigned to institutions with `institution_type = 'Customer'` or `'Employer'`. See `ensure_institution_type_matches_role_type` in `app/security/field_policies.py`.
- **Address types**: Customer address types (Customer Home, Customer Billing, Customer Employer) are allowed for both Customer and Employer institutions; entity/restaurant types remain Supplier or Employee only.
- **API/schemas**: `RoleType` in Python includes `EMPLOYER` for institution_type; DTOs and schemas support creating/returning institutions with `institution_type = 'Employer'`.

---

## 3. Roadmap: benefits-program onboarding (different route)

### 3.1 Problem

Today, B2C signup and B2B user creation assign customers as follows:

- **B2C**: Customer Comensal → backend assigns “Vianda Customers” institution (and does not send institution from client).
- **B2B (Employee creates user)**: Admin chooses institution; for Customer + Comensal, backend can force Vianda Customers.

There is **no dedicated path** where:

- An Employer (or an Employee on their behalf) creates/onboards a **benefits-program employee** (Customer + Comensal) and the backend sets **`institution_id` = the employer’s institution** (the one with `institution_type = 'Employer'`).

Without that, benefits employees would end up in Vianda Customers or the wrong institution, and institution-scoped features (e.g. “list subscriptions for my institution”) would not group them with the employer.

### 3.2 Intended behavior (to implement later)

- **Employer institution creation**: When a Customer with role_name Employer (or an Employee) creates an institution for a benefits-program company, set **`institution_type = 'Employer'`** (not `'Customer'`). This may be a new flow or an extension of existing institution create (e.g. when “benefits program” is selected).
- **Benefits-program registration route**: A **different route** (or same POST with a clear “benefits” context) for creating/registering a Customer user that:
  - Accepts or derives the **employer’s institution_id** (e.g. from token, query, or body when the caller is the Employer or an Employee acting for that institution).
  - Sets **`institution_id` = that employer institution** for the new user.
  - Optionally sets **`employer_id`** if the employer record is known (for reporting/UX).
  - Ensures the new user is Customer + Comensal (or the chosen role for benefits employees).
- **Authorization**: Only callers who are allowed to act for that Employer institution (Employer user, or Employee with scope over that institution) may create users in it. Enforce in the same way as other user-creation scoping.
- **No change to standard B2C path**: The existing B2C client subscription/signup flow continues to assign Vianda Customers and does not use this route.

### 3.3 Subscription list and institution scope (later)

- Once benefits employees are in the employer’s institution, **subscription list** (and other institution-scoped APIs) can treat “users in my institution” as the scope for that Employer.
- **Vianda Customers** (pool of non-benefits Comensals): keep **self-only** for subscription list (each user sees only their own).
- **Employer institutions**: when the subscription list is extended to be institution-scoped for Customer/Employer institutions, it will “just work” because all benefits employees share the same `institution_id`. No need for employer_id-based filtering in that list.

---

## 4. Implementation checklist (for later)

- [ ] **Institution create**: When creating an institution for a benefits-program company, set `institution_type = 'Employer'` (UI/flow to select “Employer” or “Benefits program”).
- [ ] **Benefits-program registration endpoint (or flow)**:
  - [ ] New route or existing POST with “benefits” context (e.g. `POST /api/v1/institutions/{institution_id}/users/` or `POST /api/v1/users/` with `institution_id` + `benefits_program=true` or equivalent).
  - [ ] Resolve employer institution (must have `institution_type = 'Employer'`); enforce caller can create users in that institution.
  - [ ] Set `institution_id` to employer’s institution for the new user; assign role Customer + Comensal (or as specified).
  - [ ] Optionally set `employer_id` if employer_info is linked to that institution.
- [ ] **Documentation**: Document the benefits-program registration contract (who can call, required parameters, `institution_id` assignment) in `docs/api/b2b_client/` or `docs/api/internal/`.
- [ ] **Subscription list (optional follow-up)**: For Customer users in institutions with `institution_type = 'Employer'`, scope GET /api/v1/subscriptions/ by institution (all users in that institution). For Vianda Customers (or `institution_type = 'Customer'`), keep self-only. Document in API docs.

---

## 5. References

- **Institution type and roles**: `app/config/enums/role_types.py` (RoleType.EMPLOYER), `app/security/field_policies.py` (ensure_institution_type_matches_role_type, ensure_address_type_matches_institution_type).
- **Customer Comensal institution assignment**: `docs/api/b2b_client/feedback_from_client/CUSTOMER_COMENSAL_INSTITUTION.md`.
- **B2C deployment and flows**: [B2C_DEPLOYMENT_ROADMAP.md](B2C_DEPLOYMENT_ROADMAP.md).
- **User–market and scoping**: [USER_MARKET_ASSIGNMENT_DESIGN.md](USER_MARKET_ASSIGNMENT_DESIGN.md).
