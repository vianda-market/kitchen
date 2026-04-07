# Credit and Currency — Client Guide

**Audience:** Client app agents (B2B kitchen-web, B2C mobile, any frontend integrating with the Kitchen API).

This document explains credit values, currency management, plan pricing, plate payouts, restaurant balance, and savings calculations in one place.

---

## 1. Data model at a glance

| Concept | Where it lives | Meaning |
|---------|----------------|---------|
| `credit_value_local_currency` | credit_currency_info | Local currency amount per 1 credit (e.g. 1400 ARS per credit). |
| `currency_conversion_usd` | credit_currency_info | Local units per 1 USD (for plan pricing). |
| `credit_cost_local_currency` | plan_info | Plan price ÷ credit (local currency per credit). Set by backend trigger. |
| `credit_cost_usd` | plan_info | USD equivalent per credit. Set by backend trigger. |
| `expected_payout_local_currency` | plate_info | `credit × credit_value_local_currency`. Set by backend trigger. Read-only. |
| `market_credit_value_local_currency` | Restaurant enriched API | Same as credit_value_local_currency for the restaurant’s market. Use for live payout preview when creating plates. |

---

## 2. Supported currencies and credit currency create

**Auth:** Employee only (Bearer token).

### Get supported currencies

`GET /api/v1/currencies/` — returns a list of `{ currency_name, currency_code }` (e.g. `"US Dollar"`, `"USD"`). Use this to build the Currency dropdown. Do not hardcode currency names or codes.

### Create credit currency

`POST /api/v1/credit-currencies/` — request body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `currency_name` | string | Yes | Must match a name from `GET /api/v1/currencies/` exactly. |
| `credit_value_local_currency` | number | Yes | Local currency amount per credit. Must be > 0. |

Do not send `currency_code`. The backend assigns it from the supported list.

Do not send `currency_conversion_usd`. The backend fetches it from open.er-api.com (USD = 1.0). All supported currencies (ARS, PEN, CLP, MXN, BRL, etc.) are covered.

If the exchange rate service is unavailable, create returns **503** with message "Exchange rate service temporarily unavailable" or "Could not fetch exchange rate" — retry later.

Example:

```json
{
  "currency_name": "Argentine Peso",
  "credit_value_local_currency": 1400
}
```

Response includes `credit_currency_id`, `currency_name`, `currency_code`, `credit_value_local_currency`, `currency_conversion_usd`. Use `credit_currency_id` when creating a market.

---

## 3. Credit currency edit — immutable identity

`PUT /api/v1/credit-currencies/{id}` — only these fields are editable:

- `credit_value_local_currency`
- `status`

`currency_name` and `currency_code` are immutable after creation. If the client sends them, the backend ignores or rejects. Show currency name/code as read-only in the edit form; send only `credit_value_local_currency` and `status` on update.

---

## 4. Currency from market — plans, restaurants, institution entities

Clients never send `credit_currency_id` on create for plans, restaurants, or institution entities. Currency is derived from the market.

### Plans

Each market has one credit currency. Plans belong to a market, so the plan’s currency comes from the market.

