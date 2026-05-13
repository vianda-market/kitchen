# Subscription Payment API (B2C)

**Audience**: B2C client (Customer role).  
**Purpose**: Create a subscription and complete payment in one flow (with-payment → payment UI → confirm-payment). The process is **atomic**: on **200 OK** from confirm-payment, the subscription is active and the client can show success; any **4xx/5xx** means the flow failed.

**Migration note**: Fintech Link and manual bill create/process are **deprecated**. Use this flow only. See [../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md).

---

## Design for B2C client

| Step | Client design | API |
|------|---------------|-----|
| 1. User selects market and plan | Show plan picker (market scoped). User taps “Subscribe” / “Pay now”. | GET /plans/, /enriched/ (or GET /markets/, /plans/) |
| 2. Start payment | Call with-payment. Show loading. | POST /subscriptions/with-payment |
| 3. Show payment UI | **Mock**: Simple “Confirm payment” button. **Stripe**: Stripe Elements (card form) or redirect to Stripe Checkout. Pass `client_secret` from step 2. | — |
| 4. Complete payment | **Mock**: Call confirm-payment → 200 → show success with subscription. **Stripe**: After user completes payment and returns to app, poll GET subscription until `subscription_status === "Active"` → show success. | POST /{id}/confirm-payment (mock) — or — GET /subscriptions/{id} (Stripe) |
| 5. Success screen | Show plan, balance, renewal_date from subscription object. Navigate to profile-plan or home. No extra GET needed (response has it). | — |

**Do not**: Create bills manually, process bills manually, or use Fintech Link / payment links.

---

## Success and failure semantics

| Outcome | Client assumption |
|--------|--------------------|
| **POST .../confirm-payment returns 200** | Success. Subscription is **Active**; bill was created and processed (credits and renewal_date updated). Use the **returned subscription object** in the response body to show the customer their plan, balance, renewal_date, etc. No need to call GET subscription afterward. |
| **Any 4xx or 5xx** | Failure. Do not assume the subscription is active. Show the error (e.g. `detail`) to the user and do not navigate to “success” or profile-plan. |

The backend performs activation and billing in a **single transaction**. If the response is 200, everything succeeded; if not, nothing was committed.

---

## Subscription balance and renewal

How **balance** and **renewal_date** are set so the client can show them correctly (e.g. on profile-plan and after payment success).

| Topic | Rule |
|-------|------|
| **Plans must have credits** | Subscribing to a plan with no credits (zero or missing) is not allowed; the API returns **400** and the subscription cannot be activated or renewed. Plans offered to customers must have a positive **credit** value. |
| **Balance on activation** | On first activation, balance is set to **plan.credit** (e.g. 70 for “Entry Level”) and **renewal_date** = activation + 30 days. |
| **Renewal (every 30 days or low balance)** | On each renewal, balance becomes **rolled (capped) + plan.credit**. Rolled = unused credits from the previous period: if the plan has **rollover** enabled, rolled = current balance, optionally capped by **rollover_cap** (if set); if rollover is disabled, rolled = 0. **renewal_date** is set to **previous renewal_date + 30 days**. |
| **Rollover (current behavior)** | All plans currently have rollover enabled with **no cap**. Unused credits at the end of the month carry over to the next month alongside the new credits from renewal. Display a rollover indicator (badge or icon) and reassure customers, e.g. *"Unused credits roll over to the next month—no limit"* or *"Your credits carry over each month with your renewal"*. See [CREDIT_ROLLOVER_DISPLAY_B2C.md](./CREDIT_ROLLOVER_DISPLAY_B2C.md). |
| **When renewal runs** | Renewal happens in two ways: (1) **Time-based:** when **renewal_date** has passed (e.g. a daily cron runs and renews subscriptions with renewal_date ≤ now). (2) **Low-balance at order time:** when the customer is at vianda selection and their balance is below a threshold (e.g. 10), the backend may renew early so they can keep ordering. Low-balance renewal runs **only when renewal_date is still in the future** (to avoid double renewal in the same period). |

The client can display “Balance: X” and “Renewal: &lt;date&gt;” from the subscription object and use copy such as “Renewal every 30 days” or “Next renewal: &lt;date&gt;”. See [feedback_subscription_balance_and_renewal.md](./feedback_subscription_balance_and_renewal.md) for the source of these rules.

