# Vianda Employer Benefits Program – Roadmap

**Status**: Roadmap (foundation in place)
**Last Updated**: 2026-04
**Purpose**: Enable Employer institutions to offer Vianda meal subscriptions as a workplace benefit — fully or partially subsidized — with scalable employee onboarding, flexible subsidy configuration, and aggregated employer billing.

---

## 1. Context and goals

### 1.1 What this program is

Enterprise customers ("Employers") sign a deal with Vianda to provide meal subscriptions to their employees as a workplace benefit. The employer may cover the full cost (100% subsidized) or a percentage of it up to a dollar cap, with the employee paying the remainder out of pocket. Employees always choose their own plan — the employer controls *how much* they subsidize, not *which plan* the employee picks.

### 1.2 Terminology

| Term | Definition |
|---|---|
| **Employer** | An institution with `institution_type = 'Employer'`. Has its own users with `role_type = 'Employer'` (Admin, Manager) who manage the program. |
| **Benefit employee** | A Customer (Comensal) user assigned to the Employer's institution. They order food like any B2C customer but their subscription is partially or fully covered by the employer. |
| **Benefit rate** (`benefit_rate`) | Percentage (0–100) of the plan price that the employer covers for the employee. This is what the employee sees. |
| **Benefit cap** (`benefit_cap`) | Maximum absolute amount the employer subsidizes per employee, governed by `benefit_cap_period` (per renewal or per month). |
| **Price discount** (`price_discount`) | Percentage (0–100) discount Vianda gives the employer on their aggregated bill. This is a B2B deal term — invisible to employees. |
| **Internal** | Vianda staff. Global access. Manages employer onboarding and deal configuration. (Previously called "Employee" in earlier docs — renamed to avoid confusion with Employer role type.) |

### 1.3 Design principles

1. **Reuse existing primitives**: Subscriptions, plans, institution scoping, and Stripe payment methods already exist. The benefits program layers subsidy logic on top rather than creating parallel systems.
2. **Dedicated program table**: Benefits-program configuration lives in its own `employer_benefits_program` table (keyed by `institution_id`), not on `institution_info`. This keeps the institution table general-purpose and avoids leaking program details into unrelated queries.
3. **Accommodate both models from day one**: The data model supports 0–100% subsidy with an optional cap. Starting with fully subsidized is simpler to implement but does not require schema changes when partial subsidy is enabled.
4. **Free plan choice, capped subsidy**: Employees pick any available plan in their market. The employer sets a subsidy rate and cap — not a specific plan. This gives employees flexibility while giving employers cost control.
5. **employer_info is B2C-only**: The existing `employer_info` table is a B2C company directory — Comensals use it to find their workplace and coworkers. Benefits-program configuration must never go on `employer_info`, because that data is exposed to all B2C customers. The program table is institution-scoped and only visible to Employer Admins and Internal.

---

## 2. What is in place (foundation)

- **`institution_type_enum`**: Includes `'Employer'` alongside Internal, Customer, Supplier.
- **`role_type_enum`**: Includes `'Employer'` for users who manage employer institutions (Admin, Manager roles).
- **User–institution validation**: Customer users may be assigned to institutions with `institution_type = 'Customer'` or `'Employer'`. See `ensure_institution_type_matches_role_type` in `app/security/field_policies.py`.
- **Address types**: Customer address types (Customer Home, Customer Billing, Customer Employer) are allowed for both Customer and Employer institutions.
- **Institution scoping**: Employer institutions are scoped like Supplier institutions — Employer Admins see only users/data within their `institution_id`.
- **employer_info table**: B2C-facing company directory with `name`, `address_id`. Used by Comensals to mark where they work and find coworkers. **Not** the same as the Employer institution and must not be extended with program config.
- **B2B user creation**: Internal users can already create Employer-type users via `POST /users` with `role_type = 'Employer'`.

---

## 3. Subsidy model

### 3.1 Core concept — benefit rate + cap + price discount

The employer's program is defined by three independent levers on `employer_benefits_program`:

**Employee-facing (what the employee sees):**
- **`benefit_rate`** (INTEGER, 0–100): Percentage of the plan price the employer covers for the employee.
- **`benefit_cap`** (NUMERIC, nullable): Maximum absolute amount the employer subsidizes per employee. NULL = no cap (rate alone governs).
- **`benefit_cap_period`** (ENUM: `per_renewal` | `monthly`): Whether the cap resets each time the employee renews, or is a monthly budget that spans multiple renewals.

**Employer-facing (what the employer pays Vianda):**
- **`price_discount`** (INTEGER, 0–100, default 0): Negotiated discount Vianda gives the employer on their aggregated bill. This is a B2B deal term — employees never see it.

The computation per subscription renewal:

```
plan_price       = plan.price                              (e.g., $90)
rate_amount      = plan_price × (benefit_rate / 100)       (e.g., 100% → $90)
remaining_cap    = benefit_cap - already_used_this_period   (if cap_period = monthly)
                 = benefit_cap                              (if cap_period = per_renewal)
employee_benefit = MIN(rate_amount, remaining_cap)          (e.g., MIN($90, $45) → $45)
employee_share   = plan_price - employee_benefit            (e.g., $90 - $45 → $45)

-- what employer actually pays Vianda (computed at billing time, not at renewal):
employer_cost    = employee_benefit × (1 - price_discount / 100)
                                                            (e.g., $45 × 0.90 → $40.50 if 10% discount)
```

