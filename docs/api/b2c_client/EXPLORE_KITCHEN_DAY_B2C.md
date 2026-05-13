# Enforced kitchen day for B2C restaurant explore (authorized users)

**Audience:** B2C agent and app developers  
**Purpose:** Single reference for the **enforced kitchen day** rule when authorized (logged-in) users explore restaurants. Full explore API spec: [feedback_from_client/RESTAURANT_EXPLORE_B2C.md](./feedback_from_client/RESTAURANT_EXPLORE_B2C.md).

---

## Who this applies to

- **Authorized users**: Customer or Employee with a valid `Authorization: Bearer <access_token>`.
- **Endpoints**: `GET /api/v1/restaurants/cities` and **`GET /api/v1/restaurants/by-city`** (list + map + viandas).

Suppliers get **403** on these endpoints. Unauthenticated users use the **lead flow** (cities, city-metrics) and do not get restaurant list or viandas.

---

## Enforced kitchen day rule

When the explore request is **market-scoped** (user has a market and the app uses it — either by sending `market_id` or by the backend using the user’s primary market):

1. **`kitchen_day` is required.**  
   The client **must** send `kitchen_day` as a query parameter. If it is omitted, the API returns **400 Bad Request** with a message that `kitchen_day` is required when using a market.

2. **Allowed values:** Exactly one weekday name: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, or `Friday`. Any other value returns **400**.

3. **Allowed window:** The **next occurrence** of that weekday from today (in the **market’s timezone**) must fall within **this week or next week, with next week ending on Friday**. If that date is after next week’s Friday, the API returns **400**. All date logic uses the market’s timezone.

4. **Viandas in response:** Only when `kitchen_day` is sent and valid does the response include `restaurants[].viandas` for that kitchen day. Without a valid `kitchen_day`, no viandas are returned (and if the request was market-scoped without `kitchen_day`, the request fails with 400).

5. **Kitchen-day dropdown (closest first):** Use **GET /api/v1/restaurants/explore/kitchen-days** (with `market_id` or primary market) to get the list of allowed kitchen days **ordered by date, closest first**. Default to the first item so the selector shows the closest available day (e.g. Tuesday if today is Tuesday). See [feedback_from_client/RESTAURANT_EXPLORE_B2C.md](./feedback_from_client/RESTAURANT_EXPLORE_B2C.md) for the full contract.

---

## Summary for the B2C agent

| Context | kitchen_day |
|--------|--------------|
| **Market-scoped explore** (user has market; list/map + viandas) | **Required.** Send one of `Monday`–`Friday`. Must be in window: this week or next week through Friday (market timezone). Omit → **400**. |
| **No market** (e.g. user has no primary market) | Optional; no viandas returned. |

**Full spec** (cities, by-city params, response shape, UI picker, leads vs explore): [feedback_from_client/RESTAURANT_EXPLORE_B2C.md](./feedback_from_client/RESTAURANT_EXPLORE_B2C.md).

**Restaurant visibility:** Only **Active** restaurants with at least one **active** vianda_kitchen_day appear. See [../shared_client/RESTAURANT_STATUS_AND_VIANDA_KITCHEN_DAYS.md](../shared_client/RESTAURANT_STATUS_AND_VIANDA_KITCHEN_DAYS.md).
