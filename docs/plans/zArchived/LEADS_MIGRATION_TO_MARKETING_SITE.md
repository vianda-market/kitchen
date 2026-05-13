# Leads Flow Migration: B2C App → Marketing Site

**Status:** Complete (Phase 1a/1b/1c done, Phase 2 done)  
**Decision date:** 2026-04-05  
**Affects:** kitchen (backend), vianda-home (marketing site), vianda-app (B2C mobile), vianda-platform (B2B — interest dashboard)

---

## Problem Statement

Today, the B2C mobile app owns the entire leads funnel: a new user downloads the app, picks a country and city, sees whether their area is served, and only then decides to register or express interest. Users who download the app and discover they are not served experience frustration, and the app collects negative sentiment (uninstalls, low ratings) from people who were never viable customers.

## Strategic Decision

Move the leads discovery flow to the vianda-home marketing site. The marketing site becomes the **top-of-funnel qualification tool**: visitors check coverage from a browser with zero commitment, and only download the app if they are in a served area. The B2C app becomes a product for qualified, served users — login, register, subscribe, explore, order.

**This is a one-way migration, not a dual-support scenario.** There is no backward compatibility layer. The B2C app will stop serving the leads exploration flow. The marketing site will not support login or authenticated sessions — it is purely a leads mechanism.

---

## What Moves to the Marketing Site

### Coverage check flow (core leads funnel)
1. **Country selector** — dropdown from `GET /leads/markets`
2. **City selector** — dropdown from `GET /leads/cities?country_code={code}`
3. **Optional zipcode input** — free-text field, not required. When provided, queries `GET /leads/zipcode-metrics` first. If no restaurants match the zipcode, the system falls back to city-level results from `GET /leads/city-metrics` with messaging: "No restaurants in your zipcode yet, but X restaurants serve your city." A note indicates they can remove the zipcode to see all city results.
4. **City metrics display** — restaurant count, "you're served" / "not yet here" from `GET /leads/city-metrics`
5. **Interest expression** — "notify me" form for unserved areas. Captures email, country, city, and optionally zipcode. Available in two scenarios: (a) country/city has no coverage at all, (b) zipcode has no coverage but city does — user can still express zipcode-level interest to be notified when restaurants open closer to them.
6. **App download CTA** — shown when coverage is confirmed (city or zipcode level); deep link or store link

### Marketing content (already planned in vianda_home_apis.md)
7. **Platform metrics** — trust bar with kitchen count, savings, revenue (`GET /leads/platform-metrics`)
8. **Featured restaurants** — kitchen grid and spotlight (`GET /leads/restaurants`, `GET /leads/featured-restaurant`)
9. **Pricing table** — public plans (`GET /leads/plans`)

Items 7–9 are already planned in `docs/plans/vianda_home_apis.md` and have frontend stubs ready in vianda-home. This plan does not replace that doc — it extends the scope to include items 1–6 and coordinates the B2C app and B2B dashboard changes.

---

## What Stays in the B2C App

The B2C app retains the **minimum leads API surface needed for registration**:

| What | Why it stays | Endpoint |
|------|-------------|----------|
| Country dropdown | Required for signup form (country_code is required field) | `GET /leads/markets` |
| City dropdown | Required for signup form (city_name is required field) | `GET /leads/cities?country_code={code}` |
| Email check | Determines login vs. signup routing at register screen | `GET /leads/email-registered?email={email}` |

**What is removed from the B2C app:**
- City metrics display (restaurant count, "has coverage" messaging)
- Zipcode metrics check
- Any pre-signup "explore your area" flow
- The decision gate "should I register or express interest?" — by the time a user opens the app, the marketing site has already qualified them

**The B2C app signup screen becomes:** select country → select city → enter name/email/password → verify email → done. If a user somehow arrives at the app without checking coverage (e.g., direct app store download) and selects a city that turns out to be unserved, the app shows a link to the marketing site's "notify me" page rather than a dead end. This bridges users back to the marketing site and introduces them to it.

---

## What the Marketing Site Does NOT Do

- **No login / authentication.** The marketing site has no concept of a logged-in user. Every visitor sees the same experience. There is no session, no JWT, no user context.
- **No paid API calls.** The marketing site must never trigger Mapbox, Stripe, or any metered external API. All data comes from the kitchen's own database.
- **No restaurant exploration.** The marketing site shows coverage (how many restaurants in your city) and marketing content (featured restaurants, plans). It does not show menus, viandas, kitchen days, or pickup windows. That is the app's job.
- **No signup.** Registration happens in the app. The marketing site provides the link/QR to download the app.

