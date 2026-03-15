# Plate Already Reserved: Explore UI (B2C)

**Audience:** B2C app developers  
**Purpose:** When the user views a plate they have already reserved for the current kitchen day, show alternative action buttons instead of "Reserve for [Day]".

---

## Overview

When a user explores plates for a kitchen day (e.g. Monday) and views a plate they have **already reserved** for that same day, the client must show different action buttons instead of "Reserve for [Day]".

---

## Response Fields (GET /restaurants/by-city)

When the user is authenticated and `kitchen_day` is in the request, each plate in `restaurants[].plates[]` includes:

| Field | Type | Description |
|-------|------|-------------|
| `is_already_reserved` | boolean | True when the current user has a non-archived plate_selection for this plate_id and the response kitchen_day |
| `existing_plate_selection_id` | string (UUID) or null | When `is_already_reserved` is true, the plate_selection_id for "Change or cancel" (PATCH/DELETE) |

When the user is unauthenticated or `kitchen_day` is not set, both fields are `false` and `null` respectively.

---

## Client UI Logic

**If `is_already_reserved` is false:** Show the primary action button "Reserve for [Day]".

**If `is_already_reserved` is true:** Replace "Reserve for [Day]" with these four alternative buttons:

| Button | Status | Action |
|--------|--------|--------|
| 1. Invite a friend to get this plate with you | Placeholder | Referral program (not yet implemented) |
| 2. Ask a friend to pickup | Placeholder | Deep link for non-subscribers (not yet implemented) |
| 3. Change or cancel reservation | **Implementable now** | Use `existing_plate_selection_id` for PATCH `/plate-selections/{id}` (change) or DELETE `/plate-selections/{id}` (cancel). See [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md). |
| 4. Add reservation to calendar | Roadmap | Simple export (not yet implemented) |

---

## Button 3: Change or Cancel

When the user taps "Change or cancel reservation":

- **Navigate** to the plate selection detail/edit screen using `existing_plate_selection_id`.
- **PATCH** `/api/v1/plate-selections/{existing_plate_selection_id}` — Update pickup_time_range, pickup_intent, flexible_on_time, or cancel.
- **DELETE** `/api/v1/plate-selections/{existing_plate_selection_id}` — Cancel and refund credits.

Edits are allowed until 1 hour before the kitchen day opens. Use `editable_until` from GET `/plate-selections/{id}` to show/hide edit controls.

---

## Refresh on Return to Modal (Required)

**Critical:** When the user is redirected back to the explore plate modal after completing an action, the modal **must refetch** the latest data. Do **not** rely on cached `GET /restaurants/by-city` response.

| Scenario | Action |
|----------|--------|
| **After reserving a plate** | User completes the full flow (pick time, select who picks up) and is redirected to the explore modal. The modal must **refetch** `GET /restaurants/by-city` (with same `city`, `country_code`, `market_id`, `kitchen_day`). The plate will now have `is_already_reserved: true` and `existing_plate_selection_id` set. Show the 4 alternative buttons instead of "Reserve for [Day]". |
| **After cancelling a reservation** | User cancels (DELETE `/plate-selections/{id}`) and is redirected to the modal. The modal must **refetch** `GET /restaurants/by-city`. The plate will now have `is_already_reserved: false` and `existing_plate_selection_id: null`. Show "Reserve for [Day]" again. |
| **After editing a reservation (PATCH)** | User edits and returns to the modal. **Refetch** to ensure any side effects are reflected. |

**Implementation:** When the modal is shown/focused after a navigation that originated from a reservation flow (create, cancel, edit), invalidate any cached by-city data and trigger a fresh request. Use React Query's `invalidateQueries`, SWR's `mutate`, or equivalent to ensure the next render uses up-to-date `is_already_reserved` and `existing_plate_selection_id`.

---

## Example Response (plate with is_already_reserved)

```json
{
  "plate_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "product_name": "Grilled Chicken Bowl",
  "price": 12.50,
  "credit": 5,
  "kitchen_day": "Monday",
  "is_already_reserved": true,
  "existing_plate_selection_id": "550e8400-e29b-41d4-a716-446655440000",
  "savings": 15,
  "is_favorite": false,
  "is_recommended": false
}
```

---

## Related Documentation

- [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md) — Plate selection, PATCH/DELETE
- [POST_RESERVATION_PICKUP_B2C.md](./POST_RESERVATION_PICKUP_B2C.md) — Volunteer flow, editability
- [PLATE_SELECTION_DUPLICATE_REPLACE.md](./PLATE_SELECTION_DUPLICATE_REPLACE.md) — Duplicate kitchen day replace flow
