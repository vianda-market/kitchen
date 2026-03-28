# Stripe Supplier Outbound (Connect) Integration Roadmap

**Last Updated**: 2026-03-27
**Purpose**: Build Stripe Connect outbound payment infrastructure so the platform can move funds from the Vianda Stripe account to **supplier** connected accounts. There is **no implementation for this yet**; inbound Comensal collection (PaymentIntents, subscription webhooks) exists and should be used as the reference for env vars, webhook verification, and service layout.

---

## Domain mapping (read this first)

| Product language | Kitchen backend | Why |
|-----------------|-----------------|-----|
| Supplier | `ops.institution_entity_info` row with `institution_type = 'Supplier'` (via its parent `core.institution_info`) | `institution_entity` is the **tax-registered company** — it holds `tax_id`, `name`, and will hold `stripe_connect_account_id`. Stripe KYC onboards the legal entity, not the abstract institution. |
| `supplierId` / `entityId` in API sketches | `institution_entity_id` (UUID) in routes and DB | |
| Payout transaction record | New `billing.institution_bill_payout` table (see Milestone 2) | Provider-agnostic middle table, mirrors the `customer.external_payment_method` pattern. `institution_bill_info` holds business state; payout table holds provider details. |

**Why `institution_entity` not `institution`:**
`institution_info` is a top-level grouping object that may span multiple countries and own many `institution_entity` records. `institution_entity_info` is the actual legal entity: it has a `tax_id`, a specific address, and a `credit_currency_id`. Stripe onboards legal entities — not abstract groupings — so `stripe_connect_account_id` lives on `institution_entity_info`.

**Hard dependency:** No `Transfer` to a supplier can succeed until that `institution_entity` has a persisted `stripe_connect_account_id` from Connect account creation. Milestone 1 must be complete before Milestone 2.

`SUPPLIER_PAYOUT_PROVIDER` (`mock` | `stripe`) already exists in `app/config/settings.py`. All Connect code must honor this flag the same way `PAYMENT_PROVIDER` gates inbound Stripe.

---

## Executive Summary

| | Inbound (Comensal) | Outbound (Suppliers) |
|--|-------------------|----------------------|
| Stripe product | PaymentIntents / Customers | **Connect** + **Transfers** |
| Who has the Stripe account | Platform | **Connected accounts** (supplier entities), each with `acct_…` |
| Money flow | Customer → platform | Platform balance → connected account |
| Onboarding | Not required for basic charge | **Required** — KYC via Account Links; `payouts_enabled` must be `true` |
| Webhook secret | `STRIPE_WEBHOOK_SECRET` | **Separate** `STRIPE_CONNECT_WEBHOOK_SECRET` (different endpoint and signing secret) |
| Provider ID attached to entity | `stripe_customer_id` on `user_payment_provider` | **`stripe_connect_account_id`** on `institution_entity_info` |
| Provider transaction record | `customer.external_payment_method` | **`billing.institution_bill_payout`** |

Reference: [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](./STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md), [STRIPE_INTEGRATION_HANDOFF.md](../api/internal/STRIPE_INTEGRATION_HANDOFF.md)

---

## Payout table design rationale

### Why a middle table instead of columns on `institution_bill_info`

`institution_bill_info` currently has `stripe_payout_id VARCHAR(255)` and `payout_completed_at` directly on the bill. These are Stripe-specific columns on a business table — the same design the customer pattern avoided by introducing `customer.external_payment_method`.

This codebase operates in LatAm markets (AR, MX, BR, PE, CL). Local payment providers (Mercado Pago, dLocal, PayU) are a near-certainty for supplier payouts in markets where Stripe Connect has limited country support. Adding a provider-specific column per provider is the wrong path.

**Decision: introduce `billing.institution_bill_payout`** — a provider-agnostic transaction record, one row per payout attempt. As part of this work, remove `stripe_payout_id` from `institution_bill_info` (it has not been used in production yet; this is the right moment to fix it).

### Why no history table for `institution_bill_payout`

The project's `audit.*` history pattern exists for mutable records where intermediate states matter (users, institutions, restaurants). A payout transaction has at most two state transitions: `pending` → `completed` or `failed`. Once terminal, it never changes again.

More importantly: **retries produce a new row, not an update**. If a transfer fails, a new `institution_bill_payout` row is inserted for the retry attempt. The failed row is preserved by definition. This gives a full attempt history without any trigger or history table.

This mirrors `customer.external_payment_method`, which also has no history table.

The `institution_bill_info` bill itself (the business record) continues to use the existing `audit.institution_bill_history` trigger — no change there.