### 3.2 Cap period — per-renewal vs. monthly

Employees who consume all their credits before the end of the month can renew more than once. The cap period controls how the employer's exposure scales with frequent renewers:

| cap_period | Behavior | Example ($45 cap, 100% rate, $45 plan) |
|---|---|---|
| `per_renewal` | Cap resets each renewal. Employer pays up to $45 every time the employee renews. | Employee renews 3× in a month → employer pays $135 for that employee. |
| `monthly` | Cap is a monthly budget. Once exhausted, further renewals in the same calendar month are fully employee-paid. | Employee renews 3× in a month → employer pays $45 total; employee pays $90 for renewals 2 and 3. |

**Recommendation**: Default to `monthly` for new deals — it gives employers cost predictability. `per_renewal` is available for employers who explicitly want to subsidize heavy users.

### 3.3 How the three levers combine

| Deal | benefit_rate | benefit_cap / period | price_discount | Effect |
|---|---|---|---|---|
| Fully subsidized, no cap | 100 | NULL | 0 | Employer pays 100% of any plan, any number of renewals. |
| Fully subsidized, monthly cap | 100 | $45 / monthly | 0 | Employer covers up to $45/month. Basic plan ($45) fully covered; premium plan or extra renewals → employee pays the excess. |
| Fully subsidized, capped, discounted | 100 | $45 / monthly | 10 | Same as above, but employer pays Vianda $40.50/employee instead of $45. |
| Partial subsidy, no cap | 70 | NULL | 0 | Employer pays 70% of any plan per renewal. Employee pays 30%. |
| Partial subsidy, monthly cap | 70 | $60 / monthly | 5 | Employer pays 70% up to $60/month. On a $100 plan → $70 per renewal but capped at $60 monthly budget. Employer pays Vianda $57/employee (5% off). |
| Enrollment-only | 0 | NULL | 0 | Employer manages enrollment but pays nothing. Employee pays full price. |

The **recommended default for new employer deals** is `benefit_rate = 100, benefit_cap = {price of the cheapest plan in the employer's market}, benefit_cap_period = monthly, price_discount = 0`. This covers the basic plan fully once per month and lets employees upgrade or renew more frequently at their own cost.

### 3.4 Why rate + cap instead of a default plan

Tying subsidies to a specific plan creates coupling problems:
- If the plan is discontinued or repriced, the subsidy config breaks.
- Employees who want a different plan need a separate flow.
- The employer must understand Vianda's plan catalog to configure their program.

Rate + cap is plan-agnostic. The employer says "we cover up to $X per employee per month" (a business decision they already understand), and employees choose freely. The cheapest plan happens to be fully covered; anything above it is the employee's choice and cost.

### 3.5 Why a dedicated table, not institution_info

`institution_info` is a general-purpose table shared across all institution types. Benefits-program fields (subsidy_rate, subsidy_cap, enrollment_mode, billing_day, minimum_monthly_fee) are Employer-specific and would be NULL for all other institution types — classic table-per-type smell.

A dedicated `employer_benefits_program` table:
- Keeps `institution_info` clean and general-purpose (only 11 columns today).
- Makes it impossible for non-Employer institutions to accidentally have subsidy config.
- Groups all program config in one place for Employer Admin and Internal queries.
- Can be extended (enrollment mode, billing config, domain settings) without widening a shared table.

**Note on `no_show_discount`**: This Supplier-specific column already lives on `institution_info`. It could be moved to a `supplier_program_config` table for symmetry, but the institution table is still small and `no_show_discount` is a single column — not worth the migration today. If more Supplier-specific config accumulates, consider splitting it out then.

---

## 4. Employee onboarding

### 4.1 The shared invariant

Regardless of onboarding method, the end result is the same: a `user_info` row with:
- `role_type = 'Customer'`, `role_name = 'Comensal'`
- `institution_id = {employer's institution}`
- `employer_id = {employer_info record}` (for B2C coworker features / reporting)

The onboarding method determines *how* that user row is created. All methods funnel into the same `create_benefit_employee` service function.

### 4.2 Enrollment mode — employer chooses one

When an employer signs up for the benefits program, they choose an **enrollment mode**. This is a program-level setting, not a per-employee toggle. The two modes are:

#### Mode A — Managed enrollment (manual + CSV)

The employer controls exactly who has access. Employees cannot self-register into the program.

- **Single registration**: Employer Admin calls `POST /api/v1/employer/employees` with employee email, name, and optionally mobile number. Backend creates a Customer Comensal user in the employer's institution and sends an invitation email with a password-set link.
- **Bulk CSV upload**: Employer Admin uploads a CSV via `POST /api/v1/employer/employees/bulk`. Backend validates emails (format, no duplicates in system), creates users in batch, queues invitation emails. Returns a result summary — created count, skipped (already exists), failed (invalid email). Does not fail the entire batch on one bad row.
- **CSV format**: `email,first_name,last_name` (minimal). Optional columns ignored.
- **Authorization**: Employer Admin or Manager (scoped to their institution). Internal can also do this.
- **Deprovisioning**: Employer Admin deactivates employees manually via `DELETE /api/v1/employer/employees/{user_id}`.

**Best for**: Companies that want tight control over who gets the benefit — HR-driven enrollment, specific departments, unionized environments where benefit eligibility is contractual.

#### Mode B — Domain-gated self-registration

Anyone with a matching corporate email can self-enroll. The employer's email domain(s) are the gate.

