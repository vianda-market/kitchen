# Plan API: no credit_currency_id – currency from market

**Audience:** B2B (employee portal) and any client that implements plan create/update and plan tables or modals.

Each **market** has a single assigned credit currency. Plans belong to a market, so the plan’s currency is **derived from the market**, not stored on the plan. The plan API does **not** accept or return `credit_currency_id`.

---

## Create and update

- **POST /api/v1/plans/** (create): Request body includes `market_id`, `name`, `credit`, `price`. **No `credit_currency_id` field.** Do **not** send `rollover` or `rollover_cap`; the backend applies defaults (rollover=true, no cap).
- **PUT /api/v1/plans/{plan_id}** (update): Same fields, all optional. **No `credit_currency_id` field.** Do **not** send `rollover` or `rollover_cap`; these fields are ignored.

Do not send `credit_currency_id` in the request body; the backend schema does not accept it. Picking a **market** (e.g. Argentina) is enough: the backend uses that market’s assigned currency for the plan.

---

## Responses

- **GET /api/v1/plans/**, **GET /api/v1/plans/{plan_id}**, and **GET /api/v1/plans/enriched/** do **not** include `credit_currency_id`.
- Currency is still available for display via **`currency_name`** and **`currency_code`** on the **enriched** plan response (e.g. GET /api/v1/plans/enriched/), which are derived from the plan’s market.

---

## UI instruction (B2B)

For plan management (tables and create/edit modals): **do not** add a credit currency selector or `credit_currency_id` field. Only use: **market** (required on create), name, credit, price, and status. The market dropdown determines the currency; the API and UI should not expose or request a separate credit currency for plans.

**Hide rollover and rollover cap.** The B2B Vianda platform **must hide** the rollover toggle and rollover cap field from plan create/edit modals and from plan tables. All plans currently have rollover enabled with no cap; users must not be able to configure these settings. See [PLAN_ROLLOVER_UI_HIDDEN.md](./PLAN_ROLLOVER_UI_HIDDEN.md) for details.

## Global Marketplace must not be used for plans

**Global Marketplace** (`market_id` = `00000000-0000-0000-0000-000000000001`) is only for user assignment (unrestricted query scope). It **must not** be used for plans.

- Use **GET /api/v1/markets/enriched/** for the plan market dropdown; filter out Global Marketplace before showing it in plan create/edit.
- The backend returns **400 Bad Request** if you attempt to create or update a plan with `market_id` = Global Marketplace.
- Plan list endpoints (GET /plans/, GET /plans/enriched/) exclude plans for Global Marketplace.