---

## Backend Changes Required

### Existing endpoints

The leads router (`app/routes/leads.py`) already serves most endpoints the marketing site needs. CORS is already `allow_origins=["*"]`. Rate limiting is already IP-based via slowapi.

| Endpoint | Already exists | Marketing site uses | B2C app keeps using |
|----------|---------------|-------------------|-------------------|
| `GET /leads/markets` | Yes | Yes | Yes (signup only) |
| `GET /leads/cities` | Yes | Yes | Yes (signup only) |
| `GET /leads/city-metrics` | Yes | Yes (fallback from zipcode) | No — removed from app |
| `GET /leads/zipcode-metrics` | Yes | Yes (primary when zipcode entered) | No — removed from app |
| `GET /leads/email-registered` | Yes | No | Yes (signup only) |
| `GET /leads/featured-restaurant` | Yes | Yes | No |
| `GET /leads/platform-metrics` | No — planned | Yes | No |
| `GET /leads/restaurants` | No — planned | Yes | No |
| `GET /leads/plans` | No — planned | Yes | No |
| `POST /leads/interest` | No — new | Yes | Yes (link from "not served" fallback) |

### Zipcode-metrics: reactivated, not deprecated
`GET /leads/zipcode-metrics` stays active and is used by the marketing site's coverage checker when a zipcode is provided. The flow is:
1. User enters zipcode → call `/leads/zipcode-metrics`
2. If `has_coverage: true` → show zipcode-level results + app download CTA
3. If `has_coverage: false` → fall back to `/leads/city-metrics` for the selected city
4. If city has coverage → show city results with note: "No restaurants in your zipcode yet, but X restaurants serve your city. Remove the zipcode to see all results."
5. If city also has no coverage → show "notify me" form

This fallback logic lives in the marketing site frontend, not in the backend. The two endpoints remain independent.

### New endpoints (from vianda_home_apis.md)
The three endpoints planned in `docs/plans/vianda_home_apis.md` (platform-metrics, restaurants, plans) are still needed. That plan remains valid and should be implemented as specified.

### Interest capture endpoint (new)

