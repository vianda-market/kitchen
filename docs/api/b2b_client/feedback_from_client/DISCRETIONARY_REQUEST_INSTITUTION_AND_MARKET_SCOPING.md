# Create Discretionary Request – Institution and Market Scoping for Employees

**Date**: February 2026  
**Context**: When an **Employee** creates a discretionary request, they must search for the recipient (Customer or Restaurant). Today the Customer search is unscoped (all customers); the Restaurant search can be scoped by **Market** only when the user has a global market (market picker visible). Employees need to optionally scope **both** searches by **Institution** and **Market** so they can narrow down the list and avoid selecting the wrong recipient.  
**Status**: Request for backend implementation. Frontend will add Institution and Market fields for Employees and pass them as query params to the search endpoints once the backend supports them.

---

## Situation

### Current behavior

- **Create discretionary request** form: User selects **Credit for** (Customer or Restaurant), then either:
  - **Customer**: Search by name, username, or email via `GET /api/v1/users/search/` with `role_type=Customer`. No institution or market scoping.
  - **Restaurant**: Search by name via `GET /api/v1/restaurants/search/`. Optional **Filter by market** (`restaurant_search_market_id`) is shown only when the current user has a global market; when set, the frontend passes `market_id` in the search request.
- **Employees** can act across institutions and markets. Without scoping, the Customer and Restaurant search results can be very large and error-prone.

### Desired behavior

- **Employees**: At the top of the create form, show optional **Institution** and **Market** fields. When the Employee selects an institution and/or market, the **Customer** search and **Restaurant** search are scoped to that institution and/or market (e.g. only users in that institution, only restaurants in that institution or market).
- **Suppliers / Customers** (if they can create discretionary requests): Do **not** show Institution or Market; they are already scoped by JWT. Existing behavior unchanged.

So the backend must accept optional **`institution_id`** and **`market_id`** (or equivalent) on the **search** endpoints used by the discretionary form, and restrict results accordingly when those parameters are present.

---

## Plan for UI (B2B client)

1. **Institution field** (visible for Employees only)
   - Optional dropdown or search; source: `GET /api/v1/institutions/` (or existing list). Value stored in form state (e.g. `institution_id`). When set, all downstream search requests include `institution_id`.

2. **Market field** (visible for Employees only, or extend existing “Filter by market”)
   - Optional dropdown; source: `GET /api/v1/markets/enriched/` with “All markets” option. Value stored in form state (e.g. `market_id` or reuse `restaurant_search_market_id`). When set, search requests include `market_id`.

3. **Field order**
   - Institution and Market first (for Employees), then **Credit for** (recipient type), then Customer or Restaurant search, then category, amount, reason, comment. Recipient search fields are disabled or show “Select institution/market first” until at least one scope is selected (or allow unscoped search; product decision).

4. **Search requests**
   - **Customer search** (`GET /api/v1/users/search/`): Frontend will send optional `institution_id` and `market_id` from form state when provided. Backend returns only users that belong to that institution (and optionally that market, if applicable).
   - **Restaurant search** (`GET /api/v1/restaurants/search/`): Frontend already sends `market_id` when “Filter by market” is set. Frontend will also send optional `institution_id` when the Employee has selected an institution. Backend returns only restaurants that belong to that institution (and optionally that market).

5. **Create payload**
   - No change. The client continues to send `user_id` or `restaurant_id`, `category`, `amount`, `reason`, `comment`. Backend may optionally accept `institution_id` / `market_id` in the body for validation (e.g. verify the selected user/restaurant belongs to that institution/market) or ignore them.

---

## Backend requirements

### 1. Users search (Customer recipient)

**Endpoint**: `GET /api/v1/users/search/` (or equivalent used by the discretionary form).

**New optional query parameters**:

| Parameter        | Type | Description |
|------------------|------|-------------|
| `institution_id` | UUID | When present, restrict results to users belonging to this institution. Apply in addition to existing filters (e.g. `role_type=Customer`). |
| `market_id`      | UUID | When present, restrict results to users associated with this market (if your model has user–market relationship). Optional; only if applicable. |

- **Auth**: Unchanged. Employees may pass any institution/market they are allowed to access; Suppliers/Customers remain scoped by JWT (backend may ignore these params for non-Employees or enforce that they match the caller’s context).
- **Behavior when absent**: Same as today (no institution/market filter).

### 2. Restaurants search (Restaurant recipient)

**Endpoint**: `GET /api/v1/restaurants/search/` (or equivalent).

**Existing / new optional query parameters**:

| Parameter        | Type | Description |
|------------------|------|-------------|
| `market_id`      | UUID | Already used by the frontend when “Filter by market” is set. When present, restrict results to restaurants in this market. |
| `institution_id` | UUID | **New.** When present, restrict results to restaurants belonging to this institution. When both `institution_id` and `market_id` are present, apply both (e.g. restaurants in that institution and that market). |

- **Auth**: Unchanged. Employees may pass any institution/market; others scoped by JWT.
- **Behavior when absent**: Same as today.

### 3. Create discretionary request payload

**Endpoint**: `POST /api/v1/admin/discretionary/requests/` (or equivalent).

- **No new required fields.** The client continues to send `user_id` or `restaurant_id`, `category`, `amount`, `reason`, `comment` as today.
- **Optional**: Backend may accept optional `institution_id` and/or `market_id` in the body and validate that the selected `user_id` or `restaurant_id` belongs to that institution/market. If validation fails, return **400** with a clear message. If the backend does not need them for validation, it may ignore them.

---

## Summary

| Item | Request |
|------|--------|
| **Users search** | Support optional `institution_id` and, if applicable, `market_id` query params. Restrict results to that institution (and market). |
| **Restaurants search** | Support optional `institution_id` query param (in addition to existing `market_id`). Restrict results to that institution and optionally market. |
| **Create discretionary** | No new required body fields. Optional `institution_id` / `market_id` in body for validation only. |
| **Auth** | Same as today; Employees can pass institution/market; others remain JWT-scoped. |

---

## References

- **Search API (discretionary)**: [SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md](./SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md) – existing query params for users and restaurants search.
- **Institution filter (list endpoints)**: [INSTITUTION_FILTER_QUERY_PARAMETER.md](./INSTITUTION_FILTER_QUERY_PARAMETER.md) – optional `institution_id` on list/enriched endpoints; same pattern for search endpoints.
- **Frontend**: Discretionary create form (`discretionaryFormConfig`); `SearchBySelectField` with `getSearchExtraParams(searchContext)`; `searchContext` will include `institutionId` and `marketId` when the form has Institution and Market fields for Employees.
