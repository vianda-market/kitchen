# Users Search Endpoint – Routing / Validation Error (Discretionary Modal)

**Date**: February 2026  
**Context**: Discretionary request modal uses a search-by-select to choose a Customer. When the user runs a search, the frontend calls the users search endpoint and receives a validation error indicating `user_id` (path) is not a valid UUID.  
**Status**: Resolved. **Backend response**: [USERS_SEARCH_ENDPOINT_ROUTING_FIX.md](./USERS_SEARCH_ENDPOINT_ROUTING_FIX.md)

---

## Problem

When the user uses the **search** control in the discretionary modal to find a customer (by name, username, or email), the frontend sends:

- **Method**: GET  
- **URL path**: `/api/v1/users/search/`  
- **Query parameters**: `search_by`, `q`, `limit`, `offset`, and optionally `role_type` (e.g. `Customer`). No path parameters are sent.

The backend responds with **422 Unprocessable Entity** and a body such as:

```json
{
  "detail": [
    {
      "loc": ["path", "user_id"],
      "msg": "value is not a valid uuid",
      "type": "type_error.uuid"
    }
  ]
}
```

So the backend is treating some part of the request as a **path** parameter named `user_id` and validating it as a UUID. From the frontend's perspective, the request is to a fixed path `/api/v1/users/search/` with only query parameters; no UUID is supplied in the path. The frontend contract is documented in `SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md`.

---

## Requirements

The backend **SHALL** satisfy the following so that the discretionary (and any other) client can use the users search as intended:

1. **Reachable search endpoint**  
   A GET request to the users search endpoint (e.g. **`/api/v1/users/search/`** or an equivalent path agreed with the frontend) **SHALL** be handled by the **search** handler, not by a handler that expects a single user identifier in the path.

2. **No path segment interpreted as user_id for search**  
   For that search request, **no path segment** (e.g. the literal `"search"` in `/api/v1/users/search/`) **SHALL** be interpreted or validated as the path parameter `user_id`. The search endpoint **SHALL** be defined so that it is unambiguously distinct from any route that uses a path parameter for `user_id` (e.g. get user by id).

3. **Search semantics unchanged**  
   The behaviour and contract of the users search endpoint (query parameters, response shape, auth/scoping) remain as specified in `SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md`; this document only adds requirements so that the search endpoint is correctly routed and not confused with user-by-id semantics.

---

## Out of scope

- Prescribing how the backend orders or defines routes (e.g. route registration order, path naming, or framework-specific details).
- Changes to query parameters, response format, or authorization for the search endpoint beyond what is already required elsewhere.
- Restaurants search endpoint (only users search is in scope for this issue).

---

## References

- **Backend fix**: [USERS_SEARCH_ENDPOINT_ROUTING_FIX.md](./USERS_SEARCH_ENDPOINT_ROUTING_FIX.md)
- Frontend: Discretionary request modal, Customer search-by-select; `SearchBySelectField` calling `GET /api/v1/users/search/` with query params only.
- Contract: [SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md](./SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md).
