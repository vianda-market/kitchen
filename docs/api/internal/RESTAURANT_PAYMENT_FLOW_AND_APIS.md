# Restaurant Payment Flow and APIs — Credit/Currency to $ Payout

**Audience:** Developers integrating with the Kitchen API, backend engineers, QA.

This document connects the credit/currency model to the actual restaurant payment flow. It shows how `credit_value_local_currency` flows through balance, settlement, and institution bills to the Stripe payout. See also [CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) and [SUPPLIER_INSTITUTION_PAYMENT.md](SUPPLIER_INSTITUTION_PAYMENT.md).

---

## 1. Data model: Credit/currency to $ payout

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CREDIT & CURRENCY MODEL (from credit_currency_info)                                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ credit_value_local_currency  →  Local $ per 1 credit (e.g. 1400 ARS/credit)                       │
│ currency_conversion_usd      →  Local units per 1 USD (for plan pricing)                            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌────────────────────┐    ┌────────────────────────┐    ┌────────────────────────────────────────┐
│ vianda_info         │    │ plan_info               │    │ restaurant_transaction (order flow)      │
│ expected_payout_   │    │ credit_cost_local_     │    │ final_amount = credit × (no-show disc)   │
│ local_currency =   │    │ currency, credit_cost_  │    │ (see Investigation section below)       │
│ credit × cv_local  │    │ usd (trigger-set)      │    │                                          │
└────────────────────┘    └────────────────────────┘    └────────────────────────────────────────┘
         │                                                       │
         │                                                       ▼
         │              ┌─────────────────────────────────────────────────────────────────────────┐
         │              │ restaurant_balance_info                                                  │
         └─────────────►│ balance += amount on QR scan/arrival (unit TBD — see Investigation)    │
                        │ currency_code, credit_currency_id                                       │
                        └─────────────────────────────────────────────────────────────────────────┘
                                                        │
                                                        │ Settlement pipeline (Phase 1)
                                                        ▼
                        ┌─────────────────────────────────────────────────────────────────────────┐
                        │ institution_settlement (one per restaurant per period when balance > 0)  │
                        │ amount = restaurant_balance_info.balance                                 │
                        │ institution_bill_id (linked in Phase 2)                                   │
                        └─────────────────────────────────────────────────────────────────────────┘
                                                        │
                                                        │ Phase 2: one bill per entity
                                                        ▼
                        ┌─────────────────────────────────────────────────────────────────────────┐
                        │ institution_bill_info  ←  ACTUAL $ PAYMENT RECORD                         │
                        │ institution_bill_id                                                       │
                        │ amount = sum(settlement.amount) for entity  (local currency)              │
                        │ currency_code                                                            │
                        │ stripe_payout_id, payout_completed_at  ←  Proof of payment                │
                        │ resolution: Pending → Paid (after payout)                                  │
                        └─────────────────────────────────────────────────────────────────────────┘
                                                        │
                                                        │ trigger_payout(bill_id, amount, currency_code)
                                                        ▼
                        ┌─────────────────────────────────────────────────────────────────────────┐
                        │ Stripe Connect (or mock) — Real $ transfer to restaurant bank account      │
                        └─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. APIs: Credit/currency (from CREDIT_AND_CURRENCY_CLIENT.md)

| Purpose | API |
|---------|-----|
| Supported currencies | `GET /api/v1/currencies/` |
| Create credit currency | `POST /api/v1/credit-currencies/` |
| Update credit currency | `PUT /api/v1/credit-currencies/{id}` |
| Plan form preview | `GET /api/v1/markets/enriched/` (includes `credit_value_local_currency`, `currency_conversion_usd`) |
| Plans (with credit costs) | `GET /api/v1/plans/`, `GET /api/v1/plans/enriched/` |
| Vianda payout preview | `GET /api/v1/restaurants/enriched/` (`market_credit_value_local_currency`) |

---

## 3. APIs: Restaurant $ flow (balance → bill → payout)

