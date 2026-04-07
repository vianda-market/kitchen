# Payout History Enriched — B2B Integration Guide

**Audience**: vianda-platform (B2B React) frontend agent
**Last Updated**: 2026-04-01
**Status**: Implemented

---

## Endpoint

```
GET /api/v1/payouts/enriched
```

Returns all payout attempts with enriched institution, entity, and billing period context.
Sorted by `created_at` descending (newest first).

---

## Scoping

| Role | Behavior |
|------|----------|
| **Supplier** (Admin, Manager, Operator) | Returns payouts for bills belonging to the user's institution |
| **Internal** | Returns all payouts across all institutions |

Same scoping pattern as `GET /api/v1/institution-bills/enriched`.

---

## Response Schema

Each row is a `BillPayoutEnrichedResponseSchema`:

```json
[
  {
    "bill_payout_id": "uuid",
    "institution_bill_id": "uuid",
    "institution_id": "uuid",
    "institution_name": "Acme Corp",
    "institution_entity_id": "uuid",
    "institution_entity_name": "Acme LLC",
    "provider": "stripe",
    "provider_transfer_id": "tr_...",
    "amount": "1500.00",
    "currency_code": "usd",
    "billing_period_start": "2026-03-01T00:00:00Z",
    "billing_period_end": "2026-03-31T23:59:59Z",
    "status": "Completed",
    "created_at": "2026-03-01T12:00:00Z",
    "completed_at": "2026-03-01T12:05:00Z"
  }
]
```

---

## Change from Original Request

The original request included `restaurant_name`. This field has been **removed** because payouts operate at the **entity level**, not the restaurant level:

- A bill aggregates settlements across all of an entity's restaurants for a billing period
- A payout pays one bill — so it covers multiple restaurants
- Adding `restaurant_name` to a flat table would require either duplicating rows or concatenating names, both misleading

**Restaurant-level detail** will be available through a future drill-down view (see roadmap: `docs/plans/PAYOUT_DRILL_DOWN_VIEW_ROADMAP.md`). In that view, clicking a payout row will reveal the bill, underlying settlements per restaurant, and transaction details.

For the current ResourcePage table, the **entity name** provides the right granularity: it identifies which legal company received the payout.

---

## Suggested Table Columns

For the **Supplier > Reports > Payouts** ResourcePage:

| Column | Field | Notes |
|--------|-------|-------|
| Entity | `institution_entity_name` | Which legal entity received the payout |
| Period | `billing_period_start` / `billing_period_end` | Format as date range |
| Amount | `amount` + `currency_code` | Format with currency symbol |
| Provider | `provider` | "stripe", "mock", etc. |
| Status | `status` | Pending / Completed / Failed |
| Transfer ID | `provider_transfer_id` | Show for reference; may be null while Pending |
| Date | `created_at` | When the payout was initiated |

For **Internal** users, also show `institution_name` column (Suppliers only see their own institution).

---

## Related Endpoints

| Endpoint | Use |
|----------|-----|
| `GET /api/v1/institution-bills/enriched` | See all bills (parent of payouts) |
| `GET /api/v1/institution-entities/{id}/stripe-connect/status` | Check if entity has completed payout onboarding |
| `GET /api/v1/institution-entities/{id}/payout-aggregator` | Check which payout provider is configured for the entity's market |

---

## References

- Financial data hierarchy: `docs/api/internal/FINANCIAL_DATA_HIERARCHY.md`
- Payout onboarding guide: `docs/api/b2b_client/STRIPE_CONNECT_SUPPLIER_PAYOUT_B2B.md`
- Drill-down roadmap: `docs/plans/PAYOUT_DRILL_DOWN_VIEW_ROADMAP.md`
