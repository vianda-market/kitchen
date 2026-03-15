# Feedback: GET /users/me — include city_name (resolve from city_id)

**Status:** ✅ Implemented. Both `GET /users/me` and `POST /customers/signup/verify` return `city_id` and `city_name`.

**Context:** The B2C app needs to pre-populate the Explore tab "Select city" with the user's assigned city after signup or login. The user selects a city at signup (stored as `city_id` in `user_info`). The Explore tab expects a **city name** (string) to display in the selector and to call `GET /api/v1/restaurants/by-city?city=...`.

**Previous behavior:** `GET /api/v1/users/me` and signup/verify returned only `city_id` (UUID), not `city_name`.

**Expected per docs:** [EMPLOYER_MANAGEMENT_B2C.md](./EMPLOYER_MANAGEMENT_B2C.md) and [feedback_for_backend_employer_search_and_assign.md](./feedback_for_backend_employer_search_and_assign.md) state that the enriched response includes `city_id` **and** `city_name`.

**Ask:** Enrich `GET /api/v1/users/me` (and the user object in `POST /api/v1/customers/signup/verify` response) to include `city_name` by resolving `city_id` against `city_info`. When `user_info.city_id` is set, join/lookup the city name from `city_info` and include it in the response as `city_name` (string). When `city_id` is null, `city_name` may be null or omitted.

**Why:** The B2C Explore tab uses city **names** (e.g. "Buenos Aires") for the dropdown and for `GET /restaurants/by-city?city=Buenos Aires`. The client has `city_id` but cannot use it directly for those calls. Resolving on the client would require an extra `GET /api/v1/cities/?country_code=...` call and a lookup—possible but redundant if the backend already has the relationship.

**Example response shape (desired):**
```json
{
  "user_id": "...",
  "market_id": "...",
  "city_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "city_name": "Buenos Aires",
  ...
}
```

---

**Implementation (done):**
- `GET /api/v1/users/me` returns `UserEnrichedResponseSchema` with `city_id` and `city_name` (resolved via `LEFT JOIN city_info` in `get_enriched_user_by_id`).
- `POST /api/v1/customers/signup/verify` now returns enriched user (same shape as `/me`) including `city_name`, so the B2C client gets the city name for the search box immediately after signup.
