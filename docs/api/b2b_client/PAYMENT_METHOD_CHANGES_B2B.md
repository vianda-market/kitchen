# Payment Method Changes (B2B)

**Audience**: B2B client (kitchen-web) agents and developers.  
**Purpose**: Document removed payment features and required UI changes. A number of payment-related elements were **deleted** from the backend; the B2B app must remove all corresponding pages, modals, API calls, and references.

---

## Summary: What Was Removed

| Removed feature | Action in B2B app |
|-----------------|-------------------|
| **Institution Bank Account** | Remove all pages, modals, and API calls. Payout is Stripe-only via the settlement pipeline. |
| **Fintech Links** | Remove all pages, modals, and API calls. Subscription payment uses with-payment + confirm-payment only. |
| **Institution Payment Attempts** | Remove the "Payments" read-only page. `GET /api/v1/institution-payment-attempts/enriched/` is **removed**. See institution bills for payment info. |
| **Manual client bill create/process** | Remove any UI that creates or processes bills manually. Bills are auto-created when payment succeeds. |

---

## 1. Institution Bank Account — Deleted

**Backend status**: The `institution_bank_account` table and all related APIs have been **removed**. Institution (supplier) payout is now Stripe-only and is handled by the **settlement → bill → payout** pipeline. There is no bank-account setup or selection.

### Remove from B2B app

- **Pages**
  - "Bank accounts," "Institution bank accounts," "Manage bank accounts," "Add bank account," etc.
  - Any supplier/institution setup screen that includes a bank account section or step.
- **Modals / dialogs**
  - "Add bank account," "Edit bank account," "Select bank account for payout," etc.
- **API calls** (do not call; these endpoints no longer exist or return 404):
  - `GET /api/v1/institution-bank-accounts/`
  - `POST /api/v1/institution-bank-accounts/`
  - `GET /api/v1/institution-bank-accounts/{id}`
  - `PUT /api/v1/institution-bank-accounts/{id}`
  - `DELETE /api/v1/institution-bank-accounts/{id}`
  - Any enriched variant (e.g. `/enriched/`, `/{id}`).
- **Navigation / sidebar**
  - Menu entries for "Bank accounts" or "Institution bank accounts."
- **Forms and fields**
  - `institution_bank_account_id`, `bank_account_id`, or similar fields in institution, supplier, or bill forms.

### What to use instead

- **Institution payment**: Payout happens automatically when the settlement pipeline runs. No client configuration of bank accounts.
- **Pipeline**: `POST /api/v1/institution-bills/run-settlement-pipeline?bill_date=YYYY-MM-DD&country_code=XX` creates settlements and bills, then triggers payout per bill. See [../internal/SUPPLIER_INSTITUTION_PAYMENT.md](../internal/SUPPLIER_INSTITUTION_PAYMENT.md).

---

## 2. Fintech Links — Deleted

**Backend status**: Fintech link and fintech link assignment APIs have been **removed** or return **404**. Subscription payment is done only via the **subscription with-payment** flow.

### Remove from B2B app

- **Pages**
  - "Fintech links," "Payment links," "Manage payment links," "Link payment."
  - Any plan or subscription screen that creates or edits a "fintech link" for a plan.
- **Modals / dialogs**
  - "Add fintech link," "Edit fintech link," "Create payment link," "Assign fintech link to plan," etc.
- **API calls** (do not call; deprecated/removed):
  - `POST /api/v1/fintech-links/`
  - `GET /api/v1/fintech-links/`
  - `GET /api/v1/fintech-links/{id}`
  - `PUT /api/v1/fintech-links/{id}`
  - `DELETE /api/v1/fintech-links/{id}`
  - `POST /api/v1/fintech-link-assignment/`
  - `GET /api/v1/fintech-link-assignment/`
  - `DELETE /api/v1/fintech-link-assignment/{id}`
  - Any fintech-link-transaction endpoints.
- **Navigation / references**
  - Sidebar entries for "Fintech links" or "Payment links."
  - Buttons or links that open fintech link modals.

### What to use instead

- **Subscription payment**: Use **`POST /api/v1/subscriptions/with-payment`** and **`POST /api/v1/subscriptions/{subscription_id}/confirm-payment`** (mock) or poll `GET /api/v1/subscriptions/{id}` when using Stripe.
- No fintech link, no payment link configuration. See [../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md) and [../b2c_client/SUBSCRIPTION_PAYMENT_API.md](../b2c_client/SUBSCRIPTION_PAYMENT_API.md).

---

## 3. Subscription Payment — New Flow

### Customer subscription payment (B2B-administered customers)

Use the atomic flow:

