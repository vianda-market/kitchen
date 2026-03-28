# Plate API - Client Guide (B2C and B2B)

**Document Version**: 1.0  
**Date**: March 2026  
**For**: Frontend Team (Web, iOS, Android)

---

## Overview

This document describes the plate-related APIs used by both B2C and B2B clients:

1. **Enriched plate endpoint** — Full plate details including product ingredients, restaurant pickup instructions, and market-aware address display.
2. **Plate create/update** — Savings are not stored; create/update do not accept or return savings.
3. **Plate kitchen days** — Assign a plate to multiple days in bulk (B2B); plates must have kitchen days to appear in explore.
4. **Plate selection** — Booking a plate for pickup (POST /plate-selections/, list).
5. **Plate pickup pending** — Single pending order ready for pickup (GET /plate-pickup/pending).

---

## Table of Contents

- [Enriched Plate Endpoint](#enriched-plate-endpoint)
- [Plate Create/Update (No Savings)](#plate-createupdate-no-savings)
- [Plate Kitchen Days API](#plate-kitchen-days-api)
- [Plate Selection API](#plate-selection-api)
- [Plate Pickup Pending API](#plate-pickup-pending-api)

---

## Enriched Plate Endpoint

Both B2C and B2B clients use the enriched plate endpoint for plate detail views (e.g. plate modal, B2B plate management).

### Endpoints

```http
GET /api/v1/plates/enriched/
GET /api/v1/plates/enriched/{plate_id}
```

### Authentication

Requires Bearer token (JWT). Scoping applies per role (institution, market).

### Response structure

The enriched plate response includes institution, restaurant, product, address, and review data. Key fields for client display:

| Field | Type | Description |
|-------|------|-------------|
| `plate_id` | UUID | Plate identifier |
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
| `product_name` | string | Product/plate name |
| `dietary` | string \| null | Dietary info (e.g. vegetarian, gluten-free) |
| **`ingredients`** | string \| null | Comma-separated ingredients from product (e.g. "Chicken, rice, vegetables") |
| `product_image_url` | string \| null | Product image URL |
| `product_image_storage_path` | string | Storage path |
| `has_image` | bool | True if custom image; false if default placeholder |
| `price` | decimal | Plate price |
| `credit` | int | Credit value |
| **`expected_payout_local_currency`** | decimal | Monetary amount supplier receives per plate in local currency (`credit × credit_value_local_currency`). Read-only, computed by backend. Do not send on create/update. |
| `no_show_discount` | int \| null | No-show discount (denormalized from institution; null for non-Supplier) |
| `delivery_time_minutes` | int | Delivery time in minutes |
| `is_archived` | bool | Archived flag |
| `status` | string | Status (e.g. Active) |
| `created_date` | datetime | Creation timestamp |
| `modified_date` | datetime | Last modified timestamp |

### Client usage

- **B2C:** Use for the plate detail modal when the user taps a plate (e.g. from explore). Display `ingredients`, `pickup_instructions`, and `address_display` for a complete plate and pickup experience.
- **B2C "View on map":** Use `latitude` and `longitude` from the enriched plate response to open Google Maps: `https://www.google.com/maps?q={latitude},{longitude}`. Do not show a map link when either value is `null`. See [ADDRESSES_API_CLIENT.md](ADDRESSES_API_CLIENT.md#view-on-map-latitude--longitude).
- **B2B:** Use for plate management tables and detail views. Do not display or edit savings (see [Plate Create/Update (No Savings)](#plate-createupdate-no-savings)).

### Example response (excerpt)

```json
{
  "plate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
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

## Plate Create/Update (No Savings)

**Audience:** B2B (supplier/employee portal) and any client that implements plate create/update.

Savings are **not stored** on plates. They are computed on the fly for B2C explore using the user's plan `credit_cost_local_currency`, plate price, and plate credit. The plate API does **not** accept or return `savings` for create/update or for the enriched plate list/detail.

**No-show discount** is configured at the **institution level** (not per plate). Configure it via the Institution API (`PUT /api/v1/institutions/{id}` with `no_show_discount`). See [ROLE_AND_FIELD_ACCESS_CLIENT.md](../b2b_client/ROLE_AND_FIELD_ACCESS_CLIENT.md#institution-api--no_show_discount).

### Create

```http
POST /api/v1/plates/
```

**Request body:** `product_id`, `restaurant_id`, `price`, `credit`, `delivery_time_minutes`. **No `savings` or `no_show_discount` field.**

### Update

```http
PUT /api/v1/plates/{plate_id}
```

Same fields as create, all optional. **No `savings` or `no_show_discount` field.**

### Responses

- **GET /api/v1/plates/** does **not** include `savings` or `no_show_discount`.
- **GET /api/v1/plates/enriched/** includes `no_show_discount` (from institution; can be null for non-Supplier).
- **Savings** appear only in **B2C** endpoint **GET /api/v1/restaurants/by-city**, in `restaurants[].plates[].savings` (integer 0–100), where they are computed per user/plan.

### UI instruction (B2B)

For plate management (tables and create/edit modals): **do not** add a savings or no_show_discount column/input. Only use: product, restaurant, price, credit, delivery_time_minutes. Configure no-show discount at the institution level.

### Live preview of expected payout when creating a plate (B2B)

When the Supplier creates a plate in the UI, they need live feedback on `expected_payout_local_currency` before submit. Call **GET /api/v1/restaurants/enriched** or **GET /api/v1/restaurants/enriched/{restaurant_id}** to obtain `market_credit_value_local_currency` for the selected restaurant. The UI can then show a live preview: `expected_payout_local_currency ≈ credit × market_credit_value_local_currency` before submit. The stored value is set by the backend trigger on create/update.

---

## Plate Kitchen Days API

**Audience:** B2B (Supplier, Employee). Defines which weekdays a plate is available for selection.

**Purpose:** After creating a plate, assign it to **kitchen days** (Monday–Friday). Only plates with at least one active kitchen day appear in B2C explore. The API supports **bulk assignment** — add one plate to multiple days in a single request.

### Bulk create: POST /api/v1/plate-kitchen-days/

**Method:** `POST`  
**URL:** `/api/v1/plate-kitchen-days/`

Assign a plate to one or more kitchen days in a single atomic operation. Avoids multiple calls when adding the same plate to Monday–Friday.

| Field | Required | Description |
|-------|----------|-------------|
| `plate_id` | **Yes** | UUID of the plate. |
| `kitchen_days` | **Yes** | Array of weekday names: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`. No duplicates. |
| `status` | No | Default `Active`. Use `Inactive` to add the day but keep it off explore. |

**Example:**

```json
{
  "plate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "kitchen_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
}
```

**Response:** 201 Created. Returns a list of created `PlateKitchenDayResponseSchema` objects (one per day).

**Errors:**
- **404** — Plate not found
- **409** — Plate already assigned to one or more of the given days (all operations rolled back)

### List and manage

- **GET /api/v1/plate-kitchen-days/** — List plate kitchen day assignments. Optional `institution_id` for B2B Employee scoping. Filter client-side by `plate_id` when showing kitchen days for a specific plate.
- **PUT /api/v1/plate-kitchen-days/{plate_kitchen_day_id}** — Update a single assignment (status, kitchen_day).
- **DELETE /api/v1/plate-kitchen-days/{plate_kitchen_day_id}** — Archive (soft delete) an assignment.

### Client usage (B2B)

Use bulk create when adding a new plate to all weekdays. Example flow: Create plate → Assign kitchen days in one POST with all five days → Plate appears in explore for those days.

---

## Plate Selection API

**Audience:** B2C (Customer) and B2B (Employee); **not** Supplier.

**Purpose:** How **plate selection** works — creating a selection (booking a plate for pickup), listing selections, and how it connects to **plate pickup pending**.

### Flow in short

1. **Explore** — User sees restaurants and plates for a **kitchen day** (e.g. GET /restaurants/by-city with `kitchen_day`). When `kitchen_day` is set, each restaurant includes `has_volunteer` (true if any user has offered to pick up from that restaurant). Each plate includes `is_already_reserved` (true when the current user has reserved that plate for that day) and `existing_plate_selection_id` (use for Change or cancel). When `is_already_reserved` is true, show alternative action buttons instead of "Reserve for [Day]". See [PLATE_ALREADY_RESERVED_EXPLORE_UI.md](../b2c_client/PLATE_ALREADY_RESERVED_EXPLORE_UI.md).
2. **Select** — User picks a plate and a pickup time window → **POST /api/v1/plate-selections/** with `plate_id`, `pickup_time_range`, and optionally `target_kitchen_day`.
3. **Pending pickup** — To show "your order is ready for pickup", call **GET /api/v1/plate-pickup/pending** (see [Plate Pickup Pending API](#plate-pickup-pending-api)).
4. **At restaurant** — User scans QR (POST /plate-pickup/scan-qr) and supplier can complete the order.

### Authentication

All plate selection endpoints require **Bearer token** (JWT). **Customer** and **Employee** can create and list; **Supplier** cannot (403).

### Create selection: POST /api/v1/plate-selections/

**Method:** `POST`  
**URL:** `/api/v1/plate-selections/`

| Field | Required | Description |
|-------|----------|-------------|
| `plate_id` | **Yes** | UUID of the plate (from explore/by-city or plates API). |
| `pickup_time_range` | **Yes** | Time window for pickup, e.g. `"12:00-12:15"`. Must be within allowed pickup hours (e.g. 11:30–14:30 local). |
| `target_kitchen_day` | No | Weekday: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, or `Friday`. If omitted, backend derives from plate's next available kitchen day. Must be within this week or next week (through Friday). |
| `pickup_intent` | No | `"offer"` \| `"request"` \| `"self"` (default). **offer** = volunteer to pick up coworkers' plates; **request** = need someone to pick up; **self** = pick up own plate. |
| `flexible_on_time` | No | Boolean. Only when `pickup_intent === "request"`. If true, matching allows ±30 min flexibility for volunteer matching. |

**Example:**

```json
{
  "plate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "pickup_time_range": "12:00-12:15",
  "target_kitchen_day": "Wednesday",
  "pickup_intent": "self",
  "flexible_on_time": false
}
```

**Validation:** plate_id must exist; restaurant must be Active; kitchen day within allowed window; user must have sufficient credits; pickup_time_range within allowed window.

**Response:** 201 Created (plate selection with `plate_pickup_id`, `editable_until`), or 400/401/403/404/422 on failure.

### List and get

- **GET /api/v1/plate-selections/** — List all plate selections for the current user. Each includes `pickup_date` (ISO date YYYY-MM-DD) and `editable_until`.
- **GET /api/v1/plate-selections/{plate_selection_id}** — Get one selection by ID. Includes `pickup_date` (calendar date for pickup; use for calendar export and display) and `editable_until` (ISO datetime) so client can show/hide edit UI.

**Response field `pickup_date`:** The actual calendar date (YYYY-MM-DD) for pickup. Set at creation and not editable via PATCH. Use for calendar export and display.

### Edit and delete (editable until 1h before kitchen day opens)

- **PATCH /api/v1/plate-selections/{plate_selection_id}** — Update only the allowed fields (see below). Returns 400 if the client sends non-editable fields; 403/422 if past editability cutoff.
- **DELETE /api/v1/plate-selections/{plate_selection_id}** — Cancel and refund credits. Same editability window.

**Editability:** Selections are editable until **1 hour before the kitchen day opens** (market local time). Use `editable_until` from GET to show/hide edit controls.

#### PATCH: Editable vs non-editable fields

Only the following fields may be modified via PATCH. The backend rejects any attempt to change other fields with **400 Bad Request**.

| Editable | Description |
|----------|-------------|
| `pickup_time_range` | Time window for pickup (e.g. `"12:00-12:15"`). Must be within allowed pickup hours. |
| `pickup_intent` | `"self"` \| `"offer"` \| `"request"`. **self** = pick up own plate; **offer** = volunteer to pick up coworkers' plates; **request** = need someone to pick up. |
| `flexible_on_time` | Boolean. Only when `pickup_intent === "request"`. If true, allows ±30 min flexibility for volunteer matching. |
| `cancel` | Set to `true` to cancel the selection (refunds credits, archives the record). Same effect as DELETE. |

**Non-editable (backend returns 400 if sent):** `plate_id`, `target_kitchen_day`, `kitchen_day`, `pickup_date`, `user_id`, `restaurant_id`, `product_id`, `qr_code_id`, `credit`, and other system fields.

**To change the plate:** The user must cancel the current selection (PATCH with `cancel: true` or DELETE) and create a new one via POST. Do not send `plate_id` in PATCH — it will be rejected.

### Coworker flow (Offer to pick up)

- **GET /api/v1/plate-selections/{plate_selection_id}/coworkers** — List coworkers (same employer) with eligibility. Response: `[{ user_id, first_name, last_initial, eligible }]`.
- **POST /api/v1/plate-selections/{plate_selection_id}/notify-coworkers** — Body: `{ "user_ids": ["uuid1", ...] }`. Notifies selected coworkers. All `user_ids` must be eligible.

See [POST_RESERVATION_PICKUP_B2C.md](../b2c_client/POST_RESERVATION_PICKUP_B2C.md) for full volunteer/coworker flow.

---

## Plate Pickup Pending API

This endpoint returns the current user's **single pending pickup order** (or `null`).

### Endpoint

```http
GET /api/v1/plate-pickup/pending
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
  total_plate_count?: number;      // Plates the assigned user picks up (for volunteer flow)
  plate_pickup_ids?: string[];     // UUIDs for POST /plate-pickup/{id}/complete
  orders: Array<{
    plate_name: string;
    order_count: string;            // "x1", "x2", "x3"
    delivery_time_minutes: number;
    plate_pickup_id?: string;      // UUID for POST /plate-pickup/{id}/complete
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
      "plate_name": "Grilled Chicken",
      "order_count": "x1",
      "delivery_time_minutes": 15
    },
    {
      "plate_name": "Vegetarian Pasta",
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

- [PLATE_API_NO_SAVINGS.md](../../zArchive/api/shared_client/PLATE_API_NO_SAVINGS.md)
- [PLATE_PICKUP_PENDING_API.md](../../zArchive/api/shared_client/PLATE_PICKUP_PENDING_API.md)
- [PLATE_SELECTION_API.md](../../zArchive/api/shared_client/PLATE_SELECTION_API.md)
