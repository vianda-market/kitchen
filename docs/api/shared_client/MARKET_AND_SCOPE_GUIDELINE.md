# Market and scope: single guideline for B2B and B2C

**Audience:** Backend and frontend teams, B2B (kitchen-web) and B2C (kitchen-mobile) agents  
**Purpose:** Single reference for market behavior, Markets API, scope rules, subscriptions, and UI patterns. Use this for the **initial phase** of single market per institution and single market for Customer Comensal, and for implementing changes consistently across both clients.

**Last updated:** 2026

---

## 1. Initial phase: single market (current behavior)

This section describes what is **in place now** so both B2B and B2C agents implement correctly.

### 1.1 Single market per institution

- Every **institution** has exactly one **market_id** (required; Global or a country market). No “no market”; never null.
- **Supplier institutions:** The institution’s `market_id` is set at creation and is **non-editable** via normal update; only a future paid upgrade flow can add or change markets. B2B clients must not allow editing `market_id` for Supplier institutions in the UI (backend strips it on PUT).
- **Institution create:** `market_id` is **required** in `POST /api/v1/institutions/`. Use `GET /api/v1/leads/markets` for the dropdown (excludes Global; see §3).

### 1.2 Single market for Customer Comensal (B2C)

- **Signup:** The B2C client **must** send **`country_code`** (required, ISO 3166-1 alpha-2) in `POST /api/v1/customers/signup/request`. The user selects their country in the UI before submitting; the value must come from `GET /api/v1/leads/markets` (which returns only `country_code` and `country_name`). The backend resolves `country_code` to `market_id` and uses it when creating the user at verify.
- **Non-editable after signup:** Customer Comensal (and Customer Employer) **cannot change** their market via profile update. The backend strips `market_id` and `market_ids` on `PUT /users/me` and on admin `PUT /users/{user_id}` when the target user is a Customer. B2C clients must not show or send market as editable in profile; the user is locked to the market chosen at registration until a future paid upgrade flow.
- **Restore selection after login:** Use `GET /users/me` and set the app’s selected market from `market_id` (or `market_ids[0]`) so the market selector matches the user’s assigned market.

### 1.3 Supplier and Customer Employer (B2B): institution-bound market

- **Supplier users** and **Customer Employer** users (B2B portal) must be assigned the **same market as their institution**. The backend rejects user create/update (400) if the user’s `market_id` does not match the institution’s `market_id`.
- **B2B client obligation:** When creating or updating a **Supplier** or **Customer Employer** user, send `market_id` equal to the **institution’s** `market_id`. Either fetch the institution (e.g. `GET /api/v1/institutions/{institution_id}`) and use `response.market_id`, or use a variable set from that response. Do not send Global for these roles when the institution has a country market.
- **Non-editable after creation:** Supplier and Customer Employer users cannot change their market via `PUT /users/me` or admin update; the backend strips `market_id` / `market_ids`. Only a future paid upgrade flow can add markets. Do not expose market as editable in the B2B UI for these roles.

### 1.4 Summary for agents

| Actor | Market at creation | Editable later? | Source of market_id |
|-------|--------------------|-----------------|----------------------|
| **Customer Comensal** | Required at signup (client sends `country_code` in signup request) | No | User selection from GET /leads/markets (`country_code`) |
| **Customer Employer** | Must match institution’s market | No | Institution’s market_id |
| **Supplier user** | Must match institution’s market | No | Institution’s market_id |
| **Institution (Supplier)** | Required at create | No (for Supplier institutions) | From GET /markets/enriched/ |

---

## 2. Markets API reference

### 2.1 Public (Leads): GET /api/v1/leads/markets

