# Feedback: Subscription balance vs plan credits, and renewal date

**Context:** The B2C app shows the customer’s subscription on **profile-plan** (and after payment success). We display **Balance** and **Renewal** from the subscription object returned by the API (`GET /api/v1/subscriptions/enriched/` or the confirm-payment response). We have observed two issues that need backend clarification or correction.

---

## 1. Balance lower than plan credits after first subscription

**Observed behaviour**

- The customer subscribed to a plan that is shown in the app as **Entry Level** with **70 credits** (from `plan.credit` when selecting the plan).
- Immediately after subscription became **Active**, the UI showed **Balance: 50** (from `subscription.balance`).
- So the customer sees 70 credits when choosing the plan but 50 credits as their balance once subscribed.

**Client behaviour**

- **Select-plan screen:** We show each plan’s `credit` from the plans API (e.g. “70 credits”) so the customer expects to receive 70 credits upon subscribing.
- **Profile-plan (and success screen):** We show `subscription.balance` as “Balance” with no extra logic. We do not override or recalculate; we trust the API.

**Questions for backend**

1. **Is the initial balance intended to be different from the plan’s credit amount?**  
   If yes (e.g. proration, trial, or a business rule that gives 50 for the first period), please document:
   - When and why `balance` differs from the plan’s `credit`.
   - What the client should show (e.g. “50 credits this period” vs “70 credits/month”) so we can align copy and avoid confusion.

2. **If the initial balance should equal the plan’s credits:**  
   Please ensure that when a subscription is activated (confirm-payment or Stripe webhook), the subscription’s `balance` is set to the **plan’s credit amount** (e.g. 70 for Entry Level). If there is a bug (e.g. wrong plan_id, wrong credit source, or hardcoded 50), please fix and document the rule.

3. **Optional:** If the API can expose the plan’s “credits per period” (e.g. on the subscription or in the enriched response), we can show both “Balance: 50” and “Plan: 70 credits/period” to avoid mismatch confusion.

---

## 2. Renewal date not aligned with “every 30 days” expectation

**Observed behaviour**

- The customer’s subscription is **Active** in market **Argentina**.
- The UI shows **Renewal: May 2, 2026** (from `subscription.renewal_date`).
- Product/design expectation: **renewals every 30 days** (see e.g. docs/ui_mocks/TAKEOUT_APP_SPEC.md). So if the subscription started around **March 2, 2026**, the customer expects the first renewal to be **April 2, 2026**, not May 2.

**Client behaviour**

- We display `subscription.renewal_date` as “Renewal” (formatted, e.g. “May 2, 2026”). We do not compute renewal from `created_date` or any other field; we rely on the API.

**Questions for backend**

1. **How is `renewal_date` defined?**  
   For example:
   - **Option A:** “Start date + 30 days” (e.g. March 2 → April 2).
   - **Option B:** “Same calendar day in the next month” (e.g. March 2 → April 2; if start was March 31 → April 30).
   - **Option C:** “First day of the next calendar month” or “end of current month”.
   - **Option D:** Something else (e.g. billing anchor, end of trial).

2. **Why might we see May 2 instead of April 2?**  
   Possible causes we need to rule out or confirm:
   - Use of “start + 60 days” instead of 30.
   - Timezone or date-only vs datetime handling (e.g. UTC vs local, or “next month” logic that adds an extra month).
   - Different rule for the first period (e.g. “first period = 2 months”).
   - Bug in the renewal calculation.

3. **Contract:** Please document in the subscription/billing API how `renewal_date` is set at activation and how it is updated on each renewal (e.g. “always start_date + 30 days” or “same day each month”). That way the client can show accurate copy (e.g. “Renewal every 30 days” vs “Renewal monthly on the 2nd”) and set user expectations correctly.

---

## 3. Summary table

| Topic | Observation | Request |
|--------|-------------|--------|
| **Balance vs plan credits** | Plan shows 70 credits; after subscription, `subscription.balance` is 50. | Clarify whether initial balance may differ from plan credits (and why). If it should match, fix and document. Optionally expose “credits per period” for the plan. |
| **Renewal date** | Renewal shown as May 2, 2026; customer expects April 2 (30 days after start). | Document how `renewal_date` is computed (e.g. start + 30 days vs calendar month). Fix if current behaviour is wrong; confirm timezone/date handling. |

---

## 4. Client integration

- We will continue to display **Balance** and **Renewal** from the subscription object as returned by the API.
- Once the rules are documented (and any bugs fixed), we can:
  - Adjust UI copy if needed (e.g. “X credits this period” vs “Y credits per renewal”).
  - Align any “renewal frequency” messaging (e.g. “Every 30 days” vs “Monthly on the Xth”) with the actual `renewal_date` behaviour.

We’re happy to provide more details (e.g. subscription_id, plan_id, created_date, market) for debugging if the backend team needs them.
