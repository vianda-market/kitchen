# Vianda recommendation and favorites (B2C)

**Audience:** B2C app developers  
**Purpose:** Integrate the recommendation layer, Recommended badges, and favorite heart signals on viandas and restaurants in the explore flow. Includes the Favorites API for add/remove actions.

---

## Overview

The explore flow (`GET /api/v1/restaurants/by-city`) returns two flags per vianda and per restaurant:

| Flag | Meaning | UI treatment |
|------|---------|---------------|
| `is_favorite` | User has explicitly favorited this vianda or restaurant | Heart icon (filled when true, outline when false). Tapping toggles favorite. |
| `is_recommended` | Backend recommends this item based on user preferences (e.g. favorited vianda, favorited restaurant) | "Recommended" badge. Read-only; do not toggle. |

Both flags are **only meaningful when the user is authenticated as a Customer**. When unauthenticated or when the user is an Employee, both are `false`.

---

## When values are present

- **Authenticated Customer:** `is_favorite` and `is_recommended` are computed per vianda and per restaurant. The backend sorts recommended items to the top.
- **Unauthenticated or Employee:** Both flags are `false` for all items. No favorites API access for Employees (Customer-only).

---

## Response shape (GET /restaurants/by-city)

Each restaurant in `restaurants[]` has:

```json
{
  "restaurant_id": "uuid",
  "name": "Restaurant Name",
  "cuisine": "Italian",
  "lat": -34.6,
  "lng": -58.4,
  "postal_code": "C1234",
  "city": "Buenos Aires",
  "street_type": "Av",
  "street_name": "Santa Fe",
  "building_number": "100",
  "is_favorite": false,
  "is_recommended": false,
  "viandas": [
    {
      "vianda_id": "uuid",
      "product_name": "Pasta",
      "price": 12.5,
      "credit": 8,
      "kitchen_day": "Wednesday",
      "image_url": "https://...",
      "savings": 30,
      "average_stars": 4.2,
      "average_portion_size": 2.1,
      "review_count": 15,
      "is_favorite": false,
      "is_recommended": false
    }
  ]
}
```

- **`is_favorite`** — `true` if the current Customer has favorited this vianda or restaurant.
- **`is_recommended`** — `true` when the recommendation score meets the threshold. Items are recommended when:
  - The user favorited this vianda, or
  - The user favorited this restaurant (all viandas from that restaurant are recommended).

The backend **already sorts** recommended viandas and restaurants to the top. The client should render items in the order returned.

---

## UI integration

### 1. Favorite heart (viandas and restaurants)

- **Location:** On each vianda card and on each restaurant row/card.
- **States:**
  - Filled heart when `is_favorite === true`
  - Outline heart when `is_favorite === false`
- **Action:** Tapping toggles the favorite:
  - If not favorited → `POST /api/v1/favorites/` with `{ "entity_type": "vianda" | "restaurant", "entity_id": "<vianda_id|restaurant_id>" }`
  - If favorited → `DELETE /api/v1/favorites/{entity_type}/{entity_id}`
- **Optimistic update:** After a successful API call, update local state and/or refetch explore data so the heart and sort order reflect the change.

### 2. Recommended badge

- **Location:** On vianda cards and restaurant cards that have `is_recommended === true`.
- **Display:** A badge such as "Recommended", "For you", or similar. Style to stand out (e.g. accent color, small pill).
- **Read-only:** The badge is informational. Do not add a toggle or action.

### 3. Sort order

The API returns restaurants and viandas **already sorted** with recommended items first. The client should render in the order received. No client-side re-sorting is needed.

---

## Favorites API (Customer-only)

All favorites endpoints require **Customer** role. Employees and Suppliers receive **403**.

**Auth:** `Authorization: Bearer <access_token>`

### POST /api/v1/favorites/

Add a favorite.

**Request body:**
```json
{
  "entity_type": "vianda",
  "entity_id": "019cc8e6-bd1f-752d-a06a-1f39c0a135ef"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_type` | string | Yes | `"vianda"` or `"restaurant"` |
