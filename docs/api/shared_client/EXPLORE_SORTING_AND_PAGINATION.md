# Explore: Vianda Sorting & Infinite Scroll Pagination

**Audience:** B2C app (vianda-app) and Supplier dashboard developers, FAQ content  
**Endpoint:** `GET /api/v1/restaurants/by-city`

---

## How Viandas and Restaurants Are Sorted

The explore endpoint returns restaurants and viandas in a **personalized order** for authenticated Customers. The backend handles all sorting — clients render items in the order received.

### Sort priority

| Priority | Criterion | Description |
|----------|-----------|-------------|
| 1 | **Recommended** | Items the system recommends for you appear first |
| 2 | **Relevance score** | Among recommended items, higher-scored ones appear first |
| 3 | **Alphabetical** | Non-recommended items (and ties) are sorted alphabetically by name |

### What makes an item "Recommended"?

An item is marked `is_recommended: true` when:

- **You favorited the vianda** — that vianda is recommended.
- **You favorited a restaurant** — all viandas from that restaurant are recommended.

The more you interact with favorites, the more personalized your explore feed becomes.

### When does the sort order change?

- **After you add or remove a favorite.** The next time the explore list loads, recommended items are recalculated and the sort order reflects your updated preferences.
- **Sort order does not change mid-scroll.** If you are paginating through results, the order stays stable within that browsing session.

### For unauthenticated users

When no user is logged in, `is_favorite` and `is_recommended` are both `false` for all items. Restaurants and viandas are sorted alphabetically.

---

## Infinite Scroll Pagination

The endpoint supports **cursor-based pagination** for infinite scroll. Pagination is opt-in — omitting the pagination params returns all results in a single response (backward compatible).

### Query parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `cursor` | string | No | `null` (first page) | Opaque cursor from the previous response's `next_cursor`. Never parse or construct this value. |
| `limit` | integer | No | 20 | Max number of **viandas** (not restaurants) per page. Clamped to 10–50. |

Existing params (`city`, `country_code`, `market_id`, `kitchen_day`) remain unchanged.

### Filter params (all optional, backward-compatible — #147–#151)

| Param | Type | Description | Validation |
|-------|------|-------------|------------|
| `cuisine` | `list[str]` | Filter by one or more cuisine names (restaurant-level, OR logic). Omit for all cuisines. Repeat param for multi-select: `?cuisine=Italian&cuisine=Mexican`. | None; mismatches return 0 restaurants. |
| `max_credits` | `integer ≥ 1` | Show only viandas costing at most N credits. Restaurants with no surviving viandas after this filter are **dropped from the response** (not returned with `viandas: []`). Frontend hardcodes option set (1/2/3/5). | `ge=1`. |
| `dietary` | `list[str]` | Filter by dietary flags (OR logic). A vianda matches if its `dietary` array contains **at least one** of the requested flags. Restaurants with no surviving viandas are **dropped**. Repeat param for multi-select: `?dietary=vegan&dietary=gluten_free`. Valid values: `vegan`, `vegetarian`, `gluten_free`, `dairy_free`, `nut_free`, `halal`, `kosher`. | Unknown flag → 400. |
| `lat` | `float` | Latitude of user's center point for distance filter. Requires `lng` and `radius_km`. | Must appear with `lng` + `radius_km`. Missing partner(s) → 400. |
| `lng` | `float` | Longitude of user's center point for distance filter. Requires `lat` and `radius_km`. | Must appear with `lat` + `radius_km`. Missing partner(s) → 400. |
| `radius_km` | `float > 0` | Radius in kilometres for distance filter. Requires `lat` and `lng`. | Must appear with `lat` + `lng`. `gt=0`. Missing partner(s) → 400. |

**`dietary_flag` enum values** are exposed via `GET /api/v1/enums/dietary_flag` (or the full enum dump at `GET /api/v1/enums/`) for filter-drawer population. Labels for `en`/`es`/`pt` are included.

**Drop-on-empty-viandas:** When `max_credits` or `dietary` narrows a restaurant's vianda list to 0, the restaurant is **removed** from the response entirely. Clients should never receive a restaurant with `viandas: []` as a result of these filters.

**Distance semantics:** City filter and radius filter are AND-composed. A restaurant 12 km from the user's home in the selected city is excluded by `radius_km=10`. This is the intended behavior (user opts into both city AND proximity).

