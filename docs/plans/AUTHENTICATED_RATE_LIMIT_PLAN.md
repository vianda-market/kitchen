# Authenticated User Rate Limiting Plan

**Status**: Draft  
**Goal**: Protect backend capacity and downstream API costs from browse-heavy free-tier B2C users who sign up but never subscribe.  
**Related**: [CAPTCHA_AND_RATE_LIMIT_ROADMAP.md](./CAPTCHA_AND_RATE_LIMIT_ROADMAP.md)

---

## Problem

Registered B2C users today have unlimited access to browse restaurants, viandas, and other discovery endpoints. A user who creates an account but never subscribes to a plan can still generate significant load — especially on endpoints that hit external APIs (address autocomplete, geocoding) or run expensive queries (restaurant explorer, vianda selections with JOINs). We need tiered rate limits that protect the system while keeping the experience smooth for paying subscribers.

---

## Current State

| Layer | What exists | Gap |
|---|---|---|
| **IP-based (slowapi)** | Applied to public/leads endpoints (20-60 req/min) | Cannot distinguish users; shared IPs penalize everyone |
| **Custom per-user** | Address suggest (60 req/60s, in-memory dict) | One-off, not reusable; in-memory = lost on restart; global dict pruning on every request |
| **Auth system** | JWT with `role_type`, `role_name`, `onboarding_status` in token | Onboarding status already encodes subscription state — not yet used for rate limiting |
| **Infrastructure** | No Redis; single-process deployment (Gunicorn workers share nothing) | In-memory limits don't work across workers |

---

## Design

### Tier Model — Based on Onboarding Status

The existing B2C onboarding tracker already encodes the exact distinction we need: a Customer with `onboarding_status = "complete"` has a verified email **and** an active subscription. Rather than invent a separate "rate limit tier" concept, we reuse `onboarding_status` directly from the JWT.

| Tier | Resolution rule | Global limit | Per-endpoint burst | Notes |
|---|---|---|---|---|
| **Anonymous** | No token | Keep current IP-based slowapi limits | As-is | No change |
| **Free** | `role_type = Customer` AND `onboarding_status != "complete"` | **120 req/min** globally | Endpoint-specific overrides (see below) | Covers `not_started` and `in_progress` |
| **Onboarded** | `role_type = Customer` AND `onboarding_status = "complete"` | **600 req/min** globally | Higher per-endpoint where needed | Subscribed + email verified |
| **Supplier/Employer** | `role_type` in (`Supplier`, `Employer`) | **600 req/min** globally | Same as Onboarded | B2B users are institution-managed |
| **Internal** | `role_type = Internal` | **No limit** | No limit | Ops access must never be throttled |

**How tier is resolved**: From two JWT claims already present on every authenticated request — `role_type` and `onboarding_status`. No DB lookup, no new token fields.

**Why onboarding_status instead of a dedicated tier field**:
- `onboarding_status` is already computed from real business data (email verified + active subscription) and embedded in the JWT at login
- Avoids a parallel "subscription tier" concept that would need its own refresh logic
- When a user subscribes, their next token refresh naturally moves them from Free → Onboarded
- For Suppliers/Employers, onboarding_status tracks operational readiness (7 or 4 steps), not subscription — so we tier them by `role_type` instead

### Per-Endpoint Overrides (Free Tier)

These endpoints are either expensive or hit external paid APIs:

| Endpoint | Free tier limit | Reason |
|---|---|---|
| `GET /addresses/suggest` | 30 req/min (down from 60) | Each call hits Mapbox API ($) |
| `GET /restaurants/explorer` | 20 req/min | Heavy JOIN query |
| `GET /vianda-selections/*` | 30 req/min | Multi-table query |
| `GET /cuisines/*` | 60 req/min | Lightweight, keep generous |
| Other authenticated routes | Fall back to global 120 req/min | Default |

Subscribed tier gets 2-3x these limits (or no per-endpoint cap if global is sufficient).

---

## Implementation Approach

### Option A: Middleware + In-Memory (Single-Process Safe) — Recommended for MVP

A single FastAPI middleware that runs after authentication, reads the user tier from the JWT, and enforces limits using a sliding-window counter in an in-memory dict (similar to the existing address suggest pattern but generalized).

**Pros**: No new dependencies, fast, simple.  
**Cons**: Limits are per-worker (not shared across Gunicorn workers). Acceptable for MVP since our current deployment is low-concurrency and per-worker limits still protect each process.

**Files touched**:

