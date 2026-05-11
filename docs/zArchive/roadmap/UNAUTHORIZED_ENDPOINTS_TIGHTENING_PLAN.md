# Unauthorized Endpoints Tightening Plan

**Created**: 2026-03-15  
**Updated**: 2026-03-15 (rate limiting, no backward compat, doc updates)  
**Status**: Implemented  
**Goal**: Restrict unauthenticated endpoints to return only the data required for unauthorized users. Add rate limiting to mitigate enumeration and abuse. No backward compatibility — we can break things.

---

## Summary of Changes

| Endpoint | Current Response | Proposed Response | Breaking? |
|----------|------------------|-------------------|-----------|
| GET `/api/v1/markets/available` | market_id, country_code, country_name, timezone, kitchen_close_time, currency_code, currency_name | **country_code, country_name only** | **Yes** |
| GET `/api/v1/leads/cities` | `{ "cities": ["Buenos Aires", ...] }` | No change (already minimal) | No |
| GET `/api/v1/leads/city-metrics` | requested_city, matched_city, restaurant_count, has_coverage, center | **Remove `center`** | No |
| GET `/api/v1/leads/zipcode-metrics` | requested_zipcode, matched_zipcode, restaurant_count, has_coverage, center | **Remove `center`** | No |
| GET `/api/v1/leads/email-registered` | `{ "registered": boolean }` | No change (already minimal) | No |

---

## Implementation Order

| Priority | Phase | Scope | Breaking? |
|----------|-------|-------|-----------|
| **1** | Rate limiting | Add slowapi to all unauthenticated endpoints | No |
| **2** | Phase 1 | Remove `center` from city-metrics and zipcode-metrics | No |
| **3** | Phase 2 | Slim markets/available; signup accepts `country_code` only (remove `market_id`) | **Yes** |

---

## Phase 0: Rate Limiting (Security First)

### Rationale

Unauthenticated endpoints are targets for abuse:

- **`/leads/email-registered`**: Enumeration risk — attackers can probe millions of emails to build a list of registered users
- **`/markets/available`**, **`/leads/cities`**: Can be scraped or DDoS’d
- Current ad-hoc in-memory rate limits exist for leads and markets, but are inconsistent and not centralized

### Approach

Use **slowapi** (FastAPI-compatible) to centralize rate limiting across all unauthenticated endpoints.

### Endpoints to Rate Limit

| Endpoint | Suggested Limit | Notes |
|----------|-----------------|-------|
| GET `/api/v1/markets/available` | 60/min per IP | Already has custom limit; migrate to slowapi |
| GET `/api/v1/leads/cities` | 20/60s per IP | Already has custom limit; migrate |
| GET `/api/v1/leads/city-metrics` | 20/60s per IP | Already has custom limit; migrate |
| GET `/api/v1/leads/zipcode-metrics` | 20/60s per IP | Already has custom limit; migrate |
| GET `/api/v1/leads/email-registered` | **10/60s per IP** | Stricter — enumeration risk |
| POST `/api/v1/auth/token` | 20/60s per IP | Brute-force protection |
| POST `/api/v1/auth/forgot-username` | 10/60s per IP | Enumeration risk |
| POST `/api/v1/auth/forgot-password` | 10/60s per IP | Enumeration risk |
| POST `/api/v1/auth/reset-password` | 20/60s per IP | |
| POST `/api/v1/customers/signup/request` | 10/60s per IP | Abuse / spam |
| POST `/api/v1/customers/signup/verify` | 20/60s per IP | |

### Implementation Tasks

| Task | File(s) | Description |
|------|---------|-------------|
| Add slowapi | `requirements.txt`, `application.py` | Install slowapi; configure Limiter with `key_func=get_remote_address` |
| Apply to leads | `app/routes/leads.py` | Replace `_rate_limit_leads` with `@limiter.limit("20/minute")` (or equivalent) per endpoint; use 10/min for email-registered |
| Apply to markets | `app/routes/admin/markets.py` | Replace `_rate_limit_available` with slowapi decorator |
| Apply to auth | `app/auth/routes.py`, `app/routes/user_public.py` | Add limits to token, forgot-username, forgot-password, reset-password |
| Apply to signup | `app/routes/user_public.py` | Add limits to signup/request, signup/verify |
| Remove custom rate limit logic | `app/routes/leads.py`, `app/routes/admin/markets.py`, `app/routes/user_public.py` | Delete `_rate_limit_*` functions and related globals |
| Tests | `app/tests/` | Update or add tests for 429 when limit exceeded |
| Docs | `docs/api/shared_client/EMAIL_REGISTERED_CHECK_CLIENT.md`, etc. | Document rate limits per endpoint |

---

## Phase 1: Remove `center` from Metrics (Low Risk)

### 3. GET /api/v1/leads/city-metrics

**Remove `center`** from the response. Geolocation should require authentication.

| Change | File(s) | Description |
|--------|---------|-------------|
| Service | `app/services/city_metrics_service.py` | Stop returning `center` in the dict |
| Schema | `app/schemas/consolidated_schemas.py` | Remove `center` from `CityMetricsResponseSchema` or set to `None` and exclude |
| Docs | `docs/api/b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md` | Update response shape; remove center |

### 4. GET /api/v1/leads/zipcode-metrics

