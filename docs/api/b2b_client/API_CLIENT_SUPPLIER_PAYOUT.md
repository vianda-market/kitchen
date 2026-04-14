# Supplier Payout Onboarding — B2B Integration Guide

**Audience**: vianda-platform (B2B React) frontend agent
**Last Updated**: 2026-03
**Status**: Implemented (sandbox)

---

## Domain Context

A **supplier entity** (`institution_entity_info`) is the legal company entity that receives payouts.
An institution can own multiple entities (e.g. one per country). The entity holds:
- `institution_entity_id` — FK used in all payout endpoints
- `tax_id` — used for KYC
- `payout_provider_account_id` — set during onboarding; `null` until onboarded
- `payout_aggregator` — which provider the account belongs to (e.g. `'stripe'`); set alongside `payout_provider_account_id`
- `payout_onboarding_status` — `null` | `'pending'` | `'complete'`; synced from provider webhook

Payouts are against **institution bills** (`institution_bill_info`). A bill aggregates the settlement for one entity for one period.

---

## Step 0 — Check the market's aggregator

Before rendering any payout UI, call:

```
GET /api/v1/institution-entities/{entity_id}/payout-aggregator
```

**Response:**
```json
{
  "market_id": "uuid",
  "aggregator": "stripe",
  "is_active": true
}
```

| `is_active` | `aggregator` | UI action |
|-------------|--------------|-----------|
| `true` | `"stripe"` | Render Stripe embedded onboarding (see §Onboarding Flow) |
| `false` | any | Show "Payout setup for your market is coming soon. Contact support." |

---

## Onboarding Flow — Stripe Embedded (AR, BR, CL, MX, US)

Suppliers never leave the site. The Stripe Account Onboarding component renders inside vianda-platform.

### Step 1 — Get a client_secret (idempotent account creation + session)

```
POST /api/v1/institution-entities/{entity_id}/stripe-connect/account-session
```

- No request body required
- If `payout_provider_account_id` is already set, reuses it; otherwise creates the account first
- Returns a fresh `client_secret` every time — always call this before rendering the component, never cache

**Response:**
```json
{
  "client_secret": "cs_test_…",
  "payout_provider_account_id": "acct_…"
}
```

### Step 2 — Render the embedded component

```typescript
import { loadConnectAndInitialize } from "@stripe/connect-js";
import {
  ConnectComponentsProvider,
  ConnectAccountOnboarding,
} from "@stripe/react-connect-js";

const { client_secret } = await api.post(
  `/institution-entities/${entityId}/stripe-connect/account-session`
);

const stripeConnectInstance = loadConnectAndInitialize({
  publishableKey: STRIPE_PUBLISHABLE_KEY,
  fetchClientSecret: async () => client_secret,
});

<ConnectComponentsProvider connectInstance={stripeConnectInstance}>
  <ConnectAccountOnboarding
    onExit={() => checkOnboardingStatus(entityId)}
  />
</ConnectComponentsProvider>
```

After `onExit`, call `GET /stripe-connect/status` to check `payouts_enabled` and update the UI.

### Step 3 — Check status

```
GET /api/v1/institution-entities/{entity_id}/stripe-connect/status
```

**Response:**
```json
{
  "charges_enabled": true,
  "payouts_enabled": true,
  "details_submitted": true
}
```

`payouts_enabled: true` means the entity can receive payouts.
If `payouts_enabled: false`, prompt re-entry: call `account-session` again and re-render `<ConnectAccountOnboarding>`.

The entity's `payout_onboarding_status` field is also updated to `'complete'` via the `account.updated` webhook once Stripe confirms the account.

---

## Onboarding Flow — Redirect-based (legacy / fallback)

The redirect-based flow remains available for compatibility. Use only if embedded is not feasible.

### Step 1 — Create Connect account (idempotent)

```
POST /api/v1/institution-entities/{entity_id}/stripe-connect/onboarding
```

**Response:**
```json
{
  "institution_entity_id": "uuid",
  "payout_provider_account_id": "acct_…"
}
```

### Step 2 — Get onboarding link and redirect supplier

```
GET /api/v1/institution-entities/{entity_id}/stripe-connect/onboarding-link
  ?refresh_url=https://your-app/entities/{id}/onboarding
  &return_url=https://your-app/entities/{id}/onboarding/complete
```

