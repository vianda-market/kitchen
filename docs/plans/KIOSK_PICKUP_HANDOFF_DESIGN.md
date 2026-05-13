# Kiosk Pickup & Handoff Flow — Design Document

**Status:** Draft — needs back-and-forth before implementation
**Date:** 2026-04-04
**Stakeholders:** kitchen backend, vianda-platform (B2B), vianda-app (B2C)

---

## 1. Problem Statement

The current pickup flow has a gap between "customer arrived" (QR scan) and "order complete." Today:

```
Pending → Arrived (QR scan) → Completed (cron/billing auto-completes at kitchen close)
```

This conflates several distinct real-world events:
1. **Customer scans QR** — they're at the restaurant
2. **Restaurant prepares the vianda** — may take minutes
3. **Restaurant hands off the vianda** — physical handoff happens
4. **Customer confirms receipt** — they actually got what they ordered

The B2B kiosk needs to track these steps. The B2C app needs a way for the customer to confirm receipt. And different restaurants have different needs — some want formal code verification, others just want the timer.

---

## 2. Proposed Pickup Status Lifecycle

```
Pending → Arrived → Handed Out → Completed
                         ↑              ↑
                    (restaurant)    (customer)
```

| Status | Who triggers | How | Meaning |
|--------|-------------|-----|---------|
| **Pending** | System | Vianda selection promoted to pickup | Order exists, customer hasn't shown up |
| **Arrived** | Customer (B2C) | Scans QR code | Customer is at the restaurant. Timer starts. |
| **Handed Out** | Restaurant (B2B kiosk) | Code verification OR timer expiry OR manual mark | Restaurant has given the vianda to the customer |
| **Completed** | Customer (B2C) | Taps "I received my vianda" OR auto-completes after grace period | Customer confirms receipt. Immutable final state. |

### Why separate "Handed Out" from "Completed"?

- **Arrived ≠ Handed Out**: The vianda may need preparation after the customer arrives. Scanning a QR code doesn't mean the food is ready.
- **Handed Out ≠ Completed**: The restaurant handing off a vianda doesn't mean the customer got the right order. Customer confirmation closes the loop.
- **Analytics**: We can measure prep time (Arrived → Handed Out) and confirmation delay (Handed Out → Completed) separately.

### Status enum impact

`status_enum` in PostgreSQL needs a new value: `'Handed Out'`. This is used by `vianda_pickup_live` only (via the `vianda_pickup` context). Other tables using `status_enum` are unaffected because they use different context subsets.

The Python `Status` enum gets `HANDED_OUT = "Handed Out"`, and the `vianda_pickup` context becomes: `[Pending, Arrived, Handed Out, Completed, Cancelled]`.

---

## 3. Two Handoff Modes (Per-Restaurant Setting)

Not all restaurants want the same verification level. A busy food truck doesn't want to type codes. A corporate cafeteria does. This should be **configurable per restaurant** by the Supplier Admin.

### 3a. Timer Mode (default)

- Customer scans QR → Arrived. Timer starts on both B2C app and B2B kiosk.
- Kiosk shows the customer's order with a countdown (derived from `expected_completion_time`).
- When timer expires (or restaurant manually marks it), status → **Handed Out**.
- Customer gets a push/prompt to confirm → **Completed**.

No code entry required. The timer is the signal that the customer is present and the handoff window is active.

### 3b. Code Verification Mode (opt-in)

- Customer scans QR → Arrived. Timer starts. Confirmation code generated.
- Customer shows the code to the restaurant clerk.
- Clerk enters the code on the kiosk → backend validates → status → **Handed Out**.
- Customer gets a push/prompt to confirm → **Completed**.

Code verification is an additional security layer. It proves the person at the counter is the person who scanned the QR code.

### Per-restaurant configuration

New column on `ops.restaurant_info`:

```sql
require_kiosk_code_verification BOOLEAN NOT NULL DEFAULT FALSE
```

