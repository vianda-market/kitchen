# Feedback from client (B2C app)

## Subscription payment: Pending subscription after user abandons payment (edge case)

### Observed flow

1. User selects a plan and taps "Subscribe".
2. Client calls **POST /api/v1/subscriptions/with-payment** → backend creates a subscription in **Pending** and returns 201 with `subscription_id`, `client_secret`, etc.
3. Client navigates to the payment screen (confirm payment / Stripe UI).
4. User presses **Back** without completing payment (no call to confirm-payment, no Stripe success).
5. User returns to the plan selection screen and taps "Subscribe" again (same or different plan).
6. Client calls **POST /api/v1/subscriptions/with-payment** again.
7. Backend returns **409** (user already has a subscription in this market).
8. Client shows: "You already have an active subscription in this market."

### Problems

- **User confusion:** The user did not complete payment, so they do not consider themselves "subscribed." The message implies they have an active subscription and payment is done.
- **No way to recover:** The user cannot complete payment for the existing Pending subscription from this screen, and cannot start a new subscription (e.g. different plan) because 409 blocks it.
- **Messaging:** The client currently maps any 409 to "active subscription." In this scenario the subscription is **Pending**, not Active, so the wording is incorrect and misleading.

### Requested backend changes

1. **Differentiate 409 (or error payload) by subscription state**
   - When the user already has an **Active** subscription in the market: keep 409 (or equivalent) so the client can show e.g. "You already have an active subscription in this market."
   - When the user has a **Pending** (unpaid) subscription in the market: return a distinct status or error so the client can:
     - Show a different message, e.g. "You have a subscription waiting for payment" or "Complete your pending subscription payment."
     - Offer "Complete payment" (navigate to payment screen with existing `subscription_id`) and/or "Cancel and choose another plan" if supported.

2. **Optional: Allow abandoning / cancelling a Pending subscription**
   - If the backend supports cancelling (or "abandoning") a Pending subscription (e.g. DELETE or POST cancel for Pending), document it so the client can offer "Cancel and choose another plan" and then allow a new with-payment call for the same market.

3. **Document 409 for with-payment**
   - In SUBSCRIPTION_PAYMENT_API.md (or equivalent), document when **POST /subscriptions/with-payment** returns 409 (e.g. "already have an Active or Pending subscription in this market") and, if possible, how the response body indicates Active vs Pending so the client can tailor messaging and actions.
