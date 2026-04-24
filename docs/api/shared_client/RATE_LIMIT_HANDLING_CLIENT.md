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

Since the error envelope rollout (Phase 2 K3), 429 responses match the shared envelope shape defined in `ERROR_ENVELOPE_FOR_CLIENTS.md`:

```json
{
  "detail": {
    "code": "request.rate_limited",
    "message": "Too many requests. Please try again later.",
    "params": {"retry_after_seconds": 60}
  }
}
```

- `detail.message` is localized based on `Accept-Language` (en, es, pt) — same behavior as before.
- `detail.code === "request.rate_limited"` is the stable identifier to switch on. Do not parse `message` for control flow.
- `detail.params.retry_after_seconds` mirrors the `Retry-After` header (both present). Either is authoritative; prefer the header for consistency with other HTTP clients.

**Migrating from the legacy flat shape**: pre-envelope, the response body was `{"detail": "Too many requests..."}` (a bare string). If your client still checks `detail === "rate_limited"` or parses the message, switch to `detail?.code === "request.rate_limited"`. The `resolveErrorMessage` helper (from `vianda-hooks`) handles both shapes transparently — if you've wired it per `ERROR_ENVELOPE_FOR_CLIENTS.md`, no change is needed for user-facing messaging; only control-flow checks (e.g. "is this a rate-limit error?") need the code-based update.

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