---

## Manual Stripe Dashboard setup (do this before any code runs)

These steps must be completed by a human with Stripe platform account access. Code cannot do them.

There are two tracks: **Sandbox** (for dev environment integration, do this now) and **Live** (for production, do later after Stripe account activation). The steps differ meaningfully — sandbox skips business verification entirely.

---

### Sandbox setup (dev/GCP environment — do this now)

Sandbox (test mode) requires no business profile, no Stripe review, and no HTTPS restrictions. Everything is immediate.

#### Sandbox Step 1 — Enable Connect in test mode ✅ Done
Connect overview is open and a sandbox connected account has been created. No further action needed here.

#### Sandbox Step 2 — Register the Connect webhook endpoint ✅ Done
Webhook is registered pointing to the dev GCP API URL. Signing secret collected.

> **What you observed and why:**
>
> **`transfer.failed` not available** — correct, that event does not exist. Transfers don't fail asynchronously; if Stripe can't create a transfer the API call returns an error synchronously. When a transfer is reversed after creation, Stripe fires `transfer.reversed`. The correct event list is: `account.updated`, `transfer.created`, `transfer.reversed`, `payout.paid`, `payout.failed`.
>
> **"Two different payload styles" warning** — this appears when a v2/thin event is selected alongside standard v1/snapshot events. All five events listed above are v1/snapshot. If you saw this warning, check the selected events and de-select anything flagged as "thin" or "v2". **Do not create two endpoints** — one endpoint handles all of our events.

#### Sandbox Step 3 — Complete test connected account onboarding ⬅ Still needed

You have the test connected account ID but Stripe requires `payouts_enabled = true` on a connected account before any transfer to it will succeed. Until this is done, all transfer API calls will be rejected with a capability error.

To complete test onboarding without real documents:
1. Call the Stripe API to create an Account Link for the test connected account (this is what Milestone 1 will build, but you can do it manually via the Stripe API or Dashboard now):
   - In the Stripe Dashboard (test mode) → **Connect** → click the test account → **Complete onboarding**
   - Or via API: `stripe.AccountLink.create(account=<test_acct_id>, type='account_onboarding', ...)`
2. Open the returned URL and fill in the form using Stripe's test bypass values:
   - Test SSN / personal ID: `000-00-0000`
   - Test routing number: `110000000`
   - Test bank account number: `000123456789`
3. Submit the form — Stripe immediately sets `payouts_enabled: true` in test mode
4. Confirm: retrieve the account and verify `"payouts_enabled": true`

#### Values status

| Value | Status | Config key |
|-------|--------|-----------|
| Sandbox Connect webhook signing secret | ✅ Collected | `STRIPE_CONNECT_WEBHOOK_SECRET` |
| Sandbox test connected account ID | ✅ Collected | Dev/test use only — not a config key |
| Sandbox platform account ID (`acct_…`) | Collect from **Settings → Account details** | `STRIPE_PLATFORM_ACCOUNT_ID` (optional) |
| Test connected account `payouts_enabled` | ⬅ Complete Step 3 above | Prerequisite for transfers — not a config key |
| `STRIPE_SECRET_KEY` (sandbox `sk_test_…`) | Already set (inbound Stripe exists) | `STRIPE_SECRET_KEY` |

> `STRIPE_CONNECT_WEBHOOK_SECRET` and `STRIPE_PLATFORM_ACCOUNT_ID` are not yet in `app/config/settings.py` or `.env.example` — adding them is the first task in Milestone 0.

---

### Live setup (production — do this after sandbox integration is verified)

Live mode requires completing the Stripe account activation (KYC for your business) and a platform profile before any live connected accounts can be created.

#### Live Step 1 — Activate the platform Stripe account
1. In **live mode**, go to **Settings** → **Account details**
2. Complete the account activation form: business name, address, tax ID, owner details
3. This triggers Stripe's standard KYC review — typically approved within minutes for legitimate businesses, but can take longer
4. Note your **live platform account ID** — it is the same `acct_…` as test mode but used with live keys

#### Live Step 2 — Complete the Connect platform profile
1. Go to **Connect** → **Settings**
2. Complete the **platform profile**: business description, redirect URLs for onboarding, support contact
3. This is required before you can create live Account Links for connected accounts

> **Express vs Custom:** Express accounts give suppliers a Stripe-hosted dashboard to manage their own payouts and history. Custom accounts give full UI control but require more implementation. Express is the correct default for this integration.

#### Live Step 3 — Register the live Connect webhook endpoint
Same as Sandbox Step 2, but:
- Use your production URL (`https://<prod-api-domain>/api/v1/webhooks/stripe-connect`)
- Register in **live mode** (not test mode)
- Store the live signing secret separately — it is different from the sandbox secret