- `FALSE` (default): Timer mode. Kiosk shows arrived orders, restaurant can manually mark as handed out, or timer expiry triggers it.
- `TRUE`: Code verification mode. Kiosk shows a code entry field. Handing out requires a valid confirmation code.

Only **Supplier Admin** can toggle this setting (via existing restaurant update endpoint). The B2B frontend shows a toggle in restaurant settings.

---

## 4. Handoff Triggers — Who Can Mark "Handed Out"?

| Trigger | Who | When | How |
|---------|-----|------|-----|
| **Code verification** | Restaurant clerk (kiosk) | Clerk enters confirmation code | `POST /restaurant-staff/verify-and-handoff` |
| **Manual mark** | Restaurant clerk (kiosk) | Clerk taps "Mark as handed out" on an Arrived order | `POST /vianda-pickup/{id}/hand-out` |
| **Timer expiry** | B2C app | All countdown extensions exhausted, timer hits 0 | `POST /vianda-pickup/{id}/complete` with `completion_type=timer_expired` |

**Question: Should timer expiry go straight to Completed or to Handed Out?**

Option A: Timer expiry → Handed Out (customer still needs to confirm)
Option B: Timer expiry → Completed (assume handoff happened if timer ran out)

Recommendation: **Option A** for code-verification restaurants (the timer is a fallback, but customer should still confirm). **Option B** for timer-mode restaurants (timer expiry is the end of the flow, no extra confirmation needed — this preserves current behavior).

---

## 5. Customer Confirmation ("I Received My Vianda")

After status reaches "Handed Out," the B2C app should prompt the customer to confirm:

- B2C shows a card: "Did you receive your vianda at [Restaurant Name]?"
- Customer taps "Yes" → `POST /vianda-pickup/{id}/complete` with `completion_type=user_confirmed` → **Completed**
- Customer taps "Report issue" → future: opens a support flow (out of scope for now)

### Auto-completion fallback

If the customer never confirms (app closed, forgot, etc.), a grace period auto-completes:

- **Grace period**: configurable, default 30 minutes after Handed Out.
- **Mechanism**: existing billing cron at kitchen close already completes orders. This covers the daily case. For intra-day completion, we can either:
  - (a) Add a lightweight cron that runs hourly and completes Handed Out orders older than grace period.
  - (b) Let the daily billing cron handle it (simpler, acceptable delay).

Recommendation: **(b)** for now — the billing cron at kitchen close already marks everything Completed. Intra-day auto-completion can be Phase 2.

---

## 6. B2B Kiosk Data Needs (from vianda-platform feedback)

With the above design, here's how each B2B request maps:

| B2B Request | Resolution |
|---|---|
| **Server-authoritative timer** | `expected_completion_time` already stored on vianda_pickup_live. Add to daily-orders response along with `countdown_seconds` from settings. |
| **Confirmation code lookup** | New `GET /restaurant-staff/verify-code` endpoint (or combined verify-and-handoff POST). Scoped to institution. |
| **Daily orders enhancements** | Add `expected_completion_time`, `completion_time`, `was_collected`, `vianda_pickup_id`, `extensions_used`, `pickup_type` to response. |
| **Pickup window summary** | Compute `pickup_window_start`/`pickup_window_end` per restaurant from MIN/MAX of `pickup_time_range`. |
| **No-show detection** | Deferred to Phase 4. Kiosk can derive from `status=Pending` + window passed. |
| **Server timestamp** | Add `server_time` to daily-orders response. |

### New endpoint: Verify and Hand Off

```
POST /api/v1/restaurant-staff/verify-and-handoff
{
  "confirmation_code": "AB3X7K",
  "restaurant_id": "uuid"
}
```

Response on match:
```json
{
  "match": true,
  "customer_name": "Maria G.",
  "vianda_pickup_ids": ["uuid1"],
  "viandas": [{ "vianda_name": "Grilled Chicken", "quantity": 1 }],
  "status": "Handed Out",
  "handed_out_time": "2026-04-04T12:05:00-03:00"
}
```

This endpoint both verifies the code AND transitions the order to Handed Out in one call (for code-verification restaurants).

