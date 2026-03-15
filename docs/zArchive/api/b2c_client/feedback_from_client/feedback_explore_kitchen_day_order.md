# Feedback: Explore kitchen day selector — default to closest day

**Context:** On the Explore screen (market-scoped), the user picks a **kitchen day** (Monday–Friday, this week or next week through Friday per EXPLORE_KITCHEN_DAY_B2C.md). The client needs a sensible **default** so the selector is not always "Monday" when Monday is next week.

**Ask:** If the backend exposes an endpoint or response field that returns the **list of allowed kitchen days** for the current window (e.g. for explore), return them **ordered by date, closest first** (e.g. today if it’s a weekday, then the next weekday, etc.). That way the client can default to the first item and show the closest available day (e.g. Tuesday if today is Tuesday, Monday if today is Saturday).

**Implemented:** The backend now provides **GET /api/v1/restaurants/explore/kitchen-days** (with `market_id` or primary market). Response: `{ "kitchen_days": [ { "kitchen_day": "Tuesday", "date": "2026-03-03" }, ... ] }` ordered by date ascending (closest first). The client can call this endpoint, default to the first item, and remove any local ordering logic. See [feedback_from_client/RESTAURANT_EXPLORE_B2C.md](./feedback_from_client/RESTAURANT_EXPLORE_B2C.md) and [EXPLORE_KITCHEN_DAY_B2C.md](./EXPLORE_KITCHEN_DAY_B2C.md).