- **Flow**:
  1. Employer Admin configures allowed email domains (e.g., `acme.com`, `acme.co.uk`) via `POST /api/v1/employer/domains`.
  2. Employee signs up through the standard B2C flow using their corporate email.
  3. Backend detects the email domain matches an active Employer institution. Instead of assigning to "Vianda Customers", assigns to the employer's institution.
  4. Employee completes standard email verification. Benefit applies automatically.
- **Domain management**: `employer_domain` rows on the `employer_benefits_program` table or a related table. Unique constraint on domain (one employer per domain).
- **Safeguard**: Maintain a `domain_blacklist` (gmail.com, outlook.com, yahoo.com, hotmail.com, etc.) that cannot be registered as employer domains.
- **Deprovisioning**: Manual — Employer Admin removes the employee, or removes the domain to stop new enrollments.

**Best for**: Companies that want frictionless, company-wide rollout — "everyone at acme.com gets the benefit" with zero HR overhead.

### 4.3 Recommendation: implement both, employer picks one

Both modes share the same backend invariant (Section 4.1) and the same `create_benefit_employee` function. The difference is *who calls it*:
- Mode A: Employer Admin calls it explicitly (single or batch).
- Mode B: The B2C signup flow calls it when the email domain matches.

**Implementation order:**
1. **Phase 1**: Mode A (managed enrollment) — straightforward CRUD, no changes to B2C signup.
2. **Phase 2**: Mode B (domain-gated) — requires modifying the B2C signup flow to check domains, plus domain management endpoints.

The `enrollment_mode` field on `employer_benefits_program` (`managed` or `domain_gated`) determines which path is active. If `managed`, the B2C signup flow ignores domain matching for that employer. If `domain_gated`, Employer Admin can still manually add employees but domain self-registration is the primary channel.

### 4.4 SSO / Open Directory (Phase 3 — future)

Employer manages access through their identity provider (Okta, Azure AD, Google Workspace).

- Employee clicks "Sign in with SSO" on the Vianda app and authenticates through their employer's IdP.
- On first login, backend JIT-provisions a Customer Comensal user in the employer's institution.
- **Deprovisioning**: When employer removes the employee from their IdP group/app, a SCIM webhook (or periodic sync) archives the user in Vianda.
- **Gating is managed by the employer on their IdP** — Vianda does not need to maintain a whitelist; the SSO configuration *is* the whitelist.

This is a natural evolution of domain-gated mode: instead of matching by email domain, match by IdP assertion. The enrollment mode would become `sso`, and domain-gated logic would be replaced by SAML/OIDC.

**Recommendation**: Roadmap for Phase 3. Domain-gated delivers 80% of the frictionless-enrollment value with 20% of the implementation effort. SSO is justified only at enterprise scale (500+ employees).

### 4.5 Enrollment mode comparison

| Criterion | Managed (manual + CSV) | Domain-gated | SSO/OIDC |
|---|---|---|---|
| Implementation effort | Low | Medium | High |
| Employer admin effort per employee | High (single) / Low (batch) | None | None |
| Ongoing maintenance | Manual | Automatic | Automatic |
| Deprovisioning | Manual | Manual | Automatic (SCIM) |
| Employer control | Full (whitelist) | Partial (domain = gate) | Full (IdP = gate) |
| Best for | HR-driven, < 500 employees | Company-wide, 50–5000 | Enterprise, 500+ |
| Phase | 1 | 2 | 3 |

---

## 5. Employer billing and payment aggregation

### 5.1 Billing model — aggregated invoice with price discount

The employer does not pay per-transaction like B2C customers. Instead, Vianda computes an aggregated bill of the employer's share across all benefit-employee subscription events within the billing period, applies the negotiated `price_discount`, and bills the employer once.

```
gross_employer_share  = Σ employee_benefit(subscription_event) for each renewal in the period
employer_bill_amount  = gross_employer_share × (1 - price_discount / 100)
final_billed          = MAX(employer_bill_amount, minimum_monthly_fee)
```

Where `employee_benefit(subscription_event)` uses the rate + cap formula from Section 3.1, and `price_discount` is the negotiated B2B discount (invisible to employees).

### 5.2 Billing cycle

The billing cycle determines how frequently the employer is invoiced. Stored as `billing_cycle` (ENUM) on `employer_benefits_program`:

| Cycle | Behavior | Best for |
|---|---|---|
| `daily` | Bill generated the day after each subscription renewal event. One bill per day (if there were renewals). | Small employers or trials where Vianda wants fast payment. |
| `weekly` | Bill generated weekly (configurable day of week via `billing_day_of_week`). Aggregates all renewals from the prior 7 days. | Medium employers preferring frequent reconciliation. |
| `monthly` | Bill generated monthly (configurable day of month via `billing_day`, 1–28). Aggregates all renewals from the prior calendar month. | Default. Most enterprises expect monthly invoicing aligned with their AP cycle. |

**Recommendation**: Default to `monthly`. Offer `daily` and `weekly` as options during deal negotiation. The billing engine is the same regardless — it queries renewal events within the period window and aggregates.

**Note**: `benefit_cap_period = monthly` always uses calendar months regardless of billing cycle. An employer billed weekly still has their benefit cap tracked on a monthly basis.

### 5.3 Minimum monthly fee

To discourage employers from signing up without committing to meaningful usage, the contract can include a **minimum monthly fee**. This is a floor applied at the monthly level:

