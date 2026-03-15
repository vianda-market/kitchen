# B2C city coverage and restaurant explore

This document is the single reference for **city-based coverage and explore** in the B2C app. It encompasses:

1. **Unauthenticated lead flow** — Visitors enter email and city; we show that we serve their area (aggregate metrics only, no restaurant list). Uses `GET /api/v1/leads/cities` and `GET /api/v1/leads/city-metrics`.
2. **Authenticated explore flow** — Registered users (Customer or Employee) get full restaurant detail (list + map) and, when using a market, can see **plates for a chosen kitchen day** (required; must be this week or next week through Friday). Uses `GET /api/v1/restaurants/cities` and `GET /api/v1/restaurants/by-city`.
3. **Backend alignment** — The same set of cities per country must be returned for both flows so the Explore tab dropdown matches the lead flow; implementation notes and acceptance criteria are in **Part 3** (backend-only; client teams can skip it).

**For client integration**

- **Base URL:** Use your environment’s API base (e.g. `https://api.example.com`). All paths below are relative to that base (e.g. `GET /api/v1/restaurants/cities`).
- **Authenticated endpoints** (`GET /api/v1/restaurants/cities`, `GET /api/v1/restaurants/by-city`): send **`Authorization: Bearer <access_token>`** in the request header. Obtain the token via your login flow (e.g. `POST /api/v1/auth/token`).
- **When `kitchen_day` and `plates` are present:** The response includes `kitchen_day` and `restaurants[].plates` only when the request is scoped to a market (either you send `market_id` or the backend uses the user’s primary market). If there is no market (e.g. user has no primary market), the response has no `kitchen_day` and each restaurant has no `plates` (or `plates` is omitted).
- **kitchen_day for UI:** Send a single weekday name (`Monday`–`Friday`). The backend resolves it to the **next occurrence** of that day from today in the market's timezone (no "this" vs "next" in the API). See "Client UI: kitchen_day picker" under GET /restaurants/by-city.
- **Visibility:** All explore and leads endpoints return **only Active restaurants** that have at least one **active** plate_kitchen_day (non-archived and status Active). Pending or Inactive restaurants, or restaurants with no such plate_kitchen_days, are excluded. See [RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md](../../shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md) for full rules.

---

## Part 1 — Unauthenticated lead flow

**Purpose:** Encourage signup by showing “we serve your area” without exposing the full restaurant list.

- **City first** (not zipcode) so coverage grows at city level; zipcode refinement can be added later.
- **No** `Authorization` header; rate limit per IP (e.g. 60 req/min); **429** when exceeded.

**Error responses (lead flow):** `200` — success. `429 Too Many Requests` — rate limit exceeded (retry after the indicated delay or after the window resets).

### GET /api/v1/leads/cities

| Parameter      | Required | Description |
|----------------|----------|-------------|
| `country_code` | No       | ISO 3166-1 alpha-2 (e.g. `US`, `AR`). **Default: `US`** when omitted. |

**Response:** `{ "cities": ["Buenos Aires", "Córdoba", ...] }` — city names that have at least one **Active** restaurant with plate_kitchen_days in that country.

### GET /api/v1/leads/city-metrics

When the lead picks a city, the app shows a short summary (e.g. “We have N restaurants in your area”). **No full restaurant list** is returned.

| Parameter      | Required | Description |
|----------------|----------|-------------|
| `city`         | Yes      | City name (e.g. "Buenos Aires"). Case-insensitive match. |
| `country_code` | No       | ISO 3166-1 alpha-2. **Default: `US`**. Normalized to uppercase. |

**Metrics:** Restaurant count, `has_coverage` (count > 0), matched city. No geolocation data (e.g. `center`) in the unauthenticated response.

**Response example:**

```json
{
  "requested_city": "Buenos Aires",
  "matched_city": "Buenos Aires",
  "restaurant_count": 12,
  "has_coverage": true
}
```

### Legacy

