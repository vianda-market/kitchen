# Leads Coverage Checker — Marketing Site Integration

**Audience:** vianda-home (marketing site) agent  
**Backend base URL:** `VITE_API_BASE_URL` env var (e.g. `https://api.dev.vianda.market`)  
**Auth:** None — all endpoints are public, unauthenticated  
**Bot protection:** reCAPTCHA v3 required on all `/leads/*` calls (see section below)

---

## Overview

The marketing site is the top-of-funnel qualification tool. Visitors check if their area is served, explore featured restaurants and pricing, and express interest if not yet served. All data comes from the backend's existing database — no paid external APIs are called.

---

## Endpoints

### Coverage Check Flow

#### 1. Country dropdown
```
GET /api/v1/leads/markets?language={locale}
```
Returns active markets with country name, language, phone prefix. Use for country selector.

**Audience parameter:**

| Call | Returns | Use case |
|------|---------|----------|
| `GET /leads/markets` (no param) | Only markets with **active plate coverage** | Customer coverage checker, customer interest form |
| `GET /leads/markets?audience=supplier` | All active non-global markets | Supplier/employer interest forms (they need to see all countries to express interest in markets we haven't launched yet) |

The default (no param) is intentionally restrictive — if the parameter is missing or unrecognized, only served countries are returned.

**Response:** `[{ country_code, country_name, language, phone_dial_code, phone_local_digits, locale }]`

#### 2. City dropdown (after country selected)
```
GET /api/v1/leads/cities?country_code={code}
GET /api/v1/leads/cities?country_code={code}&audience=supplier
```

**Default (no `audience` param):** Returns city names that have at least one active restaurant with plates and QR codes.

**`audience=supplier`:** Returns a broader union of city names from three sources:
- `external.geonames_city` (GeoNames raw data for the country)
- `core.city_metadata` (Vianda-curated cities)
- `core.restaurant_lead.city_name` (cities from supplier interest submissions)

Sort: alphabetical, case-insensitive. Cap: 1000 rows.

**Non-empty guarantee:** For any country returned by `GET /leads/markets?audience=supplier`, the supplier-audience cities response is guaranteed non-empty.

**Caching:** The cities response includes `Cache-Control: public, max-age=3600`.

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
GET /api/v1/leads/restaurants?language={locale}&featured={bool}&limit={int}
```
Active restaurants for grid display. `featured=true` filters to featured only. Default limit 12, max 50.

**Response:** `[{ restaurant_id, name, cuisine_name, tagline, average_rating, review_count, cover_image_url }]`

#### 5. Featured restaurant spotlight
```
GET /api/v1/leads/featured-restaurant?language={locale}
```
Single featured restaurant with spotlight label, badge, and perks. Returns 404 if none is featured.

**Response:** `{ restaurant_id, name, cuisine_name, tagline, average_rating, review_count, cover_image_url, spotlight_label, verified_badge, member_perks }`

#### 6. Pricing table
```
GET /api/v1/leads/plans?language={locale}
```
All active plans with currency. All prices are monthly. `highlighted: true` indicates the recommended plan.

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

**Every `/api/v1/leads/*` call must include a reCAPTCHA v3 token.** Requests without a valid token receive 403.

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
- `leads_coverage_check` — markets, cities, city-metrics, zipcode-metrics
- `leads_content` — restaurants, featured-restaurant, plans
- `leads_interest_submit` — POST /leads/interest

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

429 response shape (structured):
```json
{ "detail": "rate_limited", "retry_after_seconds": 42 }
```
The response also includes a `Retry-After` header (seconds until the limit resets).

---

## Response Field Naming

The backend returns **snake_case** field names (e.g. `restaurant_id`, `cover_image_url`, `interest_type`). Your TypeScript types currently use camelCase. Add a response transform or update your types to match snake_case.

---

## Corrections to Existing Frontend Stubs

The following items in `src/api/types.ts` need updating:
- `PublicPlan.yearlyPrice` — **remove**. All prices are monthly. No `yearly_price` field exists.
- `PlatformMetrics` type — **keep as stub**. The `/leads/platform-metrics` endpoint is deferred (early-stage numbers aren't compelling). Keep using placeholder data until backend ships this endpoint.
