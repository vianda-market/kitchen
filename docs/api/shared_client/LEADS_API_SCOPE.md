# Leads API — Unauthenticated Endpoints Scope

**Audience**: B2B, B2C, and backend teams
**Purpose**: Single reference for all unauthenticated lead-capture endpoints under `/api/v1/leads/`. No auth required; rate-limited per IP.

---

## Overview

Lead-capture endpoints serve pre-signup flows: country/city selection, coverage checks, and email lookup.
They return **minimal data** (no internal IDs like `market_id`) to keep the public surface small.

For authenticated flows needing `market_id`, timezone, or currency: use `GET /api/v1/markets/enriched/`.

---

## Endpoints

| Endpoint | Auth | Rate | Use case |
|----------|------|------|----------|
| `GET /api/v1/leads/markets` | None | 60/min | B2C signup country dropdown; gate subscribable markets |
| `GET /api/v1/leads/cities` | None | 20/min | Lead flow city picker; marketing site coverage display |
| `GET /api/v1/leads/city-metrics` | None | 20/min | Lead encouragement (restaurant count) |
| `GET /api/v1/leads/zipcode-metrics` | None | 20/min | Lead encouragement legacy |
| `GET /api/v1/leads/email-registered` | None | 10/min | Login vs signup routing |

---

## GET /api/v1/leads/markets

**Auth**: None. **Response fields**: `country_code`, `country_name`, `language`, `locale`, `phone_dial_code`, `phone_local_digits`, `has_active_kitchens`.

**`has_active_kitchens`** — `true` when the market has at least one active
`institution -> restaurant -> plate -> plate_kitchen_days` chain. Derived from live data;
NOT the hand-toggled `market_info.status` column.
Use this flag to gate which countries appear as subscribable on the marketing site.

- **Default (no param)**: markets that pass the active-plate chain — all have `has_active_kitchens: true`.
- **`?audience=supplier`**: all active non-global markets; `has_active_kitchens` batch-checked in one query.
- **`?language=es`** or `Accept-Language: es`: localize country names.

Excludes Global Marketplace (assignment-only; not shown in public list).

---

## GET /api/v1/leads/cities

**Query params**: `country_code` (default US), `audience`, `mode`.

### Default mode

Response: `{ "cities": ["Buenos Aires", "Cordoba", ...] }` — sorted alphabetically.
Use case: city picker for signup; send `city_name` in signup body.

### `?mode=coverage` (vianda-home marketing site)

Response: `[{ "city": "Buenos Aires", "restaurant_count": 12 }, ...]` — sorted alphabetically.

Only cities in `city_metadata` (`show_in_signup_picker = TRUE`) with >= 1 active restaurant
with `plate_kitchen_days` + QR code are included. Single JOIN query — no N+1.
Readiness derived from the same active-plate chain as `GET /leads/markets`.

Use case: vianda-home multi-country landing page — show cities with real food coverage
and an accurate restaurant count badge.

Note: `mode=coverage` and `audience=supplier` are independent params; coverage mode always
uses the customer coverage predicate.

---

## GET /api/v1/leads/city-metrics

**Query**: `city` (required), `country_code` (default US).
**Response**: `{ requested_city, matched_city, restaurant_count, has_coverage }`.
Use case: lead encouragement — show restaurant count for selected city.

---

## GET /api/v1/leads/zipcode-metrics

**Query**: `zip` (required), `country_code` (default US).
**Response**: `{ requested_zipcode, matched_zipcode, restaurant_count, has_coverage }`.
Use case: same as city-metrics; prefer city-metrics for new flows.

---

## GET /api/v1/leads/email-registered

**Query**: `email` (required).
**Response**: `{ "registered": true|false }`.
Use case: after city/zipcode step, route user to login vs signup.

---

## Coverage readiness — hard rule

All market/city readiness signals on `/leads/*` derive from the live **active-plate chain**:

```
institution (active, not archived)
  -> restaurant (active, not archived)
    -> plate (not archived)
      -> plate_kitchen_days (active, not archived)
```

The hand-toggled `market_info.status` / `is_archived` columns are **not** used as the
primary readiness signal. Do not use those columns to infer coverage for public display.

---

## Related

- [API_CLIENT_MARKETS.md](../b2b_client/API_CLIENT_MARKETS.md) — Authenticated markets (full data, `market_id`)
- [MARKET_CITY_COUNTRY.md](../b2c_client/MARKET_CITY_COUNTRY.md) — B2C signup flow
- [ZIPCODE_METRICS_LEAD_API.md](./ZIPCODE_METRICS_LEAD_API.md) — Zipcode metrics detail
- [LEADS_COVERAGE_CHECKER.md](../marketing_site/LEADS_COVERAGE_CHECKER.md) — Caching strategy
