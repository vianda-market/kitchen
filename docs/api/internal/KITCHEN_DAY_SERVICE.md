# Kitchen Day Service

**Source**: [app/services/kitchen_day_service.py](../../app/services/kitchen_day_service.py)

Centralized service for kitchen day logic. Single source of truth for effective current day, kitchen closed checks, and date-to-kitchen-day mapping across the platform.

---

## Overview

The Kitchen Day Service eliminates duplicate logic previously spread across `date_service`, `restaurant_explorer_service`, `institution_billing`, `restaurant_staff_service`, and `plate_selection_service`. All kitchen-day calculations now delegate here.

---

## Kitchen Close Time Resolution

Order cutoff (kitchen close) is resolved in this order:

1. **`market_info.kitchen_close_time`** (DB) – B2B manageable via PUT `/api/v1/markets/{id}`. Stored as `TIME` (e.g. `13:30`).
2. **`MarketConfiguration.kitchen_day_config[day].kitchen_close`** – Code fallback for markets not yet in DB or when column is NULL.
3. **Hardcoded `time(13, 30)`** – Final fallback.

See [KITCHEN_DAY_SLA.md](./KITCHEN_DAY_SLA.md) for business rules around order cutoff.

---

## Public API

### `get_effective_current_day(timezone_str, country_code=None) -> str`

Returns the effective kitchen day for “now” in the given timezone.

- **Before kitchen close** (e.g. 1:30 PM local): previous day’s service window.
- **After kitchen close**: current day’s service window.
- **`DEV_OVERRIDE_DAY`**: when set, returns the override day (for tests).

**Parameters**:
- `timezone_str`: IANA timezone (e.g. `America/Argentina/Buenos_Aires`)
- `country_code`: Optional; used for market-specific `kitchen_close_time`

**Returns**: Day name (e.g. `"Monday"`, `"Tuesday"`)

---

### `is_today_kitchen_closed(country_code, timezone_str) -> bool`

Returns `True` if the kitchen has already closed for the effective current day in the market.

- Uses the effective current day (cutoff-aware).
- Checks `now_local.time() >= kitchen_close`.
- Returns `False` for unknown markets or weekends.

---

### `date_to_kitchen_day(target_date) -> str`

Maps a calendar date to its kitchen day name. No timezone; used for billing where the date is already a closed day.

- Respects `DEV_OVERRIDE_DAY`.
- Uses `target_date.weekday()` for the mapping.

---

### `get_kitchen_day_for_date(target_date, timezone_str, country_code=None) -> str`

Resolves the kitchen day for a given date.

- **If `target_date == today` (in timezone)**: uses `get_effective_current_day`.
- **Otherwise**: uses `date_to_kitchen_day`.

---

## Constants

- **`VALID_KITCHEN_DAYS`**: `("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")` – re-exported from `KitchenDay` enum.
- **`WEEKDAY_NUM_TO_NAME`**: `("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")` – index 0 = Monday.

---

## Consumers

| Consumer | Usage |
|----------|-------|
| `date_service` | Delegates `get_effective_current_day` |
| `restaurant_explorer_service` | `get_effective_current_day`, `is_today_kitchen_closed`, `VALID_KITCHEN_DAYS` |
| `institution_billing` | `date_to_kitchen_day` |
| `restaurant_staff_service` | `get_kitchen_day_for_date` |
| `plate_selection_service` | `get_effective_current_day` (with timezone and country_code) |
| `plate_selection_validation` | `VALID_KITCHEN_DAYS`, timezone-aware today |

---

## Related

- [KITCHEN_DAY_SLA.md](./KITCHEN_DAY_SLA.md) – Order cutoff and SLA
- [MARKETS_API.md](./MARKETS_API.md) – Market CRUD and `kitchen_close_time`
- [app/config/market_config.py](../../app/config/market_config.py) – `MarketConfiguration` fallback
