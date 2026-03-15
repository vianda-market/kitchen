# Institutions List – Supplier Scoping Debug

**Issue:** When a Supplier user creates an Address (modal), the **Institution** dropdown shows all institutions instead of only the institution assigned to the logged-in user.

## What the frontend does

- **Endpoint:** `GET /api/v1/institutions/`
- **When:** The Address create/edit modal loads the Institution dropdown from this endpoint (and other forms use the same endpoint for institution selection).
- **Request:** No query parameters; auth via Bearer token (JWT with `institution_id`, `role_type`, etc.).
- **Usage:** Response is mapped to dropdown options using `name` (label) and `institution_id` (value).

## Expected behavior (per API_PERMISSIONS_BY_ROLE.md)

- **Suppliers:** Can GET their **own institution only** (scoped to their `institution_id`).
- So for a Supplier, `GET /api/v1/institutions/` should return **one** institution (the one in the user’s JWT), not the full list.

## Observed behavior

- User logged in as **Supplier**, opened **Create Address** modal, clicked **Institution** dropdown.
- Dropdown showed **all** institutions instead of only the Supplier’s institution.
- User had **cleared browser cache** and restarted the app, so the response is from the backend (no stale client cache).

## Request for backend

Please verify that the **list** endpoint `GET /api/v1/institutions/` applies **institution scoping** for callers with `role_type === "Supplier"` (and, if applicable, Customer), so that the response contains only the institution matching the authenticated user’s `institution_id`. If a different endpoint is intended for scoped listing (e.g. an enriched or “my institution” variant), share the path and we can point the dropdown there.

**Reference:** [API_PERMISSIONS_BY_ROLE.md](../../shared_client/API_PERMISSIONS_BY_ROLE.md) – Section 11 (Institutions API).