`POST /leads/interest` — captures "notify me" requests from unserved or under-served areas, as well as business interest from prospective employers and suppliers.

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
  "message": null
}
```

- `email` — required
- `country_code` — required
- `city_name` — required (for customer); optional for employer/supplier (they may be inquiring generally)
- `zipcode` — optional, included when user entered one
- `zipcode_only` — optional, default `false`. When `true`, the user only wants alerts about restaurants in their specific zipcode. When `false`, they want both zipcode-level and city-level alerts. Only meaningful for `interest_type: customer`.
- `interest_type` — required. One of: `customer` (default — "notify me when restaurants are in my area"), `employer` ("interested in the benefits program for my employees"), `supplier` ("interested in joining Vianda as a restaurant/kitchen")
- `business_name` — optional, relevant for `employer` and `supplier` types
- `message` — optional free-text, allows any interest type to include context

**Storage:** New `core.lead_interest` table. Fields: `lead_interest_id`, `email`, `country_code`, `city_name`, `zipcode`, `zipcode_only`, `interest_type` (enum: customer/employer/supplier), `business_name`, `message`, `status` (Active/Notified/Unsubscribed), `created_date`, `notified_date`, `source` (marketing_site/b2c_app).

**Rate limit:** 5/minute per IP.

**Two-tier alert system (future work — cron jobs):**
- **Zipcode alert ("Close to you"):** Triggered when a new restaurant opens in the user's zipcode. Message: "A new restaurant just opened near you in [zipcode]!" Sent to users with that zipcode regardless of `zipcode_only` flag.
- **City alert ("In your city"):** Triggered when new restaurants open in the user's city (periodic digest, not per-restaurant). Message: "X new restaurants opened in [city]!" Sent only to users where `zipcode_only = false`.

The cron jobs that power these alerts are future work — they follow the same pattern as existing cron services in `app/services/cron/`. The `lead_interest` table and `POST` endpoint come first; the alert crons are a separate implementation phase.

### Interest data — Internal visibility (B2B dashboard)

The interest capture data must be visible to Internal employees on the B2B platform (vianda-platform). This is a read-only view initially; actionable features (e.g., "mark as contacted", bulk export) can be added later.

**Backend:** New authenticated endpoint(s) for Internal role:
- `GET /leads/interest` — list all interest records with filters (country, city, zipcode, status, date range). Paginated. Internal auth required.
- Response includes aggregates useful for market expansion: count by city, count by zipcode, most-requested unserved areas.

**B2B platform (vianda-platform):** New section in the Dashboard & Core area — read-only table of interest records. Columns: email, country, city, zipcode, zipcode_only, created_date, status, source. Filterable and sortable. This is an Internal-only view (not visible to Suppliers or Employers).

### Rate limiting review
Current limits are reasonable for the marketing site's expected traffic:

| Endpoint | Current limit | Assessment |
|----------|--------------|------------|
| `/leads/markets` | 60/min per IP | Fine — cached, lightweight |
| `/leads/cities` | 20/min per IP | Fine — single dropdown load |
| `/leads/city-metrics` | 20/min per IP | Fine — one call per city selection |
| `/leads/zipcode-metrics` | 20/min per IP | Fine — one call per zipcode entry |
| `/leads/email-registered` | 10/min per IP | Not used by marketing site |
| `/leads/featured-restaurant` | 60/min per IP | Fine — single page load |
| Future: `/leads/platform-metrics` | 60/min (planned) | Fine — single page load |
| Future: `/leads/restaurants` | 60/min (planned) | Fine — single page load |
| Future: `/leads/plans` | 60/min (planned) | Fine — single page load |
| Future: `POST /leads/interest` | 5/min (proposed) | Strict — form submission |

### CAPTCHA — required for launch (reCAPTCHA v3)

Exposing the marketing site on the open web means bots will find and probe these endpoints for scraping. IP-based rate limiting alone is insufficient — bots rotate IPs. **CAPTCHA is a Phase 1 launch requirement, not a future enhancement.**

Full design details are in `docs/plans/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md`. The implementation for this migration:

- **Provider: Google reCAPTCHA v3** (decided 2026-04-05). Invisible, score-based (0.0 = bot, 1.0 = human). No user interaction — runs in the background on page load. Chosen because:
  - Already in the Google/Firebase ecosystem (Firebase Hosting, GCS, Cloud Run) — no new vendor
  - Truly invisible — zero friction on the marketing site coverage checker
  - Score-based allows tuning: start with lenient threshold (0.3), tighten if bots get through
  - Free tier: 1M assessments/month — well beyond current traffic horizon
  - If mobile protection is needed later, Google offers reCAPTCHA mobile SDKs (same project, same keys)
- **Frontend (vianda-home agent):** Load the reCAPTCHA v3 JS script with the site key. On each leads API call, execute `grecaptcha.execute(siteKey, { action: 'leads_coverage_check' })` to obtain a token. Send the token in a request header (`X-Recaptcha-Token`) on all `/leads/*` calls. Use distinct `action` values per endpoint for analytics in the reCAPTCHA admin console (e.g., `leads_coverage_check`, `leads_interest_submit`, `leads_plans`).
- **Backend (kitchen):** New FastAPI dependency (`verify_recaptcha`) that:
  1. Reads `X-Recaptcha-Token` header
  2. POSTs to `https://www.google.com/recaptcha/api/siteverify` with `secret` + `response` params
  3. Checks `success: true` and `score >= RECAPTCHA_SCORE_THRESHOLD` (configurable, default 0.3)
  4. Returns 403 if token is missing, invalid, or score is below threshold
  5. Exempt when `x-client-type: b2c-mobile` header is present (mobile apps don't send reCAPTCHA tokens; they use JWT auth as primary access control)
  6. Exempt when `RECAPTCHA_SECRET_KEY` env var is empty (local dev convenience — no CAPTCHA in dev)
  Applied to all `/leads/*` GET and POST endpoints via `Depends(verify_recaptcha)`.
- **Env vars:**
  - `RECAPTCHA_SECRET_KEY` — server-side secret key from Google reCAPTCHA admin console. Empty = CAPTCHA disabled (local dev).
  - `RECAPTCHA_SCORE_THRESHOLD` — minimum score to pass (default 0.3, range 0.0-1.0). Tunable without redeploy.
  - Site key (public, used by frontend only) is not stored in the backend — it lives in vianda-home's env config.
- **Fallback:** If Google's verify API is unreachable (network error, timeout), fail open (allow the request but log a warning). Availability of the coverage checker is more important than blocking 100% of bots during a provider outage.
- **Rate limiting stays in place** as a second layer. CAPTCHA blocks bots; rate limiting caps abuse from humans or bots that solve CAPTCHA.

### CORS tightening (Phase 1)

Currently `allow_origins=["*"]`. This must be tightened as part of Phase 1 — the marketing site going live on the open web makes a wildcard origin unacceptable.

**Mobile app behavior (confirmed by vianda-app agent):**

| Platform | Origin header | Notes |
|----------|--------------|-------|
| iOS native | None | NSURLSession — no browser sandbox, no Origin sent |
| Android native | None | OkHttp — same, no Origin sent |
| Expo Web (dev/preview) | `http://localhost:8081` (or Metro port) | Browser-based, sends Origin |
| Web production (if deployed) | TBD domain | Would need explicit allowlisting |

Native mobile apps bypass CORS entirely — the backend never sees an Origin from them. CORS is not a security control for mobile traffic; `Authorization: Bearer <token>` is the primary access control (already in place).

**CORS strategy:**
1. Requests with **no Origin header** (mobile native traffic) are **not blocked** by FastAPI/Starlette CORS middleware — it only acts on requests that include the header. No special config needed for mobile.
2. Requests with a **whitelisted Origin** (web clients) are allowed.
3. Requests with an **unrecognized Origin** (unknown browsers, scrapers) are blocked.

**Allowlist:**
- `https://dev.vianda.market` — marketing site
- `https://platform.dev.vianda.market` — B2B platform
- `https://api.dev.vianda.market` — backend (self, for docs/health)
- `http://localhost:8081` — Expo Web dev (dev environment only)
- `http://localhost:3000` — vianda-platform dev (dev environment only)
- `http://localhost:5173` — vianda-home dev (dev environment only)

**No B2C web app exists today.** There is no production web build of the React Native app. Adding one would be a separate plan due to scope (new hosting, new domain, new CORS entry, PWA considerations). Not in scope for this migration. If a web app is added later, its domain gets added to the allowlist at that time.

**Implementation:** Replace `allow_origins=["*"]` with an explicit allowlist in `application.py`. Use an env var (`CORS_ALLOWED_ORIGINS`) so infra-kitchen-gcp can manage per environment (dev, staging, prod each have different subdomains). The env var holds a comma-separated list. Localhost origins are included only in the dev environment value.

**Infra-kitchen-gcp:** Add `CORS_ALLOWED_ORIGINS` env var to Cloud Run config for each environment.

---

## B2C App Changes Required

### Registration screen (`app/(auth)/register.tsx`)
- **Keep:** Country dropdown (from `/leads/markets`), city dropdown (from `/leads/cities`), email/password/username form
- **Remove:** Any city-metrics check, any "has coverage" messaging, any in-app "express interest" flow
- **Remove:** Zipcode metrics integration
- **Add:** When a user selects a city that has no coverage (edge case — user arrived without going through marketing site), show a message with a link to the marketing site's "notify me" page: "We're not in [City] yet. Visit vianda.market to get notified when we arrive." This bridges users to the marketing site rather than leaving them at a dead end.

### Explore screen (`app/(app)/(tabs)/explore.tsx`)
- **No changes.** Explore is authenticated and uses `/restaurants/by-city`, `/restaurants/cities`, etc. — these are not leads endpoints.

### Leads API client (`src/api/endpoints/leads.ts`)
- **Keep:** `getLeadCities()`, `checkEmailRegistered()` (used by signup)
- **Remove or stop calling:** `zipcodeCheck()`, `cityMetrics()` — no longer called from any screen
- The functions can remain in the file for a transition period but should have no callers.

### Onboarding flow
- **No changes.** Post-signup onboarding (email verification → subscription prompt) is unaffected.

---

## Marketing Site Changes Required

### New section or page needed
A **coverage checker** component is needed — the centerpiece of this migration. Whether this is a new section on the existing landing page or a dedicated page (e.g., `/check-coverage`) is a vianda-home frontend decision. This plan calls out the requirement; the vianda-home agent decides the UX placement.

**Coverage checker requirements:**
- Country dropdown (from `/leads/markets`)
- City dropdown (populated after country selection, from `/leads/cities`)
- Optional zipcode text input
- Result display with zipcode → city fallback logic (see "Zipcode-metrics: reactivated" section above)
- **Served path:** App download CTA with store links
- **Partially served (city yes, zipcode no):** City results shown + "notify me for your zipcode" option + app download CTA
- **Unserved path:** "Notify me" email capture form (→ `POST /leads/interest`). Includes checkbox: "Only notify me about restaurants in my zipcode" (maps to `zipcode_only` field).

### Multi-audience interest forms (vianda-home agent design decision)

The "notify me" / interest capture system serves **three distinct audiences**, all through the same `POST /leads/interest` endpoint with different `interest_type` values. The vianda-home agent should design and place these forms considering all three audiences together — they share infrastructure but have different UX contexts:

1. **Customer interest** (`interest_type: customer`) — "Notify me when restaurants are in my area." This is the coverage checker's unserved/under-served path. Fields: email, country, city, zipcode, zipcode_only preference.

2. **Employer interest** (`interest_type: employer`) — "I want to offer Vianda's meal benefit program to my employees." Likely placed near the EmployerPrograms or ForBusinessesCTA sections already on the landing page. Fields: email, business_name, country, optional city, optional message.

3. **Supplier interest** (`interest_type: supplier`) — "I'm a restaurant/kitchen and I want to join Vianda." Likely placed near the LocalKitchensPreview section or a dedicated "Partner with us" area. Fields: email, business_name, country, city, optional message.

The vianda-home agent decides whether these are three separate forms, tabs within a single form, or distinct page sections. The backend accepts all three through one endpoint. The key design consideration: a visitor should be able to find the right form for their role without confusion — the customer "notify me" flow should not bury the employer/supplier interest paths, and vice versa.

### Existing planned sections
Already have stubs in vianda-home, just need the backend endpoints from `vianda_home_apis.md`:
- TrustBar → `/leads/platform-metrics`
- LocalKitchensPreview → `/leads/restaurants`
- FeaturedVendorSpotlight → `/leads/featured-restaurant`
- SubscriptionTiers → `/leads/plans`

### API client (`src/api/leads.ts`)
- **Add:** `getMarkets()`, `getCities(countryCode)`, `getCityMetrics(city, countryCode)`, `getZipcodeMetrics(zip, countryCode)`, `submitInterest({ email, country_code, city_name, zipcode?, zipcode_only? })`
- **Already prepared:** `getPlatformMetrics()`, `getFeaturedRestaurants()`, `getFeaturedVendor()`, `getPublicPlans()`

### No authentication infrastructure needed
No login, no JWT storage, no auth context, no protected routes. Every API call is unauthenticated. The `Accept-Language` header (already wired in `src/api/client.ts`) is the only request customization needed.

### SEO implementation (vianda-home agent)
SEO is critical for this migration to succeed — without it, users continue landing on the app store first and bypass the marketing site. The vianda-home agent owns SEO implementation:

- **Meta tags and Open Graph:** Per-page title, description, og:image for social sharing. Especially important for the coverage checker page/section.
- **Structured data (JSON-LD):** `LocalBusiness` or `FoodEstablishment` markup for served areas. `Organization` markup for Vianda.
- **Sitemap generation:** Dynamic sitemap including served cities (one URL per city with coverage). Generated from `/leads/cities` data at build time or via SSR.
- **Canonical URLs:** Ensure the coverage checker has a clean, shareable URL (e.g., `vianda.market/check-coverage?city=Austin&country=US`).
- **Performance:** Core Web Vitals — the landing page must load fast. Lazy-load below-fold sections. Pre-fetch API data where possible.
- **App store listing update:** Link to marketing site from app store description ("Check if we serve your area at vianda.market"). This is a manual update by the team, not an agent task.

### Analytics and tracking (vianda-home agent)
The vianda-home agent implements analytics using **Firebase Analytics** (already the hosting platform). This is a frontend implementation, not a backend concern:

- **Events to track:** `coverage_check` (with country, city, zipcode, result), `interest_submitted` (with country, city, zipcode), `app_download_click` (with source section), `plan_viewed`, `restaurant_card_clicked`
- **UTM parameter handling:** Parse and forward UTM params from marketing campaigns. Store in Firebase Analytics automatically.
- **Conversion funnel:** Coverage check → app download click. Interest submission as a separate conversion.
- **No backend changes needed.** Firebase Analytics is client-side JS. The vianda-home agent wires the event calls into the React components.

---

## B2B Platform Changes Required (vianda-platform)

### Interest dashboard — Internal employees only
New read-only section in Dashboard & Core for Internal role users. Displays lead interest data from `GET /leads/interest` (authenticated, Internal auth required).

**Table columns:** email, country, city, zipcode, zipcode_only, interest_type, business_name, source, created_date, status  
**Filters:** country, city, interest_type, date range, status  
**Sorting:** by date (default newest first), by city, by country, by interest_type

This is a read-only view for Phase 1. Future enhancements (not in scope):
- Bulk export to CSV
- "Mark as contacted" action
- Aggregate charts (interest by city, interest over time)
- Trigger manual notification to a cohort

---

## Sequencing

This migration has natural phases. Each phase is independently valuable — no phase depends on a later phase being completed.

**Important: backend first, then frontend.** Phase 1 is split into backend-first and frontend-after. The backend implements all endpoints, CAPTCHA, CORS, and the interest table. Once backend is complete and validated, agent-specific integration docs are produced for each frontend repo. Frontend agents start work only after receiving their tailored doc — not this full plan document, which contains too much cross-repo context. Changes during backend implementation may affect the API surface, so frontend work should not begin until the backend is stable.

### Phase 1a: Backend implementation (kitchen + infra-kitchen-gcp) — COMPLETE
- Implement CAPTCHA verification on all `/leads/*` endpoints (see CAPTCHA section above and `docs/plans/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md`)
- Implement the three planned endpoints from `vianda_home_apis.md` (platform-metrics, restaurants, plans)
- Implement `POST /leads/interest` endpoint + `core.lead_interest` table (supports customer, employer, and supplier interest types)
- Implement `GET /leads/interest` (authenticated, Internal) for B2B dashboard
- Tighten CORS to explicit allowlist via `CORS_ALLOWED_ORIGINS` env var (see CORS section above)
- Infra-kitchen-gcp: add `RECAPTCHA_SECRET_KEY`, `RECAPTCHA_SCORE_THRESHOLD`, and `CORS_ALLOWED_ORIGINS` env vars to Cloud Run config
- ~~Confirm B2C mobile app origin behavior~~ — confirmed: native apps send no Origin header, exempt from CORS. Done.
- **Result:** All backend endpoints live, bot-protected, CORS locked down. Ready for frontend integration.

### Phase 1b: Produce agent-specific integration docs (kitchen) — COMPLETE
After backend is complete, produce tailored docs in `docs/api/` for each frontend agent. These docs describe only what that agent needs — endpoints, contracts, CAPTCHA token requirements, and UX expectations. No full plan context.

| Doc to produce | Target agent | Content |
|---------------|-------------|---------|
| `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` | vianda-home | Coverage checker endpoints, interest form contracts (all 3 types), CAPTCHA frontend integration, SEO requirements, analytics events |
| `docs/api/b2c_client/LEADS_SIMPLIFICATION.md` | vianda-app | What to remove, what to keep, "not served" → marketing site link behavior |
| `docs/api/b2b_client/API_CLIENT_INTEREST_DASHBOARD.md` | vianda-platform | `GET /leads/interest` contract, filters, columns, Internal-only auth |
| `docs/infrastructure/LEADS_MIGRATION_INFRA.md` | infra-kitchen-gcp | New env vars (`RECAPTCHA_SECRET_KEY`, `RECAPTCHA_SCORE_THRESHOLD`, `CORS_ALLOWED_ORIGINS`), per-environment values, reCAPTCHA v3 site key for vianda-home |

### Phase 1c: Frontend implementation (vianda-home) — COMPLETE
- Add coverage checker (new section or page) using `/leads/markets`, `/leads/cities`, `/leads/city-metrics`, `/leads/zipcode-metrics`
- Add multi-audience interest forms: customer "notify me", employer benefits interest, supplier/restaurant join interest
- Wire up CAPTCHA on all leads API calls
- Implement SEO basics
- Implement Firebase Analytics events
- Deploy and validate the marketing site works end-to-end
- **Result:** Marketing site is live, bot-protected, and functional. B2C app still has full leads flow (both paths work).

### Phase 2: Simplify the B2C app + B2B dashboard (vianda-app + vianda-platform) — COMPLETE
- Remove city-metrics and zipcode-metrics calls from B2C signup flow
- Simplify registration screen to country → city → form → verify
- Add "not served" → marketing site link fallback in B2C app
- Add interest dashboard to B2B platform (Internal only, read-only)
- **Result:** B2C app has clean signup. Marketing site owns qualification. Internal team can see interest data.

### Phase 3: Alert crons (backend) — SEPARATE PLAN
Moved to `docs/plans/LEAD_INTEREST_ALERT_CRONS.md`. Zipcode + city alert crons that notify leads when new restaurants open in their area.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Marketing site goes down → no way to check coverage | Users can still download the app and register (city dropdown works) | The app retains country + city dropdowns; only the "coverage check" is lost, not signup |
| SEO not indexed yet → users still land on app store first | Users download without checking coverage (same as today) | Phase 1 includes SEO basics (vianda-home agent). App store listing updated to link to marketing site. Google indexing takes weeks — accept the lag and monitor Search Console. |
| Rate limiting too aggressive for marketing site traffic spikes | 429 errors during launch/campaigns | Monitor after Phase 1 launch; current limits are per-IP so organic traffic distributes naturally |

---

## Future Work (separate plans)

- **Lead interest alert crons** — `docs/plans/LEAD_INTEREST_ALERT_CRONS.md`. Zipcode + city alerts when new restaurants open.
- **Login CAPTCHA** — `docs/plans/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md`. Conditional reCAPTCHA on `POST /auth/token` after N failed attempts.
- **Platform metrics** — implemented.
- **Interest dashboard enhancements** — bulk export, "mark as contacted", aggregate charts. B2B platform work.
- **App store listing changes** — update screenshots/description to link to marketing site. Manual team task.

---

## Work Ownership Summary

| Work item | Owner (repo/agent) |
|-----------|-------------------|
| reCAPTCHA v3 backend verification (`verify_recaptcha` dependency on all `/leads/*`) | kitchen (backend) — Phase 1a |
| CORS tightening (`CORS_ALLOWED_ORIGINS` env var) | kitchen (backend) — Phase 1a |
| New backend endpoints (interest capture, internal list) | kitchen (backend) — Phase 1a |
| `lead_interest` table, schema, DTOs | kitchen (backend) — Phase 1a |
| Marketing content endpoints (platform-metrics, restaurants, plans) | kitchen (backend) — Phase 1a, per `vianda_home_apis.md` |
| Agent-specific integration docs (4 docs) | kitchen (backend) — Phase 1b, after backend complete |
| Alert cron jobs (zipcode + city level) | kitchen (backend) — Phase 3 |
| `RECAPTCHA_SECRET_KEY` + `RECAPTCHA_SCORE_THRESHOLD` + `CORS_ALLOWED_ORIGINS` env vars | infra-kitchen-gcp — Phase 1a |
| Coverage checker section/page | vianda-home (marketing site agent) — Phase 1c, after receiving integration doc |
| Multi-audience interest forms (customer, employer, supplier) | vianda-home (marketing site agent) — Phase 1c |
| reCAPTCHA v3 frontend integration (JS script + `X-Recaptcha-Token` header on all leads calls) | vianda-home (marketing site agent) — Phase 1c |
| SEO implementation (meta, structured data, sitemap) | vianda-home (marketing site agent) — Phase 1c |
| Firebase Analytics events and funnels | vianda-home (marketing site agent) — Phase 1c |
| Signup flow simplification | vianda-app (B2C agent) — Phase 2, after receiving integration doc |
| "Not served" → marketing site link | vianda-app (B2C agent) — Phase 2 |
| Interest dashboard (read-only table, filterable by interest_type) | vianda-platform (B2B agent) — Phase 2, after receiving integration doc |
| App store listing update | Manual (team) |

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `docs/plans/vianda_home_apis.md` | Specifies the 3 new marketing endpoints (platform-metrics, restaurants, plans). Still valid; this plan extends scope. |
| `docs/plans/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md` | CAPTCHA design details. reCAPTCHA v3 implemented for leads. Login CAPTCHA planned separately. |
| `docs/plans/LEAD_INTEREST_ALERT_CRONS.md` | Alert crons for lead interest (Phase 3, extracted to separate plan). |
| `docs/plans/B2C_EXPLORE_ZIPCODE.md` | Zipcode refinement in B2C explore (authenticated). Unaffected by this migration — explore is post-signup. |
| `docs/api/b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md` | Current signup spec. Phase 2 simplifies the pre-signup steps but the signup/verify flow itself is unchanged. |
| `docs/api/b2c_client/MARKET_CITY_COUNTRY.md` | Market selection at signup. Unaffected — country/city dropdowns stay in the app. |