#### Live Step 4 — Verify LatAm country support
Before onboarding real suppliers in AR, MX, BR, PE, CL:
- Go to **Connect** → **Settings** → check which countries are supported for Express accounts
- Stripe Express country coverage in LatAm has gaps — verify before committing to this provider for a specific market

---

## Milestone 0 — Environment and config

### Environment variables to add

| Variable | Purpose | Already exists |
|----------|---------|----------------|
| `STRIPE_SECRET_KEY` | Platform secret; same key serves Connect API calls | ✅ Yes |
| `STRIPE_CONNECT_WEBHOOK_SECRET` | Signing secret for `/api/v1/webhooks/stripe-connect` | ❌ Add |
| `STRIPE_PLATFORM_ACCOUNT_ID` | Optional: explicit `acct_…` of the platform; useful for logging and Stripe support | ❌ Add (optional) |
| `SUPPLIER_PAYOUT_PROVIDER` | `mock` \| `stripe` — gates all Connect code | ✅ Yes |

Add `STRIPE_CONNECT_WEBHOOK_SECRET` and `STRIPE_PLATFORM_ACCOUNT_ID` to:
- `app/config/settings.py`
- `.env.example`

### New service module

Create `app/services/payment_provider/stripe/connect_gateway.py`:
- Thin wrappers around `stripe.Account`, `stripe.AccountLink`, `stripe.Transfer`
- Calls `_ensure_stripe_configured()` (same pattern as `live.py`)
- Checks `SUPPLIER_PAYOUT_PROVIDER != "mock"` before making real Stripe calls
- Does **not** touch PaymentIntents — keeps inbound and outbound concerns separate

---

## Milestone 1 — Institution entity onboarding (blocking dependency)

### Database changes

Add to `ops.institution_entity_info`:
```sql
stripe_connect_account_id VARCHAR(255) NULL
```

Mirror in `audit.institution_entity_history`:
```sql
stripe_connect_account_id VARCHAR(255) NULL
```

Update `trigger.sql`: the audit trigger for `institution_entity_info` must INSERT `stripe_connect_account_id` into the history row.

Sync layers (in order per project convention):
1. `schema.sql` — add column to both `ops.institution_entity_info` and `audit.institution_entity_history`
2. `trigger.sql` — update audit trigger INSERT
3. `seed.sql` — no seed data needed (nullable)
4. `app/dto/models.py` — add `stripe_connect_account_id: Optional[str] = None` to `InstitutionEntityDTO`
5. `app/schemas/consolidated_schemas.py` — add field to any `InstitutionEntity*ResponseSchema` used by B2B frontend

### API endpoints

