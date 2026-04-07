# Stripe Payment Infrastructure

**Audience**: infra-kitchen-gcp (Pulumi repo)
**Purpose**: Everything the infrastructure layer must provision and configure to enable Stripe payment method management on the Kitchen backend.
**Last Updated**: 2026-03-25

---

## Status by Environment

| Environment | Status | Notes |
|-------------|--------|-------|
| Local dev | Mock only | `PAYMENT_PROVIDER=mock`, no Stripe keys needed |
| GCP dev/staging | Ready to activate | Secrets and env vars need to be set (see below) |
| GCP prod | Not yet active | Same as staging; activate once test environment validated |

---

## What the Backend Expects

The backend reads these values via `app/config/settings.py` (Pydantic `BaseSettings`, loaded from env). All Stripe values default to empty string — the app falls back to mock mode when `PAYMENT_PROVIDER` is not `stripe`.

### Required Environment Variables (Stripe active)

| Variable | Type | Required When | Description |
|----------|------|---------------|-------------|
| `PAYMENT_PROVIDER` | string | Always | Set to `stripe` to activate live Stripe. Default: `mock` |
| `STRIPE_SECRET_KEY` | secret | `PAYMENT_PROVIDER=stripe` | Server-side key. `sk_test_...` for non-prod; `sk_live_...` for prod. Never share or log. |
| `STRIPE_WEBHOOK_SECRET` | secret | `PAYMENT_PROVIDER=stripe` | Signing secret for webhook signature verification. One value per webhook endpoint registration (test secret differs from live). Format: `whsec_...` |
| `STRIPE_PUBLISHABLE_KEY` | string | Optional | Client-side key. Not used server-side today; set for completeness. `pk_test_...` / `pk_live_...` |
| `STRIPE_CUSTOMER_SETUP_SUCCESS_URL` | string | Optional | Default redirect URL after a Stripe Checkout Setup Session completes. Used when the B2C client omits `return_url` in the POST body. Example: `https://app.vianda.com/payment/success` |

### Supplier Payout (separate concern)

| Variable | Type | Notes |
|----------|------|-------|
| `SUPPLIER_PAYOUT_PROVIDER` | string | `mock` or `stripe`. Separate from customer payment methods. Not yet active. |

---

## GCP Secret Manager

Store all secret values (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) in GCP Secret Manager — not as plain Cloud Run env vars.

### Secret naming convention (recommended)

```
kitchen-stripe-secret-key-{env}          # e.g. kitchen-stripe-secret-key-staging
kitchen-stripe-webhook-secret-{env}      # e.g. kitchen-stripe-webhook-secret-staging
```

### Secret Manager → Cloud Run binding

Mount each secret as an environment variable on the Cloud Run service. The Cloud Run service account needs `roles/secretmanager.secretAccessor` on each secret.

```
# Pulumi pattern (Python)
stripe_secret_key = gcp.secretmanager.Secret("stripe-secret-key-staging", ...)
cloud_run_service = gcp.cloudrun.Service(
    "kitchen-backend",
    template=gcp.cloudrun.ServiceTemplateArgs(
        spec=gcp.cloudrun.ServiceTemplateSpecArgs(
            containers=[gcp.cloudrun.ServiceTemplateSpecContainerArgs(
                envs=[
                    gcp.cloudrun.ServiceTemplateSpecContainerEnvArgs(
                        name="PAYMENT_PROVIDER",
                        value="stripe",
                    ),
                    gcp.cloudrun.ServiceTemplateSpecContainerEnvArgs(
                        name="STRIPE_SECRET_KEY",
                        value_from=gcp.cloudrun.ServiceTemplateSpecContainerEnvValueFromArgs(
                            secret_key_ref=gcp.cloudrun.ServiceTemplateSpecContainerEnvValueFromSecretKeyRefArgs(
                                name=stripe_secret_key.secret_id,
                                key="latest",
                            )
                        ),
                    ),
                    # Repeat for STRIPE_WEBHOOK_SECRET
                ]
            )]
        )
    )
)
```

