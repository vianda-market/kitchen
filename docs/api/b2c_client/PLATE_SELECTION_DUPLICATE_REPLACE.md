# Plate Selection: Duplicate Kitchen Day Replace Flow (B2C)

**Audience:** B2C app developers  
**Purpose:** Handle the case when a user tries to reserve a second plate for the same kitchen day. Instead of a blocking error, the API returns a structured 409 so the frontend can show a modal with two options.

---

## Overview

A user can only have **one non-archived plate selection per kitchen day**. If they already have a plate reserved for Monday and try to reserve another (same or different plate) for Monday, the API returns **409 Conflict** with a structured body.

---

## 409 Response Shape

When duplicate is detected (and `replace_existing` is not used), the response is:

**Status:** 409 Conflict

**Body (in `detail`):**

```json
{
  "detail": {
    "code": "DUPLICATE_KITCHEN_DAY",
    "kitchen_day": "Monday",
    "existing_plate_selection_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "You already have a plate reserved for Monday. Continue to cancel your meal and reserve this plate?"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Always `"DUPLICATE_KITCHEN_DAY"` |
| `kitchen_day` | string | The kitchen day (e.g. "Monday") |
| `existing_plate_selection_id` | string | UUID of the user's current plate selection for that day |
| `message` | string | User-facing message for the modal |

---

## Frontend Flow

### 1. First attempt (duplicate detected)

User taps "Reserve" on a plate for Monday, but they already have a plate for Monday.

- **Request:** `POST /api/v1/plate-selections/` with normal payload
- **Response:** 409 with structured `detail` above

### 2. Show modal

Display a modal with:

- **Message:** Use `detail.message` (e.g. "You already have a plate reserved for Monday. Continue to cancel your meal and reserve this plate?")
- **Button 1:** "Yes, cancel my current plate"
- **Button 2:** "No, don't cancel my current plate"

### 3. Button 1: Replace flow

When user taps "Yes, cancel my current plate":

- **Request:** `POST /api/v1/plate-selections/` with the **same payload** as the first attempt, plus:
  - `replace_existing`: `true`
  - `existing_plate_selection_id`: `detail.existing_plate_selection_id` from the 409 response

- **Response:** 201 Created with the new plate selection (same shape as normal create)

The backend cancels the existing plate (refunds credits) and creates the new one in a single atomic transaction.

### 4. Button 2: Keep current plate

When user taps "No, don't cancel my current plate":

- **Action:** Close the modal and navigate back to the explore plate modal. **No API call.**

---

## Replace Request Example

```json
{
  "plate_id": "new-plate-uuid",
  "restaurant_id": "restaurant-uuid",
  "pickup_time_range": "12:00-12:15",
  "target_kitchen_day": "Monday",
  "replace_existing": true,
  "existing_plate_selection_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Validation

- `existing_plate_selection_id` must belong to the current user
- It must match the plate selection for the target `kitchen_day` (backend validates)
- If invalid (wrong user, wrong day, not found), the API returns 400/403/404 as appropriate