**Response:**
```json
{
  "url": "https://connect.stripe.com/setup/…",
  "expires_at": 1740000000
}
```

Redirect the supplier to `url`. Links expire in ~10 minutes — always regenerate, never cache.

---

## Payout Trigger

> **Auth: Internal Admin only.** Supplier Admins cannot self-trigger payouts.

```
POST /api/v1/institution-entities/{entity_id}/stripe-connect/payout
```

**Request body:**
```json
{
  "institution_bill_id": "uuid"
}
```

**Preconditions:**
- Bill `resolution` must be `Pending`
- No existing non-Failed payout for this bill
- Entity must have `payouts_enabled: true` on their Stripe account

**Response** (`InstitutionBillPayoutResponseSchema`):
```json
{
  "bill_payout_id": "uuid",
  "institution_bill_id": "uuid",
  "provider": "stripe",
  "provider_transfer_id": "tr_…",
  "amount": "1500.00",
  "currency_code": "usd",
  "status": "Pending",
  "created_at": "2026-03-01T12:00:00Z",
  "completed_at": null
}
```

---

## Payout History (Admin)

> **Auth: Internal only.**

```
GET /api/v1/institution-entities/{entity_id}/stripe-connect/payouts
```

Returns all payout attempts for the entity's bills, newest first. Each row is an `InstitutionBillPayoutResponseSchema`:

```json
[
  {
    "bill_payout_id": "uuid",
    "institution_bill_id": "uuid",
    "provider": "stripe",
    "provider_transfer_id": "tr_…",
    "amount": "1500.00",
    "currency_code": "usd",
    "status": "Completed",
    "created_at": "2026-03-01T12:00:00Z",
    "completed_at": "2026-03-01T12:05:00Z"
  }
]
```

Use this to audit payout attempts, see failed transfers, and track retry history.

---

## Bill State Transitions

```
institution_bill_info.resolution:
  Pending → Paid      (payout.paid webhook received — funds confirmed)
  Pending → Failed    (transfer.reversed or payout.failed webhook)
  Pending → Rejected  (admin manual rejection — not payout-related)
```

`institution_bill_payout.status`:
```
  Pending → Completed  (payout.paid webhook)
  Pending → Failed     (transfer.reversed or payout.failed webhook)
```

The payout table is append-only. Retries insert a new row. A bill with `resolution=Failed` can be retried by calling the payout endpoint again.

---

## Enum Values

### `bill_resolution` (on `institution_bill_info`)
| Value | Meaning |
|-------|---------|
| `Pending` | Bill created; awaiting payout |
| `Paid` | Payout confirmed by Stripe |
| `Rejected` | Admin-rejected (e.g. fraud review) |
| `Failed` | Payout provider failure |

### `bill_payout_status` (on `institution_bill_payout`)
| Value | Meaning |
|-------|---------|
| `Pending` | Transfer created; awaiting bank confirmation |
| `Completed` | Funds confirmed in supplier's bank |
| `Failed` | Transfer reversed or payout failed |

---

## Auth Summary

| Endpoint | Supplier Admin | Internal |
|----------|---------------|----------|
| GET `/payout-aggregator` | Own entity only | All entities |
| POST `/stripe-connect/account-session` | Own entity only | All entities |
| POST `/stripe-connect/onboarding` | Own entity only | All entities |
| GET `/stripe-connect/onboarding-link` | Own entity only | All entities |
| GET `/stripe-connect/status` | Own entity only | All entities |
| POST `/stripe-connect/payout` | ❌ Not allowed | ✅ All entities |
| GET `/stripe-connect/payouts` | ❌ Not allowed | ✅ All entities |

---

## References

- Payout history list: `docs/api/b2b_client/API_CLIENT_PAYOUT_HISTORY.md`
- Financial data hierarchy: `docs/api/internal/FINANCIAL_DATA_HIERARCHY.md`
- Entity list: `GET /api/v1/institution-entities/enriched/`
- Bill list: `GET /api/v1/institution-bills/`
- Enum service: `GET /api/v1/enums/` → `bill_resolution`, `bill_payout_status`
- Embedded onboarding roadmap (archived): `docs/zArchive/roadmap/STRIPE_CONNECT_EMBEDDED_ONBOARDING.md`
- Stripe Connect.js: https://docs.stripe.com/connect/connect-js-react
