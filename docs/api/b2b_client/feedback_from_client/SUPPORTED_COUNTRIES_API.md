# Supported Countries API for “Create Market” Dropdown (Option B)

**Date**: February 2026  
**Context**: The vianda-platform frontend uses the **markets API** with cache for country dropdowns (address form, national holidays). For **creating a new market**, the UI needs a list of **supported country codes** (countries that are valid for a new market), which may be broader than “existing markets only.”  
**Status**: Implemented. Endpoint: `GET /api/v1/countries/`. Supported countries = Americas from Canada to Argentina (single source in `app/config/supported_countries.py`); same list validates `country_code` on `POST/PUT /api/v1/markets/`. More regions can be added later.

---

## Request

### Add an endpoint that returns supported countries for new markets

Provide a **read-only** endpoint that returns the list of **country codes** (and optionally display names) that are valid when creating a new market. This allows the “Create Market” form to show a single source of truth (e.g. all ISO countries the product supports, or a curated list) instead of only existing markets.

**Suggested contract** (backend may adjust path and shape):

- **Method/Path**: `GET /api/v1/countries/` (or e.g. `GET /api/v1/markets/supported-countries/`)
- **Auth**: Same as other back-office endpoints (Bearer token).
- **Response**: JSON array of objects with at least:
  - `country_code` (string, ISO 3166-1 alpha-2, e.g. `"AR"`, `"US"`)
  - `country_name` (string, optional) — for dropdown label; if omitted, frontend will use `country_code` as label.

**Example response**:

```json
[
  { "country_code": "AR", "country_name": "Argentina" },
  { "country_code": "DE", "country_name": "Germany" },
  { "country_code": "US", "country_name": "United States" }
]
```

- **Ordering**: Sorted by `country_name` (or `country_code`) for consistent dropdown UX.
- **Scope**: Only countries that the backend considers valid for creating a new market (e.g. same source as used to validate `country_code` on `POST /api/v1/markets/`).

---

## Current frontend behavior (without this API)

- The frontend calls `GET /api/v1/countries/` (or the path you choose once documented).
- If the endpoint returns **404** or **501**, the frontend **falls back** to `GET /api/v1/markets/` and builds the country list from **existing markets** (unique by `country_code`). So “Create Market” still works, but the dropdown is limited to countries that already have a market.
- Once the backend implements this endpoint, the frontend will use it and the dropdown can show the full supported list (e.g. all countries where the product can operate) without any code change, as long as the response shape matches the above.

---

## Why this is useful

- **Option B (product choice)**: “Create market” should allow selecting from **all supported countries**, not only those that already have a market. A dedicated supported-countries endpoint keeps that list under backend control (e.g. driven by config, licensing, or validation rules).
- **Consistency**: The same source of truth can be used to validate `country_code` on market create/update and to populate the dropdown.
- **No hardcoded list**: The frontend can remove any remaining static country list and rely on the API.

---

## Summary

| Item | Requested |
|------|-----------|
| Endpoint | `GET /api/v1/countries/` (or equivalent) |
| Response | Array of `{ country_code, country_name? }` |
| Use case | Populate “Country” dropdown in Create/Edit Market form |
| If not implemented | Frontend falls back to existing markets list |

---

## References

- Frontend: `useCountryOptionsForNewMarket` hook; Market form uses `fieldOptionsOverrides` with these options.
- Plan: `docs/plans/REMOVE_HARDCODED_COUNTRIES_USE_MARKETS_API.md`.