- **`GET /api/v1/leads/zipcode-metrics?zip=...&country_code=...`** remains available; new flows should prefer **city-metrics** first.

### Optional later

- A route for “we don’t serve your city yet” (lead submits province, city, zipcode + email) may be added; no restaurant data exposed.

---

## Part 2 — Authenticated explore flow (restaurants + plates)

**Purpose:** Registered users (Customer or Employee) see full restaurant detail for **list and map**, and can explore **plates for a chosen kitchen day** (required when using a market; must be this week or next week through Friday). Only **Active** restaurants with at least one active plate_kitchen_day are returned (see [RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md](../../shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md)).

**Auth:** Send **`Authorization: Bearer <access_token>`** on every request. **Customer or Employee only** — Suppliers receive **403**. No institution scope.

**Error responses (explore flow):** `200` — success. `400 Bad Request` — e.g. missing `kitchen_day` when using a market; invalid `kitchen_day` (must be Monday–Friday); or `kitchen_day` outside the allowed window (this week or next week through Friday). `401 Unauthorized` — missing or invalid token. `403 Forbidden` — e.g. Supplier role, or `market_id` not one of the user’s assigned markets. `404 Not Found` — e.g. market not found when `market_id` is provided.

### GET /api/v1/restaurants/cities

| Parameter      | Required | Description |
|----------------|----------|-------------|
| `country_code` | No       | ISO 3166-1 alpha-2 (e.g. `US`, `AR`). **Default: `US`** when omitted. |

**Response:** `{ "cities": ["Buenos Aires", "Córdoba", ...] }` — city names that have at least one **Active** restaurant with plate_kitchen_days in that country. Used to populate the Explore city dropdown; the user then picks a city and calls **by-city** below.

### GET /api/v1/restaurants/explore/kitchen-days

Returns the list of **allowed kitchen days** for the explore window (today through next week's Friday in the market's timezone), **ordered by date ascending (closest first)**. Use this to populate the kitchen-day dropdown and default to the first item (the closest available day).

| Parameter   | Required | Description |
|-------------|----------|-------------|
| `market_id` | No       | Market UUID for timezone. If omitted, the backend uses the current user's primary market. |

**Auth:** Bearer required. Customer or Employee only. `market_id` must be one of the user's assigned markets (403 otherwise). If the user has no market (no primary and none sent), the API returns **400**.

**Response (200):**

```json
{
  "kitchen_days": [
    { "kitchen_day": "Tuesday", "date": "2026-03-03" },
    { "kitchen_day": "Wednesday", "date": "2026-03-04" },
    { "kitchen_day": "Thursday", "date": "2026-03-05" },
    { "kitchen_day": "Friday", "date": "2026-03-06" },
    { "kitchen_day": "Monday", "date": "2026-03-10" },
    ...
  ]
}
```

- **kitchen_days**: Allowed weekdays in the window, **ordered by date (closest first)**. Each item has `kitchen_day` (weekday name) and `date` (ISO YYYY-MM-DD). Use the first item as the default for the dropdown; display e.g. "Tuesday (Mar 3)" using the `date` field.

### GET /api/v1/restaurants/by-city

```
GET /api/v1/restaurants/by-city?city={city}&country_code={country_code}&market_id={market_id}&kitchen_day={kitchen_day}
```

