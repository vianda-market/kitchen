# Restaurant-Level Kitchen Hours Override — Roadmap

**Status:** Future  
**Scope:** B2B / Admin  
**Related:** [feedback_pickup_window_selection.md](../api/b2c_client/feedback_pickup_window_selection.md), Pickup Window Selection for B2C

---

## Context

Today, pickup windows and kitchen hours are defined at the **market level** via `MarketConfiguration.business_hours` (e.g. AR, PE, US). All restaurants in a market share the same open/close times (e.g. 11:30–13:30 local).

Some restaurants may need different hours (e.g. open earlier, close later, or different hours on specific days). This roadmap outlines how to support **restaurant-level overrides** of kitchen hours.

---

## Current State

- **Market config:** `app/config/market_config.py` — `business_hours` per weekday (open/close) for each market.
- **Pickup windows:** `get_pickup_windows_for_kitchen_day()` uses market `business_hours` only.
- **Plate selection:** `pickup_time_range` validation uses market windows.

---

## Proposed Phases

### Phase 1: Database schema (optional)

Add optional restaurant-level overrides:

```sql
-- Optional: restaurant_kitchen_hours override table
CREATE TABLE restaurant_kitchen_hours (
  restaurant_id UUID NOT NULL REFERENCES restaurant_info(restaurant_id),
  kitchen_day VARCHAR(10) NOT NULL,  -- Monday..Friday
  open_time TIME NOT NULL,
  close_time TIME NOT NULL,
  is_archived BOOLEAN DEFAULT FALSE,
  modified_by UUID,
  modified_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (restaurant_id, kitchen_day)
);
```

- When a row exists for `(restaurant_id, kitchen_day)`, use it instead of market `business_hours`.
- When no row exists, fall back to market config (current behavior).

### Phase 2: B2B Admin UI

- Allow Super Admin / Market Manager to set per-restaurant, per-day open/close times.
- UI: Restaurant detail → Kitchen hours tab → Override per weekday (optional).
- Default: use market config (no override).

### Phase 3: API and service changes

- **Pickup windows:** `get_pickup_windows_for_kitchen_day()` (or a variant) accepts optional `restaurant_id`. When provided, check for restaurant override first; otherwise use market config.
- **Pickup-windows route:** Optional `restaurant_id` query param for restaurant-specific windows (e.g. when reserving a plate from a specific restaurant).
- **Plate selection validation:** When creating a selection, validate `pickup_time_range` against the **restaurant’s** windows (if overrides exist) or market windows.

---

## Out of Scope (Phase 1 B2C)

- No DB migration for restaurant overrides in the initial B2C pickup window work.
- B2C uses market-level windows only.
- This roadmap is for future B2B/admin enhancement.

---

## Dependencies

- [Pickup Window Selection for B2C](feedback_pickup_window_selection.md) — Implemented; uses market config.
- Market `business_hours` open time set to 11:30 for AR, PE, US.
