
# Post-Reservation Pickup Intent Backend Implementation Plan

## Executive Summary

The frontend document ([feedback_post_reservation_pickup_intent.md](../api/b2c_client/feedback_post_reservation_pickup_intent.md)) defines 8 capabilities. This plan analyzes each against the current codebase and proposes a backend-first implementation that centralizes logic and minimizes duplication.

**Key additions from product feedback:**

- **Matching**: When an offer matches requests at same restaurant/time, the offering user is assigned ALL plates for pickup; other users depend on them and cannot pick up themselves. Assigned user must see plate count in app.
- **plate_selection_info + history**: Rename to `plate_selection_info` with `plate_selection_history` and triggers (DB tear-down/rebuild, no migration).
- **Explore visibility**: Users exploring restaurants see if any user has offered to pickup from each restaurant for the same kitchen_day ("has volunteer" indicator).
- **Terminology**: Use `offer`, `request`, `self` consistently (one term per concept).
- **Enum alignment**: Change `pickup_type_enum` to `offer`, `request`, `self` (replace for_others/by_others).
- **Volunteer multi-plate**: A volunteer can pick up different plate_ids from the same restaurant (matching by restaurant + time, not plate_id).

---

## Current State vs Requirements


| Capability                    | Current State                                                                                       | Gap                                                                                           |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **1. Pickup intent**          | `plate_selection` has no intent; `pickup_preferences` has `pickup_type` (self/for_others/by_others) | Add `pickup_intent` + `flexible_on_time`; change enum to offer/request/self                   |
| **2. List coworkers**         | No endpoint; `user_info.employer_id` exists                                                         | New endpoint + service                                                                        |
| **3. Notify coworkers**       | No mechanism                                                                                        | New endpoint; store notifications; respect user notification settings                         |
| **4. QR scan**                | Exists: `POST /plate-pickup/scan-qr` with `qr_code_payload`                                         | Minor: document QR payload format                                                             |
| **5. Complete pickup**        | Exists: `POST /plate-pickup/{pickup_id}/complete`                                                   | Gap: `GET /pending` does not return `plate_pickup_id`(s); assigned user needs plate count      |
| **6. Post-pickup survey**     | Exists: `POST /plate-reviews/` with `plate_pickup_id`                                               | Align schema: document accepts `plate_selection_id`; current uses `plate_pickup_id` (correct) |
| **7. Edit plate selection**   | No PUT/DELETE; immutable                                                                            | New: PATCH + DELETE with editability window; PATCH allows cancel (credits refund)              |
| **8. Delete plate selection** | No DELETE                                                                                           | Same as #7                                                                                    |
| **9. Explore volunteers**     | No visibility                                                                                       | New: restaurant list shows "has volunteer" for same kitchen_day                                |


---

## Architecture Decisions

### 1. Editability Window: "1 hour before kitchen day opens"

- **Definition**: Kitchen day "opens" = `business_hours.open` (11:30 AM per [market_config.py](../../app/config/market_config.py)).
- **Cutoff**: Editable until **10:30 AM local** on the kitchen day date.
- **Market resolution**: `plate_selection` → `restaurant` → `address` → `country_code` → `MarketConfiguration`.

### 2. Pickup Intent: Terminology, Enum Alignment, and Storage

**Terminology (one term per concept):** Use `offer`, `request`, `self` consistently.

**Enum alignment — should we change `pickup_type_enum`?**

Current `pickup_type_enum` (used by `pickup_preferences`): `self`, `for_others`, `by_others`.


| Option             | Description                                                                             | Pros                                                                                                 | Cons                                                                                                   |
| ------------------ | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **A. Change enum** | Replace `pickup_type_enum` with `offer`, `request`, `self` (drop for_others, by_others) | Single terminology; pickup_preferences and plate_selection_info share same values; clearer semantics | Requires updating schema, PickupType Python enum, enum_service, all references                         |
| **B. Keep both**   | Keep `pickup_type_enum` as-is; add new `pickup_intent` on plate_selection_info only     | No change to pickup_preferences; isolated                                                            | Two concepts; mapping confusion (offer≈for_others, request≈by_others); violates "one term per concept" |


**Recommendation: Option A — change the enum.** Since the DB is torn down and rebuilt, migration is straightforward. Update `pickup_type_enum` to `('offer', 'request', 'self')` and the Python `PickupType` enum accordingly. `pickup_preferences.pickup_type` and `plate_selection_info.pickup_intent` (or `pickup_type` if we unify the column name) both use the same enum. One term per concept across the codebase.

**Storage options — pros and cons:**


