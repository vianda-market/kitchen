# Kiosk Mode API — B2B Integration

**From:** kitchen backend
**To:** vianda-platform (B2B kiosk)
**Date:** 2026-04-04

---

## Overview

Backend support for tablet/phone kiosk views used by restaurant operators during pickup service hours. Three trust layers — all restaurants get Layer 0 (timer-based) automatically. Layer 1 (manual handoff) and Layer 2 (code verification) are opt-in.

Trust model: `docs/plans/PICKUP_HANDOFF_TRUST_MODEL.md`

---

## 1. Enhanced Daily Orders

`GET /api/v1/restaurant-staff/daily-orders`

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `restaurant_id` | UUID | No | Filter to a specific restaurant (Supplier: must belong to their institution) |
| `order_date` | date (YYYY-MM-DD) | No | Date to query (defaults to today) |
| `status` | string (repeatable) | No | Filter by order status. Repeat for multi-select: `?status=pending&status=arrived`. Accepted values: `pending`, `arrived`, `handed_out`, `completed`, `cancelled`, `active`. Applied at SQL level. |
| `is_no_show` | bool | No | Filter by the derived no-show flag. `true` = only orders whose pickup window passed while still pending; `false` = exclude no-shows; omit = all orders. Applied in the service layer. |

### Response

```json
{
  "order_date": "2026-04-04",
  "server_time": "2026-04-04T15:05:32Z",
  "restaurants": [
    {
      "restaurant_id": "uuid",
      "restaurant_name": "La Cocina",
      "require_kiosk_code_verification": false,
      "pickup_window_start": "11:30",
      "pickup_window_end": "13:30",
      "orders": [
        {
          "vianda_pickup_id": "uuid",
          "customer_name": "M.G.",
          "vianda_name": "Grilled Chicken",
          "confirmation_code": "482951",
          "status": "arrived",
          "arrival_time": "2026-04-04T12:02:00Z",
          "expected_completion_time": "2026-04-04T12:07:00Z",
          "completion_time": null,
          "countdown_seconds": 300,
          "extensions_used": 0,
          "was_collected": false,
          "pickup_time_range": "12:00-12:15",
          "kitchen_day": "friday",
          "pickup_type": "self",
          "is_no_show": false
        }
      ],
      "summary": {
        "total_orders": 15,
        "pending": 5,
        "arrived": 3,
        "handed_out": 2,
        "completed": 5,
        "no_show": 0
      },
      "reservations_by_vianda": [
        {
          "vianda_id": "uuid",
          "vianda_name": "Grilled Chicken",
          "count": 10,
          "completed_count": 7
        }
      ],
      "live_locked_count": 10
    }
  ]
}
```

### Fields per order

| Field | Type | Description |
|---|---|---|
| `vianda_pickup_id` | UUID | Use for `POST /vianda-pickup/{id}/hand-out` and `/complete` |
| `confirmation_code` | string | 6-digit numeric code. Display alongside each queue entry for visual matching. |
| `status` | string | Lowercase status value: `pending`, `arrived`, `handed_out`, `completed`, `cancelled`, `active` |
| `expected_completion_time` | datetime/null | Authoritative pickup deadline. Compute remaining: `expected_completion_time - server_time` |
| `completion_time` | datetime/null | When order was completed |
| `countdown_seconds` | int | Server-configured timer duration (currently 300s) |
| `extensions_used` | int | Timer extensions used (currently always 0, scaffolding) |
| `was_collected` | bool | Whether vianda was actually picked up |
| `pickup_type` | string/null | `self` / `offer` / `request` from pickup preferences |
| `is_no_show` | bool | `true` when status is Pending and the order's `pickup_time_range` end has passed. Use to filter no-shows out of the active queue and into a "No-Show" dashboard section. |

### Fields per restaurant

| Field | Type | Description |
|---|---|---|
| `require_kiosk_code_verification` | bool | Whether this restaurant requires code entry (Layer 2) |
| `pickup_window_start` | string/null | Earliest pickup time (HH:MM) |
| `pickup_window_end` | string/null | Latest pickup time (HH:MM) |
| `live_locked_count` | int | Count of promoted (live) pickup records for this restaurant today |
| `reservations_by_vianda` | array | Per-vianda reservation entries (see below) |

### `reservations_by_vianda` entries

| Field | Type | Description |
|---|---|---|
| `vianda_id` | string (UUID) | Vianda identifier |
| `vianda_name` | string | Product name |
| `count` | int | Total subscribed reservations for this vianda today |
| `completed_count` | int | Number of pickups with status `completed` or `handed_out` for this vianda today. Use as the numerator for the prep progress bar: `completed_count / count`. |

