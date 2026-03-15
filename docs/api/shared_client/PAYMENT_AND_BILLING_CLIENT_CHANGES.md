# Payment, Billing, and Fintech Link — Client Implementation Guide

**Audience**: B2B (kitchen-web) and B2C (kitchen-mobile) frontend agents and developers.  
**Purpose**: Implement backend changes for **Payment Atomic with Billing** and **Fintech Link deprecation**: remove obsolete UI and APIs; use the subscription-with-payment flow only.

---

## Summary for product/UX

| Change | What to do in the app |
|--------|------------------------|
| **Client bills** | No manual “Create bill” or “Process bill.” Bills are created and processed automatically when a payment succeeds. Remove any screens/flows that called `POST /client-bills` or `POST /client-bills/{id}/process`. |
| **Fintech links** | **Deprecated and removed.** Remove all fintech link pages, modals, and API calls. Subscription payment is done only via **subscription with-payment** (and confirm-payment). |

---

## 1. Client bills: no manual create or process

### Backend behavior (no client change required for flow)

- **Every successful payment** now creates and processes the related **client bill** in the same transaction. There is no separate “register bill” or “process bill” step.
- **Subscription payment** (first-time subscribe, renewal, or running out of credits): when payment is confirmed (`POST /subscriptions/{id}/confirm-payment` or Stripe webhook), the backend creates the bill (linked to `subscription_payment`) and processes it (credits + renewal_date, status Processed) in one go.
- **Client payment attempt** (legacy): when `PATCH /client-payment-attempts/{id}` sets status to `Completed`, the backend creates the bill (if missing) and processes it in the same request.

### What to remove in B2B and B2C

- **Remove** any UI that:
  - Creates a client bill manually (e.g. “Register bill,” “Create bill,” “Link payment to bill”).
  - Calls **`POST /api/v1/client-bills/`** (this endpoint no longer exists).
  - Calls **`POST /api/v1/client-bills/{client_bill_id}/process`** for the purpose of “processing after payment” (the manual process endpoint still exists for support/admin use only; normal flows must not depend on it).
- **Remove** any flow that:
  - After a successful payment, expects the user to “create a bill” or “process the bill” to see credits or renewal.
- **Keep** (optional):
  - **Read-only** use of client bills: `GET /api/v1/client-bills/`, `GET /api/v1/client-bills/{id}` for history or support views. Do **not** use these to drive a “create/process” workflow.

### What to keep / rely on

- **Subscription flow**: Use **`POST /api/v1/subscriptions/with-payment`** and **`POST /api/v1/subscriptions/{subscription_id}/confirm-payment`**. After confirm-payment succeeds, the subscription is active, the bill exists and is processed, and credits/renewal are updated. No extra bill step.
- **Legacy payment attempt flow**: When marking a payment completed (e.g. `PATCH /client-payment-attempts/{payment_id}` with status `Completed`), the backend creates and processes the bill. No separate “create bill” or “process bill” call from the client.

---

## 2. Fintech links: deprecated — remove all usage

### Backend status

- **Fintech link** and **fintech link assignment** (and related transaction) APIs are **deprecated** and have been **removed** or are being removed. They return **404** or are no longer available.
- Subscription payment is handled only by the **subscription-with-payment** flow (with-payment + confirm-payment or Stripe).

### What to remove in B2B and B2C

Remove **all** of the following from the apps:

- **Pages**
  - Any “Fintech links,” “Payment links,” “Link payment,” or “Manage payment links” page.
  - Any plan/subscription page that creates or edits a “fintech link” for a plan.
- **Modals / dialogs**
  - “Add fintech link,” “Edit fintech link,” “Create payment link,” “Assign fintech link to plan,” etc.
- **API calls** (do not call these; they are deprecated/removed):
  - `POST /api/v1/fintech-links/`
  - `GET /api/v1/fintech-links/`
  - `GET /api/v1/fintech-links/{id}`
  - `PUT /api/v1/fintech-links/{id}`
  - `DELETE /api/v1/fintech-links/{id}`
  - Enriched variants of the above (e.g. `GET /api/v1/fintech-links/enriched/`, etc.)
  - `POST /api/v1/fintech-link-assignment/`
  - `GET /api/v1/fintech-link-assignment/`
  - `DELETE /api/v1/fintech-link-assignment/{id}` (or by-id)
  - Any fintech-link-transaction endpoints if still present.
- **Navigation and references**
  - Sidebar/menu entries pointing to fintech link pages.
  - Buttons or links that open fintech link modals or screens.
  - References in onboarding or help text to “payment link” or “fintech link” in the old sense (replace with “pay for subscription” / subscription checkout).

### What to use instead

- **New subscription payment (B2C and B2B where applicable)**  
  - **`POST /api/v1/subscriptions/with-payment`** — creates subscription (Pending) and a payment (Stripe or mock).  
  - Client completes payment (Stripe Elements, redirect, or mock).  
  - **`POST /api/v1/subscriptions/{subscription_id}/confirm-payment`** — activates subscription and marks payment succeeded. The backend creates and processes the client bill in the same transaction.  
  - No fintech link, no separate bill create/process step.

- **Renewal / running out of credits**  
  - Same pattern: payment is created and confirmed via the subscription payment flow; the backend creates and processes the bill atomically.

---

## 3. Checklist for B2B and B2C agents

### Client bills

- [ ] Remove any “Create client bill” or “Register bill” UI and calls to `POST /client-bills/`.
- [ ] Remove any “Process bill” or “Apply payment to subscription” UI that depends on `POST /client-bills/{id}/process` as part of the normal payment flow.
- [ ] Ensure subscription checkout uses **with-payment** and **confirm-payment** only; no manual bill step.
- [ ] If you use `PATCH /client-payment-attempts/{id}` to mark payment completed, rely on the backend to create/process the bill; remove any follow-up “create/process bill” step.

### Fintech links

- [ ] Remove all fintech link **pages** (list, create, edit, by-plan, etc.).
- [ ] Remove all fintech link **modals** (add link, edit link, assign to plan, etc.).
- [ ] Remove all API calls to `/api/v1/fintech-links/`, `/api/v1/fintech-link-assignment/`, and fintech-link-transaction endpoints.
- [ ] Remove navigation and in-app references to “Fintech links,” “Payment links,” or “Manage payment links” (in the old sense).
- [ ] Use only **subscription with-payment** and **confirm-payment** for subscription payment; do not replace fintech links with another custom “link” flow.

### Optional cleanup

- [x] Stop requesting `fintech_link_provider` – fintech_link removed (Stripe/external_payment_method used).
- [ ] Update any docs or tooltips that still mention “fintech link” or “payment link” for subscriptions to say “pay for subscription” / “subscription checkout.”

---

## 4. Reference: backend plan

These client changes align with the backend plan **Payment Atomic with Billing**:

- Customer bills are **never** created in an “orphan” way; they are **always** tied to a payment (subscription_payment or client_payment_attempt).
- **POST /client-bills** (public create) has been **removed**.
- Bills are created **only** when a payment completes: (1) subscription payment (with-payment → confirm-payment or webhook), or (2) client_payment_attempt PATCH to Completed.
- Fintech link–based flows are deprecated; the subscription-with-payment flow is the only supported path for new subscription payments.

For full backend detail, see the plan document **Payment Atomic with Billing** (payment_atomic_with_billing_e9ab1d4d.plan.md).
