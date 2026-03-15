# Backend feedback: Post-reservation pickup intent, co-worker alert, and pickup flow (B2C)

**Purpose:** Define the API contract required for the B2C post-reservation flow: pickup intent selection, co-worker alerts, QR scan at restaurant, arrival countdown, pickup confirmation, and post-pickup survey. Implementation plan: [POST_RESERVATION_PICKUP_INTENT_FLOW.md](../../../plans/POST_RESERVATION_PICKUP_INTENT_FLOW.md).

**Audience:** Backend team. The documented APIs are the source of truth for the B2C client.

---

## 1. Pickup intent storage

After the user reserves a plate and selects a pickup window, they choose one of three intents:

| Intent | Description |
|--------|-------------|
| `offer` | User offers to pick up a co-worker's meal (same restaurant, same time) |
| `request` | User requests a co-worker to pick up their meal; if no one volunteers, user is responsible |
| `self` | User will pick up their own plate |

**Required:** Store the intent on the plate selection (or linked entity). For `request`, also store `flexible_on_time` (boolean): user is flexible on time (+/- 30 min) for matching purposes.

**Suggested contract:**

| Item | Detail |
|------|--------|
| **Method / path** | `PATCH /api/v1/plate-selections/{plate_selection_id}` or `PUT /api/v1/plate-selections/{plate_selection_id}/pickup-intent` |
| **Request body** | `{ "intent": "offer" | "request" | "self", "flexible_on_time"?: boolean }` — `flexible_on_time` only when `intent === "request"` |
| **Auth** | Bearer token (Customer). |
| **Response** | 200 OK with updated plate selection. |

---

## 2. List co-workers with eligibility (Offer to pick up)

When the user selects "Offer to pick up", the client needs a list of co-workers (same employer) to notify. Each co-worker must be marked as **eligible** (selectable) or **ineligible** (greyed out).

**Eligibility rules (backend to enforce):**
- **Eligible:** Co-worker has not ordered yet for the same kitchen day
- **Ineligible:** Co-worker already ordered from a different restaurant or different pickup time

**Suggested contract:**

| Item | Detail |
|------|--------|
| **Method / path** | `GET /api/v1/plate-selections/{plate_selection_id}/coworkers` or `GET /api/v1/users/me/coworkers?plate_selection_id=...` |
| **Query / path** | `plate_selection_id` to scope by restaurant, kitchen day, pickup window |
| **Auth** | Bearer token (Customer). |
| **Response** | Array of `{ user_id, first_name, last_initial, eligible: boolean }`. Display as "FirstName L." |

---

## 3. Send co-worker alert

When the user selects co-workers and taps Send, the client notifies them.

**Suggested contract:**

| Item | Detail |
|------|--------|
| **Method / path** | `POST /api/v1/plate-selections/{plate_selection_id}/notify-coworkers` |
| **Request body** | `{ "user_ids": ["uuid1", "uuid2", ...] }` |
| **Auth** | Bearer token (Customer). |
| **Response** | 200 OK or 202 Accepted. |
| **Validation** | `user_ids` must be eligible co-workers (same employer, not yet ordered for conflicting slot). |

---

## 4. QR scan — signal arrival

User taps Pickup, opens camera, scans the restaurant's QR code. On valid scan, the client signals the backend that the person **arrived** at the restaurant.

**Existing reference:** [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md) and archived docs mention `POST /plate-pickup/scan-qr`. `GET /plate-pickup/pending` returns `qr_code_id`.

**Required:**

| Item | Detail |
|------|--------|
| **Method / path** | `POST /api/v1/plate-pickup/scan-qr` |
| **Request body** | Scanned payload — format TBD by backend. Likely `{ "qr_code_id": "uuid" }` or encoded URL that resolves to `restaurant_id` + `qr_code_id`. Backend to define QR encoding. |
| **Auth** | Bearer token (Customer). |
| **Response** | 200 OK. Backend updates pickup status to "Arrived". |
| **Errors** | 400 if invalid/mismatched QR; 403 if user has no pending pickup for that restaurant. |