- If the employer's total billed amount for the calendar month `>= minimum_fee`: minimum is irrelevant.
- If below: employer pays `minimum_fee` instead.
- For daily/weekly billing cycles, the minimum fee is reconciled at month-end — a separate "minimum fee adjustment" line item is added to the final bill of the month if cumulative charges fall short.

**Data model**: `minimum_monthly_fee NUMERIC NULL` on `employer_benefits_program` (NULL = no minimum).

**Example scenarios (monthly billing, 100% benefit_rate, $45 monthly cap, 10% price_discount):**

| Employees | Plan | Gross employer share | After 10% discount | Minimum fee | Billed |
|---|---|---|---|---|---|
| 50 | $45 | $2,250 | $2,025 | $500 | $2,025 |
| 5 | $45 | $225 | $202.50 | $500 | **$500** (minimum) |
| 30 | $90 (cap applies) | $1,350 | $1,215 | $500 | $1,215 |
| 0 | — | $0 | $0 | $500 | **$500** (minimum) |

This structure naturally encourages employers to actively enroll employees — the minimum fee is wasted money if employees are not using the service.

### 5.4 Billing cycle and invoice generation

1. **Cron job** runs at the cadence matching `billing_cycle` (daily, weekly on `billing_day_of_week`, or monthly on `billing_day`).
2. Queries all subscription renewal events in the employer's institution within the billing period.
3. Computes `employee_benefit` per event using rate + cap (respecting `benefit_cap_period`).
4. Sums to `gross_employer_share`.
5. Applies `price_discount`.
6. For the last bill of the calendar month: applies `minimum_monthly_fee` floor if cumulative charges are below it.
7. Creates an `employer_bill` record with line items.
8. Triggers payment via the employer's stored payment method (ACH — see Section 6).

### 5.5 Employer bill data model

New table `billing.employer_bill`:

| Column | Type | Description |
|---|---|---|
| `employer_bill_id` | UUID PK | |
| `institution_id` | UUID FK | Employer institution |
| `billing_period_start` | DATE | First day of billing period |
| `billing_period_end` | DATE | Last day of billing period |
| `billing_cycle` | VARCHAR | `daily`, `weekly`, or `monthly` (snapshot) |
| `total_renewal_events` | INTEGER | Count of subscription renewals in period |
| `gross_employer_share` | NUMERIC | Sum of employee_benefit across all line items (before discount) |
| `price_discount` | INTEGER | Discount rate at billing time (snapshot) |
| `discounted_amount` | NUMERIC | gross_employer_share × (1 - price_discount / 100) |
| `minimum_fee_applied` | BOOLEAN | Whether the minimum fee was used instead |
| `billed_amount` | NUMERIC | Final billed amount (after discount, after minimum fee floor) |
| `currency_code` | VARCHAR | Billing currency (from market) |
| `stripe_invoice_id` | VARCHAR NULL | Stripe Invoice ID once created |
| `payment_status` | ENUM | Pending, Paid, Failed, Overdue |
| `paid_date` | TIMESTAMPTZ NULL | |

Line items in `billing.employer_bill_line` — one row per subscription renewal event:

| Column | Type | Description |
|---|---|---|
| `line_id` | UUID PK | |
| `employer_bill_id` | UUID FK | |
| `subscription_id` | UUID FK | |
| `user_id` | UUID FK | Benefit employee |
| `plan_id` | UUID FK | |
| `plan_price` | NUMERIC | Plan price at renewal time (snapshot) |
| `benefit_rate` | INTEGER | Rate at renewal time (snapshot) |
| `benefit_cap` | NUMERIC NULL | Cap at renewal time (snapshot) |
| `benefit_cap_period` | VARCHAR NULL | `per_renewal` or `monthly` (snapshot) |
| `employee_benefit` | NUMERIC | Employer's contribution for this renewal (after rate + cap) |
| `renewal_date` | TIMESTAMPTZ | When this renewal occurred |

Snapshotting all program parameters on the line item ensures historical accuracy even if rates, caps, or discounts change between billing periods. The `price_discount` is applied at the bill level (not per line item) since it's a B2B deal term, not a per-employee calculation.

---

## 6. Employer payment — Stripe ACH

Employer institutions pay in a fundamentally different pattern from B2C customers: one large payment per period covering many employees, rather than many small individual transactions. Credit card processing (2.9% + $0.30) is cost-prohibitive at this scale. Stripe ACH is the correct mechanism.

### 6.1 Why ACH, not credit cards

| Method | Fee on $10,000 | Fee on $50,000 |
|---|---|---|
| Credit card (2.9%) | $290 | $1,450 |
| ACH Direct Debit (0.8%, capped $5) | **$5** | **$5** |
| ACH Credit Transfer (flat $1) | **$1** | **$1** |

ACH also has no chargeback risk for pull payments once bank account is verified.

### 6.2 Option A — ACH Direct Debit (recommended for subscriptions)

Stripe pulls funds from the employer's bank account on a recurring schedule. Employer provides bank details once; subsequent billing cycles are automatic.

- **Stripe product:** ACH Direct Debit via Stripe Billing / Payment Intents with `payment_method_types: ['us_bank_account']`
- **Fee:** 0.8%, capped at $5.00 per transaction
- **Flow:**
  1. Employer onboarding: collect bank account via **Stripe Financial Connections** (instant verification — no micro-deposit wait)
  2. Store resulting `payment_method` ID on the employer's `Customer` object in Stripe
  3. On billing cycle: create a `PaymentIntent` or `Invoice` charged to that payment method
  4. Stripe handles mandate, retry on failure, and webhook events