For timer-mode restaurants, the kiosk uses `POST /vianda-pickup/{id}/hand-out` to manually mark individual orders.

---

## 7. `extensions_used` and Timer Extensions

The B2C app currently counts down client-side with no backend communication on extensions. To support `extensions_used`:

- Add `extensions_used INTEGER DEFAULT 0` to `vianda_pickup_live`.
- Add `POST /api/v1/vianda-pickup/{id}/extend` (B2C endpoint) that increments `extensions_used`, updates `expected_completion_time += countdown_seconds`, and checks `extensions_used < max_extensions`.
- The B2B kiosk reads `extensions_used` from daily-orders to show how many extensions remain.

This is a new B2C endpoint. The B2C app needs to call it instead of extending the timer purely client-side. This is a **breaking behavioral change** for B2C — the B2C agent needs to know about this.

**Phase question:** Should we build the extend endpoint now, or ship `extensions_used` as always-0 scaffolding and add the endpoint later?

---

## 8. Supplier Operator Role & Kiosk Access

Operators are field workers, not administrators. Their access should be kiosk-focused:

### What Operator can do:
- View daily orders (kiosk main view)
- Verify confirmation codes and mark orders as handed out
- Mark orders as complete
- View customer feedback (vianda reviews)
- View their own profile

### What Operator cannot do:
- CRUD on products, plans, viandas, restaurants, QR codes
- Create/edit/delete users or addresses
- Manage institution entities or billing
- Change restaurant settings (including kiosk code verification toggle)

### Implementation approach:
Gate at the **route factory level** — all auto-generated CRUD routes block Supplier Operators. Kiosk routes explicitly allow all Supplier roles. Details in implementation plan.

---

## 9. Open Questions

1. **Timer expiry behavior per mode**: Should timer-mode restaurants auto-complete on expiry (current behavior), while code-verification restaurants go to Handed Out and wait for customer confirmation? Or should both modes require customer confirmation?

2. **Grace period for customer confirmation**: How long after Handed Out should we wait before auto-completing? 30 min? End of kitchen day? Should this be configurable?

3. **Extensions endpoint priority**: Build the B2C extend-timer endpoint now (so `extensions_used` is real), or ship as scaffolding (always 0) and build it as a follow-up?

4. **Manual hand-out from kiosk**: In timer-mode (no code verification), should the kiosk have a "Mark as handed out" button per order, or does the restaurant just let the timer run?

5. **Partial handoff**: If a customer has 2 viandas and the restaurant hands off 1 first, do we support per-vianda handoff? Or is it all-or-nothing per confirmation code? (Recommendation: all-or-nothing per confirmation code for simplicity.)

---

## 10. Phasing

| Phase | Scope | Depends On |
|---|---|---|
| **Phase 1** (this PR) | Enhanced daily-orders response (timer fields, pickup window, server_time, vianda_pickup_id). `extensions_used` column (always 0). Supplier Operator role restrictions. | Nothing |
| **Phase 2** | `GET /restaurant-staff/verify-code` endpoint. `require_kiosk_code_verification` restaurant setting. `Handed Out` status. `POST /restaurant-staff/verify-and-handoff`. | Phase 1 |
| **Phase 3** | `POST /vianda-pickup/{id}/extend` (B2C). Real `extensions_used` tracking. B2C customer confirmation prompt ("I received my vianda"). | Phase 2 |
| **Phase 4** | No-show detection (backend status or computed flag). Auto-completion grace period for Handed Out orders. | Phase 2 |

---

## 11. Cross-Repo Impact

| Repo | What they need to know |
|---|---|
| **vianda-platform (B2B)** | New daily-orders fields, verify-code endpoint, kiosk code verification toggle in restaurant settings, Operator role restrictions |
| **vianda-app (B2C)** | Customer confirmation prompt after Handed Out, extend-timer endpoint (Phase 3), `completion_type` values |
| **infra-kitchen-gcp** | No infra changes for Phase 1-2. Phase 4 may need a new cron for intra-day auto-completion. |
