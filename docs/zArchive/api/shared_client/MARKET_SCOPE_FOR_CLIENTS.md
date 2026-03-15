# Markets and market scope for clients (B2B and B2C)

**Audience:** B2B and B2C client app teams and agents  
**Purpose:** Single reference for the **Markets API** (endpoints, types, selector implementation) and **market scope** (how market_id / country_code are used, user assignment, Global Marketplace rule, and client dropdown behavior). Applies to both B2B and B2C.

**Last updated:** 2026

---

## 1. Overview

**Markets** are country-level subscription regions (currency, timezone, plans). The **Markets API** provides the list of available markets (public and enriched) and CRUD for admins. **Market scope** is how the app uses one selected market (or the user’s assigned market) to scope leads, explore, plans, and subscriptions. B2C uses a single “flag” (selected market) in context; B2B may use the employee’s assigned market(s) from GET /users/me. See [USER_AND_MARKET_API_CLIENT.md](./USER_AND_MARKET_API_CLIENT.md) for user–market storage and GET /users/me.

---

## 2. Global Marketplace rule (critical for both clients)

**Global Marketplace** is a special market (`market_id = 00000000-0000-0000-0000-000000000001`, country_code `GL`). It is **only for user assignment**: it means “this user is not constrained by market when querying.” It is **not** a valid market for plans, subscriptions, or any other entity.

- **Backend:** The API **rejects** Global Marketplace for any non-user entity. For example, **plan create** and **plan update** must not accept `market_id` = Global; the backend returns **400 Bad Request** with a message that Global cannot be assigned to that entity.
- **Client obligation:** **Both B2B and B2C** must **exclude Global Marketplace** from any dropdown (or picker) used when **creating or editing** entities that take `market_id` (e.g. **plan**, and any other such object). If the client sends Global for those endpoints, the backend returns a **validation error (400)**.
- **Safe source for dropdowns:** **GET /api/v1/markets/available** already **excludes** Global Marketplace. Use it as the source for “plan market” (and any other entity market) dropdowns so that Global is never sent. If the client uses another list that includes Global (e.g. an admin list of all markets), they must **filter out** Global for plan (and any non-user) flows.

---

## 3. Markets API reference

### 3.1 Why markets matter

1. **Multi-Currency Support**: Each market uses a specific credit currency for transactions.  
2. **Localized Plans**: Subscription plans are market-specific.  
3. **Timezone Management**: Each market has its own timezone for time-based operations.  
4. **Regulatory Compliance**: Markets enable country-specific business rules.

### 3.2 Public endpoint: GET /api/v1/markets/available

- **Auth:** None (public). **Rate-limited** (e.g. 60 req/min per IP). **Cached** on the server.
- **Response:** Array of minimal market objects (active, non-archived **and excluding Global Marketplace**). Use this as the **single source of truth** for the market selector and for **plan/entity market dropdowns** so Global is never sent.
- **429** when rate limit exceeded.

**Response shape:**

```json
[
  {
    "market_id": "11111111-1111-1111-1111-111111111111",
    "country_code": "AR",
    "country_name": "Argentina",
    "timezone": "America/Argentina/Buenos_Aires",
    "currency_code": "ARS",
    "currency_name": "Argentine Peso"
  }
]
```

### 3.3 Enriched and base endpoints (authenticated)

