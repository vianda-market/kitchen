# Captcha and Rate Limit Roadmap

**Status**: In Progress  
**Scope**: Address suggest, leads, signup, login, password recovery (and related high-abuse endpoints)

---

## Overview

This roadmap covers human verification (e.g. CAPTCHA) and rate limiting across endpoints that are attractive targets for abuse: address autocomplete, lead flows, signup, login, and password recovery.

---

## Provider Decision

**Google reCAPTCHA v3** — decided 2026-04-05. Invisible, score-based (0.0 = bot, 1.0 = human). Already in the Google/Firebase ecosystem. Free tier: 1M assessments/month.

---

## Scope

| Endpoint / area | Rate limit (implemented) | CAPTCHA mode | Status |
|----------------|--------------------------|-------------|--------|
| `GET /leads/*`, `POST /leads/interest` | 5-60 req/min per IP (varies by endpoint) | **Always-on** — reCAPTCHA v3 token required on every call | **Implemented** |
| Country-scoped leads reads (see §below) | 20-60 req/min per IP | **Captcha-on-rate-limit** — 429 body carries `captcha_required: true` + `action: "leads_read"`; retry with token passes | **Implemented (#218)** |
| `POST /auth/token` (login) | 20/min per IP | **Conditional** — after 5 failed attempts in 15min window | **Implemented** |
| `POST /customers/signup/request` | 10/min per IP | **Always-on** for web clients; mobile exempt | **Implemented** |
| `POST /customers/signup/verify` | 20/min per IP | **Conditional** — after 3 failed attempts in 15min window | **Implemented** |
| `POST /auth/forgot-password` | 10/min per IP | **Conditional** — after 3 requests in 15min window | **Implemented** |
| `POST /auth/forgot-username` | 10/min per IP | **Conditional** — after 3 requests in 15min window | **Implemented** |
| `POST /auth/reset-password` | 20/min per IP | **Conditional** — after 3 failed attempts in 15min window | **Implemented** |
| `GET /addresses/suggest` | 60 req / 60 s per user (authenticated) | After 429, before retry | Future |

---

## Implemented: Leads Endpoints (always-on)

All `/api/v1/leads/*` endpoints require `X-Recaptcha-Token` header. Backend dependency `app/auth/recaptcha.py` validates against Google's verify API.

- **Disabled** when `RECAPTCHA_SECRET_KEY` env var is empty (local dev)
- **Exempt** when `x-client-type: b2c-mobile` header is present (native mobile apps)
- **Fail-open** if Google's verify API is unreachable
- **Score threshold:** `RECAPTCHA_SCORE_THRESHOLD` env var (default 0.3)
- Applied at router level: `APIRouter(dependencies=[Depends(verify_recaptcha)])`

---

## Implemented: Login CAPTCHA (conditional, after failed attempts)

Protects `POST /api/v1/auth/token` from brute-force credential stuffing.

- **Tracker:** `app/auth/ip_attempt_tracker.py` — in-memory sliding window, deque-based, keyed by `"{ip}:{action}"`. TTL/size eviction.
- **Guard:** `app/auth/captcha_guard.py` — `require_captcha_after_threshold()` factory returns a FastAPI dependency.
- **Threshold:** 5 failed attempts within 15min → 429 with `detail.code: "captcha_required"`.
- **Token verification:** `app/auth/recaptcha.py` → `verify_recaptcha_token(token, action="login")` validates with Google and checks action matches.
- **Reset:** Counter clears on successful login.
- **Settings:** `LOGIN_CAPTCHA_THRESHOLD` (5), `LOGIN_CAPTCHA_WINDOW_SECONDS` (900).

---

## Implemented: Signup + Password Recovery CAPTCHA

### `POST /customers/signup/request` — Always-on for web
- Guard: `always_require_captcha_for_web(action="signup")` — requires token from web clients, mobile exempt.
- Missing token → 403 `captcha_required`.

### `POST /customers/signup/verify` — Conditional after 3 failures
- Guard: `require_captcha_after_threshold(action="signup_verify", threshold=3, window=900)`.
- Counter incremented on invalid code.

### `POST /auth/forgot-password` and `POST /auth/forgot-username` — Conditional after 3 requests
- Guard: `require_captcha_after_threshold(track_all_requests=True)` — counts every request (not just failures) since these endpoints always return success.
- Threshold: 3 requests in 15min.

### `POST /auth/reset-password` — Conditional after 3 failures
- Guard: `require_captcha_after_threshold(action="reset_password", threshold=3, window=900)`.
- Counter incremented on failed reset.

### reCAPTCHA actions by endpoint

| Endpoint | Action | When CAPTCHA is sent |
|----------|--------|---------------------|
| `POST /auth/token` | `login` | After 5 failures |
| `POST /customers/signup/request` | `signup` | Always (web only) |
| `POST /customers/signup/verify` | `signup_verify` | After 3 failures |
| `POST /auth/forgot-password` | `forgot_password` | After 3 requests |
| `POST /auth/forgot-username` | `forgot_username` | After 3 requests |
| `POST /auth/reset-password` | `reset_password` | After 3 failures |

### Files added/changed
- `app/auth/ip_attempt_tracker.py` (new) — reusable IP attempt tracker
- `app/auth/captcha_guard.py` (new) — conditional + always-on CAPTCHA dependency factories
- `app/auth/recaptcha.py` — extracted `verify_recaptcha_token()` with action validation
- `app/auth/routes.py` — login CAPTCHA wiring
- `app/routes/user_public.py` — signup + recovery CAPTCHA wiring
- `app/config/settings.py` — per-endpoint threshold/window settings

---

## Implemented: Leads Captcha-on-Rate-Limit (#218)

Country-scoped leads read endpoints carry an additive captcha hint on 429.

### Covered endpoints

| Endpoint | Rate limit | Action string |
|----------|-----------|---------------|
| `GET /leads/plans` | 60/min | `leads_read` |
| `GET /leads/restaurants` | 60/min | `leads_read` |
| `GET /leads/featured-restaurant` | 60/min | `leads_read` |
| `GET /leads/cities` | 20/min | `leads_read` |
| `GET /leads/city-metrics` | 20/min | `leads_read` |
| `GET /leads/zipcode-metrics` | 20/min | `leads_read` |

**Excluded (navbar-load, captcha-exempt):** `/leads/countries`, `/leads/supplier-countries`.
These two endpoints sit on `public_router` (no `verify_recaptcha` dependency) and load on every
marketing-site page render, so they must not carry a challenge.

### Wire shape (additive on existing 429)

```json
{
  "detail": {
    "code": "request.rate_limited",
    "message": "...",
    "params": { "retry_after_seconds": 60 }
  },
  "captcha_required": true,
  "action": "leads_read"
}
```

The `detail` field is unchanged — existing consumers continue to parse it. The two new
top-level fields (`captcha_required`, `action`) are only present on the covered endpoints.

### Retry contract

Frontend detects `captcha_required: true` → renders invisible reCAPTCHA v3 with `action="leads_read"` →
retries the request with `X-Recaptcha-Token: <token>` header. The existing `verify_recaptcha` dependency
on the `leads_router` validates the token. If the token is valid, the request proceeds normally (200).

A single action string `leads_read` is used across all covered endpoints — keeps frontend retry logic simple.

### Implementation

- `application.py::_structured_rate_limit_handler` — detects `request.url.path` against a frozenset of
  covered paths; adds `captcha_required` and `action` to the response content when matched.
- No changes to `app/routes/leads.py` or `app/auth/recaptcha.py` — the existing `verify_recaptcha`
  dependency handles the token on retry.

---

## Future: Address Suggest

Remains planned but not yet designed:
- `GET /addresses/suggest` — CAPTCHA after 429 rate limit

---

## Related

- [LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md](../zArchive/roadmap/LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md) – Lead endpoints rate limit and human-check plan (archived).
- `docs/plans/LEADS_MIGRATION_TO_MARKETING_SITE.md` — Leads migration plan (reCAPTCHA v3 decision, always-on for leads)
- `app/auth/recaptcha.py` — reCAPTCHA v3 verification (`verify_recaptcha` for leads, `verify_recaptcha_token` for conditional guards)
