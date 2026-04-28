# Generic Server-Side Pagination

**Date**: April 2026
**Audience**: B2B + B2C frontends

---

## Overview

List endpoints that support pagination accept optional `page` and `page_size` query params and return an `X-Total-Count` response header. When neither param is sent, the endpoint returns all records as before (fully backward compatible).

---

## Contract

### Request — Query Parameters

| Param | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `page` | int | _(none)_ | `>= 1` | 1-based page number |
| `page_size` | int | _(none)_ | `1–100` | Rows per page (clamped server-side) |

Both must be sent together. If only one is sent, pagination is not activated.

### Response — Headers

| Header | When Present | Value | Example |
|--------|-------------|-------|---------|
| `X-Total-Count` | Only when `page` + `page_size` are sent | Total matching records (before pagination) | `1842` |
| `Access-Control-Expose-Headers` | Same | `X-Total-Count` | — |

### Response — Body

**No change.** The response body is still a JSON array — no wrapper envelope. The array contains only the records for the requested page.

---

## Which Endpoints Support Pagination

Pagination is **opt-in per endpoint**. Not all list endpoints accept `page`/`page_size`.

### CRUD List Endpoints (`GET /api/v1/{entity}`)

| Endpoint | Paginated |
|----------|-----------|
| `/products` | Yes |
| `/plates` | Yes |
| `/plans` | Yes |
| `/subscriptions` | Yes |
| `/institutions` | Yes |
| `/institution-entities` | Yes |
| `/credit-currencies` | Yes |
| `/payment-methods` | Yes |
| `/qr-codes` | Yes |
| `/geolocations` | Yes |
| `/plate-selections` | Yes |
| `/countries` | No — small reference data |
| `/currencies` | No — small reference data |
| `/cities` | No — small reference data |
| `/provinces` | No — small reference data |
| `/cuisines` | No — small reference data |
| `/enums/*` | No — small reference data |

### Enriched List Endpoints (`GET /api/v1/{entity}/enriched`)

| Endpoint | Paginated |
|----------|-----------|
| `/users/enriched` | Yes |
| `/institution-entities/enriched` | Yes |
| `/addresses/enriched` | Yes |
| `/addresses/enriched/search` | Yes |
| `/restaurants/enriched` | Yes |
| `/qr-codes/enriched` | Yes |
| `/plate-kitchen-days/enriched` | Yes |
| `/restaurant-balances/enriched` | Yes |
| `/restaurant-transactions/enriched` | Yes |
| `/employers/enriched` | Yes |
| `/institution-bills/enriched` | Yes |
| `/payouts/enriched` | Yes |
| `/supplier-invoices/enriched` | Yes |
| `/admin/markets/enriched` | Yes |
| `/super-admin/discretionary` | Yes |
| `/national-holidays` | Yes |

---

## Frontend Integration

### Basic Usage

```typescript
// Send page + page_size as query params
const response = await fetch(`/api/v1/institutions?page=1&page_size=20`, {
  headers: { Authorization: `Bearer ${token}` },
});

const totalCount = parseInt(response.headers.get("X-Total-Count") ?? "0", 10);
const items = await response.json(); // Array of items for this page
```

### With `usePaginatedData` Hook (B2B)

The existing `usePaginatedData` hook already sends `page` and `page_size` and reads `X-Total-Count`. No hook changes are needed — just point it at any paginated endpoint.

### Without Pagination (Backward Compatible)

```typescript
// Omit page/page_size → get all records, no X-Total-Count header
const response = await fetch(`/api/v1/institutions`);
const allItems = await response.json(); // Complete array
```

---

## Behavior Notes

- **Sorting**: Results are sorted by primary key descending (newest first, UUID7 monotonic). Stable across pages.
- **Out-of-range pages**: If `page` exceeds available data, an empty array is returned with `X-Total-Count` reflecting the true total.
- **Clamping**: `page_size` is clamped to `[1, 100]` server-side regardless of what the client sends.
- **Scoping**: Pagination respects institution scoping — `X-Total-Count` reflects the count within the user's scope, not the global total.
- **OpenAPI spec**: Only opted-in endpoints show `page` and `page_size` query params in `/docs`. Non-paginated endpoints do not expose these params.

---

*Last Updated: April 2026*