- **GET /api/v1/markets/enriched/** — List markets with currency details. Query: `include_archived` (default false).
- **GET /api/v1/markets/enriched/{market_id}** — Single market by ID.
- **GET /api/v1/markets/** — Base list (any authenticated user).
- **POST /api/v1/markets/** — Create market (Super Admin only). Body: `country_code`, `credit_currency_id`, `timezone`, `status`.
- **PUT /api/v1/markets/{market_id}** — Update (Super Admin only; Global market editable only by Super Admin).
- **DELETE /api/v1/markets/{market_id}** — Soft delete (Super Admin only). **Global Marketplace cannot be archived** (400).

### 3.4 Authorization

| Role           | GET | POST | PUT | DELETE |
|----------------|-----|------|-----|--------|
| Super Admin    | Yes | Yes  | Yes | Yes    |
| Admin Employee | Yes | No   | No  | No     |
| Supplier       | Yes | No   | No  | No     |
| Customer       | Yes | No   | No  | No     |

### 3.5 TypeScript interfaces

```typescript
interface MarketAvailable {
  market_id: string;
  country_code: string;   // ISO 3166-1 alpha-2
  country_name: string;
  timezone: string;
  currency_code: string | null;
  currency_name: string | null;
}

interface Market {
  market_id: string;
  country_name: string;
  country_code: string;
  credit_currency_id: string;
  currency_name: string;
  currency_code: string;
  timezone: string;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}
```

### 3.6 Client implementation: market selector

1. **Fetch:** Call `GET /api/v1/markets/available` on app load; cache with short TTL.  
2. **Default:** Use browser locale or geo to match `country_code`; fallback to US (or first market).  
3. **Store:** Keep `market_id` and `country_code` in app state or localStorage.  
4. **Use:** For endpoints that take `market_id` or `country_code`, send the stored value. For **plan create** and any entity that takes `market_id`, use **only** the list from `/markets/available` (or filter out Global if using another source).

See **§4** for where `market_id` vs `country_code` is used. React/TypeScript examples for selector and dropdowns (browser default, persistence, React hook) follow the same patterns with `GET /markets/available` as source; see archived Markets API doc in zArchive if a full copy is needed.

### 3.7 Best practices

1. Use **GET /markets/available** for the market selector and for plan/entity dropdowns (it excludes Global).  
2. Cache market data with a reasonable TTL.  
3. Display full context in UI (e.g. "Argentina (ARS)").  
4. Filter out archived markets in dropdowns unless explicitly needed.

---

## 4. Market selector and scope (B2C and B2B)

### 4.1 Data source

- **Endpoint:** **GET /api/v1/markets/available** (no auth).  
- **When:** On app load or when the market selector is first shown.  
- B2C uses the same list on marketing home (pre-login) and inside the app (post-login).

### 4.2 State: single selected market (B2C pattern)

- **State:** `markets: MarketAvailable[]`, `selectedMarket: MarketAvailable | null`, `setSelectedMarket(market | null)`.  
- **Initial selection:** If logged in, call **GET /users/me** and use `market_id` (or `market_ids[0]`) to resolve against `markets` and set `selectedMarket`. Else use device locale or fallback to US.  
- **Persistence:** After login, GET /users/me returns `market_id` and `market_ids` so the selector can be restored. See [USER_AND_MARKET_API_CLIENT.md](./USER_AND_MARKET_API_CLIENT.md).

### 4.3 Where market_id vs country_code is used

| Area        | API / usage                          | Parameter     | Source (B2C)              |
|-------------|--------------------------------------|---------------|----------------------------|
| Lead cities | GET /api/v1/leads/cities             | `country_code`| `selectedMarket?.country_code` |
| Lead city-metrics | GET /api/v1/leads/city-metrics | `country_code`| `selectedMarket?.country_code` |
| Explore restaurants | GET /api/v1/restaurants/cities, by-city | `country_code` | `selectedMarket?.country_code` |
| Plans (enriched) | GET /api/v1/plans/enriched/    | `market_id`   | `selectedMarket?.market_id` (must not be Global) |
| Subscriptions | POST /api/v1/subscriptions/ (plan_id) | —          | Plans listed per `market_id` |

**Country code normalization:** Use alpha-2 where the API expects `country_code`; default when omitted is `"US"` per [COUNTRY_CODE_API_CONTRACT.md](./COUNTRY_CODE_API_CONTRACT.md).

### 4.4 Backend behavior when params omitted

| API / area | Parameter     | When omitted | Backend behavior |
|------------|---------------|--------------|------------------|
| Leads (cities, city-metrics) | `country_code` | Optional; default **US** | Backend uses US. No error. |
| Restaurants (cities, by-city) | `country_code` | Optional; default **US** | Backend uses US. No error. |
| Plans GET /plans/enriched/ | `market_id` | Optional | **Omitted** → no filter → all plans. **Empty string** → 422 (invalid UUID). Send a valid UUID or omit. **Global** → 400 (Global cannot be assigned to plan). |

**B2C recommendation (plans):** Do not send `market_id` when there is no selection (omit the param). Sending `''` causes 422. Only call GET /plans/enriched/ when you have a valid non-Global `market_id`, or omit to see all plans. When creating/updating a **plan**, send only a `market_id` from GET /markets/available (never Global).

### 4.5 Flow summary (B2C)

1. App load → GET /markets/available → set `markets` and initial `selectedMarket` (device region or US).  
2. User changes market → pick market → `setSelectedMarket(market)`.  
3. Lead flows → use `selectedMarket?.country_code`.  
4. Explore → use `selectedMarket?.country_code`.  
5. Select plan → use `selectedMarket?.market_id` for GET plans/enriched and subscription creation (must not be Global for plan create).  
6. After login → GET /users/me and use `market_id` / `market_ids[0]` to restore `selectedMarket`.

### 4.6 B2B planning takeaways

- **Single selected market:** B2C uses one global selection; B2B may use one per user/session or the employee’s assigned market(s).  
- **Same list:** GET /markets/available is the source for the selector; no auth required. Use it for plan/entity dropdowns so Global is never sent.  
- **Two parameter shapes:** APIs take either `country_code` (leads, restaurants) or `market_id` (plans, subscriptions).  
- **Country codes:** Normalize to alpha-2; default US when omitted. See [COUNTRY_CODE_API_CONTRACT.md](./COUNTRY_CODE_API_CONTRACT.md).

---

## 5. B2B client: market scope for Support / restaurant search

**Context:** Support Managers (assigned per market) search for restaurants to support. Search must be scoped by the employee’s assigned market.

### 5.1 Guardrails

- **Always send context:** Send `country_code` or `market_id` on every restaurant search/list used for support. Do not rely on name-only search without context.  
- Prefer **market_id** when the backend supports it.

### 5.2 User–market assignment

- **Model:** Each Support Manager has one or more assigned markets (primary in `user_info.market_id`; v2: `user_market_assignment`).  
- **GET /users/me** returns `market_id` (primary) and `market_ids` (all, primary first).  
- **B2B:** After login, use `market_id` (or `market_ids[0]`) from GET /users/me as the assigned market for restaurant search/list. For **Global** users (see below), send the Global market_id for query scope; do **not** use Global for plan create/update dropdowns.

### 5.3 Global Marketplace and roles that see all markets

- **Global employees:** Employee Admin, Super Admin, Supplier Admin (when intended to see across markets) can be assigned the **Global Marketplace** `market_id`. Backend treats that id as “no market filter” for **query** scope.  
- **Global is only for user assignment:** Do **not** send Global as `market_id` when creating or updating **plans** or any other entity; backend returns 400.  
- **B2B:** For users with the Global market assigned, send that `market_id` for **query** endpoints (e.g. restaurant list) so the backend does not filter by market. For **plan create** and similar dropdowns, use GET /markets/available (which excludes Global) or filter Global out.

### 5.4 Summary for B2B

| Concern | Recommendation |
|--------|----------------|
| Restaurant search guardrails | Always send **country_code** and/or **market_id** for support-side restaurant search/list. |
| Context source | Use **market_id** from GET /users/me (assigned market). |
| Global roles | Assign **Global Marketplace** to Admin/Super Admin/Supplier Admin for query scope; send that id for list endpoints. For **plan/entity create** dropdowns, exclude Global (use GET /markets/available or filter). |
| Consistency | Prefer always sending `market_id` for query scope (including Global when user is global). Never send Global for plan (or any non-user entity) create/update. |

---

## 6. Related documentation

- [USER_AND_MARKET_API_CLIENT.md](./USER_AND_MARKET_API_CLIENT.md) — User–market storage, GET /users/me (`market_id`, `market_ids`), B2C/B2B usage.  
- [MARKET_BASED_SUBSCRIPTIONS.md](./MARKET_BASED_SUBSCRIPTIONS.md)  
- [ENRICHED_ENDPOINT_PATTERN.md](./ENRICHED_ENDPOINT_PATTERN.md)  
- [API_PERMISSIONS_BY_ROLE.md](./API_PERMISSIONS_BY_ROLE.md)  
- [COUNTRY_CODE_API_CONTRACT.md](./COUNTRY_CODE_API_CONTRACT.md)
