# Pickup Handoff Trust Model

**Status:** Requirements defined — ready for engineering plans
**Date:** 2026-04-04

---

## The Problem

Vianda collects payment from customers and pays restaurants, but is never physically present when the vianda changes hands. This creates a three-party trust gap:

```
Customer ←→ Restaurant
        ↑
      Vianda
   (not present)
```

**Vianda is on the hook for fulfillment.** If a customer claims they didn't receive their vianda, or a restaurant claims they handed it off, Vianda has no first-hand evidence either way.

**Design constraint: low friction above all else.** Restaurant clerks are slammed during lunch rush on business days. Some operate from a cheap phone, not a tablet. Some are food truck operators doing everything solo. Every mitigation mechanism must be optional, progressive, and designed for worst-case hardware and attention. We don't impose verification burdens — we offer tools, and let each restaurant manage its own risk appetite.

---

## Real Risks

### Customer-Side

| # | Risk | Description | Severity |
|---|------|-------------|----------|
| **C1** | **False non-receipt claim** | Customer picks up the vianda, then claims they didn't receive it to get a credit/refund | High |
| **C2** | **Confirmation screen replay** | Customer picks up vianda, hands phone to someone else showing the post-scan confirmation screen. Second person approaches clerk pretending they just scanned, tries to get another vianda | Medium |
| **C3** | **Delegated pickup abuse** | Customer delegates pickup, then both try to claim separately | Low |

### Restaurant-Side

| # | Risk | Description | Severity |
|---|------|-------------|----------|
| **R1** | **Phantom handoff** | Restaurant marks order as handed out without actually serving the vianda | High |
| **R2** | **Portion/quality shortchanging** | Restaurant serves a smaller or lower-quality vianda than what the customer paid for | Medium |

---

## The Handoff Flow

This is the target end-to-end flow. Every step is designed so that if either party skips their optional action, the system still resolves gracefully via timeout.

### Step 1: Customer arrives (B2C)

Customer scans restaurant QR code.
- B2C app shows confirmation screen with **numeric code** and **live count-up timer** ("Time since scan: 0:04...")
- B2C app **blocks screenshots** of this screen systemically — the only way to replay is to physically hand someone the phone, which the count-up timer exposes
- Backend records `arrival_time`, generates numeric confirmation code, sets `expected_completion_time`

### Step 2: Clerk sees arrival (B2B kiosk)

The kiosk receives a **push notification** and a new entry appears in the **live arrivals queue**.

Each queue entry shows:
- Initials only (e.g. "M.G.") — no full names for privacy
- Vianda(s) ordered (e.g. "1x Grilled Chicken")
- Count-up timer since scan
- Numeric code (visible to clerk on their screen)

The clerk has two paths depending on the restaurant's verification mode:

**Visual match (all restaurants):** Customer approaches counter. Clerk compares what they see on their queue (initials, items, code, timer) with what the customer shows on their phone. If both screens show the same code and timers are in sync, the clerk knows the person is legitimate. No typing required — just a visual comparison.

**Code entry (opt-in restaurants):** For restaurants that want system-enforced verification, the clerk taps the queue entry and types the numeric code from the customer's phone. Auto-focus, auto-submit on last digit. This locks the order to this handoff event and consumes the code.

Either way, the clerk now knows who this customer is and what they ordered.

### Step 3: Food prep and handoff (physical)