| Option                           | Pros                                                   | Cons                                                                                                                          |
| -------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| **A. Add to plate_selection**    | Single source; simple; intent lives with the selection | plate_selection grows; need to update all FKs if we rename table                                                              |
| **B. Add to pickup_preferences** | pickup_preferences already used for matching           | pickup_preferences is per-user preference; plate_selection can have multiple preferences (offer + requests); semantics differ |
| **C. New table pickup_intent**   | Clean separation                                       | Extra join; more complexity                                                                                                   |


**Recommendation:** Option A — add `pickup_intent` and `flexible_on_time` to plate_selection (renamed to `plate_selection_info`). Keeps intent with the selection; aligns with "one selection, one intent" model.

### 3. Centralized Editability Logic

- New function in [kitchen_day_service.py](../../app/services/kitchen_day_service.py): `get_plate_selection_editable_until(plate_selection_id, db) -> Optional[datetime]`.
- Returns `editable_until` (ISO) or None if past cutoff. Reused by: PATCH, DELETE, and GET response.

### 4. Coworker Notification and User Settings

- Store notifications in `coworker_pickup_notification` (who notified whom, when) for audit.
- **Backend behavior**: Send push (Firebase/APNs) or in-app notification depending on each user's notification settings. App needs a notification configuration screen where users opt in/out.
- **Fallback**: Users who disable notifications can still see volunteers in the restaurant explore list (see Section 5). No notification = no push, but volunteer visibility remains.

### 5. Matching: Offer Assigns All Plates to Volunteer

When a user with `pickup_intent=offer` matches with users who have `pickup_intent=request` at the same restaurant and within the acceptable time range (±30 min when `flexible_on_time=true`):

