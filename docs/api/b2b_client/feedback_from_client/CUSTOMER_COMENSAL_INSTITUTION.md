# Customer Comensal – Institution Assignment (Backend Responsibility)

**Date**: February 2026  
**Context**: Creating a user with Role Type = Customer and Role = Comensal; institution is fixed (Vianda Customers).  
**Status**: B2B client behavior and backend contract

---

## Situation

When registering a **Customer** user with role **Comensal**, there is exactly one valid institution: **Vianda Customers**. The B2B client does not send or resolve institution data for this case; the **backend** assigns Vianda Customers from `role_type` and `role_name` alone.

---

## B2B Client Behavior (Implemented)

1. **Create User form**
   - When **Role type** = Customer and **Role** = Comensal, the **Institution** field is **hidden** (no user input, no institution list loaded for this flow).

2. **Payload**
   - On create, when `role_type === "Customer"` and `role_name === "Comensal"`, the client **omits** `institution_id` from the request body. The backend **MUST** assign the Vianda Customers institution from these two attributes.

3. **Edit**
   - Institution remains disabled on edit (existing behavior); Comensal users are not re-assigned to a different institution from the UI.

---

## Backend Contract (Required)

- On **POST /api/v1/users/** (and, if applicable, **PUT** when role is set to Customer + Comensal):
  - If `role_type === "Customer"` and `role_name === "Comensal"`:
    - **Ignore** any submitted `institution_id` (if present).
    - **Set** `institution_id` server-side to the single allowed institution (Vianda Customers), without client involvement.
  - The client does **not** fetch or send institution data for Customer Comensal; the backend is the single source of truth for this assignment.

---

## Backend implementation note

- The backend determines assignment from `role_type` and `role_name` only (no `role_info` table lookup; roles are enums).
- **Do not** send a special key from the client; **omitting** `institution_id` is the contract. A client-sent key would be redundant because the backend already has the role and must validate it for security.
- For **POST /api/v1/users/**, `institution_id` is optional in the schema when creating Customer + Comensal; when omitted, the service sets `institution_id` to Vianda Customers (seeded constant) before scope constraints.

---

## References

- User form: `userFormConfig` (role_type, role_name, institution_id); institution_id is hidden and omitted for Customer + Comensal in Users page.