1. **`app/auth/middleware/rate_limit_middleware.py`** (new) — The middleware itself
2. **`app/config/settings.py`** — Rate limit settings (toggle on/off, tier limits)
3. **`app/config/rate_limit_config.py`** (new) — Endpoint override map, tier definitions
4. **`application.py`** — Register middleware
5. **`app/utils/rate_limit.py`** — Keep slowapi for anonymous; document coexistence
6. **`app/routes/address.py`** — Remove custom in-memory rate limit code (replaced by middleware)

### Option B: Redis-Backed (Future)

When we add Redis for other features (session store, caching), swap the in-memory backend for a Redis sliding-window counter. The middleware interface stays the same — only the storage backend changes. This is an evolution of Option A, not a separate path.

---

## Middleware Design (Option A Detail)

```
Request → CORS → ContentLanguage → RateLimitMiddleware → Route Handler
                                         │
                                    Read JWT from header
                                    (don't decode again — reuse
                                     cached user from request.state
                                     if available, else decode)
                                         │
                                    Resolve tier from JWT claims:
                                      role_type = Internal → skip
                                      role_type = Supplier|Employer → Onboarded
                                      onboarding_status = "complete" → Onboarded
                                      else → Free
                                         │
                                    Check global counter for user_id
                                    Check endpoint counter if override exists
                                         │
                                    429 with Retry-After header if exceeded
```

**Sliding window**: Store a list of timestamps per key (same pattern as address suggest). Prune entries older than the window. Count remaining. This avoids fixed-window boundary spikes.

**Key format**: `{user_id}` for global, `{user_id}:{method}:{path_pattern}` for per-endpoint.

**Eviction**: Periodically prune keys with no recent timestamps (every N requests or via a background task). Cap total keys at a configurable max (e.g., 10,000) — evict oldest-access keys first if exceeded.

**Response headers** (standard):
- `X-RateLimit-Limit`: The limit for this tier
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Seconds until window resets
- `Retry-After`: Seconds to wait (on 429 only)

---

## Settings

New entries in `app/config/settings.py`:

```python
# Rate limiting
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_FREE_GLOBAL: int = 120           # req/min for free tier (onboarding incomplete)
RATE_LIMIT_ONBOARDED_GLOBAL: int = 600     # req/min for onboarded tier (complete + B2B)
RATE_LIMIT_WINDOW_SECONDS: int = 60
RATE_LIMIT_MAX_KEYS: int = 10000         # eviction threshold
```

Per-endpoint overrides live in `app/config/rate_limit_config.py` as a dict so they can be tuned without env vars.

---

## Rollout Plan

### Phase 1 — Middleware MVP (this iteration)
1. Create middleware with in-memory sliding window
2. Add settings with `RATE_LIMIT_ENABLED = False` default (feature flag)
3. Add response headers on all authenticated requests (even when not limiting) so clients can observe
4. Remove the custom address suggest rate limit code
5. Test with Postman collection: verify 429 at threshold, headers present, internal users unthrottled
6. Enable in staging, monitor for false positives

### Phase 2 — Tune & Monitor
1. Add a lightweight log/metric on 429 events (user_id, endpoint, tier) — use existing logger
2. Review limits after 2 weeks of real usage data
3. Adjust per-endpoint overrides based on actual traffic patterns

### Phase 3 — Redis Backend (when ready)
1. Swap in-memory dict for Redis sliding window
2. Shared limits across Gunicorn workers
3. Enables future features: distributed rate limiting, abuse scoring

---

## Open Questions

1. **Should we expose rate limit tier to the client?** The B2C app already has access to `onboarding_status` from the JWT — it could use that directly to show "subscribe for unlimited browsing" prompts when a user hits a 429. No new endpoint needed, but we could add the tier name in the `X-RateLimit-Tier` response header for observability.
2. **Graceful degradation**: If the rate limit store gets large (memory pressure), should we fail-open (allow requests) or fail-closed (reject)? Recommendation: fail-open with a warning log.
3. **Per-IP fallback**: If a free-tier user rotates tokens, should we also track by IP as a secondary key? Adds complexity — probably not needed for MVP.
4. **Webhook/admin endpoints**: Confirm these should be fully exempt (they already require Internal role).

---

## What This Does NOT Cover

- **Anonymous/public rate limits** — Already handled by slowapi, no changes needed
- **CAPTCHA integration** — Covered in [CAPTCHA_AND_RATE_LIMIT_ROADMAP.md](./CAPTCHA_AND_RATE_LIMIT_ROADMAP.md)
- **DDoS protection** — Infrastructure-level concern (Cloudflare, GCP armor), not application-level
- **Subscription enforcement** — This is about *rate* limiting, not feature gating
