# Stripe live integration handoff

This document is for the team implementing **live Stripe** once e2e is ready. The app currently uses a **mock** payment provider for the atomic subscription flow (`POST /api/v1/subscriptions/with-payment` and `POST /api/v1/subscriptions/{id}/confirm-payment`). This handoff describes how to replace the mock with real Stripe without changing the flow or schema.

## 1. Prerequisites

- **Stripe account** (test and live).
- **API keys:** `STRIPE_SECRET_KEY` (test/live), `STRIPE_PUBLISHABLE_KEY` (optional, for client).
- **Webhook signing secret:** `STRIPE_WEBHOOK_SECRET` for verifying webhook payloads.
- **Environment:** Set `PAYMENT_PROVIDER=stripe` (default today is `mock`).

Add to settings (e.g. `app/config/settings.py`) and env:

- `STRIPE_SECRET_KEY` (required when `PAYMENT_PROVIDER=stripe`)
- `STRIPE_WEBHOOK_SECRET` (required for webhook endpoint)
- `PAYMENT_PROVIDER` — `mock` | `stripe` (default `mock`)

## 2. Replace mock with real implementation

- **Interface:** The shared contract is in `app/services/payment_provider/__init__.py`: `create_payment_for_subscription(subscription_id, amount_cents, currency, metadata)` returning a `PaymentIntentResult` with `id`, `client_secret`, `status`.
- **Where to implement:** Add **`app/services/payment_provider/stripe/live.py`** (or replace the mock in the same folder). Implement the same function name and return shape.
- **Behavior:**
  - Call Stripe API to create a **PaymentIntent** (or Checkout Session if you prefer redirect flow) with `amount` (in cents), `currency` (lowercase, e.g. `usd`), and `metadata` containing at least `subscription_id` (for the webhook).
  - Return `id` (e.g. `payment_intent.id`), `client_secret`, and `status` (e.g. `requires_payment_method`).
  - Store the returned `id` as `external_payment_id` in the **`subscription_payment`** table (already done in the with-payment route; ensure the row is created with the real Stripe id).
- **Config:** When `PAYMENT_PROVIDER=stripe`, `app/services/payment_provider/__init__.py` already tries to import `live.create_payment_for_subscription`; implement that function so the import succeeds.

## 3. Webhook endpoint

- **URL:** Add **POST `/api/v1/webhooks/stripe`** (or similar) that receives Stripe webhooks.
- **Verification:** Use `STRIPE_WEBHOOK_SECRET` to verify the signature (e.g. `stripe.Webhook.construct_event(payload, signature, secret)`).
- **Event:** On **`payment_intent.succeeded`** (or Checkout Session completed if using Checkout):
  - Read `subscription_id` from the payment metadata.
  - Call the same **activate subscription** logic used by the mock confirm step: `activate_subscription_after_payment(subscription_id, modified_by=...)` from `app/services/subscription_action_service.py`. For webhook, `modified_by` can be a system user or the subscription’s `user_id` (fetch from subscription).
- **Idempotency:** If the subscription is already Active, or the `subscription_payment` row is already marked `succeeded`, skip or return 200 to avoid duplicate activation. Stripe may retry webhooks.

## 4. Idempotency and failures

- **Creating PaymentIntents:** Use Stripe [idempotency keys](https://stripe.com/docs/api/idempotent_requests) when creating PaymentIntents to avoid duplicate charges on retries.
- **Webhook retries:** Stripe retries failed webhooks. Make the handler idempotent (check subscription status / `subscription_payment.status` before activating).
- **Failures:** Document how you handle payment failures (e.g. leave subscription in Pending; optional cleanup or expiry).

## 5. Testing

- Use **Stripe test mode** and [test cards](https://stripe.com/docs/testing).
- For local e2e, expose the webhook URL via a tunnel (e.g. **Stripe CLI** `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe`) and use the CLI’s webhook signing secret in `.env`.
- No change to the **subscription_payment** or **subscription_info** schema is required; only the adapter implementation and `PAYMENT_PROVIDER=stripe` switch.

## Extension points (out of scope for initial handoff)

- **Stripe Customer / saved payment methods:** Can be added later; the handoff doc does not implement them.
- **Metered billing / proration:** Same flow supports one payment per subscription start; extensions can be noted where the adapter or webhook is extended.