---

## Flow (canonical)

1. **POST /api/v1/subscriptions/with-payment** — Create subscription (Pending) and payment intent. Returns `subscription_id`, `client_secret`, etc., for the payment UI.
2. **Client shows payment UI** — Stripe Elements, redirect, or mock “Pay” button. User completes payment.
3. **POST /api/v1/subscriptions/{subscription_id}/confirm-payment** — (Mock only) Simulate payment success and activate. Returns **full subscription** (200 OK).  
   For **live Stripe**, this endpoint returns 400; activation is done by the backend via webhook. The client should then **poll GET /api/v1/subscriptions/{subscription_id}** until `subscription_status === "Active"` to show success.

---

## 1. POST /subscriptions/with-payment

Creates a subscription in **Pending** status and a payment intent (Stripe or mock). Use the returned `client_secret` (and optional `return_url`) to show the payment UI.

**Request**

```http
POST /api/v1/subscriptions/with-payment
Authorization: Bearer <token>
Content-Type: application/json

{
  "plan_id": "uuid-of-plan",
  "return_url": "https://yourapp.com/return"   // optional; for Stripe Checkout redirect
}
```

**Success (201 Created or 200 OK)**

- **201** — New subscription created (Pending). Use the returned payload for the payment UI.
- **200** — User already had a **Pending** subscription in this plan's market; the backend **updated it in place** (same or new plan) and created a new payment intent. Response shape is the same. Use the returned `subscription_id` and `client_secret` for the payment UI.

```json
{
  "subscription_id": "uuid",
  "payment_id": "uuid",
  "external_payment_id": "string",
  "client_secret": "string",
  "amount_cents": 1000,
  "currency": "usd"
}
```

- `subscription_id` — Use for confirm-payment and for polling GET subscription when using Stripe.
- `client_secret` — Pass to Stripe Elements (or mock) to complete payment.
- `external_payment_id` — Provider’s payment id (e.g. Stripe PaymentIntent id).
- `amount_cents`, `currency` — For display or Stripe.

**Errors**

| Status | When | Client behavior |
|--------|------|-----------------|
| 403 | Not Customer or Employee | Show “Not allowed.” |
| 404 | Plan or market not found | Show `detail`. |
| **409** | User already has an **Active** subscription in this plan's market | Response body: `{ "code": "already_active", "subscription_id": "uuid", "message": "You already have an active subscription in this market." }`. Show the message; do not offer "Complete payment". |
| 500 | Create subscription or payment failed | Show error; do not assume subscription exists. |

---

## 1b. Pending subscription re-pick (edge case)

If the user selected a plan and tapped "Subscribe" but **went back** without completing payment, they have a subscription in **Pending** in that market. When they tap "Subscribe" again (same or different plan):

- **Backend:** Does **not** return 409. It **edits the existing Pending subscription in place**: updates the plan if they chose a different one, cancels the previous payment intent, creates a new payment intent, and returns **200** with the **same response shape** (same `subscription_id`, new `client_secret`).
- **Client:** You can show "Complete payment" (navigate to payment screen with the returned `subscription_id` and `client_secret`) or let the user change plan and call with-payment again; the backend will keep updating the same Pending subscription until they pay or cancel.

**Differentiate 409 vs success:** Use **409** only when the response body indicates `code: "already_active"` (user already has an **Active** subscription). Do not show "You already have an active subscription" for Pending — in that case the backend returns 200 and you get a new `client_secret` to complete payment.

**Optional: Cancel Pending** — If you want to offer "Cancel and choose another plan" explicitly, call **POST /api/v1/subscriptions/{subscription_id}/cancel** (see section 2b). Otherwise, the user can simply call with-payment again with a different plan (edit in place).

**Auto-cancel:** Pending subscriptions that are never paid are **automatically cancelled after 24 hours**. After that, the user can start a new subscription with with-payment as usual.

---

## 2. POST /subscriptions/{subscription_id}/confirm-payment

**[Mock only]** Simulates successful payment, activates the subscription, creates and processes the bill in one transaction. Returns the **full subscription** so the client can show plan, balance, renewal_date without a follow-up GET.

**Request**

```http
POST /api/v1/subscriptions/{subscription_id}/confirm-payment
Authorization: Bearer <token>
```

