# Leads Coverage Checker — Marketing Site Integration

**Audience:** vianda-home (marketing site) agent  
**Backend base URL:** `VITE_API_BASE_URL` env var (e.g. `https://api.dev.vianda.market`)  
**Auth:** None — all endpoints are public, unauthenticated  
**Bot protection:** reCAPTCHA v3 required on most `/leads/*` calls. **Exceptions:** `/leads/countries` and `/leads/supplier-countries` are navbar-load fetches and do not require a token. See the reCAPTCHA section below.

---

## Overview

The marketing site is the top-of-funnel qualification tool. Visitors check if their area is served, explore featured restaurants and pricing, and express interest if not yet served. All data comes from the backend's existing database — no paid external APIs are called.

---

## Endpoints

### Country Selector — Site-Wide Scoping

The marketing site runs a single country selector in the navbar; every country-scoped surface
reads from it. Two endpoints drive this selector depending on audience.

#### 0a. Customer-facing country list
```
GET /api/v1/leads/countries?language={locale}
```

Returns markets with `status='active'` — countries currently serving customers. Drives the
navbar country selector and scopes plans, restaurants, featured-restaurant, coverage checker,
and metrics.

**Response (envelope):**
```json
{
  "countries": [{ "code": "AR", "name": "Argentina", "currency": "ARS", "phone_prefix": "+54", "default_locale": "es" }],
  "suggested_country_code": "AR"
}
```
- `countries` — array of country objects (same items as before the envelope was added)
  - `code` — ISO 3166-1 alpha-2 (e.g. `"AR"`)
  - `name` — localized per `language`
  - `currency` — ISO 4217 code (e.g. `"ARS"`)
  - `phone_prefix` — E.164 dial code, may be `null` for pseudo-markets
  - `default_locale` — one of `en`, `es`, `pt`
- `suggested_country_code` — ISO 3166-1 alpha-2 of the visitor's country inferred from the
  `cf-ipcountry` request header (set by Cloudflare). `null` when:
  - Cloudflare is not in the deploy chain (Cloud Run direct — current state),
  - the header is absent or the value is `"XX"` (CF sentinel for unresolvable IPs), or
  - the resolved code is not present in the returned `countries` list.
  Treat `null` as "no suggestion available" and fall back to your own default.

