# Post-Reservation Pickup Flow (B2C)

**Last Updated**: 2026-03  
**Audience**: B2C React Native app (Customer role)

This document describes the post-reservation pickup flow: pickup intent (offer/request/self), volunteer visibility, coworker search and notifications, and vianda selection editability.

---

## Overview

After a user reserves a vianda and selects a pickup window, they choose one of three intents:

| Intent | Description |
|--------|-------------|
| `offer` | User offers to pick up a coworker's meal (same restaurant, same time) |
| `request` | User requests a coworker to pick up their meal; if no one volunteers, user is responsible |
| `self` | User will pick up their own vianda |

---

## 1. Pickup Intent on Create and Update

**Create (POST /api/v1/vianda-selections/)**

Optional fields in the request body:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pickup_intent` | `"offer"` \| `"request"` \| `"self"` | `"self"` | User's pickup intent |
| `flexible_on_time` | boolean | null | Only when `pickup_intent === "request"`; ±30 min flexibility for matching |

**Update (PATCH /api/v1/vianda-selections/{id})**

Same fields can be updated. Editable until 1 hour before kitchen day opens.

---

## 2. Volunteer Visibility in Restaurant Explore

When users explore restaurants (GET /api/v1/restaurants/by-city) with a `kitchen_day` set, each restaurant includes:

| Field | Type | Description |
|-------|------|-------------|
| `has_volunteer` | boolean | True when at least one user has `pickup_intent=offer` for this restaurant and kitchen_day |
| `has_coworker_offer` | boolean | True when user has employer and at least one **coworker** (same employer) has `pickup_intent=offer` |
| `has_coworker_request` | boolean | True when user has employer and at least one **coworker** has `pickup_intent=request` |

Coworker flags respect messaging prefs (`coworkers_can_see_my_orders`, `can_participate_in_vianda_pickups`). Omit or false when user has no employer.

**Explore Vianda Modal:** Fetch `GET /api/v1/viandas/enriched/{vianda_id}?kitchen_day=Monday` for coworker flags when opened from Reservations. For pickup time ranges, call `GET /api/v1/restaurants/{restaurant_id}/coworker-pickup-windows?kitchen_day=Monday` only when `has_coworker_offer || has_coworker_request`.

### GET /api/v1/restaurants/{restaurant_id}/coworker-pickup-windows

**Query params:** `kitchen_day` (required, Monday–Friday)

**Auth:** Bearer token (Customer).

**Response:** `{ "pickup_windows": [{ "pickup_time_range": "11:30-11:45", "intent": "offer" | "request", "flexible_on_time": true | null }] }`

Returns empty when user has no employer. When `intent=request` and coworker has `flexible_on_time=true`, backend expands ±30 min and includes adjacent windows; `flexible_on_time` is set on the original entry.

---

## 3. Coworker List and Notify (Offer to Pick Up)

When the user selects "Offer to pick up", the client needs a list of coworkers to notify. Coworkers are users with the **same employer** (and in a future iteration, same office/address — see [EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md](./EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md)).

### GET /api/v1/vianda-selections/{vianda_selection_id}/coworkers

**Auth:** Bearer token (Customer).

**Response:** Array of `{ user_id, first_name, last_initial, eligible: boolean, ineligibility_reason: string | null }`.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | UUID | Coworker user ID |
| `first_name` | string | First name |
| `last_initial` | string | Last initial (e.g. "G.") |
| `eligible` | boolean | True if coworker can be notified |
| `ineligibility_reason` | string \| null | When `eligible: false`: `"already_ordered_different_restaurant"` or `"already_ordered_different_pickup_time"`. Null when eligible. Use to show specific messaging instead of generic text. |

**Eligibility rules (backend enforces):**
- **Eligible:** Coworker has not ordered yet for the same kitchen day
- **Ineligible:** Coworker already ordered from a different restaurant or different pickup time

Display as "FirstName L." (e.g. "Maria G.").

**Errors:** 403 if current user has no employer assigned.

### POST /api/v1/vianda-selections/{vianda_selection_id}/notify-coworkers

**Auth:** Bearer token (Customer).

**Request body:** `{ "user_ids": ["uuid1", "uuid2", ...] }`

**Response:** `{ "notified_count": N }`

**Validation:** All `user_ids` must be eligible coworkers. 400 if any are ineligible.

---

## 4. Notifications

The backend records notifications in `coworker_pickup_notification`. Push or in-app notifications are sent based on each user's notification settings. The app should provide a **notification configuration screen** where users can opt in or out of coworker pickup alerts.

- **Opted in:** User receives push/in-app when a coworker offers to pick up for them.
- **Opted out:** User does not receive push but can still see volunteers in the restaurant explore list (`has_volunteer`).

---

## 5. Vianda Selection Editability

Vianda selections are **editable** until **1 hour before the kitchen day opens** for the market.

### PATCH /api/v1/vianda-selections/{vianda_selection_id}

**Allowed fields:** `pickup_time_range`, `pickup_intent`, `flexible_on_time`, `cancel` (boolean).

**Response:** 200 OK with updated vianda selection. Includes `editable_until` (ISO datetime).

**Errors:** 403 or 422 if past editability cutoff.

### DELETE /api/v1/vianda-selections/{vianda_selection_id}

Same editability window. Refunds credits and cancels the selection.

### editable_until

GET /api/v1/vianda-selections/{id} and list responses include `editable_until` (ISO datetime or null). Use this to show/hide edit UI in the app.

---

## 6. Pending Pickup (Assigned User Vianda Count)

When a user with `pickup_intent=offer` is matched with requesters at the same restaurant and time, the **offering user** is assigned all viandas for pickup. The pending response includes:

| Field | Type | Description |
|-------|------|-------------|
| `vianda_pickup_ids` | UUID[] | IDs for POST /vianda-pickup/{id}/complete |
| `total_vianda_count` | int | Total viandas the assigned user picks up (e.g. "You're picking up 4 viandas") |

Each order in `orders` can include `vianda_pickup_id` for completing individual pickups.

---

## Related Documentation

- [VIANDA_API_CLIENT.md](../shared_client/VIANDA_API_CLIENT.md) — Vianda selection create, pending, QR scan, complete
- [feedback_post_reservation_pickup_intent.md](./feedback_post_reservation_pickup_intent.md) — Full API contract and implementation status
- [EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md](./EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md) — Future: scoping coworkers by same office (employer_address_id)