- The **offering user** is assigned ALL plates for pickup (their own + all matched requesters' plates).
- The **requesting users** can no longer pick up themselves; they depend entirely on the assigned volunteer.
- The **assigned user** must see in the app how many plates they will be picking up (e.g. "You're picking up 4 plates").
- `plate_pickup_live` (or equivalent) links each plate to the assigned picker; requesters' records show `picked_up_by_user_id` or similar.

**Volunteer picks up multiple different plates:** A volunteer may pick up 2+ different `plate_id`s from the same restaurant, as long as the restaurant offers more than 1 plate for that kitchen_day. Matching is by **restaurant + kitchen_day + time window**, not by plate_id. The grouped plates for the assigned user are therefore not limited to the same plate — they can be a mix (e.g. volunteer's Grilled Chicken + coworker's Vegetarian Pasta + another coworker's Salmon Bowl). The pending response `orders` array and `total_plate_count` must reflect this: each distinct plate selection is a separate item; `total_plate_count` = count of plate_selections (or plate_pickup_live records) the volunteer is responsible for.

---

## Implementation Plan

### Phase 1: Schema, plate_selection_info/history, Enum Change, and Editability (Foundation)

**1.1 Database: Rename plate_selection → plate_selection_info + plate_selection_history**

- **DB tear-down/rebuild** — no migration; schema changes applied fresh.
- Rename `plate_selection` → `plate_selection_info` (follows `_info` pattern per [DATABASE_TABLE_NAMING_PATTERNS.md](../database/DATABASE_TABLE_NAMING_PATTERNS.md)).
- Create `plate_selection_history` with same columns + `event_id`, `valid_from`, `valid_until`.
- Add trigger (in [trigger.sql](../../app/db/trigger.sql)) to copy INSERT/UPDATE/DELETE to history.
- Update all foreign keys: `plate_selection_id` references now point to `plate_selection_info`.
- Add to `plate_selection_info`:
  - `pickup_intent VARCHAR(20) DEFAULT 'self'` (offer | request | self)
  - `flexible_on_time BOOLEAN NULL` (only when intent=request)

**1.2 Change pickup_type_enum**

- Replace `pickup_type_enum` values: drop `for_others`, `by_others`; add `offer`, `request`. Keep `self`.
- New enum: `CREATE TYPE pickup_type_enum AS ENUM ('offer', 'request', 'self');`
- Update `pickup_preferences.pickup_type` to use new enum.
- Update Python [PickupType](../../app/config/enums/pickup_types.py): `OFFER`, `REQUEST`, `SELF`.
- Update [enum_service.py](../../app/services/enum_service.py), [db.py](../../app/utils/db.py), [db_pool.py](../../app/utils/db_pool.py), and any schemas referencing pickup_type.

**1.3 Create coworker_pickup_notification**

- `notification_id`, `plate_selection_id`, `notifier_user_id`, `notified_user_id`, `created_date`
- Optional: `user_notification_preference` table for opt-in/out (or extend `user_info` with `coworker_pickup_notifications_enabled`).

**1.4 Editability service**

- In [kitchen_day_service.py](../../app/services/kitchen_day_service.py):
  - `get_plate_selection_editable_until(plate_selection_id, db) -> Optional[datetime]`
  - `is_plate_selection_editable(plate_selection_id, db) -> bool`
- Logic: resolve `plate_selection` → restaurant → address → country_code; get `business_hours.open` for kitchen_day; compute `target_date 10:30 AM local`; compare with now (in market TZ).

**1.5 DTOs and schemas**

- Update [PlateSelectionDTO](../../app/dto/models.py): add `pickup_intent`, `flexible_on_time`.
- Update [PlateSelectionResponseSchema](../../app/schemas/consolidated_schemas.py): add `pickup_intent`, `flexible_on_time`, `editable_until` (optional, computed).

---

### Phase 2: Plate Selection PATCH and DELETE

**2.1 PATCH /api/v1/plate-selections/{id}**

- Allowed fields: `pickup_time_range`, `plate_id`, `pickup_intent`, `flexible_on_time`, and **cancel** (or `status: "Cancelled"`).
- Validate editability via `is_plate_selection_editable`.
- **Cancel via PATCH**: When user cancels (e.g. `{ "status": "Cancelled" }` or `{ "cancel": true }`), refund credits to subscription, soft-delete/archive related records. Same editability window as DELETE.
- If `plate_id` changes: validate user has sufficient credits for new plate; validate new plate (same restaurant); update related `plate_pickup_live` and transactions (complex; consider Phase 2b for plate_id change).
- **Recommendation**: Phase 2a supports `pickup_time_range`, `pickup_intent`, `flexible_on_time`, and cancel; defer `plate_id` change to a later phase.

**2.2 DELETE /api/v1/plate-selections/{id}**

- Soft-delete (or archive) plate_selection and cascade to plate_pickup_live, client_transaction (refund credits), restaurant_transaction.
- Validate editability before delete.
- Reuse existing patterns (e.g. [mark_plate_selection_complete](../../app/services/crud_service.py) inverse for refund).

**2.3 GET /api/v1/plate-selections/{id}**

- Include `editable_until` in response (computed) so client can show/hide edit UI.

---

### Phase 3: Pickup Intent on Create

**3.1 Extend POST /api/v1/plate-selections/**

- Accept optional `pickup_intent` and `flexible_on_time` in request body.
- Default `pickup_intent` = "self" if omitted.
- Validate: `flexible_on_time` only when `intent === "request"`.

---

### Phase 4: Coworkers and Notification

**4.1 GET /api/v1/plate-selections/{id}/coworkers**

- New route in [plate_selection.py](../../app/routes/plate_selection.py).
- New service: `get_coworkers_with_eligibility(plate_selection_id, current_user_id, db)`.
- Logic:
  - Get current user's `employer_id`; return 403 if null.
  - List users with same `employer_id` (exclude current user).
  - For each: **eligible** = no plate_selection for same kitchen_day (any restaurant/time); **ineligible** = has order for different restaurant or conflicting pickup time.
  - Resolve kitchen_day and target_date from plate_selection.
- Response: `[{ user_id, first_name, last_initial, eligible }]`.

**4.2 POST /api/v1/plate-selections/{id}/notify-coworkers**

- Body: `{ "user_ids": ["uuid1", ...] }`.
- Validate: all user_ids are eligible (reuse eligibility logic).
- Insert into `coworker_pickup_notification` (or equivalent).
- Return 200/202. Push integration deferred.

---

### Phase 5: Pending Response Enhancement and Assigned User Plate Count

**5.1 Add plate_pickup_ids and total_plate_count to GET /plate-pickup/pending**

- [get_pending_orders_with_company_matching](../../app/services/plate_pickup_service.py) currently returns aggregated orders.
- Add `plate_pickup_ids: UUID[]` (or `orders[].plate_pickup_id`) so the client can call `POST /plate-pickup/{id}/complete` for each.
- **Assigned user plate count**: When the current user is the volunteer (offer matched with requests), include `total_plate_count: int` — "You're picking up N plates". Sum of all plate_selections (or plate_pickup_live records) the volunteer is responsible for at this restaurant.
- **Different plate_ids**: The volunteer's bundle can include different plates (e.g. Grilled Chicken x1, Vegetarian Pasta x2, Salmon Bowl x1). The `orders` array must list each distinct plate with its count; `total_plate_count` = total number of physical plates (sum of quantities). Matching is by restaurant + kitchen_day + time, not by plate_id.
- Alternatively: add `POST /plate-pickup/complete-all` that completes all pending pickups for the user at the scanned restaurant (simpler for single-order case).

---

### Phase 5b: Explore Visibility — "Has Volunteer" Indicator

**5b.1 Add has_volunteer to restaurant explore response**

- When users explore restaurants (e.g. `GET /restaurants/by-city` or equivalent), include per-restaurant: `has_volunteer: boolean` for the same `kitchen_day`.
- **Logic**: `has_volunteer = true` if at least one user has `pickup_intent=offer` for that restaurant and kitchen_day (and is within editability window / not cancelled).
- Users can select a restaurant that has a volunteer and know they will get matched with this person for pickup.
- Works even for users who disable notifications — they see volunteers in the list instead of receiving push.

---

### Phase 6: QR Payload and Survey Alignment

**6.1 Document QR payload**

- Current: `qr_code_payload` (string). [plate_pickup_service](../../app/services/plate_pickup_service.py) uses `_extract_restaurant_id` for `restaurant_id:` prefix.
- Document in API spec: `{ "qr_code_payload": "<value from QR>" }` or URL format if different.

**6.2 Survey endpoint**

- Keep `POST /plate-reviews/` with `plate_pickup_id` (one review per pickup).
- Document that frontend should use `plate_pickup_id` from create response or pending response.

---

## Service Layer Organization (Minimize Duplication)

```
plate_selection_service.py     # create, update, delete; orchestration
plate_selection_validation.py   # existing validators
plate_selection_editability.py  # NEW: get_editable_until, is_editable (or in kitchen_day_service)
coworker_service.py            # NEW: get_coworkers_with_eligibility, validate_eligible_for_notify
```

- **Editability**: Single source in `kitchen_day_service` or new `plate_selection_editability` module.
- **Eligibility**: Centralized in `coworker_service`; used by both GET coworkers and POST notify.

---

## Resolved Questions (Product/Frontend)

1. **Co-worker notification**: Backend sends push or in-app notification depending on each user's notification settings. App needs notification configuration screen (opt in/out). Users who disable notifications still see volunteers in explore list.
2. **Complete pickup**: Add `plate_pickup_ids` to pending response (and `total_plate_count` for assigned user).
3. **Plate change on edit**: Yes, PATCH allows changing `plate_id` as long as user has sufficient credits. PATCH also allows cancel — user gets credits back.
4. **Pickup intent enum**: Change `pickup_type_enum` to `offer`, `request`, `self` (replace for_others/by_others). Single terminology across pickup_preferences and plate_selection_info.
5. **Volunteer multi-plate**: A volunteer can pick up different plate_ids from the same restaurant. Matching is by restaurant + kitchen_day + time window, not plate_id.

---

## Files to Modify/Create


| File                                                             | Action                                                                                                                                            |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/db/schema.sql`                                              | Rename plate_selection → plate_selection_info; add plate_selection_history; change pickup_type_enum to offer/request/self; add pickup_intent, flexible_on_time; add coworker_pickup_notification |
| `app/db/trigger.sql`                                             | Add plate_selection_history trigger                                                                                                               |
| `app/config/enums/pickup_types.py`                               | Change PickupType to OFFER, REQUEST, SELF                                                                                                          |
| `app/services/enum_service.py`                                   | Update pickup_type values                                                                                                                          |
| `app/utils/db.py`                                                | Update pickup_type_enum reference if needed                                                                                                       |
| `app/utils/db_pool.py`                                           | Update pickup_type_enum reference if needed                                                                                                       |
| `app/dto/models.py`                                              | Add fields to PlateSelectionDTO                                                                                                                   |
| `app/schemas/consolidated_schemas.py`                            | Add to create/update/response schemas; update pickup_type Literal if used                                                                         |
| `app/services/kitchen_day_service.py`                            | Add get_plate_selection_editable_until, is_plate_selection_editable                                                                               |
| `app/services/plate_selection_service.py`                        | Add update_plate_selection, delete_plate_selection                                                                                                |
| `app/services/coworker_service.py`                               | **New** - get_coworkers_with_eligibility                                                                                                          |
| `app/routes/plate_selection.py`                                  | Add PATCH, DELETE, GET coworkers, POST notify                                                                                                     |
| `app/services/plate_pickup_service.py`                           | Add plate_pickup_ids, total_plate_count to pending response; support different plate_ids in orders                                                 |
| `app/services/restaurant_explorer_service.py`                    | Add has_volunteer per restaurant for explore (by-city)                                                                                            |
| `app/services/crud_service.py`                                   | Update table name plate_selection → plate_selection_info                                                                                          |
| `docs/api/b2c_client/feedback_post_reservation_pickup_intent.md` | Update with implementation status                                                                                                                 |


---

## Suggested Implementation Order

1. **Phase 1** (Schema: plate_selection_info/history + pickup_type_enum change + editability) — unblocks PATCH/DELETE
2. **Phase 2** (PATCH/DELETE including cancel) — core editability
3. **Phase 3** (Intent on create) — quick win
4. **Phase 5** (Pending: plate_pickup_ids + total_plate_count + different plate_ids) — unblocks complete flow
5. **Phase 5b** (Explore: has_volunteer) — volunteer visibility
6. **Phase 4** (Coworkers + notification) — can be parallelized with 5/5b
7. **Phase 6** (Documentation) — ongoing
