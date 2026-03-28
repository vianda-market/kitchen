# Stripe Connect Supplier Payout — B2B Integration Guide

**Audience**: vianda-platform (B2B React) frontend agent
**Last Updated**: 2026-03
**Status**: Implemented (sandbox)

---

## Domain Context

A **supplier entity** (`institution_entity_info`) is the legal company entity that receives payouts.
An institution can own multiple entities (e.g. one per country). The entity holds:
- `institution_entity_id` — FK used in all Connect endpoints
- `tax_id` — used for Stripe KYC
- `stripe_connect_account_id` — set during onboarding; `null` until onboarded

Payouts are against **institution bills** (`institution_bill_info`). A bill aggregates the settlement for one entity for one period.

---

## Prerequisites (per entity)

1. Entity must exist (`GET /api/v1/institution-entities/enriched/{entity_id}`)
2. `stripe_connect_account_id` must be set (call onboarding endpoint if null)
3. Stripe account must have `payouts_enabled: true` (supplier completed KYC)

---

## Onboarding Flow (UI Steps)

### Step 1 — Create the Connect account (idempotent)

```
POST /api/v1/institution-entities/{entity_id}/stripe-connect/onboarding
```

- No request body required
- If account already exists, returns existing `stripe_connect_account_id` without creating a new one

**Response:**
```json
{
  "institution_entity_id": "uuid",
  "stripe_connect_account_id": "acct_…"
}
```

### Step 2 — Get onboarding link and redirect supplier

```
GET /api/v1/institution-entities/{entity_id}/stripe-connect/onboarding-link
  ?refresh_url=https://your-app/entities/{id}/onboarding
  &return_url=https://your-app/entities/{id}/onboarding/complete
```

- `refresh_url`: where Stripe redirects if the link expires (regenerate and redirect again)
- `return_url`: where Stripe redirects after the supplier completes the form

**Response:**
```json
{
  "url": "https://connect.stripe.com/setup/…",
  "expires_at": 1740000000
}
```

Redirect the supplier to `url`. Links expire in ~10 minutes — always regenerate, never cache.

### Step 3 — Check status after return

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

Show the supplier their onboarding status. `payouts_enabled: true` means they can receive payouts.
If `payouts_enabled: false`, prompt them to complete onboarding via a new link (Step 2).

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

`provider_transfer_id` is populated immediately after the Stripe Transfer is created.
`status` is `Pending` until Stripe confirms the payout reached the supplier's bank.

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

The payout table is append-only. Retries insert a new row. A bill with `resolution=Failed` can be retried by calling the payout endpoint again (a new `institution_bill_payout` row will be created).

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
| POST `/stripe-connect/onboarding` | Own entity only | All entities |
| GET `/stripe-connect/onboarding-link` | Own entity only | All entities |
| GET `/stripe-connect/status` | Own entity only | All entities |
| POST `/stripe-connect/payout` | ❌ Not allowed | ✅ All entities |

---

## References

- Entity list: `GET /api/v1/institution-entities/enriched/`
- Bill list: `GET /api/v1/institution-bills/`
- Enum service: `GET /api/v1/enums/` → `bill_resolution`, `bill_payout_status`
- Internal guide: `docs/roadmap/STRIPE_SUPPLIER_OUTBOUND_CONNECT_ROADMAP.md`