Clerk prepares the vianda (or it's already ready). Clerk gives food to customer.

Clerk **may or may not** tap "Delivered" on the kiosk. This is optional — it creates a stronger record but is not required.

### Step 4: Customer confirmation (B2C)

If the clerk tapped "Delivered," the customer gets an **immediate notification**: "Did you receive your vianda from [Restaurant]?"

Two options:
- **"Received"** → order completes, survey opens (see Step 5)
- **"I didn't receive this"** → immediate dispute filed, routed to support queue

This confirmation has a **5-minute timeout**. If the customer doesn't respond within 5 minutes, the system auto-completes in favor of the restaurant (the clerk did mark it as delivered).

If nobody does anything (clerk didn't mark delivered, customer didn't confirm), the **handoff times out** at the currently configured timer window (default 5 minutes from arrival). The system auto-completes and the customer sees the survey next time they open the app.

### Step 5: Post-pickup survey (B2C)

After completion (by any path), the customer sees the review survey. **First question is portion size:**

> "Check your food — how was the portion size?"

Rating 2 or 3 → survey continues normally (stars, would_order_again, comment).

Rating **1 (small)** → an additional option appears: **"File a portion complaint."** This is intentionally one extra tap of friction because a size-1 rating is subjective — a customer might think "small" but still be satisfied. The complaint is the real signal.

If the customer taps "File a portion complaint":
1. Prompt to take a photo of the vianda ("Snap a photo of your vianda before eating so we can review it")
2. Text field for details
3. Submits to support queue with order ID, timestamps, photo, and complaint flag

**Why this matters:** Per the Vianda supplier SLA, restaurants must serve the same portion to Vianda pickup customers as they would to dine-in customers. A size-1 rating alone is subjective noise. A size-1 rating **plus a complaint** is an actionable flag that accumulates on the restaurant's record. Repeated size-1 + complaint patterns can trigger SLA review and penalties.

### Step 6: End of kitchen day (system)

At kitchen close, all non-closed-out orders are **auto-completed by the billing cron**. This frees the queue and ensures no orders are left hanging. This is existing behavior — no change needed.

---

## How This Maps to Status Lifecycle

```
Pending → Arrived → [Handed Out] → Completed
```

| Status | Triggered by | What it means |
|--------|-------------|---------------|
| **Pending** | System (vianda selection promoted) | Order exists, customer hasn't shown up |
| **Arrived** | Customer scans QR (B2C) | Customer is at restaurant. Timer and code active. |
| **Handed Out** | Clerk taps "Delivered" (B2B) OR code entry match (B2B) | Restaurant claims they gave the vianda. Optional — system works without it. |
| **Completed** | Customer taps "Received" (B2C) OR 5-min timeout after Handed Out OR handoff timer expiry OR kitchen-day close cron | Final state. Triggers survey if not yet shown. |

The "Handed Out" status is the key addition. It separates "customer is here" from "vianda was given" from "customer confirms." Three timestamps, up to two independent confirmations for dispute resolution.

---

## Anti-Replay: Screenshot Blocking + Count-Up Timer

The B2C confirmation screen is the customer's proof of presence. Two defenses work together:

1. **Screenshot blocking**: The B2C app must **systemically block screenshots** of the confirmation screen (iOS: `UIScreen.isCaptured` flag, Android: `FLAG_SECURE`). This eliminates the easiest replay vector. A physical phone handoff is the only remaining attack path.

2. **Count-up timer**: The screen shows a live count-up ("Time since scan: 0:08"). If someone physically hands off the phone, the second person shows a screen reading "5:23" when they supposedly just walked in. The clerk spots the mismatch at a glance. Prominent display, live animation (pulsing dot, flipping digits), clearly not static.

Together: screenshots are blocked by the system, and physical phone handoffs are exposed by the timer.

---

## Trust Layers

Every restaurant gets Layer 0 automatically. Higher layers are opt-in or auto-escalated.

### Layer 0 — Baseline (all restaurants, automatic)
- QR scan records `arrival_time`
- B2C shows count-up timer (screenshot-blocked)
- Both screens show the same numeric code — clerk can visually compare without typing
- Handoff auto-completes on timer expiry (default 5 min)
- Post-pickup survey with portion size priority
- **Friction: zero for both sides**

### Layer 1 — Soft confirmation (default, low friction)
- Kiosk shows live arrivals queue with initials, items, codes, count-up timers
- Clerk can tap "Delivered" (one tap, optional)
- Customer gets immediate "Received?" prompt with 5-min timeout
- Both confirmations = strongest record, but neither is required
- **Friction: one optional tap per side**

### Layer 2 — Code verification (opt-in per restaurant)
- Supplier Admin enables `require_kiosk_code_verification` on the restaurant
- Clerk taps arrival in queue → numeric keypad opens → enters code from customer's phone
- Code consumed — replay fully blocked, order locked to this handoff
- Customer still gets "Received?" prompt
- **Friction: numeric code entry by clerk. Only for restaurants that want it.**

### Layer 3 — Dispute resolution (reactive, platform-level)
- Track dispute rates per customer and per restaurant
- Auto-escalate flagged restaurants from Layer 0/1 to Layer 2
- Photo evidence triggered on low portion ratings
- Escalation thresholds configurable at system level
- **Friction: zero until triggered by patterns**

---

## Dispute Resolution Matrix

| Scenario | Evidence | Resolution |
|---|---|---|
| Both confirm (clerk Delivered + customer Received) | Two independent timestamps | No dispute possible |
| Clerk marks Delivered, customer ignores | Handed Out timestamp + 5-min timeout passed | Auto-complete, favor restaurant |
| Clerk marks Delivered, customer disputes immediately | Handed Out timestamp vs immediate "I didn't receive" | Route to support queue with all timestamps |
| Nobody marks anything, timer expires | Only Arrived timestamp, auto-completed | Weak evidence. Investigate if disputed later. |
| Confirmation screen replay | Second person shows stale screen | Count-up timer exposes mismatch. Fully blocked in Layer 2 (code consumed). |

---

## Client App Responsibilities

### B2C App (customer side)

| Responsibility | Priority | Notes |
|---|---|---|
| **Screenshot blocking on confirmation screen** | P0 | System-level block. iOS: `UIScreen.isCaptured`. Android: `FLAG_SECURE`. The confirmation screen cannot be captured. |
| **Count-up timer on confirmation screen** | P0 | Live "Time since scan: 0:08" — prominent, animated (pulsing dot, flipping digits), clearly not a static image. |
| **Numeric code display** | P0 | Large, readable numeric code on confirmation screen. Clerk reads it or customer calls it out. |
| **"Received" / "I didn't receive" prompt** | P1 | Immediate push when clerk marks Delivered. Two buttons. 5-minute timeout → auto-complete. |
| **Post-pickup survey (portion-first)** | P1 | First question: portion size. Rating 1 → shows optional "File complaint" button (extra friction intentional — size 1 is subjective). Complaint → photo prompt + text details → support queue. Size 1 + complaint is the actionable SLA flag, not size 1 alone. |
| **Pickup delegation** | Separate plan | Allow customer to transfer pickup authority to another user. Own design doc needed. |

### B2B App (restaurant clerk side)

| Responsibility | Priority | Notes |
|---|---|---|
| **Live arrivals queue** | P0 | Real-time queue showing: initials (M.G.), vianda(s), count-up timer, numeric code. Primary kiosk view during service. Push notification or live polling on new arrivals. |
| **Visual code matching** | P0 | The queue shows the numeric code alongside each arrival. Clerk compares it with the customer's phone — no typing needed. This is the zero-friction verification for all restaurants. |
| **Push notification on arrival** | P0 | Customer scans QR → kiosk gets notified. Clerk taps notification → jumps to queue. Critical for phone-based kiosks. |
| **"Delivered" one-tap button** | P1 | Per-order in the queue. Optional in Layer 0/1, part of the flow in Layer 2. One tap, no typing. |
| **Numeric code entry (Layer 2)** | P2 | Only for `require_kiosk_code_verification` restaurants. Tap arrival → numeric keypad opens, auto-focused. Auto-submit on last digit. Large targets. |
| **Tablet and phone layouts** | P0 | Responsive for both. Large touch targets, minimal scrolling. Solo food-truck operator on a cheap phone is the design target. |

**Design principle:** The kiosk (B2B) is the handoff hardener for restaurants. The B2C app is the mechanism for customers to enforce on their end. Both are optional layers — the system works with neither, better with one, strongest with both.

---

## Configurable System Settings

These are global system-level settings for Phase 1. Per-restaurant granularity can come later.

| Setting | Default | Purpose |
|---|---|---|
| `PICKUP_COUNTDOWN_SECONDS` | 300 | Handoff timer window (already exists) |
| `PICKUP_MAX_EXTENSIONS` | 3 | Max timer extensions (already exists) |
| `HANDOFF_CONFIRMATION_TIMEOUT_SECONDS` | 300 | How long customer has to confirm/dispute after clerk marks Delivered |
| `DISPUTE_AUTO_ESCALATION_RATE` | 0.03 | Dispute rate threshold (3%) for auto-escalating a restaurant to Layer 2 |
| `DISPUTE_ESCALATION_MIN_ORDERS` | 20 | Minimum orders in lookback window before escalation logic applies |
| `DISPUTE_ESCALATION_LOOKBACK_DAYS` | 30 | Rolling window for dispute rate calculation |
| `PORTION_COMPLAINT_FLAG_RATE` | 0.05 | Rate of size-1 + complaint (not size-1 alone) that flags restaurant for SLA review |

---

## Requirements

### Functional Requirements — Backend (kitchen)

#### FR-B1: "Handed Out" status

Add `'Handed Out'` to `status_enum` in PostgreSQL. Update `Status` Python enum with `HANDED_OUT = "Handed Out"`. Add to `vianda_pickup` status context: `[Pending, Arrived, Handed Out, Completed, Cancelled]`.

The status transition rules for `vianda_pickup_live`:
- `Pending → Arrived` — triggered by QR scan (existing)
- `Arrived → Handed Out` — triggered by clerk marking delivered or code verification match
- `Arrived → Completed` — triggered by handoff timer expiry (no clerk action, Layer 0 fallback)
- `Handed Out → Completed` — triggered by customer confirming receipt, or confirmation timeout (5 min), or kitchen-day close cron
- `Handed Out → Disputed` (future) — triggered by customer tapping "I didn't receive this." For now, route to support queue without a status change; the dispute status can be added when the support queue plan is built.

#### FR-B2: Numeric confirmation code

Change confirmation code generation from 6-character alphanumeric to **6-digit numeric only** (e.g. `482951`). Update `_generate_confirmation_code()` in `vianda_pickup_service.py`. The `confirmation_code` column (VARCHAR 10) is already wide enough.

Numeric codes are faster to type on phone keypads and easier to call out verbally across a counter.

#### FR-B3: Extensions tracking column

Add `extensions_used INTEGER DEFAULT 0` to `vianda_pickup_live`. Add to `ViandaPickupLiveDTO`. This is scaffolding — always 0 until the B2C extend-timer endpoint is built (separate plan). Include in daily-orders response and scan-qr response so kiosk and B2C app can display it.

#### FR-B4: Enhanced daily-orders response

Expand `GET /api/v1/restaurant-staff/daily-orders` to include per-order:

| Field | Type | Source |
|---|---|---|
| `vianda_pickup_id` | UUID | `vianda_pickup_live.vianda_pickup_id` |
| `expected_completion_time` | datetime / null | `vianda_pickup_live.expected_completion_time` |
| `completion_time` | datetime / null | `vianda_pickup_live.completion_time` |
| `countdown_seconds` | int | `settings.PICKUP_COUNTDOWN_SECONDS` |
| `extensions_used` | int | `vianda_pickup_live.extensions_used` |
| `was_collected` | bool | `vianda_pickup_live.was_collected` |
| `confirmation_code` | string | `vianda_pickup_live.confirmation_code` — visible to clerk for visual matching |
| `pickup_type` | string / null | `pickup_preferences.pickup_type` via LEFT JOIN |

Add to response envelope:
- `server_time` (ISO 8601) — server's current timestamp for timer sync

Add per-restaurant:
- `pickup_window_start` (HH:MM) — MIN of `pickup_time_range` start across orders
- `pickup_window_end` (HH:MM) — MAX of `pickup_time_range` end across orders

Privacy: customer name displayed as initials only ("M.G.") — change from current "First L." format.

#### FR-B5: Verify-and-handoff endpoint

New endpoint for Layer 2 code verification:

```
POST /api/v1/restaurant-staff/verify-and-handoff
{
  "confirmation_code": "482951",
  "restaurant_id": "uuid"
}
```

Logic:
1. Look up `vianda_pickup_live` by `confirmation_code` + `restaurant_id` where status = `Arrived` and today's kitchen day
2. If no match → return `{ "match": false }`
3. If match → transition status to `Handed Out`, record `handed_out_time`, consume code (prevent reuse), return order details

Response on match:
```json
{
  "match": true,
  "customer_initials": "M.G.",
  "vianda_pickup_ids": ["uuid"],
  "viandas": [{ "vianda_name": "Grilled Chicken", "quantity": 1 }],
  "status": "Handed Out",
  "handed_out_time": "2026-04-04T12:05:00-03:00"
}
```

Auth: Supplier (any role, scoped to institution's restaurants) or Internal.

#### FR-B6: Mark-as-delivered endpoint

New endpoint for Layer 1 manual handoff:

```
POST /api/v1/vianda-pickup/{vianda_pickup_id}/hand-out
```

Transitions status from `Arrived` to `Handed Out`. Records `handed_out_time`. No code required — this is the one-tap path.

Auth: Supplier (any role, scoped) or Internal.

#### FR-B7: Customer confirmation endpoint

Update existing `POST /api/v1/vianda-pickup/{id}/complete` to accept new `completion_type` values:

| Value | Meaning |
|---|---|
| `user_confirmed` | Customer tapped "Received" (existing) |
| `user_disputed` | Customer tapped "I didn't receive this" — routes to support queue |
| `timer_expired` | Handoff timer expired with no action from either side (existing) |
| `confirmation_timeout` | 5-min timeout after Handed Out with no customer response |
| `kitchen_day_close` | Auto-completed by billing cron at end of kitchen day |

When `completion_type=user_disputed`: do NOT complete the order. Instead, flag it for support review. The order remains in `Handed Out` status until support resolves it. (If support queue is not yet built, log the dispute and auto-complete — interim behavior.)

#### FR-B8: Per-restaurant code verification setting

Add to `ops.restaurant_info`:

```sql
require_kiosk_code_verification BOOLEAN NOT NULL DEFAULT FALSE
```

Only Supplier Admin can toggle this (via existing restaurant update endpoint). Include in restaurant response schemas so the B2B app knows which mode to render.

Add to `RestaurantDTO` and relevant response schemas.

#### FR-B9: Confirmation code consumed flag

Add to `vianda_pickup_live`:

```sql
code_verified BOOLEAN DEFAULT FALSE,
code_verified_time TIMESTAMPTZ DEFAULT NULL
```

Set to `TRUE` when code is entered via verify-and-handoff (FR-B5). This distinguishes "clerk visually matched the code" (no system record) from "clerk typed the code and system verified it" (strong evidence).

#### FR-B10: Portion complaint storage

Add `customer.portion_complaint` table:

```sql
CREATE TABLE IF NOT EXISTS customer.portion_complaint (
    complaint_id UUID PRIMARY KEY DEFAULT uuidv7(),
    vianda_pickup_id UUID NOT NULL,
    vianda_review_id UUID,
    user_id UUID NOT NULL,
    restaurant_id UUID NOT NULL,
    photo_storage_path VARCHAR(500),
    complaint_text VARCHAR(1000),
    resolution_status VARCHAR(20) DEFAULT 'open',
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vianda_pickup_id) REFERENCES customer.vianda_pickup_live(vianda_pickup_id),
    FOREIGN KEY (user_id) REFERENCES core.user_info(user_id),
    FOREIGN KEY (restaurant_id) REFERENCES ops.restaurant_info(restaurant_id)
);
```

Photos stored in GCS customer bucket: `complaints/{restaurant_id}/{complaint_id}/photo`.

Endpoint: `POST /api/v1/vianda-reviews/{vianda_review_id}/portion-complaint` (multipart: photo + text). Customer-only, scoped to their own review.

#### FR-B11: Configurable system settings

Add to `app/config/settings.py`:

| Setting | Type | Default |
|---|---|---|
| `HANDOFF_CONFIRMATION_TIMEOUT_SECONDS` | int | 300 |
| `DISPUTE_AUTO_ESCALATION_RATE` | float | 0.03 |
| `DISPUTE_ESCALATION_MIN_ORDERS` | int | 20 |
| `DISPUTE_ESCALATION_LOOKBACK_DAYS` | int | 30 |
| `PORTION_COMPLAINT_FLAG_RATE` | float | 0.05 |

All system-level for now. Per-restaurant granularity deferred.

---

### Functional Requirements — B2C App (vianda-app)

#### FR-C1: Screenshot blocking on confirmation screen

Block screenshots and screen recording on the post-scan confirmation screen.
- iOS: Set `UIScreen.isCaptured` flag or use `UITextField.isSecureTextEntry` overlay trick
- Android: Set `FLAG_SECURE` on the activity/window

This is the primary defense against C2 (screen replay). Non-negotiable P0.

#### FR-C2: Count-up timer on confirmation screen

After QR scan, display a live count-up timer prominently: "Time since scan: 0:08"

- Large font, top of screen
- Animated: digits flip like a digital clock, subtle color shift every 30s (green → yellow → orange), pulsing "live" dot
- Computed client-side from `arrival_time` returned by scan-qr response
- Must be clearly not a static image — the animation is the anti-fake signal

#### FR-C3: Numeric code display

Display the 6-digit numeric confirmation code on the confirmation screen in large, readable font. The customer either:
- Calls it out to the clerk verbally
- Flips phone to show the screen (clerk compares visually with their kiosk)
- Holds still while clerk types it (Layer 2 restaurants)

#### FR-C4: Receipt confirmation prompt

When backend sends a push notification (triggered by clerk marking Delivered):
- Show in-app prompt: "Did you receive your vianda from [Restaurant Name]?"
- Two buttons: **"Received"** / **"I didn't receive this"**
- "Received" → calls `POST /vianda-pickup/{id}/complete` with `completion_type=user_confirmed` → opens survey
- "I didn't receive this" → calls `POST /vianda-pickup/{id}/complete` with `completion_type=user_disputed` → shows confirmation that dispute was filed
- If no response in 5 minutes → auto-complete with `completion_type=confirmation_timeout`
- If the customer opens the app after auto-complete (timer expiry, no clerk action), show the survey directly

#### FR-C5: Portion-first survey with complaint path

Post-completion survey flow:
1. First question: "How was the portion size?" → 1 (small), 2 (right), 3 (generous)
2. If rated 2 or 3 → continue to stars (1-5), would_order_again, comment
3. If rated 1 → show same survey fields PLUS a **"File a portion complaint"** button
4. If complaint tapped → camera opens for vianda photo → text field for details → submit to `POST /vianda-reviews/{id}/portion-complaint`
5. If complaint not tapped (size 1 but no complaint) → survey completes normally, only the rating is recorded

The complaint is the actionable flag. Size 1 alone is recorded but not escalated.

---

### Functional Requirements — B2B App (vianda-platform)

#### FR-K1: Live arrivals queue

Primary kiosk view during service hours. When a customer scans QR at the restaurant:
- New entry appears in the queue (push notification or polling, max 5s latency)
- Each entry displays: initials ("M.G."), vianda(s) with quantity, count-up timer, numeric code
- Queue sorted by arrival time (newest at top or bottom — B2B agent decides)
- Entries remain until order reaches Completed status
- Completed/timed-out orders move to a "Done" section or fade out

Data source: `GET /api/v1/restaurant-staff/daily-orders` (enhanced per FR-B4), polled every 5-10s, or push-based if WebSocket/SSE is available.

#### FR-K2: Push notification on arrival

When a customer scans QR at the restaurant, the B2B app receives a notification.
- Tapping the notification opens the app to the live queue
- Critical for phone-based kiosks where the app may be backgrounded
- Backend implementation: could be a webhook, Firebase Cloud Messaging, or the B2B app polls with a short interval. Backend provides the event; delivery mechanism is B2B infra's choice.

#### FR-K3: Visual code matching (all restaurants)

The numeric code is visible on each queue entry alongside the customer's initials and timer. The clerk compares what they see on their screen with what the customer shows on their phone. No typing, no tapping — just a visual comparison.

This is the zero-friction verification available to every restaurant regardless of verification mode setting.

#### FR-K4: "Delivered" button (Layer 1)

One-tap button per order in the queue. Calls `POST /vianda-pickup/{id}/hand-out` (FR-B6).
- Available on all queue entries in `Arrived` status
- Transitions order to `Handed Out`
- Optional — clerk may skip it. System still works via timer.

#### FR-K5: Code entry (Layer 2)

Only shown for restaurants with `require_kiosk_code_verification = true`.
- Clerk taps a queue entry → numeric keypad overlay opens, auto-focused
- 6 numeric digits, large touch targets, auto-submit on last digit (no confirm button)
- Calls `POST /restaurant-staff/verify-and-handoff` (FR-B5)
- Match → order transitions to Handed Out, confirmation shown
- Mismatch → error message, clerk retries or dismisses

#### FR-K6: Responsive phone and tablet layouts

The kiosk must work on:
- **Tablets**: Readable from arm's length. Queue entries large enough to scan while cooking. Landscape or portrait.
- **Phones**: Thumb-friendly. One-handed operation. Queue entries compact but tappable. Portrait primary.

Design target: solo food-truck operator on a budget Android phone with one free hand. If it works for them, it works for everyone.

#### FR-K7: Code verification toggle in restaurant settings

Supplier Admin can enable/disable `require_kiosk_code_verification` per restaurant in the restaurant settings page. This is a simple boolean toggle. Only visible to Supplier Admin role.

---

### Non-Functional Requirements

#### NFR-1: Latency — arrival-to-queue

When a customer scans QR, the kiosk must show the new arrival within **5 seconds**. This can be achieved via:
- Short polling interval (5s) on daily-orders
- Server-Sent Events (SSE) for real-time push (preferred if B2B supports it)
- Firebase Cloud Messaging for background notification

The exact mechanism is a B2B infra decision. The backend provides the data; the contract is "new arrival visible on kiosk within 5 seconds of QR scan."

#### NFR-2: Timer accuracy

Count-up timers on both B2C and B2B must be accurate to within 2 seconds of each other. Both derive from `arrival_time` (server timestamp). The daily-orders response includes `server_time` so the B2B app can compensate for clock drift. The B2C app uses the `arrival_time` from the scan-qr response directly.

#### NFR-3: Offline resilience

If the kiosk loses network connectivity:
- The queue shows a "Last updated X seconds ago" indicator
- Clerk can still manually mark orders as "Delivered" — the action is queued locally and synced on reconnect
- On reconnect, the queue refreshes and any queued actions are reconciled
- Code verification (Layer 2) requires network — if offline, fall back to visual matching (Layer 0)

#### NFR-4: Privacy

- Customer names displayed as **initials only** (e.g. "M.G.") on both the B2B kiosk queue and the daily-orders API response. No full first names.
- The B2C confirmation screen shows the customer's own order details (not private from them).
- Confirmation codes are single-use and expire at end of kitchen day.

#### NFR-5: Confirmation code collision avoidance

6-digit numeric codes = 1,000,000 possible values. Codes must be unique per restaurant per kitchen day. Given a restaurant handles at most ~200 orders/day, collision probability is negligible. Generation: random 6-digit, check uniqueness against today's codes for that restaurant, regenerate on collision.

#### NFR-6: Screenshot blocking enforcement

The B2C app must block screenshots on the confirmation screen. This is a platform-level enforcement:
- iOS: `UIScreen.isCaptured` detection + secure view overlay
- Android: `FLAG_SECURE` on the window

If a user finds a way around it (rooted device, screen mirroring), the count-up timer is the fallback defense.

#### NFR-7: Auto-completion guarantees

Orders must never remain open indefinitely. Three auto-completion safeguards:
1. Handoff timer expiry (default 5 min from arrival) — completes if nobody acts
2. Confirmation timeout (5 min after Handed Out) — completes if customer doesn't respond
3. Kitchen-day close cron — sweeps all remaining open orders at end of day

These three layers ensure the queue is always cleared by end of day regardless of user behavior.

---

## Deferred to Separate Plans

| Topic | Why separate | Notes |
|---|---|---|
| **Pickup delegation** | Full feature with its own UX, backend, and trust implications | Customer transfers pickup authority to another user. Needs own design doc covering delegation flow, code transfer, who confirms receipt, abuse prevention. |
| **Support queue / dispute resolution** | Operational infrastructure | "I didn't receive this" and photo complaints route to a queue. Needs: queue UI, SLA, escalation rules, resolution actions (refund, credit, flag). Own plan. |

---

## Resolved Decisions

Decisions made during the design process, documented for traceability.

| Decision | Resolution | Rationale |
|---|---|---|
| Code format | 6-digit numeric only | Faster than alphanumeric, works with numeric keypad, 1M combinations is more than enough per restaurant per day |
| Customer name privacy | Initials only (M.G.) on kiosk and API | Minimizes PII exposure to restaurant staff |
| Confirmation timeout | 5 minutes, configurable via `HANDOFF_CONFIRMATION_TIMEOUT_SECONDS` | Long enough for customer to glance at phone, short enough to not hold liability open |
| Screenshot blocking | System-level enforcement (FLAG_SECURE / isCaptured) | Count-up timer is fallback only — screenshots should not be possible |
| Portion complaint trigger | Size-1 rating + explicit complaint tap (not size-1 alone) | Size 1 is subjective; complaint is the actionable SLA flag |
| Escalation thresholds | System-level configurable for now | Per-restaurant granularity deferred to later phase |
| Timer mode vs code mode | Per-restaurant opt-in via `require_kiosk_code_verification` | Restaurants manage their own risk appetite |
| Handoff timer fallback | Auto-completes on timer expiry if nobody acts | Three-layer auto-completion guarantee (timer → confirmation timeout → kitchen-day close) |

## Open Questions

1. **Auto-escalation warning**: Should there be a warning step before forcing Layer 2 on a flagged restaurant? How long does forced Layer 2 last before review? 

2. **Portion complaint review SLA**: Who reviews complaint photos and on what timeline? This ties into the support queue plan (deferred).

3. **Kiosk delivery mechanism**: Short polling (5s) vs SSE vs Firebase for real-time arrival notifications on the B2B kiosk. Backend provides the data — the delivery mechanism is a B2B/infra decision. What's the right tradeoff for reliability on spotty connections?

---

## Appendix: Risks Already Covered

These scenarios were evaluated and determined to be non-issues due to existing Vianda mechanics.

### Customer scans QR but walks away without picking up

Not a financial risk. The customer is charged at reservation time (lock-down). The restaurant gets paid either way — full amount if QR was scanned, discounted amount on no-show.

### Restaurant claims customer never showed up

Disproved by the QR scan record. If `arrival_time` exists, the customer was there.

### Unauthorized third-party pickup

Handled by the existing coworker matching system. Will be extended into a full delegation feature (separate plan). The confirmation code serves as the authorization token.
