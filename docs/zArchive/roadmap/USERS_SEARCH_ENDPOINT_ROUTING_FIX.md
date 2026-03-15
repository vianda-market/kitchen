# Users Search Endpoint – Routing Fix (Backend Response)

**Date**: February 2026  
**Related**: [USERS_SEARCH_ENDPOINT_ROUTING_ISSUE.md](./USERS_SEARCH_ENDPOINT_ROUTING_ISSUE.md), [SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md](./SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md)  
**Status**: Implemented

---

## Problem (summary)

The frontend called `GET /api/v1/users/search/` with query parameters only. The backend was matching `GET /users/{user_id}` and treating the path segment `"search"` as `user_id`, which then failed UUID validation and returned **422 Unprocessable Entity**.

---

## Backend changes

1. **New route: `GET /api/v1/users/search/`**  
   - Implemented in `app/routes/user.py`.  
   - **Declared before** `GET /users/{user_id}` so that the path `/users/search/` is matched by the search handler and not by the user-by-id handler.

2. **Search implementation**  
   - **Handler**: `search_users_route` in `app/routes/user.py`.  
   - **Business logic**: `search_users()` in `app/services/entity_service.py`.  
   - **Query parameters**: `q`, `search_by` (name | username | email), `limit`, `offset`, `role_type` (optional).  
   - **Response**: `{ "results": [ { "user_id", "full_name", "username", "email" } ], "total": N }`.  
   - **Auth and scoping**: Same as other user list endpoints (institution scope for Employees/Suppliers; Customers see only themselves — in practice search is used by admins for the discretionary modal).

3. **Response schema**  
   - `UserSearchResultSchema`: `user_id`, `full_name`, `username`, `email`.  
   - `UserSearchResponseSchema`: `results` (list of above), `total` (integer).

---

## Requirements satisfied

| Requirement | Implementation |
|-------------|----------------|
| Reachable search endpoint | `GET /api/v1/users/search/` is handled by the search handler. |
| No path segment interpreted as user_id | The route is defined with path `/search/`; it is registered **before** `/users/{user_id}`, so `"search"` is never passed as `user_id`. |
| Search semantics unchanged | Query params, response shape, and auth/scoping follow [SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md](./SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md). |

---

## Contract (quick reference)

- **Endpoint**: `GET /api/v1/users/search/`
- **Query**: `q` (string), `search_by` (required: `name` | `username` | `email`), `limit` (default 20, 1–100), `offset` (default 0), `role_type` (optional, e.g. `Customer`).
- **Response**: `200 OK` with `{ "results": [ { "user_id", "full_name", "username", "email" } ], "total": N }`.
- **Empty query**: If `q` is empty or omitted, the backend returns `{ "results": [], "total": 0 }`.

The discretionary modal can call this endpoint with `role_type=Customer` to populate the Customer search-by-select.

---

## Same fix: Restaurants search

The **same routing issue** applied to **`GET /api/v1/restaurants/search/`**: the path segment `"search"` was being matched by `GET /restaurants/{restaurant_id}` and failed with `restaurant_id` "value is not a valid uuid".

**Backend change**: `GET /api/v1/restaurants/search/` was added in `app/routes/restaurant.py` **before** `GET /{restaurant_id}`. The search endpoint accepts `q`, `search_by` (only `name`), `limit`, `offset`, and returns `{ "results": [ { "restaurant_id", "name" } ], "total": N }` with the same auth/scoping as other restaurant list endpoints. Implementation: `search_restaurants()` in `app/services/entity_service.py`; schemas: `RestaurantSearchResultSchema`, `RestaurantSearchResponseSchema`.