- **POST /api/v1/plans/**: Send `market_id`, `name`, `credit`, `price`. Do not send `credit_currency_id`, `rollover`, or `rollover_cap`.
- **PUT /api/v1/plans/{id}**: Same fields, all optional. Do not send `credit_currency_id`, `rollover`, or `rollover_cap`.
- Enriched responses (`GET /api/v1/plans/enriched/`) include `currency_name`, `currency_code`, `credit_cost_local_currency`, `credit_cost_usd` (derived from market).
- **Plan form preview**: Use `GET /api/v1/markets/enriched/` for the market dropdown. Each market includes `credit_value_local_currency` and `currency_conversion_usd` (from the market’s credit currency). Compute preview: `credit_cost_local_currency = price / credit`, `credit_cost_usd = credit_cost_local_currency / currency_conversion_usd`. One API call provides all needed data; no separate credit currency fetch.
- **Global Marketplace** must not be used for plans. Filter it out of the plan market dropdown.

### Institution entities

The entity’s `credit_currency_id` is derived from its address: `address.country_code` → market → `market.credit_currency_id`.

- **POST /api/v1/institution-entities/**: Do not send `credit_currency_id`.
- **PUT /api/v1/institution-entities/{id}**: If `address_id` changes, the backend recomputes `credit_currency_id`.

### Restaurants

Restaurants inherit credit currency from their institution entity.

- **POST /api/v1/restaurants/**: Send `institution_id`, `institution_entity_id`, `address_id`, `name`, `cuisine`. Do not send `credit_currency_id`.
- **PUT /api/v1/restaurants/{id}**: Same fields. Do not send `credit_currency_id`.

---

## 5. Plate expected payout and live preview (B2B)

### Stored value — read-only, backend-set

`expected_payout_local_currency` = `credit × credit_value_local_currency` (amount the supplier receives per plate in local currency). The backend trigger sets this on plate INSERT/UPDATE. Do not send `expected_payout_local_currency` on create or update.

### Live preview when creating a plate

When the Supplier creates a plate, they need live feedback before submit. Call:

- `GET /api/v1/restaurants/enriched/`, or
- `GET /api/v1/restaurants/enriched/{restaurant_id}`

The response includes `market_credit_value_local_currency` for the restaurant’s market. The UI can show:

`expected_payout_local_currency ≈ credit × market_credit_value_local_currency`

This is only for preview; the stored value is written by the backend trigger on create/update.

---

## 6. B2C explore — savings

`GET /api/v1/restaurants/by-city` returns `restaurants[].plates` with `savings` (integer 0–100).

### Formula

`savings` = `(price - credit × credit_cost_local_currency) / price × 100`, clamped to 0–100.

`credit_cost_local_currency` is the plan’s local currency cost per credit (price ÷ credit).

### Source of credit_cost_local_currency

- **User with subscription in the explored market:** from the user’s plan (JWT).
- **No subscription or unauthenticated:** from the highest-priced plan in the market (teaser).

Savings are computed on the fly; the client should refresh when entering explore or on pull-to-refresh.

### UI

Show savings as a percentage per plate (e.g. "15% off", "Save 15%"). Use `price` and `credit` for secondary display (e.g. "X credits · $Y").

---

## 7. Restaurant balance

When a customer arrives (QR scan), the restaurant balance is updated with:

`credits × credit_value_local_currency`

No-show orders use a discounted amount based on the supplier’s `no_show_discount` (from `billing.supplier_terms`). The plate API does not accept or return savings; savings appear only in B2C explore.

---

## 8. Summary — do not send

| Entity | Do not send |
|--------|-------------|
| Credit currency create | `currency_code`, `currency_conversion_usd` |
| Credit currency update | `currency_name`, `currency_code`, `currency_conversion_usd` |
| Plan create/update | `credit_currency_id`, `rollover`, `rollover_cap`, `credit_cost_local_currency`, `credit_cost_usd` |
| Restaurant create/update | `credit_currency_id` |
| Institution entity create/update | `credit_currency_id` |
| Plate create/update | `savings`, `expected_payout_local_currency`, `no_show_discount` |

---

## 9. Related docs

- [RESTAURANT_PAYMENT_FLOW_AND_APIS.md](../internal/RESTAURANT_PAYMENT_FLOW_AND_APIS.md) — Full flow from credit/currency to actual $ payout; APIs for balance, settlement, institution bills; investigation of balance units vs `final_amount`.

## 10. UI implementation notes

- Build the Currency dropdown from `GET /api/v1/currencies/`; use the exact `currency_name` when creating a credit currency.
- Credit currency create form: do not add an input for `currency_conversion_usd`. Backend fetches it automatically from open.er-api.com.
- Plan form: market dropdown only; no credit currency selector.
- Restaurant form: institution entity determines currency; no credit currency selector.
- Institution entity form: address determines market and currency; no credit currency selector.
- Plate create: use `GET /restaurants/enriched/` to get `market_credit_value_local_currency` for live payout preview; do not add an input for `expected_payout_local_currency`.