- **Best for:** Recurring monthly employer billing

### 6.3 Option B — ACH Credit Transfer / Virtual Bank Account (for invoicing)

Stripe provisions a **unique virtual bank account number (VBAN)** per employer. The employer "pushes" money into it via their own bank. No pull authorization needed.

- **Stripe product:** `payment_method_types: ['customer_balance']` with `funding_type: 'bank_transfer'` → Stripe generates the VBAN
- **Fee:** Flat $1 per transfer
- **Flow:**
  1. Create a Stripe `Customer` for the employer
  2. Generate a `PaymentIntent` with bank transfer; Stripe returns the VBAN in the response
  3. Send employer an invoice with the VBAN as the payment destination
  4. When employer initiates the bank transfer, Stripe reconciles automatically and sends a webhook
- **Best for:** Employers who prefer to initiate payments themselves or have accounts payable processes that require employer-initiated transfers

### 6.4 Bank account verification

Use **Stripe Financial Connections** for instant bank account verification instead of micro-deposits. This:
- Eliminates the 1–3 day verification wait
- Reduces fraud risk on high-value ACH pulls
- Is required before charging amounts above Stripe's unverified ACH limit

### 6.5 Non-US markets (LATAM)

For markets outside the US (Argentina, Peru, etc.), ACH is not available. Options per market:

- **Argentina**: Bank transfer (CBU/CVU) via local payment processor or manual reconciliation. Mercado Pago for medium-scale.
- **Peru**: Bank transfer (CCI) or local processors.
- **General**: The billing model (aggregated monthly invoice) is payment-method-agnostic. The `employer_bill` record is created regardless of how payment is collected. Payment method integration is pluggable per market.

Store `payment_method_type` on `employer_benefits_program` to indicate which payment flow applies (ACH, bank transfer, etc.).

---

## 7. Subscription renewal control (all Customer Comensals) ✅ IMPLEMENTED

This feature applies to **all Customer Comensals**, not just benefit employees. It is a prerequisite for the benefits program because benefit employees with monthly caps need to control when renewals happen — but the feature is generally useful for any subscriber who wants budget control.

### 7.1 How subscriptions renew

A subscription always auto-renews at the 30-day mark (period end) via the cron job. There is no "don't renew" setting — users who want to stop renewing use **cancel** (permanent) or **on hold** (temporary), which already exist.

The only user control is over **early renewal** — whether the system renews mid-period when credits run low.

### 7.2 early_renewal_threshold column

Single column on `subscription_info`: `early_renewal_threshold INTEGER DEFAULT 10`.

| early_renewal_threshold | Behavior |
|---|---|
| 10 (default) | **Current behavior** — renews at period end AND when balance drops below 10 at order time. |
| NULL | **Period-end only** — renews only at the 30-day mark. Never renews early. User uses remaining credits until period ends. |
| Custom (e.g. 5) | **Custom threshold** — renews early when balance drops below 5. Less aggressive than default. |

### 7.3 How this interacts with the benefits program

For benefit employees, renewal control is critical because of the monthly cap:

**Scenario without renewal control** (previous behavior):
- Employer sets `benefit_cap = $45/month`, `benefit_cap_period = monthly`.
- Employee has a $45 plan. Employer covers the first renewal fully.
- Employee uses credits quickly, balance drops below 10 mid-month.
- System triggers early renewal. Monthly cap is already exhausted → employee is charged $45 out of pocket.

**Scenario with renewal control**:
- Same setup, but the employee's subscription has `early_renewal_threshold = NULL` (period-end only).
- Employee uses credits quickly, balance drops to 0. No early renewal triggers.
- Employee waits until `renewal_date` passes for the next renewal.
- Next month, employer's cap resets and covers the renewal again.

**Recommended defaults for benefit employees**: When a benefit employee is enrolled, the system should set `early_renewal_threshold = NULL` (period-end only) — unless the employer's program explicitly opts into allowing early renewals via `allow_early_renewal BOOLEAN DEFAULT FALSE` on `employer_benefits_program`.

### 7.4 User-facing controls

**B2C app (subscription settings):**
- "When should your plan renew?"
  - "When my credits run low" (configurable threshold, default 10)
  - "Only at the end of the billing period" (sets `early_renewal_threshold = NULL`)
- For benefit employees: contextual hint: "Your employer covers one renewal per month. Renewing early may result in charges to your payment method."

**B2B platform (employer program config):**
- Toggle: "Allow early renewal for benefit employees" → maps to `allow_early_renewal` on `employer_benefits_program`.

### 7.5 Implementation status

- [x] `early_renewal_threshold INTEGER DEFAULT 10` added to `subscription_info` and `audit.subscription_history`
- [x] History trigger updated to include new column
- [x] SubscriptionDTO, SubscriptionResponseSchema, SubscriptionEnrichedResponseSchema updated
- [x] Enriched SQL queries updated with new column
- [x] `app/services/vianda_selection_service.py` uses per-subscription threshold (NULL = skip early renewal)
- [x] `PATCH /api/v1/subscriptions/me/renewal-preferences` — Customer endpoint to update threshold
- [x] `RenewalPreferencesSchema` in `app/schemas/subscription.py`
- [ ] `allow_early_renewal BOOLEAN DEFAULT FALSE` on `employer_benefits_program` (Phase 1 of benefits program)
- [ ] Enrollment service sets `early_renewal_threshold = NULL` for benefit employees when `allow_early_renewal = FALSE`