**BREAKING CHANGE (kitchen #217):** The former array-at-root response is replaced by an
object envelope. Consumers must read `response.countries` instead of `response` directly.
The only consumer is vianda-home (vianda-home#96 migrates simultaneously).

**Empty countries contract:** `countries: []` means no markets currently serve customers. The
frontend hides the navbar country selector and every country-scoped section (plans, restaurants,
featured-restaurant, coverage checker, metrics). Country-agnostic sections (hero, how-it-works,
footer, supplier CTA) stay visible. The supplier application form is unaffected — it reads
`/leads/supplier-countries`.

**Caching:** `Cache-Control: private, no-store`.
The response contains a per-visitor `suggested_country_code` — shared caches (CDN / reverse
proxy) must not serve one visitor's suggestion to another. The countries list itself is served
from a 10-minute in-process cache per locale; only the suggestion varies per-request.

**reCAPTCHA:** **not required** — this is a navbar-load fetch called on every page render.

**Rate limit:** 60/min per IP.

#### 0b. Supplier-facing country list
```
GET /api/v1/leads/supplier-countries?language={locale}
```

Superset of `/leads/countries`: markets with `status IN ('active', 'inactive')`. `inactive`
markets are configured in `market_info` but not yet serving customers — suppliers can still
apply, and we capture interest ahead of launch.

**Response:** same envelope shape as `/leads/countries` (see §0a above).
`suggested_country_code` resolves against the supplier-countries list; a code present in
`/leads/supplier-countries` but absent from `/leads/countries` (inactive market) can still be
suggested to a visitor from that country.

**Empty countries contract:** `countries: []` means no markets are configured at all. Frontend
renders `RestaurantApplicationForm` **without** the country dropdown and promotes
`mailto:partners@vianda.market` as the primary CTA.

**Caching, reCAPTCHA, and rate limit:** same as `/leads/countries` (private, no-store;
no reCAPTCHA; 60/min per IP).

**Automated status maintenance (planned, not in v1):** the `active`/`inactive` flips are
currently admin-maintained. The daily auto-flip cron is covered in
`docs/plans/market-status-cron.md` (pending implementation).

### Coverage Check Flow

#### 1. Country dropdown (legacy — prefer `/leads/countries`)
```
GET /api/v1/leads/markets?language={locale}
```
Returns active markets with country name, language, phone prefix. Use for country selector.

**Audience parameter:**

| Call | Returns | Use case |
|------|---------|----------|
| `GET /leads/markets` (no param) | Only markets with **active vianda coverage** | Customer coverage checker, customer interest form |
| `GET /leads/markets?audience=supplier` | All active non-global markets | Supplier/employer interest forms (they need to see all countries to express interest in markets we haven't launched yet) |

The default (no param) is intentionally restrictive — if the parameter is missing or unrecognized, only served countries are returned.

**Caching:** `Cache-Control: public, max-age=60` when the market list is non-empty. `Cache-Control: no-store` when empty (see [Cache semantics on /leads/markets and /leads/cities](#cache-semantics-on-leadsmarkets-and-leadscities) below).

**Response:** `[{ country_code, country_name, language, phone_dial_code, phone_local_digits, locale }]`

#### 2. City dropdown (after country selected)
```
GET /api/v1/leads/cities?country_code={code}
GET /api/v1/leads/cities?country_code={code}&audience=supplier
```

**Default (no `audience` param):** Returns city names that have at least one active restaurant with viandas and QR codes.

**`audience=supplier`:** Returns a broader union of city names from three sources:
- `external.geonames_city` (GeoNames raw data for the country)
- `core.city_metadata` (Vianda-curated cities)
- `ops.restaurant_lead.city_name` (cities from supplier interest submissions)

Sort: alphabetical, case-insensitive. Cap: 1000 rows.

**Non-empty guarantee:** For any country returned by `GET /leads/markets?audience=supplier`, the supplier-audience cities response is guaranteed non-empty.

**Caching:** `Cache-Control: public, max-age=60` when the city list is non-empty. `Cache-Control: no-store` when the list is empty (see [Cache semantics on /leads/markets and /leads/cities](#cache-semantics-on-leadsmarkets-and-leadscities) below).

**Response:** `{ cities: ["Buenos Aires", "Lima", ...] }`

#### 3. Coverage check — zipcode first, city fallback
```
GET /api/v1/leads/zipcode-metrics?zip={zipcode}&country_code={code}
GET /api/v1/leads/city-metrics?city={name}&country_code={code}
```

**Frontend flow:**
1. If user entered a zipcode → call `/zipcode-metrics`
2. If `has_coverage: true` → show zipcode results + app download CTA
3. If `has_coverage: false` → fall back to `/city-metrics` for selected city
4. If city has coverage → show: "No restaurants in your zipcode yet, but X serve your city. Remove the zipcode to see all results." + app download CTA
5. If city also has no coverage → show "Notify me" form

**Zipcode response:** `{ requested_zipcode, matched_zipcode, restaurant_count, has_coverage }`  
**City response:** `{ requested_city, matched_city, restaurant_count, has_coverage }`

### Marketing Content

#### 4. Restaurant list
```
GET /api/v1/leads/restaurants?language={locale}&country_code={CC}&featured={bool}&limit={int}
```
Active restaurants for grid display, **scoped to a country**. `featured=true` filters to featured only. Default limit 12, max 50.

- `country_code` is **required** (ISO 3166-1 alpha-2). Missing/empty → `400 {"detail": "country_code is required"}`.
- Unsupported or supported-but-empty country → `[]` (HTTP 200), cacheable.

**Response:** `[{ restaurant_id, name, cuisine_name, tagline, average_rating, review_count, cover_image_url }]`

#### 5. Featured restaurant spotlight
```
GET /api/v1/leads/featured-restaurant?language={locale}&country_code={CC}
```
Single featured restaurant with spotlight label, badge, and perks, **scoped to a country**.

- `country_code` is **required**. Missing/empty → `400`.
- **No match for the requested country → JSON body `null`, HTTP 200, `Content-Type: application/json`.** The legacy 404 response has been retired — callers must handle a literal `null` body.

**Response (match):** `{ restaurant_id, name, cuisine_name, tagline, average_rating, review_count, cover_image_url, spotlight_label, verified_badge, member_perks }`
**Response (no match):** `null`

#### 6. Pricing table
```
GET /api/v1/leads/plans?language={locale}&country_code={CC}
```
Active plans with currency, **scoped to a country**. All prices are monthly. `highlighted: true` indicates the recommended plan.

- `country_code` is **required**. Missing/empty → `400`.
- Unsupported or supported-but-empty country → `[]` (HTTP 200), cacheable.

**Response:** `[{ plan_id, name, marketing_description, features, cta_label, credit, price, highlighted, currency }]`

### Form Enum Dropdowns

#### 7. Cuisine list (for interest forms)
```
GET /api/v1/leads/cuisines?language={locale}
```
Active cuisines for customer ("what cuisine interests you?") and supplier ("what do you serve?") dropdowns. Localized names.

**Response:** `[{ cuisine_id: "uuid", cuisine_name: "Mexican Home-Cooking" }]`

Use `cuisine_id` (UUID) as the value sent in `POST /leads/interest`. Frontend can use hardcoded fallbacks until this endpoint is available.

#### 8. Employee count ranges (for employer interest form)
```
GET /api/v1/leads/employee-count-ranges?language={locale}
```
Predefined company size ranges. Labels localized per language.

**Response:** `[{ range_id: "1-20", label: "1–20 employees" }]`

Use `range_id` as the value sent in `POST /leads/interest`. Static data, unlikely to change.

### Interest Capture

#### 9. Submit interest ("Notify me")
```
POST /api/v1/leads/interest
Content-Type: application/json
```

**Request body:**
```json
{
  "email": "user@example.com",
  "country_code": "US",
  "city_name": "Austin",
  "zipcode": "78701",
  "zipcode_only": false,
  "interest_type": "customer",
  "business_name": null,
  "message": null,
  "cuisine_id": null,
  "employee_count_range": null
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `email` | Yes | Contact email |
| `country_code` | Yes | ISO 3166-1 alpha-2 (e.g. "US") |
| `city_name` | For customer | City name from dropdown |
| `zipcode` | No | If user entered one |
| `zipcode_only` | No | Default `false`. `true` = only alert for this zipcode |
| `interest_type` | Yes | `customer`, `employer`, or `supplier` |
| `business_name` | For employer/supplier | Company or restaurant name |
| `message` | No | Free-text context (max 1000 chars) |
| `cuisine_id` | No | UUID from `GET /leads/cuisines`. For customer ("what cuisine?") and supplier ("what do you serve?") |
| `employee_count_range` | No | String from `GET /leads/employee-count-ranges`. For employer interest only. |

**Response (201):** `{ lead_interest_id, email, country_code, city_name, zipcode, zipcode_only, interest_type, business_name, message, cuisine_id, employee_count_range, status, source, created_date }`

**Rate limit:** 5 requests/minute per IP. Returns 429 on excess.

---

## Multi-Audience Interest Forms

The `POST /leads/interest` endpoint supports three audiences via `interest_type`:

1. **Customer** (`"customer"`) — "Notify me when restaurants are in my area." Shown on the coverage checker unserved/partially-served path. Fields: email, country, city, zipcode, zipcode_only.

2. **Employer** (`"employer"`) — "I want to offer Vianda's meal benefit program to my employees." Place near the Employer Programs or For Businesses section. Fields: email, business_name, country, optional city, optional message.

3. **Supplier** (`"supplier"`) — "I'm a restaurant and want to join Vianda." Place near the Local Kitchens or "Partner with us" area. Fields: email, business_name, country, city, optional message.

UX placement (separate forms, tabs, or distinct sections) is your design decision. All three use the same endpoint — just different `interest_type` values.

---

## reCAPTCHA v3 Integration

**Most `/api/v1/leads/*` calls must include a reCAPTCHA v3 token.** Requests without a valid token receive 403.

**Exceptions — tokens NOT required:**
- `GET /api/v1/leads/countries`
- `GET /api/v1/leads/supplier-countries`

These are navbar-load fetches executed on every page render and cannot sit behind a challenge. They are rate-limited (60/min per IP) and return cacheable responses with ETags, so the anti-scraping story relies on the per-IP limiter rather than a per-request token.

### Setup
1. Add reCAPTCHA v3 JS script to the page:
   ```html
   <script src="https://www.google.com/recaptcha/api.js?render={SITE_KEY}"></script>
   ```
   `SITE_KEY` is your public reCAPTCHA v3 site key (stored in vianda-home env config, e.g. `VITE_RECAPTCHA_SITE_KEY`).

2. Before each API call, execute:
   ```js
   const token = await grecaptcha.execute(SITE_KEY, { action: 'leads_coverage_check' })
   ```

3. Send the token as a header:
   ```
   X-Recaptcha-Token: {token}
   ```

### Action names (for reCAPTCHA admin console analytics)
Use distinct `action` values per endpoint type:
- `leads_coverage_check` — markets, cities, city-metrics, zipcode-metrics (normal calls)
- `leads_content` — restaurants, featured-restaurant, plans (normal calls)
- `leads_read` — **captcha retry only** — use this action when executing reCAPTCHA after a 429 with `captcha_required: true` on any country-scoped leads endpoint
- `leads_interest_submit` — POST /leads/interest
- *(no token)* — countries, supplier-countries

### Error handling
- **403 "Missing reCAPTCHA token"** — token header not sent
- **403 "reCAPTCHA verification failed"** — invalid token
- **403 "reCAPTCHA score too low"** — bot detected (score below threshold)

---

## Localization

All GET endpoints accept a `?language=` query param (`en`, `es`, `pt`). Falls back to `Accept-Language` header. Your `apiFetch` client already sends `Accept-Language` from localStorage — just add `?language=` for explicit control.

Localized fields: country names, cuisine names, taglines, plan names/descriptions/features/CTA labels, spotlight labels, member perks.

---

## SEO Requirements

SEO is critical for this migration — without it, users land on the app store first and bypass the marketing site.

- **Meta tags and Open Graph:** Per-page title, description, og:image. Especially for coverage checker.
- **Structured data (JSON-LD):** `Organization` markup for Vianda. `FoodEstablishment` for served areas.
- **Sitemap:** Dynamic sitemap including served cities. Generate from `/leads/cities` data at build time.
- **Canonical URLs:** Clean, shareable URL for coverage checker (e.g. `vianda.market/check-coverage?city=Austin&country=US`).
- **Core Web Vitals:** Fast first load. Lazy-load below-fold sections.

---

## Analytics Events (Firebase Analytics)

| Event | Params | When |
|-------|--------|------|
| `coverage_check` | country, city, zipcode, result (served/unserved/partial) | After coverage result displayed |
| `interest_submitted` | country, city, zipcode, interest_type | After successful POST /leads/interest |
| `app_download_click` | source_section | User clicks app store link |
| `plan_viewed` | plan_id, plan_name | Plans section enters viewport |
| `restaurant_card_clicked` | restaurant_id | User clicks a restaurant card |

Parse and forward UTM params from marketing campaigns. Firebase Analytics handles this automatically.

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/leads/countries` | 60/min per IP |
| `/leads/supplier-countries` | 60/min per IP |
| `/leads/markets` | 60/min per IP |
| `/leads/cities` | 20/min per IP |
| `/leads/city-metrics` | 20/min per IP |
| `/leads/zipcode-metrics` | 20/min per IP |
| `/leads/restaurants` | 60/min per IP |
| `/leads/featured-restaurant` | 60/min per IP |
| `/leads/plans` | 60/min per IP |
| `/leads/cuisines` | 60/min per IP |
| `/leads/employee-count-ranges` | 60/min per IP |
| `POST /leads/interest` | 5/min per IP |

429 response shape — all endpoints:
```json
{
  "detail": {
    "code": "request.rate_limited",
    "message": "Too many requests. Please try again later.",
    "params": { "retry_after_seconds": 60 }
  }
}
```
The response also includes a `Retry-After: 60` header.

**Captcha-on-rate-limit (country-scoped reads only):** When the rate limit is tripped on
`/leads/plans`, `/leads/restaurants`, `/leads/featured-restaurant`, `/leads/cities`,
`/leads/city-metrics`, or `/leads/zipcode-metrics`, the 429 body carries two **additive**
fields on top of the standard envelope:
```json
{
  "detail": { "code": "request.rate_limited", "message": "...", "params": { "retry_after_seconds": 60 } },
  "captcha_required": true,
  "action": "leads_read"
}
```
Frontend flow: detect `captcha_required: true` → execute `grecaptcha.execute(SITE_KEY, { action: "leads_read" })` → retry the request with `X-Recaptcha-Token: <token>` → the backend validates the token and, if valid, lets the request through (200).

`/leads/countries` and `/leads/supplier-countries` never carry `captcha_required` — they are exempt from the captcha gate.

---

## Response Field Naming

The backend returns **snake_case** field names (e.g. `restaurant_id`, `cover_image_url`, `interest_type`). Your TypeScript types currently use camelCase. Add a response transform or update your types to match snake_case.

---

## Corrections to Existing Frontend Stubs

The following items in `src/api/types.ts` need updating:
- `PublicPlan.yearlyPrice` — **remove**. All prices are monthly. No `yearly_price` field exists.
- `PlatformMetrics` type — **keep as stub**. The `/leads/platform-metrics` endpoint is deferred (early-stage numbers aren't compelling). Keep using placeholder data until backend ships this endpoint.

---

## Country-Scoped Endpoint Contract (reference table)

| Endpoint | `country_code` param | Missing param | Unsupported country |
|---|---|---|---|
| `/leads/countries` | n/a (returns the envelope) | — | — |
| `/leads/supplier-countries` | n/a | — | — |
| `/leads/markets` | key of the row, implicit | returns all | — |
| `/leads/cities` | optional, defaults to `US` | returns `US` cities | empty list |
| `/leads/city-metrics` | optional, defaults to `US` | evaluates against `US` | `has_coverage: false` |
| `/leads/zipcode-metrics` | optional, defaults to `US` | evaluates against `US` | `has_coverage: false` |
| `/leads/plans` | **required** | `400` | `[]`, 200 |
| `/leads/restaurants` | **required** | `400` | `[]`, 200 |
| `/leads/featured-restaurant` | **required** | `400` | `null`, 200 |

Legacy default-to-`US` on `/leads/cities`, `/leads/city-metrics`, and `/leads/zipcode-metrics` predates the country selector and is kept for backward compatibility; the marketing site should pass `country_code` explicitly.

---

## Error Code Conventions

- **`400`** — business-rule violation (e.g. missing required `country_code`).
- **`422`** — request-schema validation (FastAPI/Pydantic default, e.g. unknown `language`).

---

## Caching: private, no-store (kitchen #217)

Applies to `/leads/countries` and `/leads/supplier-countries` as of kitchen #217.

Both responses are now `Cache-Control: private, no-store` because the envelope includes
`suggested_country_code`, which is derived from the visitor's IP and therefore varies
per-visitor. A shared CDN cache serving one visitor's country suggestion to another visitor
would be incorrect.

The countries list itself is cached in-process (per locale, 10-minute TTL) on each API
worker pod. ETag / `If-None-Match` / `304` revalidation is no longer supported on these
endpoints — clients should issue a fresh GET on each page load (the response is small and
fast from the in-process cache).

**Former ETag strategy (option c — retired by #217):**
The former design sent `Cache-Control: public, max-age=86400, stale-while-revalidate=3600`
with an ETag hashed over `(code, currency, phone_prefix, default_locale,
market_info.modified_date, currency_metadata.modified_date, locale)`. This was valid when
the response was a plain list and could be shared across visitors. The envelope response
makes per-visitor sharing incorrect.

## Cache semantics on /leads/markets and /leads/cities

These are admin-mutable content endpoints — markets get activated, cities get populated as restaurants onboard. The cache policy is designed so that admin activation propagates to end-users within ~60 seconds, and a clean-state user who hits the endpoint before activation is never trapped behind a stale empty response.

| Endpoint | Populated response | Empty response |
|---|---|---|
| `GET /leads/markets` | `Cache-Control: public, max-age=60` | `Cache-Control: no-store` |
| `GET /leads/cities` (default + coverage modes) | `Cache-Control: public, max-age=60` | `Cache-Control: no-store` |
| `GET /leads/email-registered` | `Cache-Control: no-store` | `Cache-Control: no-store` |

**Why `max-age=60` (not 3600):** Admin activates a market (marks it active, adds a restaurant, configures a vianda, adds a QR). Under the old 1-hour TTL, the customer signup dropdowns would not reflect the activation for up to 60 minutes. Under `max-age=60`, propagation lag is at most ~60 seconds — matching the server-side process-local in-memory cache TTL.

**Why `no-store` on empty:** An empty list means the country has not yet been activated. If a pre-activation user's request returns `[]` and CDN/browser caches it for 60 seconds (or longer), they will see empty dropdowns even after admin completes activation. `no-store` prevents any intermediate cache from holding an empty response, so the next page load fetches fresh data.

**Why `no-store` on email-registered unconditionally:** This is an auth-flow query — whether an email exists changes on every signup. Caching a `registered: false` response could route a newly-signed-up user to the signup form instead of login. No caching semantics apply.

**Note for vianda-home:** Do not add client-side caching for `/leads/markets` or `/leads/cities` beyond what the browser default provides from the `Cache-Control` header. If you add a query-level cache (e.g. React Query `staleTime`), set it to ≤60s for markets/cities. For `email-registered`, set `staleTime: 0` or disable caching entirely.

---

## Server-Side Cache Semantics

- Both country endpoints use a process-local, locale-keyed cache with a 10-minute TTL for the
  countries list (mirrors `_markets_cache` / `_cities_cache`).
- `suggested_country_code` is computed per-request from the `cf-ipcountry` header and is never
  cached — it is derived from the request, not the data.
- **Per-worker visibility:** when an admin flips a market to `active`/`inactive`, other workers
  pick up the change within 10 minutes. There is no client-side browser cache (responses are
  `private, no-store`), so end users see fresh data on their next page load after the worker
  TTL expires.
- **Redis:** scaffolded in the repo but not used for this feature. A shared cross-worker cache
  isn't needed at the current change frequency. Considered, deferred.

## Future "All Countries" View

The `is_global_market` sentinel row in `market_info` (UUID `00000000-0000-0000-0000-000000000001`) is the intended primitive for a future "global / all countries" aggregate view. The country endpoints exclude it today. Any later work that exposes per-country metrics in an aggregate form should start from this row rather than introducing a new "global" mechanism.