**Remove `center`** from the response.

| Change | File(s) | Description |
|--------|---------|-------------|
| Service | `app/services/zipcode_metrics_service.py` | Stop returning `center` in the dict |
| Schema | `app/schemas/consolidated_schemas.py` | Remove `center` from `ZipcodeMetricsResponseSchema` |
| Docs | `docs/api/shared_client/ZIPCODE_METRICS_LEAD_API.md` | Update response; remove center |

### Phase 1 Doc Updates

| Doc | Changes |
|-----|---------|
| `docs/api/b2c_client/B2C_ENDPOINTS_OVERVIEW.md` | Update zipcode-metrics and city-metrics response (no center) |
| `docs/api/b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md` | Update city-metrics response |
| `docs/api/shared_client/ZIPCODE_METRICS_LEAD_API.md` | Update response example |

---

## Phase 2: Markets + Signup Breaking Change

### No Backward Compatibility

We will **not** support `market_id` during transition. Signup accepts **`country_code` only**. Backend resolves `country_code` → `market_id` internally.

### 1. GET /api/v1/markets/available

**Proposed response** (confirmed):

```json
[
  { "country_code": "AR", "country_name": "Argentina" },
  { "country_code": "US", "country_name": "United States" }
]
```

| Change | File(s) | Description |
|--------|---------|-------------|
| Markets route | `app/routes/admin/markets.py` | Slim `_get_available_markets_cached()` to return only `country_code`, `country_name` |
| Schema | `app/schemas/consolidated_schemas.py` | Replace `MarketPublicResponseSchema` (or add `MarketPublicMinimalSchema`) with `country_code`, `country_name` only |

### Signup API Change

**Current**: `POST /api/v1/customers/signup/request` requires `market_id` (UUID).

**New**: `POST /api/v1/customers/signup/request` requires **`country_code`** (string, e.g. `"AR"`, `"US"`). Backend resolves to active non-Global market.

| Change | File(s) | Description |
|--------|---------|-------------|
| Signup schema | `app/schemas/consolidated_schemas.py` | `CustomerSignupSchema`: replace `market_id` with `country_code` (required) |
| Signup service | `app/services/user_signup_service.py` | Resolve `country_code` → `market_id` (active, non-Global); remove `market_id` validation path |
| Docs | Multiple (see below) | Update all references to market_id in signup |

### Phase 2 Doc Updates (B2C and B2B)

| Doc | Changes |
|-----|---------|
| `docs/api/b2c_client/MARKET_CITY_COUNTRY.md` | Rewrite: signup uses `country_code` from markets/available; remove market_id; document new response shape |
| `docs/api/b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md` | Update request body: `country_code` required, `market_id` removed |
| `docs/api/b2c_client/B2C_ENDPOINTS_OVERVIEW.md` | Update markets/available response; signup request body |
| `docs/api/b2c_client/FRONTEND_AGENT_README.md` | Update market selection guidance |
| `docs/api/b2c_client/investigations/UNAUTHENTICATED_HOME_MARKETS_AND_CITIES.md` | Update response shape for markets/available |
| `docs/api/b2b_client/API_CLIENT_MARKETS.md` | Update GET /markets/available response to country_code + country_name only |
| `docs/api/shared_client/MARKET_AND_SCOPE_GUIDELINE.md` | Update signup flow: country_code instead of market_id; markets/available response |
| `docs/api/shared_client/USER_AND_MARKET_API_CLIENT.md` | Update market selector guidance |
| `docs/api/b2b_client/PLAN_API_MARKET_CURRENCY.md` | Note: markets/available no longer returns market_id; plans/institutions still use market_id (authenticated) |
| `docs/api/shared_client/PLANS_FILTER_CLIENT_INTEGRATION.md` | Clarify: for plan market dropdown, use authenticated endpoints or derive from country_code |

### Client Migration (B2C Mobile App)

Before or in the same release as Phase 2:

1. Update market picker to use `country_code` and `country_name` from `/markets/available` (already sufficient for display).
2. Change signup request to send `country_code` instead of `market_id`.
3. Remove any stored `market_id` usage for signup; use `country_code` only.

### Client Migration (B2B Web)

B2B typically uses markets for institution create and plan dropdowns. Those flows use **authenticated** endpoints (`GET /api/v1/markets/` or enriched). The public `/markets/available` is mainly for B2C pre-login. If B2B uses it for any pre-auth flow, update to use `country_code` + `country_name` only.

---

## References

- [MARKET_CITY_COUNTRY.md](../api/b2c_client/MARKET_CITY_COUNTRY.md)
- [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](../api/b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md)
- [API_CLIENT_MARKETS.md](../api/b2b_client/API_CLIENT_MARKETS.md)
- [ZIPCODE_METRICS_LEAD_API.md](../api/shared_client/ZIPCODE_METRICS_LEAD_API.md)
- [EMAIL_REGISTERED_CHECK_CLIENT.md](../api/shared_client/EMAIL_REGISTERED_CHECK_CLIENT.md)
- [RESTAURANT_EXPLORE_B2C.md](../api/b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md)
- [LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md](./LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md)
- [ADDRESS_RATE_LIMITING_AND_CACHING.md](./ADDRESS_RATE_LIMITING_AND_CACHING.md)