---

## 8. Subscription flow for benefit employees

### 8.1 Fully subsidized (employee_share = $0)

This applies when `benefit_rate = 100` and the plan price is within the remaining cap (or no cap is set).

1. Benefit employee is onboarded (any enrollment mode from Section 4). Subscription is created with `early_renewal_threshold = NULL` by default (period-end only — see Section 7.3).
2. Employee opens the app, sees all available plans in their market.
3. Employee picks a plan. Backend computes `employee_benefit` using rate + cap (Section 3.1). If `employee_share = $0`, subscription activates immediately — no payment step.
4. Employer's next bill includes this renewal event as a line item.

### 8.2 Partially subsidized (employee_share > $0)

This applies when `benefit_rate < 100`, or the plan price exceeds the remaining cap, or the monthly cap is already exhausted from prior renewals.

1. Benefit employee is onboarded. Subscription defaults to period-end-only renewal.
2. Employee opens the app, sees plans with price breakdown: total price, "Your employer covers $X", employee pays $Y. If `benefit_cap_period = monthly` and the employee has already renewed this month, the app shows the remaining cap budget.
3. Employee must have a saved payment method (standard B2C Stripe flow).
4. Employee confirms subscription. Backend charges `employee_share` to the employee's card.
5. On success, subscription activates. Employer's next bill includes `employee_benefit` as a line item.
6. **On subsequent renewals**: Same computation. If monthly cap is partially or fully consumed, the employee's share increases accordingly.

### 8.3 Multi-renewal scenario (monthly cap)

