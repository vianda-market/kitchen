# Fintech link and fintech link assignment — deprecated

**Fintech link** and **fintech link assignment** endpoints are **deprecated**. Use the atomic Stripe subscription flow for new subscription flows.

## Replacement

- **New flow:** **POST /api/v1/subscriptions/with-payment** — creates a subscription in Pending status and a payment intent (Stripe or mock). The client completes payment (e.g. with Stripe Elements or redirect), then the subscription is activated on payment success (webhook in production, or **POST /api/v1/subscriptions/{id}/confirm-payment** when using the mock provider).
- No manual consolidation or external payment links; subscription and payment are handled in one flow.

## Deprecated endpoints

- **Fintech links:** POST/GET/PUT/DELETE `/api/v1/fintech-links` and enriched variants.
- **Fintech link assignment:** POST/GET/DELETE `/api/v1/fintech-link-assignment` and enriched variants.

These endpoints will be **removed in a future API version**. Migrate to the subscription-with-payment flow before removal.

## References

- Atomic subscription flow: see **STRIPE_INTEGRATION_HANDOFF.md** and the subscription payment routes under `/api/v1/subscriptions`.