| `entity_id` | UUID | Yes | `vianda_id` or `restaurant_id` |

**Response:** `201 Created` with favorite record:
```json
{
  "favorite_id": "uuid",
  "user_id": "uuid",
  "entity_type": "vianda",
  "entity_id": "uuid",
  "created_date": "2026-03-06T12:00:00Z"
}
```

**Errors:**
- `400` — Invalid `entity_type`, already favorited, or entity not found
- `404` — Vianda or restaurant not found

### DELETE /api/v1/favorites/{entity_type}/{entity_id}

Remove a favorite. Idempotent (no-op if not favorited).

**Path params:** `entity_type` = `vianda` or `restaurant`, `entity_id` = UUID

**Response:** `204 No Content`

### GET /api/v1/favorites/me

List all favorites. Optional filter by `entity_type`.

**Query params:** `entity_type` (optional) — `vianda` or `restaurant`

**Response:** Array of favorite objects (same shape as POST response).

### GET /api/v1/favorites/me/ids

Lightweight list of favorite IDs for client use (e.g. pre-populating state before explore load).

**Response:**
```json
{
  "vianda_ids": ["uuid", "uuid"],
  "restaurant_ids": ["uuid"]
}
```

---

## Entity type values

Use `entity_type` values exactly as shown: `"vianda"` or `"restaurant"`.

For dropdowns or validation, the enum can be fetched from:
- `GET /api/v1/enums/` — returns all enums; look for `favorite_entity_type`
- `GET /api/v1/enums/favorite_entity_type` — returns `["vianda", "restaurant"]`

---

## Client flow summary

1. **Explore load:** Call `GET /api/v1/restaurants/by-city` with `city`, `country_code`, `market_id`, `kitchen_day`. Ensure the user is logged in as Customer to get personalized `is_favorite` and `is_recommended`.
2. **Render:** Show viandas and restaurants in the order returned. Display heart (filled/outline) and Recommended badge based on the flags.
3. **Toggle favorite:** On heart tap, call `POST /api/v1/favorites/` or `DELETE /api/v1/favorites/{entity_type}/{entity_id}`. Refresh explore or update local state.
4. **Optional preload:** Before explore, call `GET /api/v1/favorites/me/ids` to have favorite IDs available for optimistic UI if needed.

---

## Refresh behavior

When the user adds or removes a favorite, the explore list order can change (recommended items move to the top). After a successful add/remove:

- **Option A:** Refetch `GET /api/v1/restaurants/by-city` to get the new order and flags.
- **Option B:** Optimistically update `is_favorite` locally and optionally refetch in the background. Recommended items may not reorder until the next full fetch.

Prefer refetching after favorite changes so the user sees the updated sort order immediately.

---

## Pagination

The explore endpoint (`GET /api/v1/restaurants/by-city`) supports **cursor-based infinite scroll pagination**. When `cursor` and/or `limit` query params are provided, the response includes `next_cursor` and `has_more` fields for paging through results.

- Favorites and recommendation sorting are applied **before** pagination — recommended items always appear first, even across pages.
- Sort order is stable within a browsing session. If the user adds/removes a favorite mid-scroll, the change takes effect on the next full explore reload (pull-to-refresh).
- The `center` (city lat/lng) is only returned on the first page. Cache it client-side.

For full pagination details, query params, and examples, see:
[EXPLORE_SORTING_AND_PAGINATION.md](../shared_client/EXPLORE_SORTING_AND_PAGINATION.md)

---

## Related docs

- [EXPLORE_SORTING_AND_PAGINATION.md](../shared_client/EXPLORE_SORTING_AND_PAGINATION.md) — sorting logic, cursor pagination, FAQ
- [CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) — savings, price, credit (B2C explore)
- [EXPLORE_KITCHEN_DAY_B2C.md](./EXPLORE_KITCHEN_DAY_B2C.md) — kitchen day requirement
- [feedback_from_client/RESTAURANT_EXPLORE_B2C.md](./feedback_from_client/RESTAURANT_EXPLORE_B2C.md) — full explore spec