When `benefit_cap_period = monthly` and an employee has `early_renewal_threshold` set (i.e., the employer's program has `allow_early_renewal = TRUE` and the employee opted in):

| Renewal | Plan price | Remaining monthly cap | employee_benefit | employee_share |
|---|---|---|---|---|
| 1st (month start) | $45 | $45 of $45 | $45 | $0 |
| 2nd (mid-month) | $45 | $0 of $45 | $0 | $45 |
| 3rd (late month) | $45 | $0 of $45 | $0 | $45 |

The employee is informed upfront: "Your employer benefit for this month has been used. This renewal will be charged to you."

**Default behavior** (when `allow_early_renewal = FALSE`): the employee's subscription has `early_renewal_threshold = NULL`, so early renewal never triggers. The employee uses their credits until the period ends, then the next renewal is covered by the employer's cap which has reset. This prevents unexpected charges.

### 8.4 What each actor sees

| View | Information |
|---|---|
| **Employee (app)** | Plan name, total price, "Your employer covers $X", their portion, remaining monthly cap budget (if applicable), renewal preference (period-end vs. early), payment method (if partial). Cannot see other employees' subscriptions, price_discount, or program config. |
| **Employer Admin (B2B)** | Program config (benefit_rate, benefit_cap, enrollment mode, allow_early_renewal), list of all benefit employees, their subscription status, aggregate cost (before and after price_discount), billing history. Cannot see individual employee payment methods. |
| **Internal (B2B)** | Everything. Full visibility for support and operations. |

---

## 9. Phased implementation plan

### Phase 1 — Foundation (renewal control + managed enrollment + full subsidy + monthly billing)

**Goal**: Ship subscription renewal control (platform-wide) and the simplest end-to-end employer benefits flow: one employer, fully subsidized, managed enrollment, monthly billing.

**Subscription renewal control (platform-wide, prerequisite) — ✅ DONE:**
- [x] Add `early_renewal_threshold INTEGER DEFAULT 10` to `subscription_info` and `audit.subscription_history`
- [x] Add column to history trigger
- [x] Update vianda selection (`app/services/vianda_selection_service.py`): use per-subscription threshold; skip early renewal when NULL
- [x] Add `PATCH /api/v1/subscriptions/me/renewal-preferences` — user updates `early_renewal_threshold`
- [x] Include `early_renewal_threshold` in subscription response schemas
- Note: Cron job unchanged — always renews at 30-day mark. No `auto_renew` column; cancel/hold cover "don't renew".

**Benefits program schema — ✅ DONE:**
- [x] Create `employer_benefits_program` table with all columns (see Section 10)
- [x] Create `billing.employer_bill` and `billing.employer_bill_line` tables
- [x] Audit tables + history triggers for both
- [x] 4 new PostgreSQL ENUMs: `benefit_cap_period_enum`, `enrollment_mode_enum`, `billing_cycle_enum`, `employer_bill_payment_status_enum`

**Endpoints — ✅ DONE:**
- [x] `POST /api/v1/employer/program` — Internal creates/configures a benefits program
- [x] `GET /api/v1/employer/program` — Employer Admin views their program config
- [x] `PUT /api/v1/employer/program` — Internal updates program config
- [x] `POST /api/v1/employer/employees` — Employer Admin registers a single benefit employee
- [x] `POST /api/v1/employer/employees/bulk` — Employer Admin uploads CSV of employees
- [x] `GET /api/v1/employer/employees` — Employer Admin lists benefit employees (with subscription status)
- [x] `DELETE /api/v1/employer/employees/{user_id}` — Employer Admin deactivates a benefit employee
- [x] `POST /api/v1/employer/employees/{user_id}/subscribe` — Subscribe employee (no payment for 100% subsidy)
- [x] `GET /api/v1/employer/billing` — Employer Admin views billing history
- [x] `GET /api/v1/employer/billing/{bill_id}` — Employer Admin views a single bill with line items
- [x] `POST /api/v1/employer/billing/generate` — Internal manual trigger to generate a bill

**Services — ✅ DONE:**
- [x] `app/services/employer/program_service.py` — program CRUD, configuration
- [x] `app/services/employer/enrollment_service.py` — create/deactivate benefit employees (single + batch), subscribe with no payment
- [x] `app/services/employer/billing_service.py` — compute aggregate, apply price_discount, apply minimum fee, benefit calculator

**Subscription flow — ✅ DONE:**
- [x] `POST /employer/employees/{user_id}/subscribe` — computes employee_share via benefit calculator; if $0, activates immediately with no Stripe
- [x] Sets `early_renewal_threshold = NULL` when `allow_early_renewal = FALSE`
- [x] Monthly cap usage tracked via benefit calculator (already_used_this_month param)

**Billing — ✅ DONE:**
- [x] Manual trigger (Internal) `POST /employer/billing/generate` generates bill for a period
- [x] Bill stores line items with snapshotted rates, price_discount at bill level
- [x] Payment collection is manual until ACH is wired (Phase 2)

### Phase 2 — Partial subsidy + domain-gated enrollment + automated billing

**Goal**: Enable the partial-subsidy model, domain-gated self-registration, daily/weekly billing, and automated payment.

**Schema changes:**
- [ ] Create `employer_domain` table
- [ ] Maintain `domain_blacklist` table or config for common email providers

**Partial subsidy:**
- [ ] Extend subscription creation: when `employee_share > 0`, compute and charge employee's payment method
- [ ] Show `employee_benefit` and `employee_share` breakdown in the app, including remaining monthly cap budget
- [ ] On renewal, charge employee for their share; record employer's employee_benefit for next aggregate bill

**Domain-gated enrollment:**
- [ ] `POST /api/v1/employer/domains` — Employer Admin configures allowed domains
- [ ] `GET /api/v1/employer/domains` — List configured domains
- [ ] `DELETE /api/v1/employer/domains/{domain_id}` — Remove a domain
- [ ] Modify B2C signup flow: after email verification, check if email domain matches an active employer domain. If yes, assign to employer's institution instead of Vianda Customers.
- [ ] Update `enrollment_mode` to `domain_gated` when domains are configured

**Billing cycle options:**
- [ ] Enable `daily` and `weekly` billing cycles in the cron job
- [ ] Month-end minimum fee reconciliation for non-monthly cycles

**Automated payment:**
- [ ] Stripe ACH integration for automated payment collection (see Section 6)
- [ ] Webhook handling for ACH payment events
- [ ] `stripe_customer_id` and `stripe_payment_method_id` on `employer_benefits_program`

### Phase 3 — SSO + enterprise features

**Goal**: Enterprise-grade onboarding and reporting.

**SSO integration:**
- [ ] SAML 2.0 and/or OIDC support for employer IdPs
- [ ] JIT user provisioning on first SSO login
- [ ] SCIM endpoint for automated deprovisioning
- [ ] Employer Admin configures IdP metadata in B2B platform

**Enterprise features:**
- [ ] Employer dashboard: enrollment analytics, usage metrics, cost projections
- [ ] Multi-tier subsidy: support multiple Employer institutions per company (e.g., executive vs. standard) with different rates/caps
- [ ] Annual contract management: pre-paid annual billing with monthly reconciliation

---

## 10. Data model summary

### New tables

**`core.employer_benefits_program`** — one row per Employer institution:

| Column | Type | Description |
|---|---|---|
| `program_id` | UUID PK | |
| `institution_id` | UUID FK UNIQUE | Must be `institution_type = 'Employer'` |
| **Benefit config** | | |
| `benefit_rate` | INTEGER NOT NULL | 0–100. Percentage of plan price employer covers for the employee. |
| `benefit_cap` | NUMERIC NULL | Max absolute amount employer subsidizes per employee. NULL = no cap. |
| `benefit_cap_period` | ENUM NOT NULL DEFAULT 'monthly' | `per_renewal` or `monthly`. How the cap resets. |
| **Employer pricing** | | |
| `price_discount` | INTEGER NOT NULL DEFAULT 0 | 0–100. Negotiated discount on what the employer pays Vianda. |
| `minimum_monthly_fee` | NUMERIC NULL | Floor for monthly employer charges. NULL = no minimum. |
| **Billing config** | | |
| `billing_cycle` | ENUM NOT NULL DEFAULT 'monthly' | `daily`, `weekly`, or `monthly`. |
| `billing_day` | INTEGER NULL DEFAULT 1 | Day of month for monthly billing (1–28). NULL if not monthly. |
| `billing_day_of_week` | INTEGER NULL | Day of week for weekly billing (0=Mon, 6=Sun). NULL if not weekly. |
| **Enrollment** | | |
| `enrollment_mode` | ENUM NOT NULL | `managed` or `domain_gated`. Determines how employees join. |
| **Payment** | | |
| `stripe_customer_id` | VARCHAR NULL | Stripe Customer for ACH billing. |
| `stripe_payment_method_id` | VARCHAR NULL | Stored ACH payment method. |
| `payment_method_type` | VARCHAR NULL | `ach_debit`, `ach_credit`, `bank_transfer`, etc. |
| **Renewal** | | |
| `allow_early_renewal` | BOOLEAN NOT NULL DEFAULT FALSE | If FALSE, benefit employees default to period-end-only renewal. |
| **Status** | | |
| `is_active` | BOOLEAN NOT NULL DEFAULT TRUE | Program can be suspended without deleting. |

**`core.employer_domain`** — email domains for domain-gated enrollment:

| Column | Type | Description |
|---|---|---|
| `domain_id` | UUID PK | |
| `institution_id` | UUID FK | Must be `institution_type = 'Employer'` |
| `domain` | VARCHAR NOT NULL UNIQUE | e.g., `acme.com`. One employer per domain. |
| `is_active` | BOOLEAN NOT NULL DEFAULT TRUE | |

**`billing.employer_bill`** — monthly aggregated employer invoice (see Section 5.4)

**`billing.employer_bill_line`** — per-subscription line items on an employer bill (see Section 5.4)

### Modified tables

**`customer.subscription_info`** — new column (✅ implemented):
```
early_renewal_threshold INTEGER DEFAULT 10          -- NULL = period-end only; >= 1 = early renew when balance below this
```

Also added to `audit.subscription_history`.

### Unchanged tables

**`core.institution_info`** — no new columns. Benefits config lives on `employer_benefits_program`.

**`core.employer_info`** — no changes. Remains a B2C company directory. Not related to benefits-program config.

---

## 11. Key design decisions and rationale

### Why renewal control is a platform feature, not a benefits-only feature?

The `early_renewal_threshold` column lives on `subscription_info`, not on `employer_benefits_program`. Any Customer Comensal benefits from controlling when early renewal triggers — a regular B2C user might want to avoid mid-month charges just as much as a benefit employee. Putting the control on the subscription means the benefits program simply sets a smart default at enrollment time (via `allow_early_renewal`), and the user can adjust from there. No parallel system needed. Subscriptions always auto-renew at the 30-day mark — users who want to stop renewing use cancel or on-hold, which already exist.

### Why benefit_rate + benefit_cap instead of a default plan?

Tying subsidies to a specific plan creates coupling: if the plan is discontinued or repriced, the subsidy config breaks. Rate + cap is plan-agnostic — the employer says "we cover up to $X per employee" and employees choose freely. The cheapest plan happens to be fully covered; anything above it is the employee's choice.

### Why separate benefit_rate and price_discount?

These serve different purposes and audiences:
- `benefit_rate` is employee-facing: "your employer covers 100% of the plan price up to $45."
- `price_discount` is B2B-facing: "Vianda gives your company a 10% volume discount on the aggregated bill."

Conflating them into one field would either leak the B2B discount to employees (confusing — "my employer covers 90%?") or hide the employee benefit from the employer's bill (hard to reconcile). Keeping them separate means each audience sees exactly the number that matters to them.

### Why benefit_cap_period (per-renewal vs. monthly)?

Employees who use all their credits can renew multiple times per month. Without a cap period, the employer's exposure is unbounded for heavy users. `monthly` caps give employers cost predictability; `per_renewal` is opt-in for employers who explicitly want to subsidize high-frequency users.

### Why a dedicated table, not institution_info?

`institution_info` is a general-purpose table shared across all institution types. Benefits-program fields would be NULL for all non-Employer institutions. A dedicated table keeps the institution table clean, makes Employer-specific queries efficient, and groups all program config in one place.

### Why employer_info stays B2C-only?

`employer_info` feeds B2C features — Comensals use it to find their workplace and discover coworkers. Mixing program config into that table would expose billing details, benefit rates, and enrollment settings to B2C queries. The benefits program is an institution-scoped B2B concern; it belongs on its own table, visible only to Employer Admins and Internal.

### Why enrollment mode is a choice, not a stack of features?

Offering all enrollment methods simultaneously creates ambiguity: if domain-gating is active and an HR admin also manually adds people, which is the source of truth? Conflicting enrollment paths make deprovisioning unreliable ("was this person added manually or did they self-register?"). A single mode per employer keeps the enrollment contract clear. Employer Admins in managed mode can still add individual employees — CSV is just the batch variant of the same managed path.

### Why configurable billing cycle?

Different employers have different AP (accounts payable) cadences. Monthly is the default and simplest. Daily billing suits small employers or trial periods where fast payment reduces risk. Weekly is a middle ground. The billing engine is the same regardless — it queries renewal events within the period window, aggregates, applies discount, and generates a bill.

### Why aggregated billing, not per-subscription invoicing?

Per-subscription invoicing would generate hundreds of small ACH transactions at $5 each (or credit card at 2.9% each). One aggregated bill per cycle means one $5-capped ACH fee regardless of employee count.

### Why minimum monthly fee instead of upfront commitment?

A minimum fee is recurring and self-reinforcing: each month the employer either uses the service enough to exceed the floor (good) or pays the floor (which motivates them to enroll more employees). An upfront commitment is a one-time event with no ongoing incentive alignment.

---

## 12. References

- **Institution type and roles**: `app/config/enums/role_types.py` (RoleType.EMPLOYER), `app/security/field_policies.py`
- **employer_info (B2C company directory)**: `app/db/schema.sql` (core.employer_info), `app/routes/employer.py`
- **Customer Comensal institution assignment**: `docs/api/b2b_client/feedback_from_client/CUSTOMER_COMENSAL_INSTITUTION.md`
- **Stripe Customer integration**: `docs/plans/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md`
- **User–market and scoping**: `docs/plans/USER_MARKET_ASSIGNMENT_DESIGN.md`
- **Existing Stripe integration**: `app/services/payment_provider/stripe/`, `app/routes/webhooks.py`
