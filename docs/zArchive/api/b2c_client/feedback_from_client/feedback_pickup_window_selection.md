# Feedback: Pickup window selection for plate reservation (B2C)

**Purpose:** The B2C app needs to show a "Select pickup window" modal when the user taps "Reserve for [Day]" in the Explore Plate Modal. The client must display 15-minute time windows from when the kitchen day opens until when it closes for the market. The selected window is sent as `pickup_time_range` to `POST /api/v1/plate-selections/`.

**Audience:** Backend team.

---

## Context

When a Customer reserves a plate from the Explore screen:

1. User taps a plate card → Explore Plate Modal opens.
2. User taps "Reserve for [Day]" → A second modal should open: **Select pickup window**.
3. Modal shows: "You are reserving a plate for [Day]" and a scrollable list of 15-minute windows (e.g. 11:30–11:45, 11:45–12:00, 12:00–12:15, …).
4. User selects a window → Client calls `POST /api/v1/plate-selections/` with `plate_id`, `pickup_time_range` (e.g. `"12:00-12:15"`), and `target_kitchen_day`.

Per [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md), `pickup_time_range` must be within the **allowed pickup hours** (e.g. 11:30–14:30 local). The docs mention "kitchen close (per market config)" in [RESTAURANT_EXPLORE_B2C.md](./RESTAURANT_EXPLORE_B2C.md), but the client has no way to obtain these times today.

---

## Ask

**Expose the kitchen day open and close times** (or equivalent pickup window bounds) so the B2C client can generate the list of 15-minute windows for the "Select pickup window" modal.

Two implementation options:

### Option A: Pickup windows endpoint (preferred)

Add an endpoint that returns the list of available 15-minute pickup windows for a given kitchen day and market:

```http
GET /api/v1/restaurants/explore/pickup-windows?market_id={uuid}&kitchen_day={Monday|Tuesday|...}&date={YYYY-MM-DD}
```

- `market_id` — Optional; when omitted, use the user's primary market.
- `kitchen_day` — Required. One of `Monday`–`Friday`.
- `date` — Optional. The concrete date for the kitchen day (e.g. from `GET /api/v1/restaurants/explore/kitchen-days`). When omitted, backend can derive from kitchen_day + market timezone.

**Response:**

```json
{
  "kitchen_day": "Wednesday",
  "date": "2026-03-12",
  "pickup_windows": [
    "11:30-11:45",
    "11:45-12:00",
    "12:00-12:15",
    "12:15-12:30",
    "12:30-12:45",
    "12:45-13:00",
    "13:00-13:15",
    "13:15-13:30",
    "13:30-13:45",
    "13:45-14:00",
    "14:00-14:15",
    "14:15-14:30"
  ]
}
```

- Times in **market local time** (HH:MM format, 24h).
- Windows are 15 minutes, non-overlapping, from kitchen open to kitchen close.
- Backend applies market config (and any holidays/restaurant-specific rules) so the client does not need to know open/close logic.

### Option B: Market-level open/close times

If a dedicated endpoint is not feasible, add to the **market** (or kitchen-days) response:

- `kitchen_day_open_time` — e.g. `"11:30"` (HH:MM, market local).
- `kitchen_day_close_time` — e.g. `"14:30"` (HH:MM, market local).

The client would then generate 15-minute windows between open and close. This requires the client to handle timezone and edge cases; Option A is preferred.

**Suggested locations if Option B:**

- Extend `GET /api/v1/markets/available` or `GET /api/v1/markets/enriched/{market_id}` with `kitchen_day_open_time` and `kitchen_day_close_time`.
- Or extend `GET /api/v1/restaurants/explore/kitchen-days` so each item includes `open_time` and `close_time` for that day.

---

## Questions for backend

1. **Does the market (or equivalent config) already have kitchen day open/close times?**  
   RESTAURANT_EXPLORE_B2C.md references "kitchen close (per market config)" — if this exists, can it be exposed via API?

2. **Are pickup hours the same for all kitchen days in a market?**  
   Or do they vary by day (e.g. different hours on Friday)?

3. **Timezone:**  
   All times should be in the market's timezone (per [MARKETS_API_CLIENT.md](../shared_client/MARKETS_API_CLIENT.md), market has `timezone`). Confirm that pickup windows are always expressed in market local time.

---

## Implementation (Option A)

**Implemented.** The B2C client can use:

- **GET /api/v1/restaurants/explore/pickup-windows** — Returns 15-minute pickup windows for a kitchen day and market. Params: `kitchen_day` (required), `date` (optional, ISO YYYY-MM-DD), `market_id` (optional). When `date` is omitted, the backend uses the next occurrence of `kitchen_day` in the market timezone.
- **pickup_time_range validation** — `POST /api/v1/plate-selections/` validates that `pickup_time_range` is within the market's allowed windows (from `business_hours` in market config). Invalid windows return 400 with allowed windows in the error detail.
- **Default pickup open** — Market `business_hours` open time is 11:30 (kitchen open) for AR, PE, US.

See [RESTAURANT_EXPLORE_B2C.md](./RESTAURANT_EXPLORE_B2C.md) and [B2C_ENDPOINTS_OVERVIEW.md](./B2C_ENDPOINTS_OVERVIEW.md) for full endpoint documentation.

---

## Related docs

- [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md) — Plate selection API, `pickup_time_range` format
- [RESTAURANT_EXPLORE_B2C.md](./RESTAURANT_EXPLORE_B2C.md) — kitchen_day, "kitchen close (per market config)"
- [EXPLORE_KITCHEN_DAY_B2C.md](./EXPLORE_KITCHEN_DAY_B2C.md) — Kitchen day rules, `GET /api/v1/restaurants/explore/kitchen-days`
- [MARKETS_API_CLIENT.md](../shared_client/MARKETS_API_CLIENT.md) — Market structure, timezone
