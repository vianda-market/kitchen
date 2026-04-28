# Restaurant status, plate_kitchen_days, and QR codes (B2B and B2C)

This document describes how restaurant **status**, **plate_kitchen_days**, and **QR codes** interact. It applies to both B2B (admin/portal) and B2C (explore/leads) clients.

**Active plate_kitchen_days:** A plate_kitchen_days row counts as “active” only when it is **non-archived** (`is_archived = FALSE`) **and** has **status = "Active"**. Rows that are archived or have status Inactive/Pending do not count for restaurant activation or visibility.

**Active QR code:** A QR code counts as "active" when it is **non-archived** (`is_archived = FALSE`) **and** has **status = "Active"**. Customers scan QR codes to confirm arrival for plate pickup.

## Overview

- A restaurant is created with status **Pending**.
- It can be set to **Active** only when it has (1) at least one non-archived plate with at least one **active** plate_kitchen_days row (non-archived and status Active), **and** (2) at least one non-archived QR code with **status = "Active"**; otherwise the update API returns **400**.
- It can be set to **Inactive** at any time (no validation).
- **Lazy activation (kitchen#123):** When a `plate_kitchen_days` row is created OR a QR code is provisioned for a `pending` restaurant, the backend checks whether all prerequisites are now met. If yes, the restaurant is automatically promoted from `pending` to `active`. This promotion is **one-way only** (no auto-demotion) and **silent** (no event, no email, no audit row). When activation fires, the mutation response includes a `restaurant_activated` envelope — see [Response field: `restaurant_activated`](#response-field-restaurant_activated) below.
- If all **active** plate_kitchen_days for a restaurant are removed (archived, deleted, or set to non-Active status), the system **automatically** sets that restaurant’s status to **Inactive**.
- If all **active** QR codes for a restaurant are removed (archived, deleted, or set to non-Active status), the system **automatically** sets that restaurant’s status to **Inactive**.
- **Leads and Explorer** endpoints return only restaurants that (a) have at least one **active** plate_kitchen_day, (b) have at least one **active** QR code, and (c) have **status = Active**, so metrics and lists are accurate.

## Computed readiness field: `is_ready_for_signup` and `missing`

Admin-facing restaurant endpoints (`GET /api/v1/restaurants/enriched`, `GET /api/v1/restaurants/enriched/{id}`) return two additional computed fields on each restaurant:

| Field | Type | Description |
|-------|------|-------------|
| `is_ready_for_signup` | `bool \| null` | `true` when all four prerequisites are met at read time. `null` on plain (non-enriched) endpoints. |
| `missing` | `list[str] \| null` | Subset of `["status_active", "not_archived", "plate_kitchen_days", "qr"]` listing unmet prerequisites. Empty list when `is_ready_for_signup` is `true`. `null` on plain endpoints. |

**No DB column.** These are computed via EXISTS subqueries at read time; the readiness rules may evolve without a migration.

**`market.active = true` does NOT imply restaurant readiness.** A market can be active while having restaurants that are not ready. Use `is_ready_for_signup` (not `market.status`) to determine signup-readiness.

Admin market endpoints (`GET /api/v1/admin/markets/enriched`) similarly return `is_ready_for_signup` and `missing` on the market:

| Field | Type | Description |
|-------|------|-------------|
| `is_ready_for_signup` | `bool \| null` | `true` when `market.status=’active’` AND ≥1 ready restaurant exists in the market. |
| `missing` | `list[str] \| null` | `["ready_restaurant"]` when no ready restaurant; `[]` when ready. `null` on plain (non-enriched) endpoints. |

## Create (B2B)

- **POST /api/v1/restaurants** creates a restaurant. The response includes **`status: "Pending"`**. The client must not send `status` on create; the backend sets it.
- **Do not send `credit_currency_id`** on restaurant create. Currency is inherited from the institution entity (derived from the entity’s address → market). See [CREDIT_AND_CURRENCY_CLIENT.md](CREDIT_AND_CURRENCY_CLIENT.md).

## Update status (B2B)

- **PUT /api/v1/restaurants/{restaurant_id}** accepts an optional **`status`** field. Valid values are **Active**, **Pending**, and **Inactive** only. For dropdowns, use `GET /api/v1/enums/` and the **`status_restaurant`** key, or `GET /api/v1/enums/status?context=restaurant` (see [ENUM_SERVICE_API.md](ENUM_SERVICE_API.md)).
- **Setting `status` to `"Active"`:**
  - The backend checks that the restaurant has (1) at least one non-archived plate with at least one **active** plate_kitchen_days row (non-archived and status = Active), **and** (2) at least one non-archived QR code with **status = "Active"**.
  - If **both yes** → update succeeds (200).
  - If **plate_kitchen_days missing** → **400 Bad Request** with: *"Cannot set restaurant to Active. The restaurant must have at least one plate with active plate_kitchen_days. Add and activate plate_kitchen_days for the restaurant's plates, then try again."*
  - If **QR code missing** → **400 Bad Request** with: *"Cannot set restaurant to Active. The restaurant must have at least one active QR code. Create a QR code via POST /api/v1/qr-codes for this restaurant, then try again."*
  - If **both missing** → **400** with a combined message listing both requirements.
- **Setting `status` to `"Inactive"` (or `"Pending"`):** Always allowed (200).

## Auto-deactivation

When the last **active** plate_kitchen_days row for a restaurant is archived, deleted, or set to a non-Active status, the system sets that restaurant's status to **Inactive**.

When the last **active** QR code for a restaurant is archived, deleted, or set to a non-Active status, the system sets that restaurant's status to **Inactive**.

This keeps leads and explorer lists consistent: a restaurant with no active plate_kitchen_days or no active QR code will not appear.

## Visibility (Leads and Explorer)

The following endpoints return **only** restaurants that:

1. Have at least one non-archived plate with at least one **active** plate_kitchen_days row (non-archived and status = Active), and  
2. Have at least one non-archived QR code with **status = "Active"**, and  
3. Have **status = "Active"**.

**Leads (unauthenticated):**

- **GET /api/v1/leads/cities**
- **GET /api/v1/leads/city-metrics**
- **GET /api/v1/leads/zipcode-metrics**

**Explore (authenticated):**

- **GET /api/v1/restaurants/cities**
- **GET /api/v1/restaurants/by-city**

So Pending or Inactive restaurants, or restaurants with no **active** plate_kitchen_days or no **active** QR code, do **not** appear in these lists or in counts/centers. No extra client-side filtering is required.

## For B2B clients

**Activation checklist:**

1. Create restaurant (status **Pending**).
2. Create plates and assign **plate_kitchen_days** for at least one day; ensure each has **status = "Active"** and is not archived.
3. Create at least one QR code via **POST /api/v1/qr-codes** with `{"restaurant_id": "<uuid>"}` (payload is auto-generated by the backend).
4. **Lazy activation:** Once both (2) and (3) are complete for a `pending` restaurant, the backend automatically promotes it to `active`. No explicit `PUT /restaurants/{id}` call is needed. You can observe the result via the enriched restaurant endpoint (`GET /api/v1/restaurants/enriched/{id}`) — `is_ready_for_signup` will be `true` and `status` will be `active`.
5. Manual activation remains possible: call **PUT /api/v1/restaurants/{id}** with **`{"status": "Active"}`** as before. If prereqs are not met, the call returns **400**.
6. To disable a restaurant without touching plate_kitchen_days or QR codes, set **`{"status": "Inactive"}`**.
7. If you archive, delete, or set to non-Active all plate_kitchen_days (or all QR codes) for a restaurant, the system will set that restaurant to Inactive automatically. The restaurant will NOT auto-reactivate if prereqs are later re-satisfied (one-way promotion only).

**Reading readiness:**

- `GET /api/v1/restaurants/enriched` and `GET /api/v1/restaurants/enriched/{id}` — `is_ready_for_signup` (bool) and `missing` (list of unmet prereq keys) are returned on every record.
- `GET /api/v1/admin/markets/enriched` — market-level `is_ready_for_signup` and `missing` fields.
- The `is_ready_for_signup` field should be the primary signal for admin UI readiness indicators, not `market.status` or `restaurant.status` alone.

See [API_CLIENT_QR_CODES.md](../b2b_client/API_CLIENT_QR_CODES.md) for QR code create flow and display options (print vs screen).

---

## Response field: `restaurant_activated`

**Applies to:** `POST /api/v1/plate-kitchen-days` and `POST /api/v1/qr-codes`.

Both mutation endpoints now include `restaurant_activated` in their responses. This field allows the frontend to detect when lazy activation fires and show a contextual toast or progress update.

### Shape

```json
{
  "restaurant_activated": {
    "restaurant_id": "<uuid>",
    "name": "La Cocina"
  }
}
```

When lazy activation does **not** fire (restaurant was already active, or not all prereqs are yet met):

```json
{
  "restaurant_activated": null
}
```

The field is **always present** in the response (never missing) — `null` means no activation, object means activation fired.

### POST /api/v1/plate-kitchen-days response shape

The create endpoint now returns a wrapper object instead of a bare array:

```json
{
  "items": [
    { "plate_kitchen_day_id": "...", "plate_id": "...", "kitchen_day": "monday", ... }
  ],
  "restaurant_activated": {
    "restaurant_id": "<uuid>",
    "name": "My Restaurant"
  }
}
```

`items` contains the list of created records (same shape as before). `restaurant_activated` is `null` when activation did not fire.

**CONTRACT CHANGE:** The `POST /plate-kitchen-days` response shape changed from `list[PlateKitchenDayResponseSchema]` (bare array) to `PlateKitchenDayCreateResponseSchema` (object with `items` array + `restaurant_activated`). Frontend consumers must update their response parsing.

### POST /api/v1/qr-codes response shape

The `QRCodeResponseSchema` gains an optional `restaurant_activated` field (always present, `null` when no activation):

```json
{
  "qr_code_id": "...",
  "restaurant_id": "...",
  "qr_code_payload": "...",
  "qr_code_image_url": "...",
  "image_storage_path": "...",
  "is_archived": false,
  "status": "active",
  "created_date": "...",
  "modified_date": "...",
  "restaurant_activated": {
    "restaurant_id": "<uuid>",
    "name": "My Restaurant"
  }
}
```

`GET`, `PUT`, `DELETE` responses for QR codes also include `restaurant_activated: null` as it is part of the schema. Clients should treat it as `null` on non-create operations.

---

## Checklist semantic: `has_active_restaurant` (lazy-activation-aware)

The supplier onboarding checklist field `has_active_restaurant` (returned by `GET /institutions/{id}/onboarding-status`) has been redefined to avoid a circular dependency introduced by lazy activation:

| Version | Definition |
|---------|-----------|
| Before kitchen #172 follow-up | `≥1 restaurant with status = 'active' AND is_archived = false` |
| After (current) | `≥1 restaurant with status IN ('pending', 'active') AND is_archived = false` |

**Rationale:** With lazy activation, a restaurant starts `pending` and only becomes `active` after plate_kitchen_days AND a QR code exist. The checklist gates the "Plates" and "QR Codes" nav items on `has_active_restaurant`. Under the old definition, suppliers couldn't see those nav items until after the restaurant was active — but the restaurant can only become active via those very routes. The new definition counts `pending` as "usable" for navigation gating purposes.

**Field name unchanged:** The field is still called `has_active_restaurant`. "Active" in this context means "usable" (non-archived and in pending or active state), not strictly `status = 'active'`.

**No regression:** Restaurants already in `active` status are still counted (the `IN ('pending', 'active')` clause includes `active`).

## For B2C clients

- Use **GET /api/v1/restaurants/cities** and **GET /api/v1/restaurants/by-city** (and leads endpoints if applicable). The backend already filters to Active restaurants with at least one **active** plate_kitchen_day and at least one **active** QR code (non-archived and status Active); no extra logic needed on the client.
