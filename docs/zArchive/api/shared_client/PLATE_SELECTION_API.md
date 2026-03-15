# Plate Selection API (B2C and B2B client)

> **Superseded by:** [PLATE_API_CLIENT.md](PLATE_API_CLIENT.md) — Combined plate API guide including enriched endpoint, plate selection, and plate pickup pending.

**Audience:** B2C app (Customer) and B2B (Employee); **not** Supplier  
**Purpose:** How **plate selection** works — creating a selection (booking a plate for pickup), listing selections, and how it connects to **plate pickup pending**.

**Related:** After the user has a selection ready for pickup, use [PLATE_PICKUP_PENDING_API.md](PLATE_PICKUP_PENDING_API.md) for GET /plate-pickup/pending (single pending order or null) and QR scan. This doc is about **selecting** plates; that doc is about **viewing the pending order** and completing pickup.

---

## Flow in short

1. **Explore** — User sees restaurants and plates for a **kitchen day** (e.g. GET /restaurants/by-city with `kitchen_day`). See [b2c_client/EXPLORE_KITCHEN_DAY_B2C.md](../b2c_client/EXPLORE_KITCHEN_DAY_B2C.md) and [b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md](../b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md).
2. **Select** — User picks a plate and a pickup time window → **POST /api/v1/plate-selections/** with `plate_id`, `pickup_time_range`, and optionally `target_kitchen_day`. Backend validates (restaurant Active, kitchen day, credits, holidays) and creates the selection and related records (e.g. plate_pickup_live, transactions).
3. **Pending pickup** — To show “your order is ready for pickup”, call **GET /api/v1/plate-pickup/pending**. Returns a single pending order object or `null`. See [PLATE_PICKUP_PENDING_API.md](PLATE_PICKUP_PENDING_API.md).
4. **At restaurant** — User scans QR (POST /plate-pickup/scan-qr) and supplier can complete the order.

---

## Authentication

All plate selection endpoints require **Bearer token** (JWT). **Customer** and **Employee** can create and list; **Supplier** cannot use the plate selection API (403).

---

## Create selection: POST /api/v1/plate-selections/

**Method:** `POST`  
**URL:** `/api/v1/plate-selections/`  
**Headers:** `Authorization: Bearer <access_token>`, `Content-Type: application/json`

### Request body

| Field | Required | Description |
|-------|----------|-------------|
| `plate_id` | **Yes** | UUID of the plate (from explore/by-city or plates API). |
| `pickup_time_range` | **Yes** | Time window for pickup, e.g. `"12:00-12:15"`. Must be within allowed pickup hours (e.g. 11:30–14:30 local); backend validates. |
| `target_kitchen_day` | No | Weekday name: `Monday`, `Tuesday`, `Wednesday`, `Thursday`, or `Friday`. If omitted, backend derives from plate’s next available kitchen day (in market timezone). Must be within this week or next week (through Friday). |

**Example:**

```json
{
  "plate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "pickup_time_range": "12:00-12:15",
  "target_kitchen_day": "Wednesday"
}
```

### Validation (backend)

- **plate_id** must exist and belong to a plate that has an active plate_kitchen_day for the target day.
- **Restaurant** must be **Active**; restaurant-specific or national **holidays** can block the target date (400).
- **Kitchen day** must be within the allowed window (this week or next week through Friday in market timezone).
- **Credits:** User must have sufficient subscription credits; otherwise 400 with an insufficient-credits message.
- **pickup_time_range** must fall within the allowed pickup window (e.g. 11:30 AM–2:30 PM local).

### Response

- **201 Created** — Returns the created plate selection (e.g. `plate_selection_id`, plate, pickup window, status).
- **400** — Validation failure (restaurant not Active, holiday, insufficient credits, invalid time/day).
- **401** — Missing or invalid token.
- **403** — Supplier role.
- **404** — Plate or related resource not found.
- **422** — Missing `plate_id` or `pickup_time_range`.

---

## List and get: GET /api/v1/plate-selections/ and GET /api/v1/plate-selections/{id}

- **GET /api/v1/plate-selections/** — List all plate selections for the **current user**. Customer sees only their own; Employee can see according to scoping.
- **GET /api/v1/plate-selections/{plate_selection_id}** — Get one selection by ID. User can only access their own (or within Employee scope).

**Plate selections are immutable:** There is no PUT or DELETE. User cannot edit or cancel via this API; only create and read.

---

## For the B2C agent

- **Plate selection** = booking a plate for a specific kitchen day and pickup time (POST /plate-selections/).
- **Plate pickup pending** = the single “order ready for pickup” (GET /plate-pickup/pending). Documented in [PLATE_PICKUP_PENDING_API.md](PLATE_PICKUP_PENDING_API.md).
- Use **EXPLORE** docs for how the user discovers plates (by-city + kitchen_day). Use **this doc** for creating and listing selections. Use **PLATE_PICKUP_PENDING_API** for showing the pending order and QR flow.
