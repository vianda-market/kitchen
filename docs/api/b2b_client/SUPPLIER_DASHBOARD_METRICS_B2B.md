# Supplier Dashboard Metrics (B2B)

**Audience:** B2B app developers (kitchen-web, restaurant/supplier portal)  
**Purpose:** What metrics the supplier dashboard must show and how to obtain them via the API

---

## Overview

The supplier dashboard should give restaurants visibility into reservations, live orders, customer flow, deliveries, and quality metrics. This document specifies the metrics and the APIs to use.

---

## Required Metrics

| Metric | Description | API / Data Source |
|--------|-------------|-------------------|
| **Reservations per day and plate** | Count of non-archived plate_selection_info for each kitchen_day, pickup_date, and plate | `GET /restaurant-staff/daily-orders` → `reservations_by_plate` |
| **Live plates locked for today** | Count of plate_pickup_live (promoted orders) for today | `GET /restaurant-staff/daily-orders` → `live_locked_count` |
| **People waiting** | Count of orders with status Arrived (customer scanned QR, at restaurant) | `GET /restaurant-staff/daily-orders` → `summary.arrived` |
| **Plates delivered today** | Count of orders completed (was_collected or status Complete) | `GET /restaurant-staff/daily-orders` → `summary.completed` |
| **Daily balance** | Restaurant balance (credited at promotion, updated on collection) | `GET /restaurant-balances/{restaurant_id}` or enriched balances |
| **Average portion size** | Per-plate aggregate from reviews (1–3; light/standard/large) | `GET /plates/enriched/` (filter by restaurant) → `average_portion_size`, `portion_size` |
| **Average plate rating** | Per-plate average stars from reviews | `GET /plates/enriched/` → `average_stars` |

---

## Lock-at-Kitchen-Start Context

Reservations are **not** charged or credited until **kitchen start** (e.g. 11:30 AM local). Until then:

- **reservations_by_plate** counts all active plate_selection_info (what customers have reserved).
- **live_locked_count** is 0 before kitchen start; it grows when the promotion cron runs at 11:30.
- **Restaurant balance** is only updated when plates are promoted and when customers collect.

Customers can cancel until 1 hour before kitchen day. After promotion, no refunds; credits are forfeited on no-show.

---

## API Details

### 1. Daily Orders (reservations, live locked, waiting, delivered)

**Endpoint:** `GET /api/v1/restaurant-staff/daily-orders`

**Query params:**
- `restaurant_id` (optional): Filter to one restaurant
- `order_date` (optional): Date (YYYY-MM-DD). Default: today

**Response (per restaurant):**
```json
{
  "order_date": "2026-03-08",
  "restaurants": [
    {
      "restaurant_id": "uuid",
      "restaurant_name": "La Cocina",
      "orders": [...],
      "summary": {
        "total_orders": 15,
        "pending": 8,
        "arrived": 4,
        "completed": 3
      },
      "reservations_by_plate": [
        { "plate_id": "uuid", "plate_name": "Grilled Chicken", "count": 5 },
        { "plate_id": "uuid", "plate_name": "Vegetarian Pasta", "count": 3 }
      ],
      "live_locked_count": 15
    }
  ]
}
```

| Field | Metric |
|-------|--------|
| `reservations_by_plate` | Reservations per day and plate |
| `live_locked_count` | Live plates locked for today (promoted at kitchen start) |
| `summary.arrived` | People waiting (scanned QR, at restaurant) |
| `summary.completed` | Plates delivered today |

---

### 2. Restaurant Balance

**Endpoint:** `GET /api/v1/restaurant-balances/{restaurant_id}`

Returns the current balance for the restaurant (credited at promotion, settlement handled via billing).

---

### 3. Average Portion Size and Plate Rating

**Endpoint:** `GET /api/v1/plates/enriched/` (filter by restaurant/institution scope)

Each plate in the enriched response includes:
- `average_stars` – Average star rating (1–5). Null when `review_count` &lt; 5.
- `average_portion_size` – Average portion size rating (1–3). Null when `review_count` &lt; 5.
- `portion_size` – Bucketed label: `"light"` \| `"standard"` \| `"large"` \| `"insufficient_reviews"`.
- `review_count` – Number of reviews.

For the supplier dashboard:
- Show **average portion size** (or `portion_size` label) per plate.
- Show **average plate rating** (`average_stars`) per plate.
- Use `"insufficient_reviews"` when `review_count` &lt; 5.

See [PORTION_SIZE_DISPLAY_B2B.md](./PORTION_SIZE_DISPLAY_B2B.md) for display rules.

---

## Metric Mapping Summary

| Supplier dashboard UI | API field |
|----------------------|-----------|
| Reservations by plate for today | `reservations_by_plate` |
| Live plates locked today | `live_locked_count` |
| People waiting (at restaurant) | `summary.arrived` |
| Plates delivered today | `summary.completed` |
| Daily / current balance | `GET /restaurant-balances/{id}` |
| Average portion size | `plates/enriched` → `portion_size` or `average_portion_size` |
| Average plate rating | `plates/enriched` → `average_stars` |

---

## Authorization

- **Supplier:** Can access restaurants within their institution_entity_id.
- **Employee:** Can access all restaurants (must pass `restaurant_id` for daily-orders).

See [API_CLIENT_ROLE_FIELD_ACCESS.md](./API_CLIENT_ROLE_FIELD_ACCESS.md) for role-based access.