| Purpose | API | Notes |
|---------|-----|-------|
| **Add to balance** (customer arrival) | `POST /api/v1/vianda-pickup/scan-qr` | Body: `{ "qr_code_payload": "..." }`. Triggers `_update_restaurant_transaction_arrival` → `update_balance_on_arrival`. |
| **Read restaurant balance** | `GET /api/v1/restaurant-balances/`, `GET /api/v1/restaurant-balances/{restaurant_id}`, `GET /api/v1/restaurant-balances/enriched` | Read-only. |
| **Run settlement → bill → payout** | `POST /api/v1/institution-bills/run-settlement-pipeline?bill_date=YYYY-MM-DD&country_code=XX` | Phase 1: settlements from balances; Phase 2: one bill per entity; tax doc; payout; `mark_paid`. |
| **Alternative pipeline entry** | `POST /api/v1/institution-bills/generate-daily-bills?bill_date=...&country_code=...` | Same pipeline as above. |
| **View bill (payment record)** | `GET /api/v1/institution-bills/{bill_id}` | Bill includes `amount`, `currency_code`. After payout: `stripe_payout_id`, `payout_completed_at` (if schema exposes them). |
| **List bills (enriched)** | `GET /api/v1/institution-bills/enriched` | Institution/entity names, etc. |
| **List bills (filtered)** | `GET /api/v1/institution-bills/?institution_id=...&status=...&start_date=...&end_date=...` | |
| **Cancel bill** | `POST /api/v1/institution-bills/{bill_id}/cancel` | |

---

## 4. Connection: Credits to institution_bill_id and actual payment

End-to-end flow:

1. **Credit definition** (`credit_currency_info`): `credit_value_local_currency` defines local $ per credit.
2. **Balance accrual** (QR scan): `POST /vianda-pickup/scan-qr` → `_update_restaurant_transaction_arrival` → `update_balance_on_arrival(restaurant_id, credit_difference, db)`.
3. **Balance store** (`restaurant_balance_info`): `balance` is the amount that feeds settlements.
4. **Settlement** (Phase 1): For each restaurant with `balance > 0`, create settlement with `amount = balance`, then reset balance.
5. **Bill** (Phase 2): One `institution_bill_info` per entity; `amount = sum(settlement.amount)` for that entity.
6. **Payout**: `trigger_payout(institution_bill_id, bill.amount, bill.currency_code)` — this amount is sent to Stripe.
7. **Payment record**: `institution_bill_info` stores `stripe_payout_id` and `payout_completed_at`.

Key relationship:

```
institution_bill_info.amount  =  sum of institution_settlement.amount for that entity
                               =  sum of restaurant_balance_info.balance (before reset)
                               =  (intended) sum of (credits × credit_value_local_currency) from QR scans
```

The `institution_bill_id` is the canonical record for the actual payment; `amount` and `currency_code` define what gets paid; `stripe_payout_id` and `payout_completed_at` tie it to the payout provider.

**Pipeline response** (from `run-settlement-pipeline`):

```json
{
  "settlements_created": N,
  "bills_created": M,
  "bills_paid": M,
  "bill_ids": ["uuid", ...],
  "paid_bills": [
    {
      "institution_bill_id": "uuid",
      "stripe_payout_id": "po_mock_xxx",
      "payout_completed_at": "2025-03-17T..."
    }
  ],
  "total_amount": 1234.56
}
```

---

## 5. Investigation: Balance units and final_amount semantics

**Status:** Needs verification. There is a potential discrepancy between documentation and implementation.

### 5.1 What the documentation says

[CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) Section 7 states:

> When a customer arrives (QR scan), the restaurant balance is updated with:
> `credits × credit_value_local_currency`

So `restaurant_balance_info.balance` should be in **local currency** (e.g. ARS, USD).

### 5.2 What the code does

In the promotion/arrival flow:

- **`vianda_selection_promotion_service._create_restaurant_transaction_for_promotion`**  
  - `final_amount = credit_decimal * discount_multiplier` (e.g. 8 credits × 0.8 = 6.4 credits for 20% no-show discount).  
  - `final_amount` is in **credits**, not local currency.

- **`create_with_conservative_balance_update`** (crud_service)  
  - Passes `transaction.final_amount` to `update_balance_on_transaction_creation`.  
  - No multiplication by `credit_value_local_currency` in this path.

- **`vianda_pickup_service._update_restaurant_transaction_arrival`**  
  - Uses `credit_difference = float(credit_amount - current_final_amount)` (credits).  
  - Calls `update_balance_on_arrival(restaurant_id, credit_difference, db)` — again, credits, not local currency.

