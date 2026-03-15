# Search API for Discretionary Recipients – Backend Requirements

**Date**: February 2026  
**Context**: Discretionary request modal needs to search for Customer (user) or Restaurant by name, username, or email (users) or by name (restaurants). Frontend uses a search API with pagination; it does **not** store the full list.  
**Status**: Functional requirements for backend (no prescribed implementation)

---

## Situation

The frontend discretionary request form includes a **search-by-select** control for choosing the recipient (Customer or Restaurant). The user selects a search type (e.g. Name, Username, or Email for customers; Name for restaurants), types a query, and sees a paginated list of results. The frontend will **not** load or store the full list; it will request **one page at a time** and only keep the current page of results and the single selected item in state. When the backend supports pagination, the frontend will use **limit** and **offset** (or equivalent) to request subsequent pages (e.g. "Load more") and append results.

This document states the **functional requirements** the backend must satisfy for the search endpoints. It does not prescribe implementation (database, indexing, or response structure beyond what is needed for the client).

---

## Users search (for Customer)

### Endpoint

- **GET** **`/api/v1/users/search/`** (or an equivalent path agreed with the frontend).

### Query parameters

- **`q`** (string): Search string entered by the user. The backend filters users by the field indicated in `search_by` (e.g. substring or prefix match). Empty or omitted may return no results or a default/recent set, as the backend decides.
- **`search_by`** (string): Which field to search. The frontend will send one of:
  - `name` – search by full name (e.g. `full_name` or equivalent).
  - `username` – search by username.
  - `email` – search by email.
- **`limit`** (integer): Maximum number of items to return per page (e.g. 20).
- **`offset`** (integer): Number of items to skip for pagination (e.g. 0 for first page, 20 for second page). Alternatively the backend may support **`page`** and a fixed page size; the frontend can adapt if the contract is documented.
- **`role_type`** (optional, string): When present (e.g. `Customer`), the backend **SHALL** restrict results to users with that role type so the discretionary Customer dropdown only shows customers.
- **`institution_id`** (optional, UUID): When present, the backend restricts results to users belonging to this institution. Employees may pass any institution; Suppliers/Customers are restricted to their own institution. Used when the Employee has selected an institution in the discretionary form.
- **`market_id`** (optional, UUID): When present, the backend restricts results to users in this market. Employees with market scope (e.g. Manager, Operator) may only pass one of their assigned markets; Admin/Super Admin may pass any. Used when the Employee has selected a market in the discretionary form.

### Response

- JSON body containing:
  - A **list of user objects** in a key such as **`results`** or **`data`**. Each item **SHALL** include at least:
    - The unique identifier used by the client as the selected value (e.g. **`user_id`**).
    - The fields needed to build the display label: e.g. **`full_name`**, **`username`**, **`email`** (so the client can show "Name (email)" or similar).
  - Optional **pagination metadata** so the client can request the next page or show "Load more", e.g.:
    - **`total`** (integer) – total number of matching items, or
    - **`has_more`** (boolean), or
    - **`next_offset`** (integer) – offset for the next page.
- The backend **SHALL** apply the same authorization and scoping rules as for other user list endpoints (e.g. institution scoping for Suppliers). No prescription of how filtering or sorting is implemented.

---

## Restaurants search (for Restaurant)

### Endpoint

- **GET** **`/api/v1/restaurants/search/`** (or an equivalent path agreed with the frontend).

### Query parameters

- **`q`** (string): Search string. The backend filters restaurants by the field indicated in `search_by`.
- **`search_by`** (string): Which field to search. The frontend will send at least:
  - `name` – search by restaurant name. Additional values (e.g. address) may be added later if the backend supports them.
- **`limit`** (integer): Maximum number of items per page.
- **`offset`** (integer): Number of items to skip (or equivalent **`page`**-based scheme if documented).
- **`institution_id`** (optional, UUID): When present, the backend restricts results to restaurants in this institution. Employees may pass any institution; others only their own. Used when the Employee has selected an institution in the discretionary form.
- **`market_id`** (optional, UUID): When present, the backend restricts results to restaurants in this market (by credit currency). Employees with market scope may only pass one of their assigned markets; Admin/Super Admin may pass any. Used when "Filter by market" is set or the Employee has selected a market.

### Response

- JSON body containing:
  - A **list of restaurant objects** (e.g. in **`results`** or **`data`**). Each item **SHALL** include at least:
    - The unique identifier (e.g. **`restaurant_id`**).
    - The field(s) used for the display label (e.g. **`name`**).
  - Optional **pagination metadata** (e.g. **`total`**, **`has_more`**, or **`next_offset`**) so the frontend can paginate.

Same auth/scoping as other restaurant list endpoints; no prescription of implementation.

---

## Create discretionary request – optional validation

**Endpoint**: **POST** **`/api/v1/admin/discretionary/requests/`** (or equivalent).

The request body may include optional **`institution_id`** and **`market_id`** (UUID) for validation only. When present, the backend validates that the selected **`user_id`** (for Client credit) or **`restaurant_id`** (for Restaurant credit) belongs to that institution and/or market. If validation fails, the backend returns **400** with a clear message (e.g. "Selected user is not in the specified institution"). These fields are not stored on the discretionary request; they are used only to prevent mismatched selections. No new required fields.

---

## Frontend usage

- The frontend will call these endpoints from the discretionary request modal. It will **not** store the full list; it will:
  - Request the first page with `offset=0` (or page 1) when the user types a query (after debounce).
  - Request the next page (e.g. "Load more") by increasing `offset` (or page) and **append** the new items to the current result list for display.
  - Store only the **current page of results** and the **single selected item** (id + label) in component state.
- If the backend does not yet expose these endpoints, the frontend may show "Search not available" or disable the control until the API exists.

---

## Out of scope

- How the backend implements search (indexes, DB, full-text, etc.).
- Exact response key names (e.g. `results` vs `data`); the frontend will be configured to match the chosen contract.
- Additional search_by values or filters beyond those listed above (can be added later by agreement).

---

## References

- Frontend: Discretionary create form; new field type **`search_by_select`** for Customer and Restaurant.
- [DISCRETIONARY_REQUEST_INSTITUTION_AND_MARKET_SCOPING.md](./DISCRETIONARY_REQUEST_INSTITUTION_AND_MARKET_SCOPING.md) – institution and market scoping for the discretionary form.
- [INSTITUTION_FILTER_QUERY_PARAMETER.md](./INSTITUTION_FILTER_QUERY_PARAMETER.md) – optional `institution_id` on list endpoints; same pattern for search.
- Existing docs: e.g. `docs/api/feedback_for_backend/DISCRETIONARY_REQUEST_ONE_RECIPIENT_AND_CUSTOMER_FILTER.md`, `docs/api/API_PERMISSIONS_BY_ROLE.md`.
