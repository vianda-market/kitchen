# Customer Payment Methods (B2C)

**Audience**: B2C client (kitchen-mobile) — Customer role only.  
**Purpose**: Implement "Manage payment methods" UI for customers who pay subscriptions. Use mock endpoints now; live Stripe later.

---

## Status and Roadmap (Agent-Aware)

| Phase | Status | What to expect |
|-------|--------|----------------|
| **Phase 1** | **Live** | Mock endpoints return fixture data or no-op. **Build UI now** — list, add, delete, set default. |
| **Phase 2** | Planned | Database schema (`stripe_customer_id`). No client change. |
| **Phase 3** | Planned | Live Stripe: real Setup Session, webhooks. `setup_url` will redirect to Stripe Checkout. |
| **Phase 4** | Planned | Subscription flow: if user has saved card, with-payment may skip card form. |

**Roadmap**: [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](../../roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md)

---

## Summary for B2C Agent

- **Use the endpoints now.** They are functional (mock). Implement "Payment methods" / "Manage cards" in profile or settings.
- **Mock behavior**: GET returns 1 fixture card (Visa •••• 4242) when user has none. POST setup-session returns a fixed URL; redirect to it to test flow. DELETE and PUT default return 200 with no real effect.
- **Live (Phase 3+)**: Same contract. `setup_url` will be real Stripe Checkout; after redirect back, refresh the list (webhook syncs new card).
- **Access**: Customer role only. 403 for Employees/Suppliers.

---

## API Reference

Full endpoint details, request/response schemas: [CUSTOMER_PAYMENT_METHODS_API.md](../shared_client/CUSTOMER_PAYMENT_METHODS_API.md)

---

## B2C UI Flow

### List payment methods

1. Navigate to "Payment methods" or "Manage cards" (e.g. from profile/settings).
2. Call `GET /api/v1/customer/payment-methods/`.
3. Render cards: `brand` + `last4` (e.g. "Visa •••• 4242"), highlight `is_default`, show Delete and "Set as default" actions.

### Add payment method

1. User taps "Add card" or "Add payment method".
2. Call `POST /api/v1/customer/payment-methods/setup-session` with optional `return_url` (deep link back to payment-methods screen).
3. Redirect user to `setup_url` (Stripe Checkout or mock URL).
4. User completes flow and returns to app.
5. Call `GET /api/v1/customer/payment-methods/` to refresh list.

**Mock**: `setup_url` is `https://mock-stripe-setup.example`. You can open it in WebView/browser for flow testing; no real card will be added until Phase 3.

### Delete payment method

1. User taps Delete on a card.
2. Confirm: "Remove this card?"
3. Call `DELETE /api/v1/customer/payment-methods/{payment_method_id}`.
4. On 200, remove from list or refetch.

### Set default

1. User taps "Set as default" on a non-default card.
2. Call `PUT /api/v1/customer/payment-methods/{payment_method_id}/default`.
3. On 200, update local state or refetch.

---

## B2B / Supplier Note

These endpoints are **Customer-only**. B2B (kitchen-web) is used by Employees and Suppliers. Suppliers do **not** manage payment methods here — their payouts are handled by the settlement pipeline. See [CUSTOMER_PAYMENT_METHODS_API.md](../shared_client/CUSTOMER_PAYMENT_METHODS_API.md) for the B2B vs B2C distinction.

---

## Related

- [SUBSCRIPTION_PAYMENT_API.md](./SUBSCRIPTION_PAYMENT_API.md) — Subscribe + pay flow (with-payment, confirm-payment)
- [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](../../roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md)
- [PAYMENT_AND_BILLING_CLIENT_CHANGES.md](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md)
