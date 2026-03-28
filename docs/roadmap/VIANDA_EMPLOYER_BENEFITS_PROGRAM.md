# Vianda Employer Benefits Program – Roadmap

**Status**: Roadmap (foundation in place)  
**Last Updated**: 2026-02  
**Purpose**: Enable Employer institutions to offer Vianda subscriptions as benefits and onboard their employees via a dedicated path, distinct from the standard B2C customer subscription flow.

---

## 1. Context and goals

- **Employer institutions**: Companies that participate in the benefits program get their own institution with `institution_type = 'Employer'`. The Employer user (Customer, role_name Employer) represents that company.
- **Benefits-program employees**: Employees who join through their employer are onboarded **under the employer’s institution** (same `institution_id`), so they are in scope for that institution. No need to derive “employees” via `employer_info` + `user_info.employer_id` for listing; institution-scoped APIs naturally include them.
- **Standard B2C path**: Customers who subscribe on their own (e.g. via kitchen-mobile) are assigned to the shared “Vianda Customers” institution (`institution_type = 'Customer'`) and use the normal signup/subscription flow.
- **This roadmap**: Define the **different route** for benefits-program onboarding so that new customers get the correct `institution_id` (employer’s institution) and, later, any institution-scoped behavior (e.g. subscription list, reporting) works without extra employer-specific logic.

---

## 2. What is in place (foundation)

- **`institution_type_enum`**: Extended with `'Employer'` (in addition to Employee, Customer, Supplier). Employer institutions are distinct from Supplier (restaurant) and Customer (e.g. Vianda Customers pool).
- **User–institution validation**: Customer users may be assigned to institutions with `institution_type = 'Customer'` or `'Employer'`. See `ensure_institution_type_matches_role_type` in `app/security/field_policies.py`.
- **Address types**: Customer address types (Customer Home, Customer Billing, Customer Employer) are allowed for both Customer and Employer institutions; entity/restaurant types remain Supplier or Employee only.
- **API/schemas**: `RoleType` in Python includes `EMPLOYER` for institution_type; DTOs and schemas support creating/returning institutions with `institution_type = 'Employer'`.

---

## 3. Roadmap: benefits-program onboarding (different route)

### 3.1 Problem

Today, B2C signup and B2B user creation assign customers as follows:

- **B2C**: Customer Comensal → backend assigns “Vianda Customers” institution (and does not send institution from client).
- **B2B (Employee creates user)**: Admin chooses institution; for Customer + Comensal, backend can force Vianda Customers.

There is **no dedicated path** where:

- An Employer (or an Employee on their behalf) creates/onboards a **benefits-program employee** (Customer + Comensal) and the backend sets **`institution_id` = the employer’s institution** (the one with `institution_type = 'Employer'`).

Without that, benefits employees would end up in Vianda Customers or the wrong institution, and institution-scoped features (e.g. “list subscriptions for my institution”) would not group them with the employer.

### 3.2 Intended behavior (to implement later)

- **Employer institution creation**: When a Customer with role_name Employer (or an Employee) creates an institution for a benefits-program company, set **`institution_type = 'Employer'`** (not `'Customer'`). This may be a new flow or an extension of existing institution create (e.g. when “benefits program” is selected).
- **Benefits-program registration route**: A **different route** (or same POST with a clear “benefits” context) for creating/registering a Customer user that:
  - Accepts or derives the **employer’s institution_id** (e.g. from token, query, or body when the caller is the Employer or an Employee acting for that institution).
  - Sets **`institution_id` = that employer institution** for the new user.
  - Optionally sets **`employer_id`** if the employer record is known (for reporting/UX).
  - Ensures the new user is Customer + Comensal (or the chosen role for benefits employees).
- **Authorization**: Only callers who are allowed to act for that Employer institution (Employer user, or Employee with scope over that institution) may create users in it. Enforce in the same way as other user-creation scoping.
- **No change to standard B2C path**: The existing B2C client subscription/signup flow continues to assign Vianda Customers and does not use this route.

### 3.3 Subscription list and institution scope (later)

- Once benefits employees are in the employer’s institution, **subscription list** (and other institution-scoped APIs) can treat “users in my institution” as the scope for that Employer.
- **Vianda Customers** (pool of non-benefits Comensals): keep **self-only** for subscription list (each user sees only their own).
- **Employer institutions**: when the subscription list is extended to be institution-scoped for Customer/Employer institutions, it will “just work” because all benefits employees share the same `institution_id`. No need for employer_id-based filtering in that list.

---

## 4. Implementation checklist (for later)

- [ ] **Institution create**: When creating an institution for a benefits-program company, set `institution_type = 'Employer'` (UI/flow to select “Employer” or “Benefits program”).
- [ ] **Benefits-program registration endpoint (or flow)**:
  - [ ] New route or existing POST with “benefits” context (e.g. `POST /api/v1/institutions/{institution_id}/users/` or `POST /api/v1/users/` with `institution_id` + `benefits_program=true` or equivalent).
  - [ ] Resolve employer institution (must have `institution_type = 'Employer'`); enforce caller can create users in that institution.
  - [ ] Set `institution_id` to employer’s institution for the new user; assign role Customer + Comensal (or as specified).
  - [ ] Optionally set `employer_id` if employer_info is linked to that institution.
- [ ] **Documentation**: Document the benefits-program registration contract (who can call, required parameters, `institution_id` assignment) in `docs/api/b2b_client/` or `docs/api/internal/`.
- [ ] **Subscription list (optional follow-up)**: For Customer users in institutions with `institution_type = 'Employer'`, scope GET /api/v1/subscriptions/ by institution (all users in that institution). For Vianda Customers (or `institution_type = 'Customer'`), keep self-only. Document in API docs.