| Parameter     | Required | Description |
|---------------|----------|-------------|
| `city`        | Yes      | City name (from dropdown). Case-insensitive match. |
| `country_code`| No       | ISO 3166-1 alpha-2. **Default: `US`** when omitted (or derived from user's market when `market_id` is used). |
| `market_id`   | No       | User's market UUID. If omitted, the backend uses the current user's primary market. Restaurants are restricted to this market (by `country_code`). |
| `kitchen_day` | **Yes when using a market** | A **single weekday name**: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, or `Friday`. **Required** when the request is scoped to a market (so that plates are returned). The backend resolves this to the **next occurrence** of that weekday from today (in the market's timezone). That date must fall within this week or next week (next week ends on Friday); otherwise the API returns **400**. There is no separate "this Wednesday" vs "next Wednesday" — send only the weekday; the backend picks the single next occurrence. If no market is used, `kitchen_day` is optional and no plates are returned. |

**Response:** Matched city, optional center (lat/lng), the **kitchen_day** used for the response (when provided and valid), and list of restaurants in that city (in the user's market). Each restaurant includes list/map fields and **plates** for the chosen kitchen day when a market is used and `kitchen_day` was provided and within the allowed window.

#### Explore by market, city, and kitchen day

- **Market scoping:** Only restaurants whose address is in the market's country (`address_info.country_code` = market's `country_code`) are returned. When `market_id` is sent, it must be one of the user's assigned markets (403 otherwise). When omitted, the user's primary market is used.
- **kitchen_day required when using a market:** To get restaurant plates, the request must be market-scoped and include `kitchen_day`. The backend does **not** allow omitting `kitchen_day` when a market is used; if omitted, the API returns **400** with a message that `kitchen_day` is required.
- **kitchen_day window:** The backend enforces that the chosen weekday falls within **this week and next week at most, with next week ending on Friday**. The date used is the *next occurrence* of that weekday from today (in the market's timezone). If that date is after next week's Friday, the API returns **400**. All date logic (today, window, next occurrence) uses the **market's timezone**.
- **kitchen_day values:** Only `Monday`, `Tuesday`, `Wednesday`, `Thursday`, or `Friday` are valid; any other value returns **400**.

#### Client UI: kitchen_day picker

- **Single value:** Send exactly one weekday name per request. The API does not support "this Wednesday" vs "next Wednesday" — the backend always uses the **next occurrence** of the chosen weekday from today (in the market's timezone). For example, if today is Wednesday, sending `Thursday` returns tomorrow's plates; sending `Tuesday` returns next week's Tuesday.
- **Building the picker:** Call **GET /api/v1/restaurants/explore/kitchen-days** (with `market_id` or primary market) to get the list of allowed kitchen days **ordered by date, closest first**. Use the first item as the default so the selector shows the closest available day (e.g. Tuesday if today is Tuesday). Display each option using `kitchen_day` and `date` (e.g. "Tuesday (Mar 3)"). This avoids a fixed Monday–Friday order and ensures the default is always the closest day.

#### Response shape

```json
{
  "requested_city": "Buenos Aires",
  "city": "Buenos Aires",
  "center": { "lat": -34.6037, "lng": -58.3816 },
  "kitchen_day": "Monday",
  "restaurants": [
    {
      "restaurant_id": "uuid",
      "name": "Restaurant A",
      "cuisine": "Italian",
      "lat": -34.6130,
      "lng": -58.3862,
      "postal_code": "C1425",
      "city": "Buenos Aires",
      "has_volunteer": false,
      "has_coworker_offer": true,
      "has_coworker_request": false,
      "plates": [
        {
          "plate_id": "uuid",
          "product_name": "Pasta",
          "image_url": "https://.../thumb.png",
          "credit": 100,
          "savings": 15,
          "is_recommended": false,
          "is_favorite": false,
          "is_already_reserved": false,
          "existing_plate_selection_id": null
        }
      ]
    }
  ]
}
```

- **requested_city**: Echo of the city the client sent.
- **city**: Matched city (case-insensitive).
- **center**: Optional lat/lng to center the map.
- **kitchen_day**: The day used for the response (required when using a market; must be this week or next week through Friday). Omitted when no market is in use.
- **restaurants**: Each item has `restaurant_id`, `name`, `cuisine`, `lat`, `lng`, `postal_code`, `city`, `has_volunteer`, `has_coworker_offer`, `has_coworker_request` (coworker flags when user has employer), and **plates** (lean payload: `plate_id`, `product_name`, `image_url` thumbnail, `credit`, `savings`, `is_recommended`, `is_favorite`, `is_already_reserved`, `existing_plate_selection_id`).
- **Explore Plate Modal:** Fetch full plate data via `GET /api/v1/plates/enriched/{plate_id}?kitchen_day=Monday`; when opened from Reservations, pass `kitchen_day` for `has_coworker_offer`, `has_coworker_request`. For pickup time ranges, call `GET /api/v1/restaurants/{restaurant_id}/coworker-pickup-windows?kitchen_day=Monday` when `has_coworker_offer` or `has_coworker_request`.

### Postman

Use the **Restaurant Explorer B2C** collection (file: `RESTAURANT_EXPLORER_B2C.postman_collection.json` in `docs/postman/collections/`). Run **Login** first to set `authToken`, then **GET cities** and **GET by-city**.

### Later: zipcode refinement

`GET /api/v1/restaurants/by-zipcode?zip=...&country_code=...` may be added (e.g. user picks city then refines by zipcode). Same auth and response shape, keyed by zipcode. See [docs/roadmap/B2C_EXPLORE_ZIPCODE.md](../../roadmap/B2C_EXPLORE_ZIPCODE.md).

---

## Part 3 — Backend implementation and alignment

**Audience:** Backend team. Client teams can skip this section; it does not change the API contract.

### Cities alignment (leads vs explore)

The app expects **the same set of cities per country** in both flows. If a country (e.g. Argentina) has cities in `GET /api/v1/leads/cities`, then `GET /api/v1/restaurants/cities` for that country must return the same (or a superset of) cities so the Explore dropdown is populated.

**Acceptance:** For any `country_code` (e.g. `AR`) where `GET /api/v1/leads/cities` returns a non-empty `cities` array, `GET /api/v1/restaurants/cities?country_code=AR` must also return a non-empty array (same or superset). Both can share the same source (e.g. one service/table); normalize `country_code` to uppercase and keep city names consistent.

### Endpoint summary

| Endpoint | Purpose | Auth | Notes |
|----------|---------|------|--------|
| `GET /api/v1/leads/cities?country_code=...` | City dropdown (lead flow) | None (rate-limited) | Same cities as restaurants/cities per country. |
| `GET /api/v1/leads/city-metrics?city=...&country_code=...` | “We have N restaurants” summary | None | No restaurant list. |
| `GET /api/v1/restaurants/cities?country_code=...` | City dropdown (Explore tab) | Bearer required | Same (or superset) cities per country as leads/cities. |
| `GET /api/v1/restaurants/explore/kitchen-days?market_id=...` | Kitchen-day dropdown (Explore); ordered by date, closest first | Bearer required | Returns allowed kitchen days for the window (today–next Friday); default to first item. |
| `GET /api/v1/restaurants/by-city?city=...&country_code=...&market_id=...&kitchen_day=...` | Restaurant list + map (+ plates for kitchen day) | Bearer required | Market filter by `address_info.country_code` = market’s `country_code`. kitchen_day required when market used; must be this week or next week through Friday. |

### Implementation notes (by-city)

- **City match:** Case-insensitive; consistent with `restaurants/cities` and `leads/cities`.
- **Market:** Filter restaurants by `address_info.country_code` = (SELECT `country_code` FROM `market_info` WHERE `market_id` = :market_id). When `market_id` is omitted, use the authenticated user’s primary market (`user_info.market_id` or `user_market_assignment`).
- **kitchen_day required when market used:** When the request is market-scoped, `kitchen_day` is required; do not resolve or default. Return 400 if missing.
- **kitchen_day window:** Validate that the requested weekday’s next occurrence (in market timezone) is within the allowed window: from today through next week’s Friday (inclusive). If the date is after that Friday, return 400.
- **Plates:** Join `plate_info` → `plate_kitchen_days` (non-archived and status Active) for the requested `kitchen_day`. Return restaurants with empty `plates` or omit them (backend-defined).