**Ask:** Define the exact QR payload format (e.g. JSON, URL with query params) so the client can parse and send correctly.

---

## 5. Complete pickup (I have picked up my food)

After the 10-minute countdown, the user taps "I have picked up my food". The client must signal the backend that the pickup is complete.

**Suggested contract:**

| Item | Detail |
|------|--------|
| **Method / path** | `POST /api/v1/plate-pickup/{pickup_id}/complete` or `PATCH /api/v1/plate-pickup/pending` with `{ "status": "Completed" }` |
| **Auth** | Bearer token (Customer). |
| **Response** | 200 OK. |

---

## 6. Post-pickup survey

After the user confirms pickup, a survey modal collects:
- **Stars** (1–5) for the plate
- **Portion size** (1–3)

**Suggested contract:**

| Item | Detail |
|------|--------|
| **Method / path** | `POST /api/v1/plates/{plate_id}/reviews` or `POST /api/v1/plate-selections/{plate_selection_id}/feedback` |
| **Request body** | `{ "stars": 1-5, "portion_size": 1-3 }` |
| **Auth** | Bearer token (Customer). |
| **Response** | 201 Created. |
| **Validation** | User must have completed pickup for this plate selection. |

**Note:** Enriched plate response already includes `average_stars`, `average_portion_size`, `review_count` — backend to confirm these are updated from this feedback.

---

## 7. Plate selection editability

**Current:** Plate selections are **immutable** (no PUT or DELETE per [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md)).

**Required:** Plate selections must be **editable** to support future UI features (e.g. change pickup window, change plate, cancel).

**Editability window:**
- **Editable:** Until **1 hour before the kitchen_day opens** for the market
- **Not editable:** After that cutoff

**Suggested contract:**

| Item | Detail |
|------|--------|
| **Method / path** | `PUT /api/v1/plate-selections/{plate_selection_id}` or `PATCH /api/v1/plate-selections/{plate_selection_id}` |
| **Request body** | `{ "pickup_time_range"?: "12:00-12:15", "plate_id"?: "uuid", ... }` — fields that can be updated |
| **Auth** | Bearer token (Customer). |
| **Response** | 200 OK with updated plate selection. |
| **Errors** | 403 or 422 if past editability cutoff (1 hour before kitchen_day opens for market). |
| **Optional** | `GET /api/v1/plate-selections/{id}` or response field `editable_until` (ISO datetime) so client can show/hide edit UI. |

**Delete/cancel:** `DELETE /api/v1/plate-selections/{plate_selection_id}` — same editability window.

---

## 8. Summary table

| Capability | Endpoint | Status |
|------------|----------|--------|
| Store pickup intent | `PATCH /plate-selections/{id}` (includes `pickup_intent`, `flexible_on_time`) | **Implemented** |
| List co-workers with eligibility | `GET /plate-selections/{id}/coworkers` | **Implemented** |
| Notify co-workers | `POST /plate-selections/{id}/notify-coworkers` | **Implemented** |
| Signal arrival (QR scan) | `POST /plate-pickup/scan-qr` | **Implemented** — contract TBD |
| Complete pickup | `POST /plate-pickup/{id}/complete` | **Implemented** |
| Pending response (plate count) | `GET /plate-pickup/pending` — returns `plate_pickup_ids`, `total_plate_count` | **Implemented** |
| Explore: has volunteer | Restaurant explore — `has_volunteer` per restaurant for same kitchen_day | **Implemented** |
| Post-pickup survey | `POST /plate-reviews/` with `plate_pickup_id` | **Implemented** |
| Edit plate selection | `PATCH /plate-selections/{id}` — editable until 1h before kitchen_day | **Implemented** |
| Delete plate selection | `DELETE /plate-selections/{id}` — same editability window | **Implemented** |

---

**Document status:** Backend implementation complete. APIs are available for B2C client integration.