**Cursor pagination with distance filter:** The `ST_DWithin` geo-filter is applied inside the SQL `WHERE` clause (before `LIMIT`/cursor slicing), so pagination works correctly — geo-filtered restaurants never appear on a later page.

### Response fields

| Field | Type | Description |
|-------|------|-------------|
| `restaurants` | array | This page's restaurants with their viandas |
| `next_cursor` | string or null | Pass this as `cursor` in the next request. `null` means no more results. |
| `has_more` | boolean | `true` if more results exist after this page |
| `center` | object or null | City center (lat/lng). Present on first page only; cache it client-side. |
| `requested_city` | string | City name the client sent |
| `city` | string | Matched city (may differ in casing) |

### Pagination rules

1. **Pagination is always active.** Every response includes `next_cursor` and `has_more`. When `limit` is omitted, the default (20 viandas) is used.
2. **Pagination unit is viandas.** The backend counts viandas to determine page boundaries. A restaurant is never split across pages — if any of its viandas fit, all are included.
3. **Stable sort order.** The sort is deterministic for a given city + kitchen_day + user. Pages are consistent within a session.
4. **Cursor is opaque.** Treat it as an unmodifiable string. The backend may change the encoding at any time.
5. **`next_cursor = null` means done.** When there are no more results, `next_cursor` is `null` and `has_more` is `false`.

### Example flow

```
# Page 1
GET /api/v1/restaurants/by-city?city=Miami&country_code=US&kitchen_day=wednesday&limit=15

Response:
{
  "restaurants": [...],       // ~15 viandas worth of restaurants
  "next_cursor": "eyJyaSI6M30=",
  "has_more": true,
  "center": { "lat": 25.76, "lng": -80.19 },
  ...
}

# Page 2
GET /api/v1/restaurants/by-city?city=Miami&country_code=US&kitchen_day=wednesday&limit=15&cursor=eyJyaSI6M30=

Response:
{
  "restaurants": [...],       // next batch
  "next_cursor": "eyJyaSI6Nn0=",
  "has_more": true,
  "center": null,             // omitted on page 2+
  ...
}

# Last page
GET ...&cursor=eyJyaSI6Nn0=

Response:
{
  "restaurants": [...],
  "next_cursor": null,
  "has_more": false,
  ...
}
```

### Edge cases

| Scenario | Behavior |
|----------|----------|
| City has 0 restaurants | `restaurants: []`, `next_cursor: null`, `has_more: false` |
| Total viandas < limit | Single page, `next_cursor: null`, `has_more: false` |
| Invalid or expired cursor | HTTP 400 with error message. Reset to page 1 (no cursor). |
| `limit` out of range | Silently clamped to 10–50 |

---

## Frequently Asked Questions

### Why did a vianda move to the top of the list?

You (or the system on your behalf) favorited that vianda or its restaurant. Favorited items are recommended and sorted to the top of the explore feed.

### Why don't I see "Recommended" badges?

You haven't favorited any viandas or restaurants yet. Start favoriting items you like, and the explore feed will personalize over time.

### Does the order change between pages while I'm scrolling?

No. The sort order is stable for the duration of your browsing session. If you add or remove a favorite while scrolling, the change will take effect the next time you reload the explore list (pull-to-refresh or navigate back).

### What happens if a restaurant is added or removed while I'm scrolling?

Best-effort consistency. In rare cases, an item may be skipped or appear twice across pages. The frontend deduplicates by `vianda_id` to handle this gracefully.

### Do I need to send `limit` every time?

No. When `limit` is omitted, the backend uses a default of 20 viandas per page. You can override it with any value from 1 to 50 (values outside this range are clamped).

---

## Related docs

- [VIANDA_RECOMMENDATION_AND_FAVORITES_B2C.md](../b2c_client/VIANDA_RECOMMENDATION_AND_FAVORITES_B2C.md) — Favorites API, recommendation badges
- [GENERIC_PAGINATION_CLIENT.md](./GENERIC_PAGINATION_CLIENT.md) — Offset-based pagination used on other endpoints
- [CREDIT_AND_CURRENCY_CLIENT.md](./CREDIT_AND_CURRENCY_CLIENT.md) — Savings, price, credit in explore
