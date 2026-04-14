# B2C Leads Endpoints Migration

**Audience**: B2C app (kitchen-mobile, React Native)  
**Purpose**: Migration guide for the market country dropdown endpoint change.

---

## Breaking change: Market country dropdown moved

| Old | New |
|-----|-----|
| `GET /api/v1/markets/available` | `GET /api/v1/leads/markets` |

**Response shape unchanged**: `[{ "country_code": "AR", "country_name": "Argentina" }, ...]`

---

## What to update

1. **Signup flow**: Replace `GET /api/v1/markets/available` with `GET /api/v1/leads/markets` when loading the country dropdown.
2. **Unauthenticated home**: If the app loads markets on the public/landing page, switch to `GET /api/v1/leads/markets`.

No changes to request parameters or response parsing. The new endpoint is under `/leads/` to make unauthenticated endpoints explicit.

---

## Why

All unauthenticated lead-capture endpoints now live under `/api/v1/leads/` for clear API organization:

- `GET /api/v1/leads/markets` — Country list (country_code, country_name only)
- `GET /api/v1/leads/cities` — City list
- `GET /api/v1/leads/city-metrics` — Coverage metrics
- `GET /api/v1/leads/zipcode-metrics` — Zipcode metrics
- `GET /api/v1/leads/email-registered` — Email check

For authenticated flows that need `market_id` (e.g., plans, subscriptions), use `GET /api/v1/markets/enriched/`.

---

## Related

- [MARKET_CITY_COUNTRY.md](./MARKET_CITY_COUNTRY.md)
- [LEADS_API_SCOPE.md](../shared_client/LEADS_API_SCOPE.md)
