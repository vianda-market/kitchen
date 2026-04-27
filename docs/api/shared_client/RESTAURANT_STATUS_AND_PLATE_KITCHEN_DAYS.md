# Restaurant status, plate_kitchen_days, and QR codes (B2B and B2C)

This document describes how restaurant **status**, **plate_kitchen_days**, and **QR codes** interact. It applies to both B2B (admin/portal) and B2C (explore/leads) clients.

**Active plate_kitchen_days:** A plate_kitchen_days row counts as “active” only when it is **non-archived** (`is_archived = FALSE`) **and** has **status = "Active"**. Rows that are archived or have status Inactive/Pending do not count for restaurant activation or visibility.

**Active QR code:** A QR code counts as "active" when it is **non-archived** (`is_archived = FALSE`) **and** has **status = "Active"**. Customers scan QR codes to confirm arrival for plate pickup.

## Overview

- A restaurant is created with status **Pending**.
- It can be set to **Active** only when it has (1) at least one non-archived plate with at least one **active** plate_kitchen_days row (non-archived and status Active), **and** (2) at least one non-archived QR code with **status = "Active"**; otherwise the update API returns **400**.
- It can be set to **Inactive** at any time (no validation).
- **Lazy activation (kitchen#123):** When a `plate_kitchen_days` row is created OR a QR code is provisioned for a `pending` restaurant, the backend checks whether all prerequisites are now met. If yes, the restaurant is automatically promoted from `pending` to `active`. This promotion is **one-way only** (no auto-demotion) and **silent** (no event, no email, no audit row).
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

## For B2C clients

- Use **GET /api/v1/restaurants/cities** and **GET /api/v1/restaurants/by-city** (and leads endpoints if applicable). The backend already filters to Active restaurants with at least one **active** plate_kitchen_day and at least one **active** QR code (non-archived and status Active); no extra logic needed on the client.
