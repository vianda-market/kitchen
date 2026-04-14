# Financial Data Hierarchy

**Last Updated**: 2026-04-01
**Audience**: All agents (backend, B2B, B2C, infra)

Single reference for the financial data model — from customer pickup to supplier payout. Read this before building features that touch transactions, balances, settlements, bills, payouts, or invoices.

---

## Data Flow

```
Customer picks up plate
        │
        ▼
┌─────────────────────┐
│  Transaction         │  plate_pickup_live — one per pickup event
│  Level: Restaurant   │  Records credit deduction and restaurant credit
└────────┬────────────┘
         │ accumulates into
         ▼
┌─────────────────────┐
│  Balance             │  restaurant_balance_info — running total per restaurant
│  Level: Restaurant   │  Reset to 0 on settlement
└────────┬────────────┘
         │ daily settlement closes balance
         ▼
┌─────────────────────┐
│  Settlement          │  institution_settlement — one per restaurant per billing period
│  Level: Restaurant   │  Links to settlement_run_id (batch) and institution_bill_id
└────────┬────────────┘
         │ N settlements aggregate into 1 bill per entity
         ▼
┌─────────────────────┐
│  Bill                │  institution_bill_info — one per entity per billing period
│  Level: Entity       │  Aggregates amount + transaction_count across entity's restaurants
└────────┬────────────┘
         │ payout transfers funds to supplier
         ▼
┌─────────────────────┐
│  Payout              │  institution_bill_payout — one attempt per bill (retries = new row)
│  Level: Entity       │  Provider-agnostic (Stripe, future: dLocal, etc.)
└────────┬────────────┘
         │ matched by supplier
         ▼
┌─────────────────────┐
│  Invoice             │  supplier_invoice_info — supplier-uploaded, matched to bills
│  Level: Entity       │  Country-specific validation (AR factura, US invoice)
└─────────────────────┘
```

---

## Table-to-Level Map

| Layer | Table | Schema | Level | Primary Key | Key FKs |
|-------|-------|--------|-------|-------------|---------|
| Transaction | `plate_pickup_live` | `ops` | Restaurant | `plate_pickup_id` | `restaurant_id`, `user_id`, `subscription_id` |
| Balance | `restaurant_balance_info` | `ops` | Restaurant | `restaurant_balance_id` | `restaurant_id` |
| Settlement | `institution_settlement` | `billing` | Restaurant | `settlement_id` | `restaurant_id`, `institution_entity_id`, `institution_bill_id`, `settlement_run_id` |
| Bill | `institution_bill_info` | `billing` | Entity | `institution_bill_id` | `institution_id`, `institution_entity_id`, `credit_currency_id` |
| Payout | `institution_bill_payout` | `billing` | Entity (via bill) | `bill_payout_id` | `institution_bill_id` |
| Invoice | `supplier_invoice_info` | `billing` | Entity | `supplier_invoice_id` | `institution_entity_id` |

---

## Key Design Decisions

### Why bills aggregate at entity level, not restaurant
An `institution_entity` is the legal company — it has a `tax_id`, receives payouts, and issues invoices. A single entity can operate multiple restaurants. The bill represents the amount owed to the legal entity for a billing period. Restaurant-level detail is preserved in settlements.

### Why payouts are append-only (no history table)
Payout rows are never updated to a different terminal state. A payout transitions `Pending → Completed` or `Pending → Failed` once. Retries insert a new row rather than updating the old one. This makes the table an append-only audit trail — no history trigger needed.

### Why settlements are per-restaurant
Each restaurant has its own balance and transaction history. Settlements close one restaurant's balance at a time, producing a clear audit trail of how much each restaurant contributed to the entity's bill.

### Why there's no restaurant on a bill or payout
A bill can cover 5 restaurants for the same entity. Adding `restaurant_id` to the bill would break the 1-bill-per-entity-per-period invariant. To see which restaurants contributed to a bill, query `institution_settlement WHERE institution_bill_id = ?`.

---

## API Endpoints by Layer

| Layer | Endpoint | Audience | Notes |
|-------|----------|----------|-------|
| Balance | `GET /api/v1/restaurant-balances/` | B2B | Enriched with restaurant name |
| Settlement | `GET /api/v1/institution-bills/{bill_id}` → settlements via report | B2B (Internal) | Settlement detail via billing service reports |
| Bill | `GET /api/v1/institution-bills/enriched` | B2B | Institution-scoped; enriched with entity, market |
| Payout | `GET /api/v1/payouts/enriched` | B2B | Institution-scoped; enriched with entity, billing period |
| Payout (entity) | `GET /api/v1/institution-entities/{id}/stripe-connect/payouts` | B2B (Internal) | Raw payout rows for one entity |
| Invoice | `GET /api/v1/supplier-invoices/enriched` | B2B | Institution-scoped; enriched with entity, bill match |

---

## Related Docs

- [SUPPLIER_INSTITUTION_PAYMENT.md](SUPPLIER_INSTITUTION_PAYMENT.md) — Settlement → bill → payout pipeline details, pipeline entry points, debugging
- [RESTAURANT_PAYMENT_FLOW_AND_APIS.md](RESTAURANT_PAYMENT_FLOW_AND_APIS.md) — Credit/currency → balance → settlement → bill flow; balance unit semantics
- [API_CLIENT_SUPPLIER_PAYOUT.md](../b2b_client/API_CLIENT_SUPPLIER_PAYOUT.md) — B2B integration guide for payout onboarding and trigger
- [API_CLIENT_PAYOUT_HISTORY.md](../b2b_client/API_CLIENT_PAYOUT_HISTORY.md) — B2B integration guide for enriched payout list
- [API_CLIENT_SUPPLIER_INVOICES.md](../b2b_client/API_CLIENT_SUPPLIER_INVOICES.md) — Invoice upload and bill matching