No request body.

**Success (200 OK)**

Response body is the **full subscription object** (same shape as GET /api/v1/subscriptions/{subscription_id}):

```json
{
  "subscription_id": "uuid",
  "user_id": "uuid",
  "plan_id": "uuid",
  "renewal_date": "2026-03-15T12:00:00Z",
  "balance": 10,
  "is_archived": false,
  "status": "Active",
  "subscription_status": "Active",
  "hold_start_date": null,
  "hold_end_date": null,
  "created_date": "...",
  "modified_by": "uuid",
  "modified_date": "..."
}
```

- **200** → Treat as success. Show the returned subscription to the customer (e.g. plan, balance, renewal_date). Navigate to profile-plan or home.
- No need to call GET subscription again unless you want refreshed data later.

**Errors**

| Status | When | Client behavior |
|--------|------|-----------------|
| 400 | PAYMENT_PROVIDER is not mock (e.g. Stripe); or subscription not Pending; or no subscription payment found; or **plan has no credits** (plan.credit zero or missing) | With Stripe, do not call this endpoint; poll GET subscription until Active. If plan has no credits, subscription cannot be activated; show `detail`. |
| 403 | Not owner of the subscription | Show “You cannot confirm this payment.” |
| 404 | Subscription not found | Show “Subscription not found.” |

---

## 2b. POST /subscriptions/{subscription_id}/cancel

**Optional.** Cancel a subscription (Pending, Active, or On Hold). The same endpoint handles all states. All cancels archive the subscription so the user can re-subscribe in the same market.

- **Pending**: Cancels Stripe PaymentIntent(s), marks subscription_payment rows cancelled, archives.
- **Active / On Hold**: Archives via subscription action (no payment changes).

See [SUBSCRIPTION_ACTIONS_API.md](./SUBSCRIPTION_ACTIONS_API.md) for hold and resume. Cancel is documented in both places because it overlaps payment (Pending) and lifecycle (Active/On Hold).

**Request:** `POST /api/v1/subscriptions/{subscription_id}/cancel` with Bearer token. No body.

**Success (200):** `{ "detail": "Subscription cancelled. You can choose a new plan and subscribe again." }`

**Errors:** 400 (subscription already cancelled), 403 (not owner), 404 (not found).

---

## Profile-plan: Subscription actions

On **profile-plan**, the B2C app shows non-archived subscriptions (e.g. from GET /api/v1/subscriptions/enriched/).

### Cancel (from profile-plan)

- For **Pending** subscriptions: show a **Cancel** button. On tap, show a Pending-specific confirmation, e.g. *"Cancel this pending subscription? The payment will be cancelled."*
- For **Active** or **On Hold** subscriptions: show a **Cancel** button. On tap, show a confirmation, e.g. *"Cancel your subscription? You can choose a new plan and subscribe again."*
- On confirm, call **POST /api/v1/subscriptions/{subscription_id}/cancel**.
- On **200**, refresh the subscription list and show the success message (e.g. from response `detail`). The subscription is cancelled and archived; the user can choose a new plan and subscribe again via with-payment.

### Complete payment (from profile-plan)

- For each **Pending** subscription, show a **Complete payment** button.
- On tap, navigate to the same subscription payment screen used after plan selection (Stripe Elements or mock "Confirm payment").
- The client may only have `subscription_id` (e.g. from the enriched list). Call **GET /api/v1/subscriptions/{subscription_id}/payment-details** to get `client_secret`, `amount_cents`, `currency` (and optionally `payment_id`, `external_payment_id`).
- Show the same payment UI as after with-payment, using the returned data.
- On success: **Mock** — call **POST /api/v1/subscriptions/{subscription_id}/confirm-payment** and use the returned subscription; **Stripe** — poll **GET /api/v1/subscriptions/{subscription_id}** until `subscription_status === "Active"`.

See section **2c** below for the GET payment-details contract. Optionally reference [feedback_pending_subscription_profile_plan.md](./feedback_pending_subscription_profile_plan.md) for the source of these requirements.

---

## 2c. GET /subscriptions/{subscription_id}/payment-details

Returns the existing payment intent details for a **Pending** subscription so the client can open the "Complete payment" screen (e.g. from profile-plan) without calling with-payment again. Use this when the user taps "Complete payment" on a Pending subscription and you only have `subscription_id`.

