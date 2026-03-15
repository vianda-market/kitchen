# Feedback: Coworker pickup activity on Explore (B2C)

**Purpose:** Request backend support so the B2C app can show when a **coworker** (same employer) has offered or requested pickup for a restaurant on the current kitchen day. Users need to see flags on the Explore page and time ranges in the Explore Plate Modal to order with matching pickup windows.

**Audience:** Backend team.

**Related:** [POST_RESERVATION_PICKUP_B2C.md](./POST_RESERVATION_PICKUP_B2C.md) (volunteer flow), [EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md](./EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md) (coworker scoping)

---

## 1. Coworker-scoped flags (by-city)

`has_volunteer` exists per restaurant but is **any** user. We need **coworker**-only (same employer):

| Field | Level | Description |
|-------|-------|-------------|
| `has_coworker_offer` | Restaurant | True when at least one **coworker** (same employer) has reserved a plate at this restaurant for response `kitchen_day` with `pickup_intent=offer` |
| `has_coworker_request` | Restaurant | True when at least one **coworker** has reserved with `pickup_intent=request` |

**Endpoint:** Add to `GET /api/v1/restaurants/by-city` response, per `RestaurantByCityItem`, when `kitchen_day` is set and user is authenticated with an employer.

**Visibility:** Respect `coworkers_can_see_my_orders` and `can_participate_in_plate_pickups` (per MESSAGING_PREFERENCES_B2C). Omit or set false when user has no employer.

---

## 2. Coworker pickup windows endpoint (new)

The Explore Plate Modal needs the actual pickup time ranges so users can pick a matching slot. Fetch only when the modal is open and `has_coworker_offer || has_coworker_request`.

| Item | Detail |
|------|--------|
| **Method / path** | `GET /api/v1/restaurants/{restaurant_id}/coworker-pickup-windows` |
| **Query params** | `kitchen_day` (required) |
| **Auth** | Bearer token (Customer) |
| **Response** | `{ pickup_windows: [{ pickup_time_range: string, intent: "offer" \| "request", flexible_on_time?: boolean }] }` |

**pickup_time_range:** Same format as plate-selection (e.g. `"11:30-11:45"`).

**intent:** `"offer"` = coworker offered to pick up; `"request"` = coworker requested someone to pick up.

**flexible_on_time:** When intent is `"request"` and the coworker has `flexible_on_time=true`, include this. When true, the backend should include the +/- 30 min adjacent windows in the response so the client can badge all matching slots in the Pickup Window Modal.

---

## 3. flexible_on_time handling

When `flexible_on_time` is true for a request:
- Backend expands the coworker's pickup window by +/- 30 min.
- Include those adjacent windows in the response so the client can badge them as "Matches coworker" in the time slot picker.

---

## 4. Example response (coworker-pickup-windows)

```json
{
  "pickup_windows": [
    { "pickup_time_range": "12:00-12:15", "intent": "offer" },
    { "pickup_time_range": "12:15-12:30", "intent": "request", "flexible_on_time": true }
  ]
}
```

When `flexible_on_time` is true, backend includes the adjacent windows (e.g. 11:45-12:00, 12:30-12:45) so the client receives all matching slots.

---

## 5. Implementation status

| Item | Status |
|------|--------|
| has_coworker_offer, has_coworker_request (by-city) | **Done** |
| GET coworker-pickup-windows | **Done** |
| flexible_on_time in response | **Done** |
| Enriched: kitchen_day param + has_coworker_* for Reservations flow | **Done** |
| Product thumbnail + full-size (1 upload → 2 stored; by-city=thumb, enriched=full) | **Done** |

**Plan update (March 2026):** Frontend confirmed (Section 0): use existing `GET /plates/enriched/{plate_id}` with optional `?kitchen_day=` for coworker flags; keep `GET /restaurants/{id}/coworker-pickup-windows` as separate call; narrow by-city per Section 0. **Thumbnail/full-size:** Store thumbnail + full-size separately (1 upload → 2 stored); by-city uses thumbnail URL, enriched uses full-size. Ready for implementation.

---

## 6. Explore by-city — Required data (GET /restaurants/by-city)

**Use case:** Explore page: RestaurantMapSection (plate cards list + map).

**When called:** On Explore load, city/kitchen_day change.

### UI elements and required fields

