# Vianda API - Client Guide (B2C and B2B)

**Document Version**: 1.0  
**Date**: March 2026  
**For**: Frontend Team (Web, iOS, Android)

---

## Overview

This document describes the vianda-related APIs used by both B2C and B2B clients:

1. **Enriched vianda endpoint** — Full vianda details including product ingredients, restaurant pickup instructions, and market-aware address display.
2. **Vianda create/update** — Savings are not stored; create/update do not accept or return savings.
3. **Vianda kitchen days** — Assign a vianda to multiple days in bulk (B2B); viandas must have kitchen days to appear in explore.
4. **Vianda selection** — Booking a vianda for pickup (POST /vianda-selections/, list).
5. **Vianda pickup pending** — Single pending order ready for pickup (GET /vianda-pickup/pending).

---

## Table of Contents

- [Enriched Vianda Endpoint](#enriched-vianda-endpoint)
- [Vianda Create/Update (No Savings)](#vianda-createupdate-no-savings)
- [Vianda Kitchen Days API](#vianda-kitchen-days-api)
- [Vianda Selection API](#vianda-selection-api)
- [Vianda Pickup Pending API](#vianda-pickup-pending-api)

---

## Enriched Vianda Endpoint

Both B2C and B2B clients use the enriched vianda endpoint for vianda detail views (e.g. vianda modal, B2B vianda management).

### Endpoints

```http
GET /api/v1/viandas/enriched/
GET /api/v1/viandas/enriched/{vianda_id}
```

### Authentication

Requires Bearer token (JWT). Scoping applies per role (institution, market).

### Response structure

The enriched vianda response includes institution, restaurant, product, address, and review data. Key fields for client display:

| Field | Type | Description |
|-------|------|-------------|
| `vianda_id` | UUID | Vianda identifier |
| `product_id` | UUID | Product identifier |
| `restaurant_id` | UUID | Restaurant identifier |
| `institution_name` | string | Institution name |
| `restaurant_name` | string | Restaurant name |
| `cuisine` | string \| null | Restaurant cuisine |
| **`pickup_instructions`** | string \| null | Restaurant pickup instructions for customers (e.g. "Enter through side door, ask for pickup counter") |
| `country_name` | string | Country name |
| `country_code` | string | ISO country code |
| `province` | string | Province/state |
| `city` | string | City |
| `street_type` | string \| null | Street type (St, Ave, etc.) |
| `street_name` | string \| null | Street name |
| `building_number` | string \| null | Building number |
| **`address_display`** | string \| null | Pre-formatted street line per market (e.g. "123 Main St" or "Av Santa Fe 100"). Use for display instead of building from raw parts. See [ADDRESSES_API_CLIENT.md](ADDRESSES_API_CLIENT.md#address-display-formatting-per-market). |
| `latitude` | float \| null | Geolocation latitude |
| `longitude` | float \| null | Geolocation longitude |
| `average_stars` | float \| null | Average star rating (1–5) from reviews. **Null when review_count < 5.** |
| `average_portion_size` | float \| null | Average portion size rating (1–3) from reviews. **Null when review_count < 5.** Optional for granular display (e.g. partial fill icons). |
| **`portion_size`** | string | Human-readable portion size: `"light"` \| `"standard"` \| `"large"` \| `"insufficient_reviews"`. Primary field for display. When `"insufficient_reviews"`, client shows "not enough reviews" message. See [b2c_client/PORTION_SIZE_DISPLAY_B2C.md](../b2c_client/PORTION_SIZE_DISPLAY_B2C.md) and [b2b_client/PORTION_SIZE_DISPLAY_B2B.md](../b2b_client/PORTION_SIZE_DISPLAY_B2B.md). |
| `review_count` | int | Number of reviews |
| `product_name` | string | Product/vianda name |
| `dietary` | string \| null | Dietary info (e.g. vegetarian, gluten-free) |
| **`ingredients`** | string \| null | Comma-separated ingredients from product (e.g. "Chicken, rice, vegetables") |
| `product_image_url` | string \| null | Product image URL |
| `product_image_storage_path` | string | Storage path |
| `has_image` | bool | True if custom image; false if default placeholder |
| `price` | decimal | Vianda price |
| `credit` | int | Credit value |
| **`expected_payout_local_currency`** | decimal | Monetary amount supplier receives per vianda in local currency (`credit × credit_value_local_currency`). Read-only, computed by backend. Do not send on create/update. |
| `no_show_discount` | int \| null | No-show discount (from `supplier_terms`; null when no terms configured) |
| `delivery_time_minutes` | int | Delivery time in minutes |
| `is_archived` | bool | Archived flag |
| `status` | string | Status (e.g. Active) |
| `created_date` | datetime | Creation timestamp |
| `modified_date` | datetime | Last modified timestamp |

### Client usage

- **B2C:** Use for the vianda detail modal when the user taps a vianda (e.g. from explore). Display `ingredients`, `pickup_instructions`, and `address_display` for a complete vianda and pickup experience.
- **B2C "View on map":** Use `latitude` and `longitude` from the enriched vianda response to open Google Maps: `https://www.google.com/maps?q={latitude},{longitude}`. Do not show a map link when either value is `null`. See [ADDRESSES_API_CLIENT.md](ADDRESSES_API_CLIENT.md#view-on-map-latitude--longitude).
- **B2B:** Use for vianda management tables and detail views. Do not display or edit savings (see [Vianda Create/Update (No Savings)](#vianda-createupdate-no-savings)).

### Example response (excerpt)

```json
{
  "vianda_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "product_name": "Grilled Chicken Bowl",
  "restaurant_name": "La Cocina",
  "pickup_instructions": "Enter through side door, ask for pickup counter",
  "ingredients": "Chicken, rice, vegetables, olive oil",
  "address_display": "123 Main St",
  "price": 12.50,
  "credit": 2,
  "average_stars": 4.5,
  "review_count": 24
}
```

---

## Vianda Create/Update (No Savings)

**Audience:** B2B (supplier/employee portal) and any client that implements vianda create/update.

Savings are **not stored** on viandas. They are computed on the fly for B2C explore using the user's plan `credit_cost_local_currency`, vianda price, and vianda credit. The vianda API does **not** accept or return `savings` for create/update or for the enriched vianda list/detail.

**No-show discount** is configured per supplier via `billing.supplier_terms` (not per vianda or per institution). Configure it via the Supplier Terms API (`PUT /api/v1/supplier-terms/{institution_id}`). See [API_CLIENT_SUPPLIER_TERMS.md](../b2b_client/API_CLIENT_SUPPLIER_TERMS.md).

### Create

```http
POST /api/v1/viandas/
```

**Request body:** `product_id`, `restaurant_id`, `price`, `credit`, `delivery_time_minutes`. **No `savings` or `no_show_discount` field.**

### Update

```http
PUT /api/v1/viandas/{vianda_id}
```

Same fields as create, all optional. **No `savings` or `no_show_discount` field.**

### Responses

- **GET /api/v1/viandas/** does **not** include `savings` or `no_show_discount`.
- **GET /api/v1/viandas/enriched/** includes `no_show_discount` (from `supplier_terms`; null when no terms configured).
- **Savings** appear only in **B2C** endpoint **GET /api/v1/restaurants/by-city**, in `restaurants[].viandas[].savings` (integer 0–100), where they are computed per user/plan.

### UI instruction (B2B)

For vianda management (tables and create/edit modals): **do not** add a savings or no_show_discount column/input. Only use: product, restaurant, price, credit, delivery_time_minutes. Configure no-show discount via Supplier Terms (`PUT /api/v1/supplier-terms/{institution_id}`).

### Live preview of expected payout when creating a vianda (B2B)

When the Supplier creates a vianda in the UI, they need live feedback on `expected_payout_local_currency` before submit. Call **GET /api/v1/restaurants/enriched** or **GET /api/v1/restaurants/enriched/{restaurant_id}** to obtain `market_credit_value_local_currency` for the selected restaurant. The UI can then show a live preview: `expected_payout_local_currency ≈ credit × market_credit_value_local_currency` before submit. The stored value is set by the backend trigger on create/update.

---

## Vianda Kitchen Days API

**Audience:** B2B (Supplier, Employee). Defines which weekdays a vianda is available for selection.

**Purpose:** After creating a vianda, assign it to **kitchen days** (Monday–Friday). Only viandas with at least one active kitchen day appear in B2C explore. The API supports **bulk assignment** — add one vianda to multiple days in a single request.

### Bulk create: POST /api/v1/vianda-kitchen-days/

**Method:** `POST`  
**URL:** `/api/v1/vianda-kitchen-days/`

Assign a vianda to one or more kitchen days in a single atomic operation. Avoids multiple calls when adding the same vianda to Monday–Friday.

| Field | Required | Description |
|-------|----------|-------------|
| `vianda_id` | **Yes** | UUID of the vianda. |
| `kitchen_days` | **Yes** | Array of weekday names: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`. No duplicates. |
| `status` | No | Default `Active`. Use `Inactive` to add the day but keep it off explore. |

**Example:**

```json
{
  "vianda_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "kitchen_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
}
```

**Response:** 201 Created. Returns a list of created `ViandaKitchenDayResponseSchema` objects (one per day).

**Errors:**
- **404** — Vianda not found
- **409** — Vianda already assigned to one or more of the given days (all operations rolled back)

### List and manage

- **GET /api/v1/vianda-kitchen-days/** — List vianda kitchen day assignments. Optional `institution_id` for B2B Employee scoping. Filter client-side by `vianda_id` when showing kitchen days for a specific vianda.
- **PUT /api/v1/vianda-kitchen-days/{vianda_kitchen_day_id}** — Update a single assignment (status, kitchen_day).
- **DELETE /api/v1/vianda-kitchen-days/{vianda_kitchen_day_id}** — Archive (soft delete) an assignment.

### Client usage (B2B)

Use bulk create when adding a new vianda to all weekdays. Example flow: Create vianda → Assign kitchen days in one POST with all five days → Vianda appears in explore for those days.

---

## Vianda Selection API

**Audience:** B2C (Customer) and B2B (Employee); **not** Supplier.

**Purpose:** How **vianda selection** works — creating a selection (booking a vianda for pickup), listing selections, and how it connects to **vianda pickup pending**.

### Flow in short

1. **Explore** — User sees restaurants and viandas for a **kitchen day** (e.g. GET /restaurants/by-city with `kitchen_day`). When `kitchen_day` is set, each restaurant includes `has_volunteer` (true if any user has offered to pick up from that restaurant). Each vianda includes `is_already_reserved` (true when the current user has reserved that vianda for that day) and `existing_vianda_selection_id` (use for Change or cancel). When `is_already_reserved` is true, show alternative action buttons instead of "Reserve for [Day]". See [VIANDA_ALREADY_RESERVED_EXPLORE_UI.md](../b2c_client/VIANDA_ALREADY_RESERVED_EXPLORE_UI.md).
2. **Select** — User picks a vianda and a pickup time window → **POST /api/v1/vianda-selections/** with `vianda_id`, `pickup_time_range`, and optionally `target_kitchen_day`.
3. **Pending pickup** — To show "your order is ready for pickup", call **GET /api/v1/vianda-pickup/pending** (see [Vianda Pickup Pending API](#vianda-pickup-pending-api)).
4. **At restaurant** — User scans QR (POST /vianda-pickup/scan-qr) and supplier can complete the order.

### Authentication

All vianda selection endpoints require **Bearer token** (JWT). **Customer** and **Employee** can create and list; **Supplier** cannot (403).

### Create selection: POST /api/v1/vianda-selections/

**Method:** `POST`  
**URL:** `/api/v1/vianda-selections/`

| Field | Required | Description |
|-------|----------|-------------|
| `vianda_id` | **Yes** | UUID of the vianda (from explore/by-city or viandas API). |
| `pickup_time_range` | **Yes** | Time window for pickup, e.g. `"12:00-12:15"`. Must be within allowed pickup hours (e.g. 11:30–14:30 local). |
| `target_kitchen_day` | No | Weekday: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, or `Friday`. If omitted, backend derives from vianda's next available kitchen day. Must be within this week or next week (through Friday). |
| `pickup_intent` | No | `"offer"` \| `"request"` \| `"self"` (default). **offer** = volunteer to pick up coworkers' viandas; **request** = need someone to pick up; **self** = pick up own vianda. |
| `flexible_on_time` | No | Boolean. Only when `pickup_intent === "request"`. If true, matching allows ±30 min flexibility for volunteer matching. |

**Example:**

```json
{
  "vianda_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "pickup_time_range": "12:00-12:15",
  "target_kitchen_day": "Wednesday",
  "pickup_intent": "self",
  "flexible_on_time": false
}
```

**Validation:** vianda_id must exist; restaurant must be Active; kitchen day within allowed window; user must have sufficient credits; pickup_time_range within allowed window.

**Response:** 201 Created (vianda selection with `vianda_pickup_id`, `editable_until`), or 400/401/403/404/422 on failure.

### List and get

- **GET /api/v1/vianda-selections/** — List all vianda selections for the current user. Each includes `pickup_date` (ISO date YYYY-MM-DD) and `editable_until`.
- **GET /api/v1/vianda-selections/{vianda_selection_id}** — Get one selection by ID. Includes `pickup_date` (calendar date for pickup; use for calendar export and display) and `editable_until` (ISO datetime) so client can show/hide edit UI.

**Response field `pickup_date`:** The actual calendar date (YYYY-MM-DD) for pickup. Set at creation and not editable via PATCH. Use for calendar export and display.

### Edit and delete (editable until 1h before kitchen day opens)

- **PATCH /api/v1/vianda-selections/{vianda_selection_id}** — Update only the allowed fields (see below). Returns 400 if the client sends non-editable fields; 403/422 if past editability cutoff.
- **DELETE /api/v1/vianda-selections/{vianda_selection_id}** — Cancel and refund credits. Same editability window.

**Editability:** Selections are editable until **1 hour before the kitchen day opens** (market local time). Use `editable_until` from GET to show/hide edit controls.

#### PATCH: Editable vs non-editable fields

Only the following fields may be modified via PATCH. The backend rejects any attempt to change other fields with **400 Bad Request**.

| Editable | Description |
|----------|-------------|
| `pickup_time_range` | Time window for pickup (e.g. `"12:00-12:15"`). Must be within allowed pickup hours. |
| `pickup_intent` | `"self"` \| `"offer"` \| `"request"`. **self** = pick up own vianda; **offer** = volunteer to pick up coworkers' viandas; **request** = need someone to pick up. |
| `flexible_on_time` | Boolean. Only when `pickup_intent === "request"`. If true, allows ±30 min flexibility for volunteer matching. |
| `cancel` | Set to `true` to cancel the selection (refunds credits, archives the record). Same effect as DELETE. |

**Non-editable (backend returns 400 if sent):** `vianda_id`, `target_kitchen_day`, `kitchen_day`, `pickup_date`, `user_id`, `restaurant_id`, `product_id`, `qr_code_id`, `credit`, and other system fields.

**To change the vianda:** The user must cancel the current selection (PATCH with `cancel: true` or DELETE) and create a new one via POST. Do not send `vianda_id` in PATCH — it will be rejected.

### Coworker flow (Offer to pick up)

- **GET /api/v1/vianda-selections/{vianda_selection_id}/coworkers** — List coworkers (same employer) with eligibility. Response: `[{ user_id, first_name, last_initial, eligible }]`.
- **POST /api/v1/vianda-selections/{vianda_selection_id}/notify-coworkers** — Body: `{ "user_ids": ["uuid1", ...] }`. Notifies selected coworkers. All `user_ids` must be eligible.

See [POST_RESERVATION_PICKUP_B2C.md](../b2c_client/POST_RESERVATION_PICKUP_B2C.md) for full volunteer/coworker flow.

---

## Vianda Pickup Pending API

This endpoint returns the current user's **single pending pickup order** (or `null`).

### Endpoint

```http
GET /api/v1/vianda-pickup/pending
```

### Authentication

Requires Bearer token (JWT).

### Response

**Not an array.** Returns either `null` or a single object.

#### No pending orders

**Status:** 200 OK  
**Body:** `null`

#### Pending orders found

**Status:** 200 OK  
**Body:** Single `PendingOrdersResponse` object

```typescript
interface PendingOrdersResponse {
  restaurant_id: string;           // UUID
  restaurant_name: string;
  qr_code_id: string;               // UUID
  total_orders: number;
  total_vianda_count?: number;      // Viandas the assigned user picks up (for volunteer flow)
  vianda_pickup_ids?: string[];     // UUIDs for POST /vianda-pickup/{id}/complete
  orders: Array<{
    vianda_name: string;
    order_count: string;            // "x1", "x2", "x3"
    delivery_time_minutes: number;
    vianda_pickup_id?: string;      // UUID for POST /vianda-pickup/{id}/complete
  }>;
  pickup_window: {
    start_time: string;             // ISO 8601
    end_time: string;
    window_minutes: number;         // Always 15
  };
  status: "Pending" | "Arrived";
  created_date: string;            // ISO 8601
}
```

### Frontend handling

1. **Response is NOT an array** — Single object or `null`.
2. **Null check** — Always check `if (response === null)` before accessing properties.
3. **Orders array** — `orders` can have 0, 1, or multiple items.
4. **Order count format** — `order_count` is a string like `"x1"`, `"x2"`.

### Example response

```json
{
  "restaurant_id": "123e4567-e89b-12d3-a456-426614174000",
  "restaurant_name": "La Cocina",
  "qr_code_id": "987fcdeb-51a2-43f7-b890-123456789abc",
  "total_orders": 3,
  "orders": [
    {
      "vianda_name": "Grilled Chicken",
      "order_count": "x1",
      "delivery_time_minutes": 15
    },
    {
      "vianda_name": "Vegetarian Pasta",
      "order_count": "x2",
      "delivery_time_minutes": 20
    }
  ],
  "pickup_window": {
    "start_time": "2025-11-17T12:00:00-08:00",
    "end_time": "2025-11-17T12:15:00-08:00",
    "window_minutes": 15
  },
  "status": "Pending",
  "created_date": "2025-11-17T11:30:00-08:00"
}
```

---

## Related Documentation

- [ADDRESSES_API_CLIENT.md](ADDRESSES_API_CLIENT.md) — Address display formatting per market (`address_display`, `formatted_address`)
- [CREDIT_AND_CURRENCY_CLIENT.md](CREDIT_AND_CURRENCY_CLIENT.md) — Savings (B2C explore), expected payout, market credit value
- [b2c_client/EXPLORE_KITCHEN_DAY_B2C.md](../b2c_client/EXPLORE_KITCHEN_DAY_B2C.md) — Kitchen day and explore flow
- [b2c_client/POST_RESERVATION_PICKUP_B2C.md](../b2c_client/POST_RESERVATION_PICKUP_B2C.md) — Volunteer flow, coworker list/notify, `has_volunteer`, editability

---

## Legacy documents (archived)

The following documents have been combined into this guide and moved to `docs/zArchive/api/shared_client/`:

- [VIANDA_API_NO_SAVINGS.md](../../zArchive/api/shared_client/VIANDA_API_NO_SAVINGS.md)
- [VIANDA_PICKUP_PENDING_API.md](../../zArchive/api/shared_client/VIANDA_PICKUP_PENDING_API.md)
- [VIANDA_SELECTION_API.md](../../zArchive/api/shared_client/VIANDA_SELECTION_API.md)
