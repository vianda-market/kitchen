# Rate Limit Handling for Client Apps

**Audience**: B2C (vianda-app) and B2B (vianda-platform)  
**Status**: Implemented, will be activated via feature flag

---

## What Changed

The backend now enforces per-user rate limits on all authenticated endpoints. Limits are tiered based on the user's onboarding status (already in the JWT `onboarding_status` claim).

| Tier | Who | Global limit |
|---|---|---|
| **Free** | Customer, `onboarding_status != "complete"` | 120 req/min |
| **Onboarded** | Customer, `onboarding_status = "complete"` | 600 req/min |
| **B2B** | Supplier / Employer (any onboarding status) | 600 req/min |
| **Internal** | Internal users | No limit |

Some endpoints have tighter limits for Free-tier users:

| Endpoint | Free-tier limit |
|---|---|
| `GET /addresses/suggest` | 30 req/min |
| `GET /restaurants/explorer` | 20 req/min |
| `GET /plate-selections/*` | 30 req/min |
| `GET /cuisines/*` | 60 req/min |

---

## Response Headers

All authenticated responses now include these headers:

| Header | Example | Description |
|---|---|---|
| `X-RateLimit-Limit` | `120` | Max requests allowed in the current window |
| `X-RateLimit-Remaining` | `87` | Requests remaining before limit is hit |
| `X-RateLimit-Reset` | `1712345678` | Unix timestamp when the window resets |

When rate-limited (HTTP 429), an additional header is included:

| Header | Example | Description |
|---|---|---|
| `Retry-After` | `60` | Seconds to wait before retrying |

---

## Handling 429 Responses

### Response Shape

```json
{
  "detail": "Too many requests. Please try again later."
}
```

The `detail` message is localized based on the `Accept-Language` header (en, es, pt).

### Recommended Client Behavior

1. **Show a non-blocking message** — e.g., a toast or inline banner: "You're browsing too fast. Please wait a moment."
2. **Use the `Retry-After` header** to determine when to allow the next request. Do not retry immediately.
3. **Disable the triggering UI element** (e.g., search input, refresh button) for the `Retry-After` duration, then re-enable.
4. **Do NOT log the user out** — 429 is not an auth error.

### B2C-Specific: Subscribe Prompt

For Free-tier users (`onboarding_status != "complete"`), a 429 response is a natural moment to prompt subscription. The app already knows the user's onboarding status from the JWT — use it to show messaging like:

> "Subscribe to a plan for unlimited browsing."

This is optional UX polish, not required for correctness.

---

## No Client Changes Required for Activation

- The backend feature is toggled server-side (`RATE_LIMIT_ENABLED` env var). No client deployment needed to activate.
- Clients that don't handle 429 will see the standard error detail string — existing error handling should catch it.
- The `X-RateLimit-*` headers are informational — clients can ignore them initially and adopt them later for proactive UI (e.g., showing remaining requests in dev tools).