| UI element | Required fields | Notes |
|------------|-----------------|-------|
| Plate card thumbnail | `plate_id`, `image_url` | Per plate |
| Plate name | `product_name` | Per plate |
| Restaurant name + cuisine | `restaurant_id`, `name`, `cuisine` | Per restaurant |
| Address line | `address_display` or `street_type`, `street_name`, `building_number` | Per restaurant |
| Map markers | `lat`, `lng` | Per restaurant (nullable) |
| Credits | `credit` | Per plate |
| Savings % | `savings` | Per plate (0–100) |
| Reserved badge | `is_already_reserved`, `existing_plate_selection_id` | Per plate |
| Coworker badges | `has_coworker_offer`, `has_coworker_request` | Per restaurant (conditional: only when user has employer and kitchen_day set) |
| Recommended badge | `is_recommended` | Per plate |
| Favorite heart | `is_favorite` | Per plate (Customer only) |
| Response-level | `kitchen_day`, `city`, `center`, `requested_city` | Top level |

### Fields returned but not used on Explore page

- Plate: `price`, `kitchen_day`, `average_stars`, `average_portion_size`, `portion_size`, `review_count`, `pickup_instructions`, `ingredients_text` — used in modal, not in cards.
- Restaurant: `postal_code`, `is_favorite`, `is_recommended`, `pickup_instructions` — `pickup_instructions` is fallback for modal.

### Optimization recommendations

1. Keep by-city plates **light**: id, name, image_url, credit, savings, badges only.
2. `has_coworker_offer`, `has_coworker_request` — include only when user has employer; omit or false otherwise.
3. Consider pagination or limit if many restaurants.

---

## 7. Enriched / Explore Plate Modal — Required data (GET /plates/enriched/{plate_id})

**Use case:** Explore Plate Modal — plate details, restaurant info, review scores, pickup instructions, Reserve/Pickup actions. Same modal is used from **Explore tab** (pass-through) and **Reservations tab** (enriched-only).

**When called:** When user taps a plate card (Explore) or a reservation (Reservations).

### UI elements and required fields

| UI element | Required fields | Notes |
|------------|-----------------|-------|
| Plate image | `product_image_url` | Fallback: plate.image_url from props |
| Plate name | `product_name` | |
| Ingredients | `ingredients` | Fallback: plate.ingredients_text |
| Credits, savings | `credit`, `price` (or from plate) | Modal uses plate for consistency |
| Coworker badges | `has_coworker_offer`, `has_coworker_request` | **Must be in enriched when modal opened from Reservations** — see below |
| Restaurant name | `restaurant_name` | |
| Address + Maps link | `address_display`, `latitude`, `longitude` | |
| Review stars | `average_stars` | |
| Portion size | `portion_size` | "insufficient_reviews" when < 5 reviews |
| Pickup instructions | `pickup_instructions` | |
| Restaurant id | `restaurant_id` | For coworker-pickup-windows call |

### Coworker flags from Reservations flow

When the modal is opened from **Reservations**, the client has:

- `plate_id` (from selection)
- `restaurant_id` (from enriched)
- `kitchen_day` (from selection.target_kitchen_day)

**Request:** Extend enriched with optional query param `kitchen_day` (and optionally `restaurant_id`). When both are provided and the user has an employer, include `has_coworker_offer` and `has_coworker_request` in the response. This allows the modal to show coworker badges and fetch coworker-pickup-windows when opened from Reservations.

**Alternative:** If adding params is not preferred, a minimal `GET /restaurants/{id}/coworker-flags?kitchen_day=Y` returning `{ has_coworker_offer, has_coworker_request }` would work, but adds a third call from Reservations. Enriched extension is preferred for payload minimality.

### Fields returned but not used in Explore Plate Modal

- `product_id`, `institution_name`, `country_name`, `province`, `city`, `street_type`, `street_name`, `building_number`, `no_show_discount`, `delivery_time_minutes`, `is_archived`, `status`, `created_date`, `modified_date`, etc.

### Optimization recommendations

1. Consider optional `?fields=` param for Explore use case vs full response for B2B.
2. When `kitchen_day` is provided: include `has_coworker_offer`, `has_coworker_request` to support Reservations flow without extra calls.

---

## 8. Thumbnail vs full-size image (product/plate)

**Use case:** Plate card thumbnail on Explore (by-city) vs full-size image in Explore Plate Modal (enriched).

**Request:** Store thumbnail and full-size separately. From 1 uploaded image (PUT product), backend generates and stores both. Avoids: (a) overloading by-city with full-size URLs/payload, (b) client converting full-size to thumbnail on each API call.

| API | Field | Use |
|-----|-------|-----|
| by-city (plates) | `image_url` | Thumbnail URL (small, fast for card list) |
| enriched (modal) | `product_image_url` | Full-size URL (quality for modal) |

**Action:** Add `image_thumbnail_url`, `image_thumbnail_storage_path` to product_info. On PUT product with image upload, generate both thumbnail (e.g. 300×300) and full-size (e.g. max 1024); persist both.
