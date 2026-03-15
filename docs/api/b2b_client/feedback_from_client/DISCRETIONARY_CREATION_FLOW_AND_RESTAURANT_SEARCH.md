# Discretionary Creation Flow & Restaurant Search — Backend Feedback

**Date**: March 2026  
**Context**: Discretionary Request create form (B2B kitchen-web) — user flow and restaurant search issues  
**Status**: Frontend has been updated; backend verification and possible fixes needed

---

## Summary

The discretionary creation flow for **Restaurant** credits requires:

1. **Credit for** (recipient type) → **Market** → **Institution** → **Restaurant** (in that order)
2. Restaurant search scoped by `institution_id` and `market_id` must return restaurants under that institution for that market.

The frontend has been updated to enforce this flow. The following describes what the frontend sends and what we need from the backend.

---

## Expected User Flow (Restaurant Credit)

1. User selects **Credit for** = Restaurant
2. User selects **Market** (e.g. Argentina) — Institutions dropdown is then filtered to those scoped to that market
3. User selects **Institution** (filtered by market)
4. User searches for **Restaurant** by name — search is scoped by `institution_id` and `market_id`

---

## Important: Use Form Field Values Only

For discretionary restaurant (and customer) search, **`market_id` and `institution_id` must come from the form fields** (`scope_market_id`, `scope_institution_id`), **not** from the authenticated user's profile (e.g. `/users/me` market). The user explicitly selects Market and Institution in the form to scope the search.

---

## Current Frontend Behavior