Add under `app/routes/institution_entity.py` (prefix `/institution-entities`):

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/institution-entities/{entity_id}/stripe-connect/onboarding` | Create Stripe Express connected account; persist `stripe_connect_account_id` | Supplier Admin (own entity) or Internal |
| GET | `/institution-entities/{entity_id}/stripe-connect/onboarding-link` | Generate Account Link URL; returns `{ url, expires_at }` for frontend redirect | Same |
| GET | `/institution-entities/{entity_id}/stripe-connect/status` | Return `{ charges_enabled, payouts_enabled, details_submitted }` from Stripe | Same |

**Access control:** Supplier Admin may only act on their own `institution_entity_id` (enforce via `EntityScopingService`). Internal roles act globally. Pattern is identical to existing enriched entity endpoints in `app/routes/institution_entity.py`.

**Service function:** `create_connect_account(entity_id, db)` in `connect_gateway.py`:
1. Verify entity exists and has `institution_type = 'Supplier'` (via parent institution)
2. If `stripe_connect_account_id` already set, skip creation (idempotent)
3. Call `stripe.Account.create(type='express', email=..., metadata={'institution_entity_id': str(entity_id)})`
4. Persist `stripe_connect_account_id` on the entity

### Webhook: `account.updated`

Handler in Milestone 3 connect webhook route:
- Load entity by `stripe_connect_account_id` (or by metadata)
- Update any cached onboarding flags if stored
- Must be idempotent and signature-verified with `STRIPE_CONNECT_WEBHOOK_SECRET`

---

## Milestone 2 — Transfer execution

Prerequisite: `stripe_connect_account_id` exists on the entity and `payouts_enabled = true`.

### Database: new `billing.institution_bill_payout` table

Provider-agnostic payout transaction record. One row per attempt. **No history table** — retries insert a new row; terminal state (`completed`/`failed`) is never overwritten. This makes the table an append-only audit trail by design.

```sql
CREATE TABLE IF NOT EXISTS billing.institution_bill_payout (
    bill_payout_id       UUID PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id  UUID NOT NULL,
    provider             VARCHAR(50)  NOT NULL,          -- 'stripe', 'mercadopago', 'bank_transfer'
    provider_transfer_id VARCHAR(255) NULL,              -- tr_… for Stripe; equivalent for others
    amount               NUMERIC      NOT NULL,
    currency_code        VARCHAR(10)  NOT NULL,
    status               VARCHAR(50)  NOT NULL DEFAULT 'pending',  -- 'pending', 'completed', 'failed'
    idempotency_key      VARCHAR(255) NOT NULL UNIQUE,   -- deterministic per bill+provider; safe to retry
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at         TIMESTAMPTZ  NULL,
    modified_by          UUID         NOT NULL,
    modified_date        TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_bill_id) REFERENCES billing.institution_bill_info(institution_bill_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by)         REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_bill_payout_bill_id  ON billing.institution_bill_payout(institution_bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_payout_provider ON billing.institution_bill_payout(provider);
```

### Changes to `institution_bill_info`

Remove `stripe_payout_id VARCHAR(255)` and `payout_completed_at TIMESTAMPTZ` from `institution_bill_info` and `audit.institution_bill_history`. These columns have not been used in production; this is the right moment to clean them before any code depends on them.

`resolution bill_resolution_enum` (`Pending` / `Paid` / `Failed`) stays on the bill — it is the **business outcome**, provider-agnostic. Webhooks drive the transition.

### Sync layers

1. `schema.sql` — add `billing.institution_bill_payout`; remove `stripe_payout_id` and `payout_completed_at` from `institution_bill_info` and `institution_bill_history`
2. `trigger.sql` — remove the two columns from the `institution_bill_info` audit trigger INSERT
3. `seed.sql` — no seed data needed
4. `app/dto/models.py` — remove `stripe_payout_id` / `payout_completed_at` from `InstitutionBillDTO`; add new `InstitutionBillPayoutDTO`
5. `app/schemas/consolidated_schemas.py` — update bill response schemas; add payout response schema

### API endpoint

| Method | Path | Body | Behavior |
|--------|------|------|---------|
| POST | `/api/v1/institution-entities/{entity_id}/stripe-connect/payout` | `{ institution_bill_id }` | Resolve `stripe_connect_account_id`, insert `institution_bill_payout` row, create Stripe `Transfer`, write `provider_transfer_id` back |

### Service logic

`execute_supplier_payout(institution_bill_id, entity_id, db)` in `connect_gateway.py`:
1. Load bill — verify `resolution = 'Pending'`; check no existing `institution_bill_payout` row with `status != 'failed'` for this bill (guard against double-pay)
2. Load entity — verify `stripe_connect_account_id` is set and `payouts_enabled`
3. Compute `idempotency_key = f"bill_{institution_bill_id}_stripe"` — deterministic, includes provider
4. Insert `institution_bill_payout` row with `status = 'pending'` and `idempotency_key` **before** calling Stripe (write-first so a crash after Stripe responds is recoverable)
5. Call `stripe.Transfer.create(destination=..., idempotency_key=idempotency_key, ...)`
6. Update row: set `provider_transfer_id = transfer.id`
7. Leave `status`, `completed_at`, and `bill.resolution` for the webhook to set

**Write the payout row before the Stripe call.** If the process crashes between the Stripe call succeeding and the DB write, the idempotency key lets you recover on retry without creating a second transfer.

---

## Milestone 3 — Webhook handlers (Connect events)

### Route

Add `POST /api/v1/webhooks/stripe-connect` as a **separate route** from the existing inbound webhook.
- Verify signature using `STRIPE_CONNECT_WEBHOOK_SECRET` (not `STRIPE_WEBHOOK_SECRET`)
- Register separately in Stripe Dashboard (Step 2 above)

### Events and actions

| Event | Action |
|-------|--------|
| `account.updated` | Load entity by `stripe_connect_account_id`; log onboarding status change |
| `transfer.created` | Confirm `provider_transfer_id` is written on the payout row (belt-and-suspenders) |
| `transfer.reversed` | Set `bill_payout.status = 'failed'`; set `bill.resolution = 'Failed'`; log entity, bill, reversal reason |
| `payout.paid` | Set `bill_payout.status = 'completed'`, `bill_payout.completed_at = now`, `bill.resolution = 'Paid'` |
| `payout.failed` | Set `bill_payout.status = 'failed'`, `bill.resolution = 'Failed'`; notify ops |

**All handlers must be idempotent** — look up the payout row by `provider_transfer_id` and check current state before writing.

---

## Milestone 4 — Dev/GCP testing scaffolding

Testing is done against the dev GCP environment (not local). The webhook endpoint is already registered in Stripe sandbox pointing to the dev API URL.

### Manually trigger test events via Stripe CLI

The Stripe CLI can fire test events directly to the registered sandbox webhook endpoint:

```bash
stripe trigger transfer.created
stripe trigger account.updated
stripe trigger payout.paid
```

These hit the real registered endpoint (dev GCP URL) in sandbox mode. No local forwarding needed.

### Manually trigger test events via Stripe Dashboard

Alternatively: **Developers** → **Webhooks** → select the endpoint → **Send test webhook** → choose event type.

### Dev-only trigger endpoint (guard with `DEV_MODE`)

`POST /api/v1/dev/trigger-test-payout` — creates a minimal transfer to the sandbox test connected account for end-to-end integration testing. Guard with `DEV_MODE=true`. **Never enable in production.**

---

## Milestone 5 — Error handling and observability

### Stripe error mapping

| Stripe exception | HTTP response |
|-----------------|--------------|
| `stripe.error.AuthenticationError` | 500 (config problem) |
| `stripe.error.InvalidRequestError` | 400 with safe message |
| `stripe.error.PermissionError` | 400 — account not ready for transfers |
| `stripe.error.APIConnectionError` | 503 — retry eligible |
| `stripe.error.RateLimitError` | 429 — retry with backoff |

Never leak raw Stripe error messages to clients.

### Logging

Every transfer attempt must log: `institution_entity_id`, `institution_bill_id`, `bill_payout_id`, `amount`, `currency`, `provider`, `provider_transfer_id` (when known). Webhook handlers for `transfer.reversed` must log the reversal reason from the Stripe event.

### Admin visibility

`GET /api/v1/institution-entities/{entity_id}/stripe-connect/payouts` — list payout rows with bill context. Restrict to Internal role.

---

## Milestone 6 — Production checklist

- [ ] Stripe Connect enabled on live platform account (complete Stripe review if required — see Manual Setup Step 1)
- [ ] Live Connect webhook endpoint registered; `STRIPE_CONNECT_WEBHOOK_SECRET` updated to live `whsec_…`
- [ ] `SUPPLIER_PAYOUT_PROVIDER=stripe` set in production environment
- [ ] Every active supplier `institution_entity` has completed live onboarding (`payouts_enabled = true`)
- [ ] Run a micro transfer to one verified test entity before full rollout
- [ ] Document reconciliation: Stripe Dashboard transfers vs `billing.institution_bill_payout` vs accounting exports

---

## Implementation order (strict)

1. Manual Stripe Dashboard setup (Steps 1–4 above) — human action, no code
2. Milestone 0 — settings + `connect_gateway.py` module
3. Milestone 1 — `stripe_connect_account_id` on `institution_entity_info` + onboarding endpoints
4. Milestone 2 — new `institution_bill_payout` table + remove Stripe columns from bill + transfer API
5. Milestone 3 — Connect webhook route + event handlers
6. Milestone 4 — CLI + dev trigger
7. Milestone 5 — error handling + admin list
8. Milestone 6 — production cutover

Skipping Milestone 1 guarantees blocked transfers. Milestone 2 DB cleanup (removing `stripe_payout_id` from `institution_bill_info`) must happen before any code references those columns.

---

## Related documentation

- [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](./STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md) — inbound patterns, webhook verification, CLI forwarding
- [STRIPE_INTEGRATION_HANDOFF.md](../api/internal/STRIPE_INTEGRATION_HANDOFF.md) — handoff from mock to live Stripe
- [RESTAURANT_PAYMENT_FLOW_AND_APIS.md](../api/internal/RESTAURANT_PAYMENT_FLOW_AND_APIS.md) — institutional billing context
- [SUPPLIER_INSTITUTION_PAYMENT.md](../api/internal/SUPPLIER_INSTITUTION_PAYMENT.md) — supplier payment domain notes

---

## Key difference vs inbound (one-liner for agents)

**Inbound** = platform charges customers with PaymentIntents. **Outbound** = platform pays connected accounts (`institution_entity`) with Connect Transfers. `stripe_connect_account_id` on `institution_entity_info` is mandatory before any transfer. The payout transaction lives in `billing.institution_bill_payout` (provider-agnostic, append-only, no history table); the bill's `resolution` field reflects the business outcome.