- **Auth:** None (public). Rate-limited (e.g. 60 req/min). Cached on server.
- **Response:** Active, non-archived countries **excluding Global Marketplace**. Use as the **single source** for the signup country selector and lead flow.
- **Shape:** `{ country_code, country_name }` only (no `market_id`, timezone, or currency). ISO 3166-1 **alpha-2** for `country_code`. For authenticated flows that need `market_id`, use **GET /api/v1/markets/enriched/**.

### 2.2 Authenticated endpoints

- **GET /api/v1/markets/enriched/** — List markets with currency details. Query: `include_archived` (default false).
- **GET /api/v1/markets/enriched/{market_id}** — Single market by ID.
- **GET /api/v1/markets/** — Base list (any authenticated user).
- **POST /api/v1/markets/** — Create market (Super Admin only).
- **PUT /api/v1/markets/{market_id}** — Update (Super Admin only).
- **DELETE /api/v1/markets/{market_id}** — Soft delete (Super Admin only). Global Marketplace cannot be archived (400).

### 2.3 Global Marketplace rule (critical)

- **Global Marketplace** = `market_id` `00000000-0000-0000-0000-000000000001` (country_code `GL`). It is **only for user assignment** (“this user is not constrained by market when querying”).
- **Do not** use Global for plans, subscriptions, or any other entity. The backend returns **400** if Global is sent for plan create/update or similar.
- **Client obligation:** **Exclude Global** from any dropdown used when creating or editing entities that take `market_id`. **GET /leads/markets** already excludes Global — use it for those dropdowns.

### 2.4 Where market_id vs country_code is used

| Area | Parameter | Typical source (B2C) | Notes |
|------|------------|----------------------|--------|
| Lead cities / city-metrics | `country_code` | `selectedMarket?.country_code` | Default US if omitted |
| Explore restaurants | `country_code` | `selectedMarket?.country_code` | Default US if omitted |
| Plans (enriched) | `market_id` | `selectedMarket?.market_id` | Must not be Global for plan create |
| Subscriptions | Via `plan_id` | Plans listed per `market_id` | Market from plan |
| User create (Supplier / Customer Employer) | `market_id` | Institution’s `market_id` | Must match institution |
| B2B restaurant search | `market_id` or `country_code` | GET /users/me assigned market | Always send context |

---

## 3. Market selector and country-flag UI (B2B and B2C)

### 3.1 Data source and state

- **Fetch:** `GET /api/v1/leads/markets` on load; cache with short TTL.
- **State:** B2C (pre-auth): store `{ country_code, country_name }` from GET /leads/markets for signup. B2C (post-auth) and B2B: store `{ market_id, country_code, country_name }` from GET /users/me or enriched markets.
- **Persistence:** B2C (mobile) — AsyncStorage/SecureStore (e.g. `selected_market_id`). B2B (web) — localStorage. After login, restore from GET /users/me `market_id` / `market_ids[0]`.

### 3.2 Country flag

- Use **alpha-2** `country_code` from the API. No mapping needed.
- **Web:** e.g. `country-flag-icons` by alpha-2. **Mobile:** flag emoji or same package. Backend uses alpha-2 everywhere (Markets, Addresses, Autocomplete).

### 3.3 Behavior tied to active market

- Address form `country_code` pre-fill (B2B: restaurant/entity; B2C: customer, checkout).
- Plan filtering by market.
- Timezone for date/time from market timezone.
- Market-scoped API calls: send `market_id` or `country_code` as required by each endpoint.

### 3.4 Default selection

- Use device locale (e.g. region code) and match to a market in the list; fallback to US or first market.

---

## 4. Market-based subscriptions

- **One active subscription per user per market** (DB constraint). Each subscription has its own balance, renewal date, hold status.
- **Plans are market-specific.** Filter plans by market: `GET /api/v1/plans/enriched/?market_id={market_id}`. Use only non-Global `market_id`.
- **Create subscription:** `POST /api/v1/subscriptions/` with `user_id` and `plan_id`; market is derived from the plan. **409** if user already has an active subscription in that market.
- **Hold:** `POST /api/v1/subscriptions/{id}/hold` and `.../resume`. On Hold = not billed, vianda selection not allowed; auto-resume after hold end date.
- **GET /api/v1/subscriptions/me** returns subscriptions with `market_id`, `market_name`, `country_code` for display. Show market context (name, currency) in all subscription UIs.

---

## 5. Enriched responses and TypeScript

- Enriched endpoints (plans, subscriptions, institution-bills, institution-bank-accounts, institution-entities, discretionary) include **market_id**, **market_name**, **country_code**. Add these to your interfaces.
- **Plan create/update:** Request body must include `market_id` (required); use only values from GET /markets/enriched/ (never Global).
- **Migration:** Existing endpoints remain compatible; new fields are additive. Exclude Global from any dropdown used for plan or other entity `market_id`.

---

## 6. B2B support and assigned market

- **GET /users/me** returns `market_id` (primary) and `market_ids` (all, primary first). Use as the assigned market for restaurant search/list and support flows.
- **Global-assigned users** (Admin, Super Admin, Supplier Admin): backend treats Global as “no market filter” for **query** scope. Still **do not** send Global for plan create/update or any non-user entity.
- **Always send context:** For support-side restaurant search/list, send `country_code` and/or `market_id`; do not rely on name-only search without context.

---

## 7. Related documentation

- [USER_MODEL_FOR_CLIENTS.md](./USER_MODEL_FOR_CLIENTS.md#7-user-and-market-market_id--market_ids) — User–market storage, GET /users/me, B2C/B2B usage.
- [ENRICHED_ENDPOINT_PATTERN.md](./ENRICHED_ENDPOINT_PATTERN.md)
- [API_PERMISSIONS_BY_ROLE.md](./API_PERMISSIONS_BY_ROLE.md)
- [COUNTRY_CODE_API_CONTRACT.md](./COUNTRY_CODE_API_CONTRACT.md)
- [ADDRESSES_API_CLIENT.md](./ADDRESSES_API_CLIENT.md)
- B2C signup: [b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](../b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md), [b2c_client/MARKET_CITY_COUNTRY.md](../b2c_client/MARKET_CITY_COUNTRY.md)
- B2B institution market: [b2b_client/API_CLIENT_INSTITUTIONS.md](../b2b_client/API_CLIENT_INSTITUTIONS.md)

---

## 8. Archived source docs (merged into this guideline)

The following docs were merged into this single guideline and are no longer updated; they are archived under `docs/zArchive/api/shared_client/` for reference only:

- MARKET_BASED_SUBSCRIPTIONS.md  
- MARKET_COUNTRY_FLAG_UI_PATTERN.md  
- MARKET_MIGRATION_GUIDE.md  
- MARKET_SCOPE_FOR_CLIENTS.md  

Use **this document** as the single source for market and scope behavior for both agents and clients.
