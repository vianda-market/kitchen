# Discretionary Request – One Recipient (Customer or Restaurant) and Customer Dropdown Filter

**Date**: February 2026  
**Context**: Create discretionary credit request for either a customer or a restaurant; customer dropdown limited to Customers.  
**Status**: Functional requirements for backend

---

## Situation

Discretionary credit requests are created for **either** a customer (user) **or** a restaurant, not both. The frontend now enforces this with a "Credit for" toggle (Customer | Restaurant) so only one recipient can be chosen. The customer dropdown in the create form should list only users with **role_type = Customer** (not Employees or Suppliers).

This document states the **functional requirements** the backend should satisfy. It does not prescribe implementation.

---

## Functional Requirements

### 1. Exactly one recipient (user_id XOR restaurant_id)

- For **create** discretionary request (e.g. **POST** **`/api/v1/admin/discretionary/requests/`** or equivalent), the request body **SHALL** contain **exactly one** of:
  - **`user_id`** (UUID): credit for a customer (user), or  
  - **`restaurant_id`** (UUID): credit for a restaurant.
- The backend **SHALL** reject requests that:
  - contain **both** `user_id` and `restaurant_id`, or  
  - contain **neither** (no `user_id` and no `restaurant_id`).
- Rejection **SHALL** use a clear error response (e.g. **400 Bad Request**) with a message that explains the rule (e.g. "Exactly one of user_id or restaurant_id must be provided, not both and not neither").
- The backend **SHALL** accept a request that contains exactly one of these two fields (and may ignore or reject the other if present).

### 2. Customer dropdown – filter by role_type (optional backend support)

- The frontend uses **GET** **`/api/v1/users/enriched/`** (or equivalent) to populate the "Customer" dropdown when creating a discretionary request.
- The frontend **SHALL** show only users with **role_type = Customer** in that dropdown (e.g. for discretionary credits to end-users, not to Employees or Suppliers).
- **Option A**: The backend **MAY** support an optional query parameter (e.g. **`role_type=Customer`**) on the users list endpoint so that the response contains only customers. If supported, the frontend can use it to avoid loading and filtering all users client-side.
- **Option B**: If the backend does not support such a filter, the frontend will filter the full user list client-side (e.g. by `role_type === 'Customer'`). The backend **SHALL** include **`role_type`** (or equivalent) in each user object in the users list/enriched response so the client can filter correctly.

No change to the API contract is strictly required for the dropdown if **Option B** is used; documenting **Option A** allows the backend to optimize later if desired.

---

## Out of scope

- How the backend validates or stores the chosen recipient (user vs restaurant).
- Other discretionary request fields (category, amount, reason, comment, etc.) or approval flows.
- Implementation details (DB constraints, application logic, etc.).

---

## References

- Frontend: Discretionary create form with "Credit for" toggle (Customer | Restaurant); customer dropdown filtered to `role_type === 'Customer'`.
- Existing docs: e.g. `docs/api/feedback_for_backend/DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md`, `docs/api/API_PERMISSIONS_BY_ROLE.md`.