---

## 5. Employer Billing — Stripe ACH for Bulk B2B Payments

Employer institutions pay in a fundamentally different pattern from B2C customers: one large payment per period covering hundreds of employees, rather than many small individual transactions. Credit card processing (2.9% + $0.30) is cost-prohibitive at this scale. Stripe ACH is the correct mechanism.

### 5.1 Why ACH, not credit cards

| Method | Fee on $10,000 | Fee on $50,000 |
|---|---|---|
| Credit card (2.9%) | $290 | $1,450 |
| ACH Direct Debit (0.8%, capped $5) | **$5** | **$5** |
| ACH Credit Transfer (flat $1) | **$1** | **$1** |

ACH also has no chargeback risk for pull payments once bank account is verified.

### 5.2 Option A — ACH Direct Debit (recommended for subscriptions)

Stripe pulls funds from the employer's bank account on a recurring schedule. Employer provides bank details once; subsequent billing cycles are automatic.

- **Stripe product:** ACH Direct Debit via Stripe Billing / Payment Intents with `payment_method_types: ['us_bank_account']`
- **Fee:** 0.8%, capped at $5.00 per transaction
- **Flow:**
  1. Employer onboarding: collect bank account via **Stripe Financial Connections** (instant verification — no micro-deposit wait)
  2. Store resulting `payment_method` ID on the employer's `Customer` object in Stripe
  3. On billing cycle: create a `PaymentIntent` or `Invoice` charged to that payment method
  4. Stripe handles mandate, retry on failure, and webhook events
- **Best for:** Recurring monthly/quarterly employer subscriptions

### 5.3 Option B — ACH Credit Transfer / Virtual Bank Account (recommended for invoicing)

Stripe provisions a **unique virtual bank account number (VBAN)** per employer. The employer "pushes" money into it via their own bank. No pull authorization needed.

- **Stripe product:** `payment_method_types: ['customer_balance']` with `funding_type: 'bank_transfer'` → Stripe generates the VBAN
- **Fee:** Flat $1 per transfer
- **Flow:**
  1. Create a Stripe `Customer` for the employer
  2. Generate a `PaymentIntent` with bank transfer; Stripe returns the VBAN in the response
  3. Send employer an invoice (via Stripe Invoicing or our own) with the VBAN as the payment destination
  4. When employer initiates the bank transfer, Stripe reconciles automatically and sends a webhook
- **Best for:** One-time or irregular large invoices, employers who prefer to initiate payments themselves

### 5.4 Bank account verification

Use **Stripe Financial Connections** for instant bank account verification instead of micro-deposits. This:
- Eliminates the 1–3 day verification wait
- Reduces fraud risk on high-value ACH pulls
- Is required before charging amounts above Stripe's unverified ACH limit

```python
# Create a Financial Connections session during employer onboarding
stripe.financial_connections.Session.create(
    account_holder={"type": "customer", "customer": employer_stripe_customer_id},
    permissions=["payment_method"],
)
```

### 5.5 Large payment notes

- Transactions of $10k–$50k+ work without special configuration after the account is verified
- For transactions approaching $1M+, contact Stripe support in advance to confirm limits
- Stripe ACH settlement is T+2 business days (vs. credit card T+2 as well, but ACH has no interchange fees)
- Failed ACH pulls generate a `payment_intent.payment_failed` webhook — implement retry logic or notify the employer

### 5.6 Implementation checklist (add to Section 4)

- [ ] **Stripe Customer per Employer institution**: Create a `stripe_customer_id` on `employer_info` (or `institution_info`) at onboarding time
- [ ] **Bank account collection flow**: Integrate Stripe Financial Connections in the Employer onboarding UI; store verified `payment_method` ID
- [ ] **Billing trigger**: On employer billing cycle, create Stripe Invoice or PaymentIntent against the stored ACH payment method
- [ ] **Webhook handling**: Handle `payment_intent.succeeded`, `payment_intent.payment_failed`, `invoice.paid`, `invoice.payment_failed` in `app/routes/webhooks.py`
- [ ] **Store payment method**: `employer_info` (or a linked `employer_payment_method` table) needs `stripe_customer_id` and `stripe_payment_method_id` columns
- [ ] **Fee modeling**: Calculate billing amounts assuming $5 ACH cap — factor into employer pricing

### 5.7 References
- Stripe ACH Direct Debit: https://stripe.com/docs/payments/ach-direct-debit
- Stripe Bank Transfers (VBAN/ACH Credit): https://stripe.com/docs/payments/bank-transfers
- Stripe Financial Connections: https://stripe.com/docs/financial-connections
- Existing Stripe integration: `app/services/payment_provider/stripe/live.py`, `app/routes/webhooks.py`
- Stripe roadmap: `docs/roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md`

---

## 6. References

- **Institution type and roles**: `app/config/enums/role_types.py` (RoleType.EMPLOYER), `app/security/field_policies.py` (ensure_institution_type_matches_role_type, ensure_address_type_matches_institution_type).
- **Customer Comensal institution assignment**: `docs/api/b2b_client/feedback_from_client/CUSTOMER_COMENSAL_INSTITUTION.md`.
- **B2C deployment and flows**: [B2C_DEPLOYMENT_ROADMAP.md](../zArchive/roadmap/B2C_DEPLOYMENT_ROADMAP.md) *(archived; deployment tracked in repo and Pulumi)*.
- **User–market and scoping**: [USER_MARKET_ASSIGNMENT_DESIGN.md](USER_MARKET_ASSIGNMENT_DESIGN.md).
