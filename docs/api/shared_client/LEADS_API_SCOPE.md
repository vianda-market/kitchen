# Leads API — Unauthenticated Endpoints Scope

**Audience**: B2B, B2C, and backend teams  
**Purpose**: Single reference for all unauthenticated lead-capture endpoints. All endpoints under `/api/v1/leads/` require **no authentication** and are rate-limited per IP.

---

## Overview

Lead-capture endpoints serve pre-signup flows: country/city selection, coverage checks, and email lookup. They return **minimal data** (no internal IDs like `market_id`) to keep the public surface small and avoid exposing internal UUIDs.

**For authenticated flows that need `market_id`, timezone, or currency**: use `GET /api/v1/markets/enriched/` instead.

---

## Endpoints

| Endpoint | Auth | Rate limit | Response | Use case |
|----------|------|------------|----------|----------|
| `GET /api/v1/leads/markets` | None | 60/min | `country_code`, `country_name` only | B2C signup country dropdown, pre-auth country selector |
| `GET /api/v1/leads/cities` | None | 20/min | city names | Lead flow, signup city picker |
| `GET /api/v1/leads/city-metrics` | None | 20/min | restaurant count, has_coverage | Lead encouragement |
| `GET /api/v1/leads/zipcode-metrics` | None | 20/min | restaurant count, has_coverage | Lead encouragement (legacy) |
| `GET /api/v1/leads/email-registered` | None | 10/min | registered boolean | Lead flow: login vs signup routing |

---

## GET /api/v1/leads/markets

**Auth**: None.

**Response**: Array of `{ country_code, country_name }` only. No `market_id`, timezone, or currency.

```json
[
  { "country_code": "AR", "country_name": "Argentina" },
  { "country_code": "US", "country_name": "United States" }
]
```

**Use case**: Country dropdown for B2C signup; send `country_code` in signup request. Backend resolves `country_code` to `market_id` internally.

**Excludes**: Global Marketplace (assignment-only; not shown in public list).

---

## GET /api/v1/leads/cities

**Query**: `country_code` (optional, default US).

**Response**: `{ "cities": ["Buenos Aires", "Córdoba", ...] }`.

**Use case**: City picker for signup; user selects city, send `city_name` in signup. Backend resolves to `city_id`.

---

## GET /api/v1/leads/city-metrics

**Query**: `city` (required), `country_code` (optional, default US).

**Response**: `restaurant_count`, `has_coverage`, `matched_city`.

**Use case**: "We have N restaurants in your area" — lead encouragement before signup.

---

## GET /api/v1/leads/zipcode-metrics

**Query**: `zip` (required), `country_code` (optional, default US).

**Response**: `restaurant_count`, `has_coverage`, `matched_zipcode`.

**Use case**: Same as city-metrics; prefer city-metrics for new flows.

---

## GET /api/v1/leads/email-registered

**Query**: `email` (required).

**Response**: `{ "registered": true|false }`.

**Use case**: After city/zipcode step, check if email exists to route user to login vs signup.

---

## Related

- [MARKETS_API_CLIENT.md](../b2b_client/MARKETS_API_CLIENT.md) — Authenticated markets (full data, `market_id`)
- [MARKET_SELECTION_AT_SIGNUP.md](../b2c_client/MARKET_SELECTION_AT_SIGNUP.md) — B2C signup flow
- [ZIPCODE_METRICS_LEAD_API.md](./ZIPCODE_METRICS_LEAD_API.md) — Zipcode metrics detail
