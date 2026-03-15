# Captcha and Rate Limit Roadmap

**Status**: Planned  
**Scope**: Address suggest, leads, signup (and related high-abuse endpoints)

---

## Overview

This roadmap covers human verification (e.g. CAPTCHA) and rate limiting across endpoints that are attractive targets for abuse: address autocomplete, lead flows, and signup.

---

## Scope

| Endpoint / area       | Rate limit (implemented)        | Captcha trigger (roadmap) |
|----------------------|---------------------------------|---------------------------|
| `GET /addresses/suggest` | 60 req / 60 s per user (authenticated) | After 429, before retry     |
| `GET /leads/*`       | 20 req / 60 s per IP            | After 429, before retry     |
| Signup / auth flows  | TBD                             | TBD (e.g. after N failed attempts) |

---

## Captcha trigger

- **When**: User receives **429** (rate limit exceeded) and later retries.
- **Flow**: Frontend shows a human-check challenge (e.g. reCAPTCHA, hCaptcha) before calling the endpoint again. Backend optionally accepts a verification token and skips or relaxes rate limit for a short window.
- **Out of scope for now**: Full implementation. Captured here for product/security planning.

---

## Backend / frontend integration (planned)

- **Backend**: Optional CAPTCHA verification step; issue short-lived token or flag per user/session/IP after successful human check; endpoints accept requests when within rate limit or when token is present.
- **Frontend**: When user gets 429 and retries, show human-check challenge before re-calling the endpoint.
- **Product decisions**: Enable by default vs opt-in, which provider (e.g. reCAPTCHA v3), how long "verified" state lasts.

---

## Related

- [LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md](./LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md) – Lead endpoints rate limit and human-check plan.
