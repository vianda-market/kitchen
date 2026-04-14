# Payout Drill-Down View — Roadmap

**Status**: Planned
**Last Updated**: 2026-04-01
**Affects**: B2B + Backend

---

## Context

The enriched payout list (`GET /api/v1/payouts/enriched`) provides a flat entity-level table of payout history. Users can see which entity received a payout, the amount, status, and billing period.

The next step is a **drill-down view**: clicking a payout row reveals the full financial chain behind it — bill details, underlying settlements (per restaurant), balance events, and the transactions that produced the balance.

---

## Drill-Down Chain

```
Payout (entity level)
  └── Bill (entity level) — amount, period, resolution, tax doc
        └── Settlement(s) (restaurant level) — one per restaurant in this bill
              └── Restaurant — name, balance at time of settlement
                    └── Transaction(s) — individual pickups that accumulated the balance
```

---

## Proposed Endpoints

| Endpoint | Returns | Purpose |
|----------|---------|---------|
| `GET /api/v1/payouts/{bill_payout_id}/detail` | Bill + settlements + restaurant names | First click: expand a payout to see the bill and which restaurants contributed |
| `GET /api/v1/institution-settlements/{settlement_id}/transactions` | Transactions for one settlement | Second click: expand a settlement to see the individual pickup transactions |

### Payout detail response shape (sketch)

```json
{
  "bill_payout_id": "uuid",
  "bill": {
    "institution_bill_id": "uuid",
    "amount": "4500.00",
    "period_start": "2026-03-01",
    "period_end": "2026-03-31",
    "resolution": "Paid",
    "transaction_count": 150
  },
  "settlements": [
    {
      "settlement_id": "uuid",
      "restaurant_id": "uuid",
      "restaurant_name": "Downtown Bistro",
      "amount": "2000.00",
      "transaction_count": 80,
      "kitchen_day": "2026-03-15"
    },
    {
      "settlement_id": "uuid",
      "restaurant_id": "uuid",
      "restaurant_name": "Uptown Cafe",
      "amount": "2500.00",
      "transaction_count": 70,
      "kitchen_day": "2026-03-15"
    }
  ]
}
```

---

## Frontend UX (B2B)

1. **Payout list page** (exists) — flat table of enriched payouts
2. **Payout detail panel** — click a row → slide-out or expand showing bill + settlements table
3. **Settlement transactions** — click a settlement row → expand showing individual transactions

Progressive disclosure: each level loads on demand, not upfront.

---

## Backend Work

- New endpoint: `GET /payouts/{bill_payout_id}/detail` — JOIN payout → bill → settlements → restaurants
- New endpoint: `GET /institution-settlements/{settlement_id}/transactions` — JOIN settlement → balance events → transactions
- Response schemas for nested detail views
- Scoping: same institution scoping as enriched payout list

---

## Dependencies

- Enriched payout list (`GET /payouts/enriched`) must be complete first (implemented)
- Financial data hierarchy doc: `docs/api/internal/FINANCIAL_DATA_HIERARCHY.md`

---

## References

- [FINANCIAL_DATA_HIERARCHY.md](../api/internal/FINANCIAL_DATA_HIERARCHY.md) — Full financial data model
- [API_CLIENT_PAYOUT_HISTORY.md](../api/b2b_client/API_CLIENT_PAYOUT_HISTORY.md) — Current flat payout list