**When to use:** Only when the subscription is **Pending** and belongs to the current user. Do not use for Active or Cancelled subscriptions.

**Request**

```http
GET /api/v1/subscriptions/{subscription_id}/payment-details
Authorization: Bearer <token>
```

**Success (200 OK)**

Same shape as the with-payment response (subset needed for the payment UI):

```json
{
  "subscription_id": "uuid",
  "payment_id": "uuid",
  "external_payment_id": "string",
  "client_secret": "string",
  "amount_cents": 1000,
  "currency": "usd"
}
```

Use `client_secret`, `amount_cents`, and `currency` to render the same payment UI as after with-payment; then complete the flow with confirm-payment (mock) or Stripe + polling (live).

**Errors**

| Status | When | Client behavior |
|--------|------|-----------------|
| **400** | Subscription is not Pending (e.g. already Active or Cancelled) | Show `detail`; do not offer "Complete payment" for this subscription. |
| **403** | Not the owner of the subscription | Show "You cannot access this subscription." |
| **404** | Subscription not found, or no pending payment record for this subscription | Show "Subscription not found." or "No pending payment found."; remove or refresh the item. |
| **501** | PAYMENT_PROVIDER does not support retrieving payment details (e.g. Stripe live not yet implemented) | Show a generic "Payment details not available" message. |

---

## 3. When using live Stripe

- **with-payment** is unchanged: create subscription + payment intent; show Stripe UI.
- **confirm-payment** is disabled (400). The backend activates the subscription and creates/processes the bill when it receives the **Stripe webhook** (payment_intent.succeeded).
- **Client:** After the user completes payment in Stripe and returns to your app, **poll GET /api/v1/subscriptions/{subscription_id}** until `subscription_status === "Active"`. Then show success and the subscription (same as using the confirm-payment response in mock).

**Polling guidance (Stripe):**
- Poll every 2–3 seconds. Cap at ~30 attempts (~90 s) then show “Payment is processing; check your subscription shortly.”
- On success, use the returned subscription for the success screen (no extra GET).

---

## Types (for client implementation)

- **WithPaymentPayload**: `{ plan_id: string (UUID), return_url?: string }`
- **WithPaymentResponse**: `{ subscription_id, payment_id, external_payment_id, client_secret, amount_cents, currency }` — same shape as **GET payment-details** response.
- **PaymentDetailsResponse** (GET .../payment-details): same as WithPaymentResponse.
- **ConfirmPaymentPayload**: none (optional empty object for future use).
- **Confirm-payment success response**: Full **Subscription** (same as GET subscription by id): `subscription_id`, `user_id`, `plan_id`, `renewal_date`, `balance`, `is_archived`, `status`, `subscription_status`, `hold_start_date`, `hold_end_date`, `created_date`, `modified_by`, `modified_date`.

---

## Summary

- **Atomic:** 200 from confirm-payment = subscription active and bill processed. Any error = assume failure.
- **Best practice:** Backend returns the **full subscription** on confirm-payment success so the client can show it immediately without an extra GET.
- **Mock:** Use with-payment → payment UI → confirm-payment → 200 + subscription → show success.
- **Stripe:** Use with-payment → Stripe UI → then poll GET subscription until `subscription_status === "Active"`.
- **409** from with-payment = user already has an **Active** subscription in that market; show the message from the response body (`code`, `message`). Do not confuse with Pending — when they have Pending, the backend returns **200** with a new `client_secret`.
- **Pending re-pick:** If the user goes back without paying and taps Subscribe again, the backend updates the existing Pending subscription in place and returns 200 with the same shape; use the new `client_secret` for the payment UI.
- **Pending auto-cancel:** Subscriptions that stay Pending and are never paid are automatically cancelled after 24 hours so the user can start a new one.
- **Profile-plan Pending actions:** For each Pending subscription, offer **Cancel** (POST .../cancel with confirmation) and **Complete payment** (GET .../payment-details → same payment UI as after with-payment → confirm-payment or Stripe polling).

---

## Related

- **Cancel, hold, resume**: [SUBSCRIPTION_ACTIONS_API.md](./SUBSCRIPTION_ACTIONS_API.md)
- **Fintech Link deprecation, no manual bills**: [../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md)
