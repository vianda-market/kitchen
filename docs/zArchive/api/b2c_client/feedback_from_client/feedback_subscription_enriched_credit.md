# Request: Add plan `credit` to subscription enriched response

**Context:** The B2C app shows subscription details (Balance, Renewal, etc.) from **GET /api/v1/subscriptions/enriched/**. There is no `credit` field on the subscription entity itself; that value lives on the **plan** (e.g. `GET /api/v1/plans/enriched/?market_id=...` returns plans with `credit`). To show “Credits on renewal: XX” in the subscription details modal without an extra request per subscription, the client needs the plan’s credits-per-period in the subscription response.

---

## Recommendation

**Enhance the subscription enriched endpoint** so that each subscription in the response includes the plan’s credit amount.

- **Endpoint:** `GET /api/v1/subscriptions/enriched/` (and, if applicable, `GET /api/v1/subscriptions/enriched/{id}` or single-subscription responses that are “enriched”).
- **Add to each subscription object:** a field such as **`credit`** (number), populated from the **plan** linked to that subscription (e.g. the plan’s `credit` or “credits per period”).
- **Semantics:** “Credits added on each renewal” — same meaning as `plan.credit` in the plans API.

---

## Client use

- The B2C app will display **Balance** (current credits) and **Credits on renewal** (the plan’s credit value) in the subscription details view (eye icon on Profile → Plan section).
- If the enriched response does not yet include `credit`, the app shows “Credits on renewal: —” and continues to work; once the backend adds the field, the value will appear without client changes.

---

## Why enrich instead of client fetching the plan?

- **One call:** List (and detail) already return subscription + market/plan identifiers; adding `credit` from the plan table avoids N+1 (fetching each plan by `plan_id` when rendering the list or opening details).
- **Consistent with “enriched”:** The endpoint already returns `plan_name`, `market_name`, etc.; including plan-derived `credit` fits the same pattern.
- **Simpler client:** No extra GET /plans/ per subscription or per details open.

---

**Summary:** Add a `credit` field (from the plan) to the subscription enriched response so the B2C app can show “Credits on renewal: XX” in subscription details.