**`completed_count` note:** counts pickups with DB status `completed` OR `handed_out`. Status values are lowercase (e.g. `completed`, `handed_out`) — compare with lowercase in frontend code.

### Timer sync

Use `server_time` to avoid client clock drift:
```
remaining_seconds = expected_completion_time - server_time
```
Then count down (or count up) locally from there.

### Privacy

Customer names are **initials only**: "M.G." (not "Maria G.").

---

## 2. Status Lifecycle

```
Pending → Arrived → Handed Out → Completed
```

| Status | Meaning | Kiosk display |
|---|---|---|
| `Pending` | Customer hasn't scanned QR | Show in "Expected" section |
| `Arrived` | Customer scanned QR, timer running | Show in live queue with count-up timer |
| `Handed Out` | Restaurant gave the vianda | Show in "Served" section |
| `Completed` | Customer confirmed or auto-completed | Show in "Done" section or fade out |

---

## 3. Verify and Hand Off (Layer 2)

`POST /api/v1/restaurant-staff/verify-and-handoff`

For restaurants with `require_kiosk_code_verification = true`.

### Request

```json
{
  "confirmation_code": "482951",
  "restaurant_id": "uuid"
}
```

Code must be exactly 6 numeric digits.

### Response (match)

```json
{
  "match": true,
  "customer_initials": "M.G.",
  "vianda_pickup_ids": ["uuid1"],
  "viandas": [{ "vianda_name": "Grilled Chicken", "quantity": 1 }],
  "status": "Handed Out",
  "arrival_time": "2026-04-04T12:02:00Z",
  "expected_completion_time": "2026-04-04T12:07:00Z",
  "handed_out_time": "2026-04-04T12:05:00Z",
  "countdown_seconds": 300,
  "extensions_used": 0,
  "max_extensions": 3
}
```

### Response (no match)

```json
{
  "match": false,
  "message": "No order found with this confirmation code"
}
```

Auth: Supplier (any role, scoped to institution) or Internal.

---

## 4. Manual Hand Out (Layer 1)

`POST /api/v1/vianda-pickup/{vianda_pickup_id}/hand-out`

One-tap handoff. Transitions Arrived → Handed Out. No code required.

Response: `{ "status": "Handed Out", "handed_out_time": "..." }`

Auth: Supplier (any role, scoped) or Internal.

---

## 5. Mark Complete

`POST /api/v1/vianda-pickup/{vianda_pickup_id}/complete`

Existing endpoint, updated with new `completion_type` values:

| Value | Source | Meaning |
|---|---|---|
| `user_confirmed` | B2C customer | Customer tapped "Received" |
| `user_disputed` | B2C customer | Customer tapped "I didn't receive this" |
| `timer_expired` | System | Handoff timer ran out |
| `confirmation_timeout` | System | 5-min timeout after Handed Out |
| `kitchen_day_close` | System | Billing cron at end of day |

---

## 6. Code Verification Toggle

Per-restaurant setting on `restaurant_info`:

| Field | Type | Default | Who can change |
|---|---|---|---|
| `require_kiosk_code_verification` | bool | `false` | Supplier Admin only |

Update via `PUT /api/v1/restaurants/{id}` with `{ "require_kiosk_code_verification": true }`.

When enabled, the kiosk should show a code entry flow for arrived orders instead of just a "Delivered" button.

---

## 7. Supplier Operator Access Matrix

Operators are kiosk-focused. They are blocked from all CRUD management routes.

| Endpoint | Admin | Manager | Operator |
|---|---|---|---|
| `GET /restaurant-staff/daily-orders` | Yes | Yes | **Yes** |
| `POST /restaurant-staff/verify-and-handoff` | Yes | Yes | **Yes** |
| `POST /vianda-pickup/{id}/hand-out` | Yes | Yes | **Yes** |
| `POST /vianda-pickup/{id}/complete` | Yes | Yes | **Yes** |
| `GET /vianda-reviews/by-institution/enriched` | Yes | Yes | **Yes** |
| `GET /users/me`, `PUT /users/me` | Yes | Yes | **Yes** |
| All CRUD routes (products, plans, viandas, restaurants, etc.) | Yes | Yes | **No (403)** |
| Create/edit/delete users | Yes | Yes | **No (403)** |
| Create/edit/delete addresses | Yes | Yes | **No (403)** |
| Toggle `require_kiosk_code_verification` | Yes | No | **No** |

---

## 8. Portion Complaint

`POST /api/v1/vianda-reviews/{vianda_review_id}/portion-complaint`

Customer-only (B2C). Filed when customer rates portion size as 1 and taps "File complaint." Accepts multipart photo + text.

Not directly relevant to kiosk, but complaints accumulate on the restaurant's record and may trigger auto-escalation to Layer 2 code verification.