1. **`POST /api/v1/subscriptions/with-payment`** — Create subscription (Pending) and payment intent. Returns `subscription_id`, `client_secret`, etc.
2. **Client shows payment UI** — Stripe Elements, redirect, or mock "Pay" button.
3. **`POST /api/v1/subscriptions/{subscription_id}/confirm-payment`** — (Mock only) Simulate success and activate. Returns full subscription.
4. **Stripe**: When using live Stripe, `confirm-payment` returns 400. Poll `GET /api/v1/subscriptions/{id}` until `subscription_status === "Active"`.

### No manual bill create/process

- Bills are created and processed automatically when payment succeeds (confirm-payment or webhook).
- Remove any UI that calls `POST /client-bills/` or `POST /client-bills/{id}/process` as part of the payment flow.
- `GET /client-bills/` and `GET /client-bills/{id}` remain for history/support views.

---

## 4. Institution Payment Attempts — Removed

**Backend status**: The `institution_payment_attempt` table and all related APIs have been **removed**. With atomic settlement → bill → payout, there is no separate payment-attempt table. Payment info is on the bill (`stripe_payout_id`, `payout_completed_at`).

### Remove from B2B app

- **Pages**
  - "Payments," "Institution payment attempts," "Payment history" (institution-supplier context).
- **API calls** (do not call; these endpoints are removed and return 404):
  - `GET /api/v1/institution-payment-attempts/`
  - `GET /api/v1/institution-payment-attempts/enriched/`
  - `GET /api/v1/institution-payment-attempts/{id}` and enriched variants.
- **Navigation**
  - Sidebar/menu entries for "Payments" or "Institution payment attempts."

### What to use instead

- **Institution bills**: `GET /api/v1/institution-bills/` and `GET /api/v1/institution-bills/enriched/` list bills with payment details (`stripe_payout_id`, `payout_completed_at`, `resolution`). Each bill row is the payment record.

---

## 5. Institution (Supplier) Payment — Pipeline Only

Institution bills and payouts are handled entirely by the backend pipeline:

- **Flow**: Settlement (per restaurant with balance) → Bill (per entity) → Tax doc → Payout (Stripe).
- **API**: `POST /api/v1/institution-bills/run-settlement-pipeline?bill_date=YYYY-MM-DD&country_code=XX`
- **Payout**: Stripe only. No bank account configuration. `stripe_payout_id` and `payout_completed_at` are stored on the bill.
- **Manual payment APIs removed**: `POST /institution-bills/{id}/mark-paid`, `POST /institution-bills/{id}/record-payment` no longer exist.

---

## Checklist for B2B Agent

### Institution payment attempts

- [ ] Remove the "Payments" (institution payment attempts) read-only page.
- [ ] Remove API calls to `/api/v1/institution-payment-attempts/` and `/api/v1/institution-payment-attempts/enriched/`.
- [ ] Remove navigation entries for "Payments" or "Institution payment attempts."
- [ ] Use `GET /api/v1/institution-bills/enriched/` for payment/bill history instead.

### Institution bank account

- [ ] Remove all "Bank accounts" or "Institution bank accounts" pages.
- [ ] Remove all bank account modals (add, edit, select).
- [ ] Remove API calls to `/api/v1/institution-bank-accounts/` and enriched variants.
- [ ] Remove `institution_bank_account_id`, `bank_account_id` from forms and types.
- [ ] Remove sidebar/navigation entries for bank accounts.

### Fintech links

- [ ] Remove all "Fintech links," "Payment links," or "Manage payment links" pages.
- [ ] Remove all fintech link modals (add, edit, assign to plan).
- [ ] Remove API calls to `/api/v1/fintech-links/`, `/api/v1/fintech-link-assignment/`.
- [ ] Remove sidebar/navigation entries for fintech links.
- [ ] Use subscription with-payment + confirm-payment for subscription payment only.

### Subscription and client bills

- [ ] Use `POST /subscriptions/with-payment` and `POST /subscriptions/{id}/confirm-payment` (or poll for Stripe).
- [ ] Remove any "Create bill" or "Process bill" UI from the normal payment flow.
- [ ] Remove calls to `POST /client-bills/` and `POST /client-bills/{id}/process` for payment completion.

---

## Related docs

- [PAYMENT_AND_BILLING_CLIENT_CHANGES](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md) — Shared migration guide (B2B + B2C)
- [SUBSCRIPTION_PAYMENT_API](../b2c_client/SUBSCRIPTION_PAYMENT_API.md) — Subscription with-payment flow (applies to B2B when managing customer subscriptions)
- [SUPPLIER_INSTITUTION_PAYMENT](../internal/SUPPLIER_INSTITUTION_PAYMENT.md) — Settlement → bill → payout pipeline (internal)
