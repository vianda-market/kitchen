# Feedback: Pending subscription on profile-plan

**Context:** The B2C app shows all non-archived subscriptions on **profile-plan** (GET /api/v1/subscriptions/enriched/). When a subscription is in **Pending** (user started with-payment but did not complete payment), the user can visit profile-plan and see that subscription with status "Pending". We need two behaviors that require backend support.

---

## 1. Cancel button for Pending subscriptions

**Current behavior:** On profile-plan we show a "Cancel" button for any subscription that is not already Cancelled (including Pending). When the user taps Cancel we call **POST /api/v1/subscriptions/{subscription_id}/cancel**. For Pending subscriptions this currently appears to do nothing (or the backend may return an error).

**Requested behavior:**

- **POST /api/v1/subscriptions/{subscription_id}/cancel** should be allowed when `subscription_status === "Pending"`.
- On success, the backend should:
  1. Cancel the Pending subscription (e.g. set status to Cancelled or remove it from the active list per your domain rules).
  2. **Cancel the associated Stripe payment intent** (or mock payment) so the user is not left with an open payment intent.
- Response: **200 OK** with a clear message (e.g. updated subscription or `{ "detail": "Subscription and payment cancelled. You can choose a new plan when you're ready." }`).
- Errors: **400** if subscription is not Pending (e.g. already Cancelled or already Active); **403** if not owner; **404** if not found.

This aligns with **SUBSCRIPTION_PAYMENT_API.md** section 2b (Cancel Pending). We need this to be implemented and documented so the client can rely on it.

---

## 2. Deep link to complete payment (Pending → payment UI)

**Requested behavior:** When the user sees a **Pending** subscription on profile-plan, we want to show a **"Complete payment"** action that takes them to the same payment screen used after select-plan (Stripe or mock "Confirm payment"). To do that, the client needs the same data we get from with-payment: **subscription_id**, **client_secret** (for Stripe), **amount_cents**, **currency** (for display).

Today we only get subscription_id (and plan/market info) from GET /subscriptions/enriched/. We do **not** get `client_secret` or payment amount/currency from the list or from GET /subscriptions/{id} (current response shape is the subscription entity only).

**Proposed backend options (you choose what fits best):**

**Option A — New endpoint: get payment details for Pending subscription**

- **GET /api/v1/subscriptions/{subscription_id}/payment-details** (or a name you prefer).
- **Allowed only when** the subscription belongs to the current user and `subscription_status === "Pending"`.
- **Success (200):** JSON with the same shape as the with-payment response (or a subset needed for the payment UI), e.g.:
  ```json
  {
    "subscription_id": "uuid",
    "client_secret": "string",
    "amount_cents": 1000,
    "currency": "usd",
    "payment_id": "uuid",
    "external_payment_id": "string"
  }
  ```
  The backend would return the **existing** payment intent’s client_secret (and amount/currency) for that Pending subscription, so the client can open the payment UI (Stripe Elements or mock "Confirm payment") without calling with-payment again.
- **Errors:** **400** if subscription is not Pending; **403** if not owner; **404** if not found or no payment intent.

**Option B — Include payment details in GET subscription when Pending**

- For **GET /api/v1/subscriptions/{subscription_id}** (and optionally GET /api/v1/subscriptions/enriched/), when `subscription_status === "Pending"`, include optional fields such as `client_secret`, `amount_cents`, `currency` in the response (or in an embedded `payment` object). The client would use these only when opening the "Complete payment" flow.
- Consider security: if client_secret is sensitive, Option A (dedicated endpoint) may be preferable so it is not cached or logged with the rest of the subscription.

**Option C — Other**

- If you have a different way to expose "payment intent details for this Pending subscription" (e.g. a one-time link, or re-use with-payment with the same plan to get a new client_secret), please document it so we can integrate.

---

## 3. Client integration plan

- **Cancel:** We will keep calling **POST .../cancel** for Pending subscriptions. We will use Pending-specific confirmation copy (e.g. "Cancel this pending subscription? The payment will be cancelled."). Once the backend supports cancel-for-Pending and cancels the payment intent, the button will work as expected.
- **Complete payment:** We will add a "Complete payment" action on profile-plan for Pending subscriptions that navigates to our subscription-payment screen with `subscription_id`.  
  - If you provide **Option A**, we will call **GET .../payment-details** when the payment screen is opened with only `subscription_id` (no client_secret in params), then show the payment UI with the returned client_secret and amount/currency.  
  - If you provide **Option B**, we will pass the payment fields from the subscription response as params to the payment screen.  
  We are ready to integrate once the contract (endpoint and response shape) is defined.

---

## Summary

| Need | Request |
|------|--------|
| **Cancel Pending** | POST /subscriptions/{id}/cancel must be supported for Pending subscriptions and must cancel the subscription and the Stripe (or mock) payment intent. Document in SUBSCRIPTION_PAYMENT_API or SUBSCRIPTION_ACTIONS_API. |
| **Complete payment from profile-plan** | A way to get `client_secret`, `amount_cents`, `currency` for a Pending subscription (e.g. GET .../payment-details or include in GET subscription when Pending) so we can deep link to the payment screen. |

Please confirm or adjust the contract (status codes, response bodies, and any security considerations) so we can align the client implementation.