- **`update_balance_on_arrival`** and **`update_balance_on_transaction_creation`**  
  - Both add the passed value directly to `restaurant_balance_info.balance`.  
  - No conversion by `credit_value_local_currency` in these functions.

### 5.3 Possible explanations

| Hypothesis | Description |
|------------|-------------|
| **A. Conversion elsewhere** | Balance is intended to be in local currency, and conversion happens in another code path we haven’t found. |
| **B. credit_value_local_currency = 1** | In some markets (e.g. USD), 1 credit = 1 unit of currency, so credits and local currency coincide. |
| **C. Doc/code mismatch** | The doc describes the intended design; the code may not yet implement it. Balance could be stored in credits, which would be wrong for Stripe if `credit_value_local_currency ≠ 1`. |

### 5.4 Verification checklist

To resolve this, verify:

1. **`restaurant_transaction.final_amount` unit**  
   - Is it credits or local currency?  
   - Trace all writers: promotion flow, discretionary/credit loading, any other flows.

2. **`restaurant_balance_info.balance` unit**  
   - Is it credits or local currency?  
   - Check seed data and any existing production values.

3. **Consistency with `institution_bill_info.amount`**  
   - `institution_bill_info.amount` is sent to Stripe as the payout amount.  
   - It must be in the same unit as `restaurant_balance_info.balance` (since settlement `amount = balance`).  
   - If balance is in credits and `credit_value_local_currency ≠ 1`, payouts would be incorrect.

4. **Credit loading / discretionary flow**  
   - `credit_loading_service` creates `restaurant_transaction` with an `amount`.  
   - Confirm whether that amount is credits or local currency and how it affects balance.

### 5.5 Code locations to inspect

| Area | File / function |
|------|------------------|
| Promotion transaction creation | `app/services/vianda_selection_promotion_service.py` — `_create_restaurant_transaction_for_promotion` |
| Arrival balance update | `app/services/vianda_pickup_service.py` — `_update_restaurant_transaction_arrival` |
| Balance update helpers | `app/services/crud_service.py` — `update_balance_on_arrival`, `update_balance_on_transaction_creation`, `create_with_conservative_balance_update` |
| Credit loading | `app/services/credit_loading_service.py` |
| Settlement creation | `app/services/billing/institution_billing.py` — Phase 1 uses `balance_record.balance` for `settlement_data["amount"]` |
| Payout | `app/services/supplier_payout/` — `trigger_payout(bill_id, bill.amount, bill.currency_code)` |

### 5.6 Recommended fix (if mismatch confirmed)

If balance is currently stored in credits instead of local currency:

1. At transaction creation (promotion, arrival, credit loading):  
   - Compute `monetary_amount = credits × credit_value_local_currency` using the restaurant’s `credit_currency_id`.
2. Pass `monetary_amount` (not credits) to `update_balance_on_arrival` and `update_balance_on_transaction_creation`.
3. Ensure `restaurant_balance_info.balance` is always in local currency.
4. Update CREDIT_AND_CURRENCY_CLIENT.md if the doc is already correct and only the code needs changing.

---

## 6. Key code locations

| Concept | Location |
|---------|----------|
| QR scan → balance update | `app/routes/vianda_pickup.py` (scan-qr), `vianda_pickup_service._update_restaurant_transaction_arrival` |
| Balance update | `app/services/crud_service.py` — `update_balance_on_arrival` |
| Settlement pipeline | `app/services/billing/institution_billing.py` — `run_phase1_settlements`, `run_phase2_bills_and_payout`, `run_daily_settlement_bill_and_payout` |
| Bill creation | Same file — Phase 2 creates `institution_bill_info`, links settlements |
| Payout | `app/services/supplier_payout/` — `trigger_payout` (mock/Stripe) |
| Institution bill routes | `app/routes/billing/institution_bill.py` |

---

## 7. Related docs

- [CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) — Credit values, plan pricing, vianda payouts, B2C savings
- [SUPPLIER_INSTITUTION_PAYMENT.md](SUPPLIER_INSTITUTION_PAYMENT.md) — Settlement → bill → payout pipeline, cron, configuration
