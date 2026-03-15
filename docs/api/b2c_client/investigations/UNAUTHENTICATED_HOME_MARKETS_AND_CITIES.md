# Investigation: Unauthenticated home — markets and cities not loading

**Status**: Open  
**Reported**: B2C app (vianda-app)  
**Context**: Unauthenticated marketing home page (index when user is not logged in).

---

## Symptom

On the unauthenticated home page:

1. **"Loading cities..."** appears in the city selector and can persist (city dropdown does not become usable).
2. **Only the global (🌐) icon** is shown for the market/country selector; no country flag is selected.
3. **Market/country is not editable**: the user cannot pick a market — either the flag button does not respond or the picker shows no options.

After a refresh or when the issue occurs, the page appears stuck in this state.

---

## Client flow (for reference)

1. **Markets**
   - On app load, `MarketContext` calls **GET `/api/v1/markets/available`** (no `Authorization` header — user is not authenticated).
   - Response: `[{ "country_code": "AR", "country_name": "Argentina" }, ...]` — `country_code` and `country_name` only (no `market_id`).
   - On success: client parses the list, selects a country (from stored `country_code`, device locale, or default e.g. US) and shows its flag in the header.
   - On failure (e.g. throw): client sets `selectedMarket = null`, `markets = []`, and shows the global (🌐) icon. The flag picker modal then lists `markets`; if the list is empty, the user has nothing to select.

2. **Cities**
   - When the selected market (or its `country_code`) is available, the client calls **GET `/api/v1/leads/cities`** with query **`country_code=<alpha2>`** (e.g. `AR`, `US`). No auth.
   - When there is **no** selected market, the client still calls **GET `/api/v1/leads/cities`** with **no** `country_code` (or empty). The UI shows "Loading cities..." until this request completes.
   - If this request hangs, errors, or is very slow, "Loading cities..." persists.

So the observed behaviour is consistent with:

- **GET `/api/v1/markets/available`** failing (e.g. 401, 5xx, or very slow) when called **without** auth, leading to no market selected and an empty picker; and/or  
- **GET `/api/v1/leads/cities`** hanging, failing, or being very slow (with or without `country_code`), leading to "Loading cities..." stuck on screen.

---

## What the backend should verify

1. **GET `/api/v1/markets/available`**
   - Is this endpoint **public** (no authentication required) for B2C?
   - When called **without** `Authorization`, does it return **200** and a non-empty list of markets (e.g. US, Argentina) that the B2C client can show in the country selector?
   - If it now requires auth and returns 401 (or another error) when unauthenticated, that would explain the global-only icon and non-editable market selector on the home page.

2. **GET `/api/v1/leads/cities`**
   - When called **without** auth:
     - With a valid `country_code` (e.g. `AR`, `US`): does it return 200 and a list of cities in a reasonable time?
     - With **no** `country_code` or empty `country_code`: what is the contract? (e.g. 400, empty list, or list of all cities?) Does the request complete quickly or can it hang?
   - If the request without (or with invalid) `country_code` hangs or is very slow, that would explain the persistent "Loading cities..." message.

3. **Rate limiting / errors**
   - Are either of these endpoints rate-limited or returning 4xx/5xx in a way that could cause the client to retry or appear stuck?
   - Any CORS or network errors that might prevent the client from receiving a response?

---

## Endpoints summary

| Endpoint | Auth | Used on unauthenticated home | Expected |
|----------|------|------------------------------|----------|
| GET `/api/v1/markets/available` | None | Yes | 200, list of `{ country_code, country_name }` (country options for selector). |
| GET `/api/v1/leads/cities` | None | Yes, with `country_code` from selected market (or without if no market) | 200, list of city names; or defined behaviour when `country_code` is missing. |

---

## Client-side follow-up (optional)

If the backend confirms that both endpoints are public and respond quickly, the B2C client can be updated to avoid showing "Loading cities..." when no market is selected (e.g. skip calling `/leads/cities` until a market is chosen, or show "Select country first" instead of "Loading cities..." in that case).