---

## Stripe Dashboard Configuration

These steps are performed in the Stripe Dashboard by a team member with account access — not automated by Pulumi. Document them here so the infra repo can track them.

### Per-environment webhook endpoint registration

Each deployed environment needs its own webhook endpoint registered in the Stripe Dashboard.

| Environment | Stripe mode | Webhook URL |
|-------------|-------------|-------------|
| GCP staging | Test mode | `https://<staging-cloud-run-url>/api/v1/webhooks/stripe` |
| GCP prod | Live mode | `https://<prod-cloud-run-url>/api/v1/webhooks/stripe` |

**Steps** (per environment):
1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. Enter the Cloud Run URL above
3. Select events to listen for (see below)
4. Copy the signing secret (`whsec_...`) — this becomes `STRIPE_WEBHOOK_SECRET` for that environment
5. Store in GCP Secret Manager under the per-env name (see above)

### Events to subscribe

| Event | Purpose |
|-------|---------|
| `payment_method.attached` | Sync newly saved card to `payment_method` + `external_payment_method` tables |
| `payment_method.detached` | Archive local card row when detached in Stripe |
| `payment_intent.succeeded` | Activate subscription after successful payment |

Do not subscribe to `customer.updated` in v1 — intentionally omitted.

---

## Key Separation Rules

**Critical**: test and live Stripe keys/secrets must never be mixed across environments.

| Environment | Stripe Dashboard mode | Key prefix | Webhook |
|-------------|----------------------|-----------|---------|
| Local dev | N/A (mock) | None | None |
| GCP staging | Test mode | `sk_test_`, `pk_test_`, `whsec_` (test) | Registered under Test mode tab |
| GCP prod | Live mode | `sk_live_`, `pk_live_`, `whsec_` (live) | Registered under Live mode tab |

Stripe test and live webhook endpoints produce **different** signing secrets. The `STRIPE_WEBHOOK_SECRET` for staging is different from prod even if the URL pattern looks similar.

---

## Activation Checklist (per environment)

Use this to move an environment from mock to live Stripe:

- [ ] Stripe API key (`sk_test_` or `sk_live_`) created in Stripe Dashboard and stored in GCP Secret Manager
- [ ] Webhook endpoint registered in Stripe Dashboard for this environment's Cloud Run URL
- [ ] Webhook signing secret (`whsec_...`) stored in GCP Secret Manager
- [ ] `PAYMENT_PROVIDER=stripe` set on Cloud Run service
- [ ] `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` mounted from Secret Manager
- [ ] `STRIPE_CUSTOMER_SETUP_SUCCESS_URL` set to the B2C app redirect URL for this environment (optional but recommended)
- [ ] Cloud Run service redeployed with new env vars
- [ ] Smoke test: POST `/api/v1/customer/payment-methods/setup-session` returns a real `checkout.stripe.com` URL (not `mock-stripe-setup.example`)
- [ ] Stripe CLI or test event confirms webhook signature verification passes

---

## PCI Scope

The backend uses **Stripe-hosted Checkout / Setup Sessions** — raw card data never touches application servers. This keeps the platform in PCI **SAQ A** (lowest tier). Do not add any server-side card collection endpoints.

---

## Backend Documentation References

| Document | Purpose |
|----------|---------|
| `docs/api/internal/STRIPE_INTEGRATION_HANDOFF.md` | Backend implementation details — webhook handler, PaymentIntent flow, idempotency |
| `docs/api/b2c_client/PAYMENT_PROVIDERS_B2C.md` | B2C client integration for the provider connection/disconnect UI |
| `docs/api/shared_client/CUSTOMER_PAYMENT_METHODS_API.md` | Full API contract for card management endpoints |
| `docs/plans/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md` | Phase plan — what is live, what is next (Phase 3 live Stripe, Phase 4 subscription integration) |
| `docs/plans/STRIPE_CUSTOMER_INTEGRATION_FOLLOWUPS.md` | Production hardening items — race conditions, webhook sync, idempotency |
