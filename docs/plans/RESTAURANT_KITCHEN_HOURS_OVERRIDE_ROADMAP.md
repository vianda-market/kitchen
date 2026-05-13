# Restaurant-Level Kitchen Hours Override — Roadmap

**Status:** Active (revived 2026-04-30)
**Scope:** B2B / Admin + restaurant self-service
**Related:** [feedback_pickup_window_selection.md](../api/b2c_client/feedback_pickup_window_selection.md)

---

## Context

Today, pickup windows and kitchen hours are defined at the **market level** via `MarketConfiguration.business_hours` (e.g. AR, PE, US). All restaurants in a market share the same open/close times.

Restaurants need to define their own operating hours within the market's envelope. This is **not** a change to the billing-cron's notion of a kitchen day — that boundary stays market-level. This is purely about when a specific restaurant accepts orders and serves pickups.

---

## Constraints (from product)

1. **Restaurant defines two times per kitchen day, per weekday:**
   - **Open** — orders lock in (the restaurant starts taking orders for that day's pickups).
   - **Close** — orders cannot be placed and pickups cannot occur after this time.
2. **Bounded by a market-level envelope.** The restaurant's open cannot precede the market's earliest allowed open; the restaurant's close cannot exceed the market's latest allowed close. Threshold values live with market config and are admin-tunable.
3. **Decoupled from the billing cron.** The cron that closes the kitchen day for billing/settlement still uses the market boundary. Restaurant overrides only affect order-taking and pickup availability, not the billing window.
4. **Per-weekday granularity.** A restaurant may run different hours Mon–Fri vs. Sat. Days the restaurant is closed have no row (or an explicit closed flag).
5. **Fallback.** If a restaurant has no override for a given weekday, it inherits the market's business hours for that day.

---

## Current State

- **Market config:** `app/config/market_config.py` — `business_hours` per weekday (open/close) for each market.
- **Pickup windows:** `get_pickup_windows_for_kitchen_day()` uses market `business_hours` only.
- **Vianda selection:** `pickup_time_range` validation uses market windows.
- **Billing cron:** uses the market kitchen-day boundary; must remain unchanged by this work.

---

## Phases

### Phase 1: Schema + envelope

Add the override table plus envelope thresholds on the market.

```sql
-- Restaurant-level override
CREATE TABLE ops.restaurant_kitchen_hours (
  restaurant_id UUID NOT NULL REFERENCES ops.restaurant_info(restaurant_id),
  weekday VARCHAR(10) NOT NULL,  -- Monday..Sunday
  open_time TIME NOT NULL,
  close_time TIME NOT NULL,
  is_closed BOOLEAN NOT NULL DEFAULT FALSE,
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (restaurant_id, weekday)
);

-- Envelope thresholds on market (bounds for what a restaurant can choose)
ALTER TABLE core.market_info
  ADD COLUMN earliest_allowed_open  TIME,
  ADD COLUMN latest_allowed_close   TIME;
```

Mirror into `audit.restaurant_kitchen_hours_history` and `audit.market_history` per the schema-change protocol.

### Phase 2: Service layer

- New service `restaurant_hours_service.py` exposes `get_effective_hours(restaurant_id, weekday) -> (open, close, is_closed)`. Returns the override row if present, else falls back to market `business_hours`.
- Refactor `get_pickup_windows_for_kitchen_day()` to take optional `restaurant_id` and use `get_effective_hours`.
- Validation helper rejects override values outside `(market.earliest_allowed_open, market.latest_allowed_close)`.

### Phase 3: API

- `GET /api/v1/restaurants/{id}/kitchen-hours` — returns the 7-day matrix (effective values, with `source: "override" | "market"` per row).
- `PUT /api/v1/restaurants/{id}/kitchen-hours` — Supplier-scoped (restaurant owner) or Internal Admin. Validates against the market envelope; rejects out-of-bounds with `envelope_exception` (`hours.out_of_envelope`).
- `/pickup-windows` route accepts optional `restaurant_id`.
- Vianda-selection validation pulls from effective hours when a restaurant context is present.

### Phase 4: Frontend

- **vianda-platform (B2B Supplier):** Restaurant settings page — kitchen-hours editor (per-weekday open/close, "closed today" toggle), with the envelope as input min/max. Out-of-bounds errors render inline.
- **vianda-app (B2C):** No UI change — pickup-window selection automatically narrows to the restaurant's effective hours via the existing endpoint.

---

## Non-goals

- The billing-cron kitchen-day boundary is **out of scope**. It remains market-level.
- Restaurant-specific timezones (different from market timezone) — not in this roadmap.
- Holiday / one-off date overrides — separate future feature.

---

## Open questions

- Should `earliest_allowed_open` / `latest_allowed_close` be per-weekday on the market, or a single pair? (Default: single pair to start; revisit if Saturday rules need different bounds.)
- How does the system represent a restaurant being closed for an entire weekday — `is_closed = TRUE` row, or no row + an `operating_days` set on `restaurant_info`?
- Should overrides require admin approval before going live? (Default: no — supplier self-service within the envelope. Audit table provides the trail.)

---

## Dependencies

- Market `business_hours` model in `app/config/market_config.py`.
- `feedback_pickup_window_selection.md` (B2C pickup-window selection — implemented, uses market config).