- **Field order**: Credit for → Market → Institution → Customer/Restaurant → Category → Amount → …
- **Cascade**: When Market changes → Institution, Customer, Restaurant are cleared. When Institution changes → Customer, Restaurant are cleared.
- **Restaurant search**: See [Exact Restaurant Search Request](#exact-restaurant-search-request) below.

---

## Exact Restaurant Search Request

**Endpoint**: `GET /api/v1/restaurants/search/`

**When**: User types a search query (min 2 characters) in the Restaurant search field, after having selected Credit for = Restaurant, Market, and Institution.

**Headers**: `Authorization: Bearer <token>` (same as other authenticated requests)

**Query parameters** (the frontend sends these exactly):

| Param | Source | Example | Notes |
|-------|--------|---------|-------|
| `search_by` | Fixed | `name` | Only option configured |
| `q` | User input | `parrilla` | Min 2 chars, debounced 300ms |
| `limit` | Fixed | `20` | Page size |
| `offset` | Pagination | `0`, `20`, … | 0 for first page |
| `institution_id` | Form field `scope_institution_id` | `33333333-3333-3333-3333-333333333333` | **Only sent when user has selected Institution**; omitted if empty; must be a **Supplier** institution (only those have restaurants) |
| `market_id` | Form field `scope_market_id` | `00000000-0000-0000-0000-000000000002` | **Only sent when user has selected Market**; omitted if empty; **never** from `/users/me`; must be a **market_info** UUID (e.g. Argentina = `00000000-0000-0000-0000-000000000002`) |

**⚠️ Critical – UUID semantics**:
- `market_id` must be from **market_info** (e.g. Argentina = `00000000-0000-0000-0000-000000000002`, Global = `00000000-0000-0000-0000-000000000001`). Do **not** send an institution UUID as `market_id`.
- `institution_id` must be from **institution_info** (a Supplier institution that has restaurants).

**Example full URL** (with both scope params):

```
GET /api/v1/restaurants/search/?search_by=name&q=parrilla&limit=20&offset=0&institution_id=33333333-3333-3333-3333-333333333333&market_id=00000000-0000-0000-0000-000000000002
```

**Frontend code path**:
1. `FormModal` builds `searchContext = { institutionId: formData.scope_institution_id || null, marketId: formData.scope_market_id || null }`
2. `SearchBySelectField` receives `searchContext` and calls `getSearchExtraParams(ctx)` from the restaurant field config
3. Params with empty/null values are **stripped** before the request (so if Market not selected, `market_id` is not sent)

**Expected response shape** (frontend parses):
- `{ results: [{ restaurant_id, name, ... }], total?: number, has_more?: boolean, next_offset?: number }` — or —
- `{ data: [...] }` — or —
- `[...]` (plain array)

Each item must have at least `restaurant_id` (or configured `valueKey`) and `name` (or configured `labelKey`).

---

## Exact Customer Search Request (for reference)

**Endpoint**: `GET /api/v1/users/search/`

**Query params**: `search_by` (name|username|email), `q`, `limit`, `offset`, `role_type=Customer`, plus `institution_id` and `market_id` from form when selected (same pattern as restaurant search).

---

## Issue: Restaurant List Coming Up Empty

**Symptom**: User selects Credit for = Restaurant, Market, and Institution; a restaurant exists under that institution, but the search returns no results.

**Possible causes (backend to verify)**:

1. **Endpoint not implemented**: `GET /api/v1/restaurants/search/` may return 404 or 501. Frontend shows "Search not available" in that case. If the endpoint exists and returns 200 with empty results, the problem is filtering logic.

2. **`institution_id` / `market_id` not supported**: The search endpoint may not accept or apply these query parameters. Per [SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md](../../zArchive/api/backend/SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md), the backend should:
   - Accept optional `institution_id` — restrict to restaurants in that institution
   - Accept optional `market_id` — restrict to restaurants in that market

3. **Incorrect filtering logic**: Restaurant ↔ Institution ↔ Market relationship:
   - Restaurant belongs to an institution (via institution_entity)
   - Institution has `market_id`
   - When filtering by `institution_id`, results should include all restaurants under that institution
   - When both `institution_id` and `market_id` are present, results should be the intersection (restaurants in that institution AND that market). Since an institution typically has one market (or Global), this should usually match.

4. **Response shape**: Frontend expects one of:
   - `{ results: [...] }`
   - `{ data: [...] }`
   - `[...]` (array)
   and `total`, `has_more`, or `next_offset` for pagination.

---

## Debugging Tips

1. **Inspect the actual request** in browser DevTools → Network tab when user searches for a restaurant. Filter by "search" or "restaurants". Check:
   - Request URL and query params
   - Whether `institution_id` and `market_id` are present when Market and Institution are selected
   - Response status and body (empty `results` vs error)

2. **Frontend source**:
   - `src/components/forms/FormModal.tsx` (lines ~329–336): builds `searchContext` from `formData.scope_market_id`, `formData.scope_institution_id`
   - `src/components/forms/fields/SearchBySelectField.tsx`: merges `searchContext` into request params via `getSearchExtraParams`
   - `src/utils/formConfigs.ts` (restaurant field ~lines 175–191): `searchEndpoint`, `getSearchExtraParams`

3. **Duplicate keys in pending-requests table**: The frontend has seen `discretionary_id` duplicated in `GET /api/v1/super-admin/discretionary/pending-requests/` responses, causing React key warnings. If the same `discretionary_id` appears more than once, that indicates a backend-side issue (e.g. join producing duplicates).

4. **Check for swapped UUIDs**: If `market_id` is accidentally an institution UUID (e.g. `11111111-1111-1111-1111-111111111111`), the backend's market subquery returns nothing and the filter yields 0 results. Verify in Network tab that `market_id` is a valid `market_info.market_id` (e.g. `00000000-0000-0000-0000-000000000002` for Argentina).

---

## Backend diagnostic SQL

Run these to verify data when search returns empty (replace placeholders with actual UUIDs from the request):

```sql
-- 1. Is market_id valid? (must return 1 row)
SELECT market_id, country_name, credit_currency_id FROM market_info
WHERE market_id = '<market_id_from_request>' AND is_archived = FALSE;

-- 2. Does the institution exist and have restaurants?
SELECT r.restaurant_id, r.name, r.institution_entity_id, ie.credit_currency_id
FROM restaurant_info r
JOIN institution_entity_info ie ON r.institution_entity_id = ie.institution_entity_id
WHERE r.institution_id = '<institution_id_from_request>' AND r.is_archived = FALSE;

-- 3. Does the institution's entity credit_currency match the market's?
-- (The search filters by ie.credit_currency_id = market's credit_currency_id)
SELECT m.market_id, m.country_name, m.credit_currency_id AS market_cc,
       ie.institution_entity_id, ie.credit_currency_id AS entity_cc,
       ie.credit_currency_id = m.credit_currency_id AS matches
FROM market_info m
CROSS JOIN institution_entity_info ie
WHERE m.market_id = '<market_id_from_request>' AND m.is_archived = FALSE
  AND ie.institution_id = '<institution_id_from_request>' AND ie.is_archived = FALSE;
```

If (1) returns no rows → `market_id` is invalid (e.g. institution UUID passed by mistake).  
If (2) returns no rows → no restaurants under that institution, or all archived.  
If (3) has `matches = false` for all rows → institution's entities use a different currency than the selected market; no restaurants will match.

---

## Backend Checklist

- [ ] Verify `GET /api/v1/restaurants/search/` exists and returns 200
- [ ] Verify it accepts `institution_id` (UUID) and `market_id` (UUID) as optional query params
- [ ] When `institution_id` is present, restrict results to restaurants under that institution
- [ ] When `market_id` is present, restrict results to restaurants in that market
- [ ] When both are present, apply logical AND (intersection)
- [ ] Response shape: `{ "results": [ { "restaurant_id", "name" } ], "total": N }` (or `data` / array)
- [ ] Ensure `search_by=name` and `q` work for name substring match (ILIKE)

## Frontend responsibility

The frontend must pass **`market_id` from the form fields** (the Market selected in the discretionary form), not the current user's assigned market. If the user selects Market = Argentina in the form, send `market_id` = Argentina's UUID. Do not send the user's `market_id` from GET /users/me (e.g. Global for Global Managers) when the form has a different market selected.

---

## Related Docs

- [SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md](../../zArchive/api/backend/SEARCH_API_FOR_DISCRETIONARY_RECIPIENTS.md) — full search API contract
- [DISCRETIONARY_REQUEST_INSTITUTION_AND_MARKET_SCOPING.md](../../zArchive/api/backend/DISCRETIONARY_REQUEST_INSTITUTION_AND_MARKET_SCOPING.md) — scoping UI and API
- [INSTITUTION_MARKET_ID.md](../INSTITUTION_MARKET_ID.md) — institution–market relationship
