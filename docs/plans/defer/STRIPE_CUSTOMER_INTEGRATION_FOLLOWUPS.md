# Stripe customer integration — follow-ups (out of current implementation scope)

**Purpose:** Track improvements **not** in the initial live setup-session + `payment_method.attached` / `detached` slice. The main roadmap remains [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](./STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md).

---

## Production-grade race handling for `stripe_customer_id`

The first slice uses `SELECT … FOR UPDATE` and **first writer wins**; a racing second request may see **409 / 500** and the user retries.

**Future:** Optional **ON CONFLICT / rollback + re-select** (or retry loop) when `UNIQUE (stripe_customer_id)` fires, so concurrent setup-session calls converge without user-visible errors.

---

## `customer.updated` webhook

**Skipped** in the first slice to reduce handler and Dashboard noise.

**Future:** Subscribe in Stripe and sync Stripe Customer default payment method vs local `payment_method.is_default` if product requires single source of truth on Stripe for invoicing.

---

## Max payment methods per user

**Skipped** in the first slice (only a **TODO** in code referencing this file).

**Future:** Enforce a cap (e.g. 5 active, non-archived Stripe PMs per `user_id`) before creating a new Setup Session; optional setting `MAX_STRIPE_PAYMENT_METHODS_PER_USER`.

---

## Optional `STRIPE_CUSTOMER_SETUP_CANCEL_URL`

**Skipped:** `cancel_url` defaults to `success_url` when omitted.

**Future:** Separate env for cancel landing page if product wants different UX for abandoned checkout.

---

## Checkout Setup Session: `payment_method_types` vs Stripe direction

The first slice uses `payment_method_types=["card"]` on `stripe.checkout.Session.create` for `mode=setup`. Stripe may emit **deprecation warnings** and is moving toward **`automatic_payment_methods`** and/or explicit **`payment_method_configuration`**.

**Future:** Migrate Session creation to the recommended Stripe pattern once product scope (wallets, etc.) is clear; watch Dashboard/API changelog and log warnings in CI.

---

## Related

- [STRIPE_INTEGRATION_HANDOFF.md](../api/internal/STRIPE_INTEGRATION_HANDOFF.md)
- Phase 4 subscription reuse in main roadmap (saved card for `with-payment`)
