# Backend feedback: Plans page shows wrong currency (Argentina → USD)

**Resolved.** Root cause was seed data: all markets referenced the single USD credit currency. Fix: seed now includes ARS, PEN, CLP, MXN, BRL and assigns each market its correct credit currency. After DB tear-down and rebuild, Argentina plans display ARS. See plan: Argentina Plans USD Currency Fix.

---

**Purpose:** Investigate why plans for the **Argentina** market display **USD** as the currency instead of the market's credit currency (expected: **ARS** or whatever `credit_currency_code` is stored for that market). The B2C Select plan screen shows "Plans for Argentina" and next to the price (e.g. 100000) it incorrectly shows "USD".

**Audience:** Backend team. Use this document to trace the source of the currency code and ensure plans display the correct market currency.

---

## 1. Observed behavior

| What | Expected | Actual |
|------|----------|--------|
| Plans for Argentina | Price with **ARS** (or market's `credit_currency_code`) | Price with **USD** |
| Display | e.g. `100,000 ARS` | `100,000 USD` |

The user has selected **Argentina** as the market (from `GET /api/v1/markets/available`). The client loads plans via `GET /api/v1/plans/enriched/?market_id=<argentina_market_id>`. The displayed currency comes from either:

1. **Plan-level:** `currency_code` on each item in the plans enriched response, or  
2. **Market-level:** `currency_code` from the selected market (from `GET /api/v1/markets/available`).

The client now prefers the market's `currency_code` (from `markets/available`) over the plan's `currency_code`. If the market's `currency_code` is null or missing, it falls back to the plan's `currency_code`. In the observed case, **both** appear to yield or allow USD to be shown for Argentina.

---

## 2. Relevant endpoints and data sources

### 2.1 GET /api/v1/markets/available (public, no auth)

**Client use:** Fetched on app load. Populates the market selector. The selected market is stored and used for plans, subscriptions, etc.

**Contract (from [MARKETS_API_CLIENT.md](../shared_client/MARKETS_API_CLIENT.md)):** Each market object should include:

```json
{
  "market_id": "11111111-1111-1111-1111-111111111111",
  "country_code": "AR",
  "country_name": "Argentina",
  "timezone": "America/Argentina/Buenos_Aires",
  "currency_code": "ARS",
  "currency_name": "Argentine Peso"
}
```

**Questions for backend:**

- Does the Argentina market in the live response include `currency_code: "ARS"` (or equivalent)?
- Is `currency_code` ever null, missing, or defaulting to USD for Argentina?
- Is there a separate `credit_currency_code` field the backend uses that is not being exposed as `currency_code` on this endpoint?

---

### 2.2 GET /api/v1/plans/enriched/?market_id=... (authenticated)

**Client use:** Fetched when the user opens the Select plan screen with a market selected. Displays plan name, credits, price, and currency.

**Contract (client `PlanEnriched`):**

```typescript
interface PlanEnriched {
  plan_id: string;
  market_id: string;
  market_name: string;
  country_code: string;
  currency_name: string | null;
  currency_code: string | null;  // ← Used when market.currency_code is unavailable
  name: string;
  credit: number;
  price: number;
  rollover?: boolean;
  rollover_cap?: number | null;
  status: string;
}
```

**Questions for backend:**

- Where does `currency_code` on each plan come from (plan table, market, credit_currency, payment provider)?
- For plans in the Argentina market, what value is returned for `currency_code`? If it is "USD", why?
- Is the plan's price stored/denominated in a different currency (e.g. payment currency) than the market's credit currency? If so, should the client display the market's `credit_currency_code` instead of the plan's `currency_code` for consistency?

---

## 3. Hypotheses for backend investigation

| # | Hypothesis | How to verify |
|---|------------|---------------|
| 1 | **Markets/available does not return `currency_code` for Argentina** | Inspect the actual JSON response for the Argentina market. If `currency_code` is null, missing, or wrong, the client falls back to the plan's `currency_code`. |
| 2 | **Plans enriched returns `currency_code: "USD"` for Argentina plans** | Inspect the plans enriched response when `market_id` is the Argentina market. Check whether each plan has `currency_code` set to USD (e.g. from a default, payment provider, or wrong join). |
| 3 | **Backend uses `credit_currency_id` but does not expose `credit_currency_code`** | The market may have a `credit_currency_id` (UUID) linked to a currency table. The backend might not be resolving and returning the ISO code (e.g. ARS) as `currency_code` on markets/available or on plans. |
| 4 | **Plans join to wrong currency table** | Plans enriched may join to a payment/pricing currency (e.g. USD) instead of the market's credit currency. Verify the join and which currency is used for `currency_code` in the plans response. |
| 5 | **Global/default currency fallback** | If the backend uses a global default currency (e.g. USD) when market or plan currency is unspecified, that could explain USD appearing for Argentina. |

---

## 4. Suggested backend checks

1. **Log or capture the response of `GET /api/v1/markets/available`**  
   - Confirm whether the Argentina market includes `currency_code: "ARS"` (or the correct code).

2. **Log or capture the response of `GET /api/v1/plans/enriched/?market_id=<argentina_market_id>`**  
   - For each plan, check the value of `currency_code`.  
   - Trace in code where this value is set (plan, market, credit_currency, payment currency).

3. **Verify the credit-currency relationship**  
   - Each market has a `credit_currency_id` (or equivalent).  
   - Confirm that the resolved credit currency's ISO code (e.g. ARS) is:
     - Exposed as `currency_code` on `GET /markets/available`, and/or  
     - Exposed as `currency_code` (or a dedicated `credit_currency_code`) on plans enriched for that market.

4. **If plans price is stored in a different currency**  
   - Document whether plan prices are in payment currency vs. credit currency.  
   - Consider returning both a display currency (`credit_currency_code`) and any payment currency, or ensure `currency_code` on plans reflects what the user should see for that market.

---

## 5. Client-side workaround (current)

The B2C client has been updated to **prefer the market's `currency_code`** over the plan's `currency_code` when displaying the price:

```
displayCurrency = selectedMarket?.currency_code ?? plan.currency_code ?? ''
```

If `GET /api/v1/markets/available` returns the correct `currency_code` for Argentina, the Select plan screen will display ARS. If it does not (null, missing, or wrong), the client will still fall back to the plan's `currency_code`, which currently leads to USD for Argentina.

---

## 6. Summary

| Item | Action |
|------|--------|
| Root cause | Backend to determine why Argentina plans show USD instead of ARS |
| Markets/available | Confirm Argentina market returns `currency_code: "ARS"` (or correct code) |
| Plans enriched | Trace source of `currency_code` for Argentina plans; ensure it reflects market's credit currency |
| Credit currency | Expose `credit_currency_code` (or equivalent) for the market and use it consistently for plans in that market |

**Document status:** Feedback for backend investigation. Client has implemented market-currency preference; backend fix will ensure correct display across all markets.
