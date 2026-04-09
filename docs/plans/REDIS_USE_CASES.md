# Redis Infrastructure Use Cases

**Status:** Planning. Redis (Cloud Memorystore) is provisioned for the ads platform ARQ queue. This document identifies additional use cases that justify the infrastructure cost.

**Current:** ARQ job queue for ads conversion uploads (deferred 5min-24h).

---

## High-Value Use Cases

### 1. Rate Limiting (replace in-memory)

**Current state:** Authenticated rate limiting (`app/auth/middleware/`) and CAPTCHA thresholds (`app/auth/ip_attempt_tracker.py`) use in-memory sliding-window counters. These reset on every deploy/restart and do not share state across Cloud Run instances.

**With Redis:** Rate limit counters persist across restarts and are shared across all Cloud Run instances. This is critical for production where Cloud Run scales to multiple instances.

**Effort:** Low. Replace the in-memory dict with Redis GET/INCR/EXPIRE. The `slowapi` library already supports Redis backends.

**Priority:** High. This is a correctness issue in production, not just a nice-to-have.

### 2. Session/Token Blocklist (JWT Revocation)

**Current state:** No JWT revocation mechanism. If a user's token is compromised, it remains valid until expiry.

**With Redis:** Store revoked token JTIs in Redis with TTL matching the token expiry. Check on every authenticated request. Redis SET with TTL is perfect for this: fast, auto-expiring, shared across instances.

**Effort:** Low. Add JTI to JWT payload, check Redis SET membership in `get_current_user`.

**Priority:** Medium. Security improvement, especially for the B2B portal where employer admin tokens have higher privilege.

### 3. Permission Cache (replace in-memory)

**Current state:** `app/auth/middleware/permission_cache.py` caches user permissions in-memory. Same restart/multi-instance problem as rate limiting.

**With Redis:** Shared permission cache with TTL. All instances see the same cached permissions. Invalidation is instant (delete the key) instead of waiting for cache expiry across all instances.

**Effort:** Low. Swap the in-memory dict for Redis HSET/HGET with TTL.

**Priority:** Medium. Improves consistency in multi-instance deployments.

### 4. Notification Banner Deduplication

**Current state:** `customer.notification_banner` uses DB-level UNIQUE constraint for dedup. The `get_active_notifications()` query runs on every poll (60s per user).

**With Redis:** Cache active notifications per user in Redis (HASH with user_id key, TTL 60s). Reduces DB load from N queries/minute to N queries/TTL. The DB becomes the source of truth; Redis is a read-through cache.

**Effort:** Low. Add Redis cache layer in `notification_banner_service.py`.

**Priority:** Low-medium. Matters at scale (1000+ active users polling every 60s).

### 5. Pub/Sub for Real-Time Events

**Current state:** No real-time event system. Push notifications use FCM (external service).

**With Redis:** Redis Pub/Sub can broadcast events across instances for internal coordination:
- "Zone X reached 5 restaurants" -> trigger B2C campaign activation
- "Subscription confirmed" -> notify ads conversion service (alternative to direct function call)
- "Restaurant approved" -> fire ApprovedPartner event

**Effort:** Medium. Requires a subscriber pattern in the FastAPI lifespan.

**Priority:** Low. Direct function calls work fine for now. Pub/Sub becomes useful when the system grows beyond a single service.

### 6. Cron Job Deduplication

**Current state:** Cron jobs (billing_events, currency_refresh, holiday_refresh, etc.) run via Cloud Scheduler hitting HTTP endpoints. If the endpoint is hit twice (retry on timeout), the job runs twice.

**With Redis:** Use Redis SET NX with TTL as a distributed lock. The first instance to acquire the lock runs the job; duplicates are rejected. Pattern: `SET cron:billing_events:2026-04-09 1 NX EX 3600`.

**Effort:** Low. Decorator pattern: `@redis_cron_lock("billing_events")`.

**Priority:** Medium. Prevents double-billing, double-email, and other duplicate side effects.

### 7. ARQ for Non-Ads Background Jobs

**Current state:** Email sending, Wikidata enrichment, and other background tasks run synchronously in request handlers or in cron job endpoints.

**With Redis + ARQ:** Any long-running or deferrable task can be offloaded to ARQ:
- Email sending (currently blocks the request thread)
- Wikidata image enrichment batch processing
- USDA nutrition data fetch
- Employer billing generation
- Supplier stall detection emails

**Effort:** Medium. Each task needs to be extracted into an ARQ function and enqueued from the calling code.

**Priority:** Low-medium. Email sending is the highest-value candidate (blocks request threads today).

---

## Recommendation

| Use Case | Effort | Priority | Implement When |
|----------|--------|----------|---------------|
| Rate limiting (shared) | Low | High | Before production multi-instance deployment |
| Cron job deduplication | Low | Medium | Before production (prevents double-billing) |
| Permission cache (shared) | Low | Medium | With rate limiting (same migration) |
| JWT revocation | Low | Medium | Security hardening sprint |
| Notification cache | Low | Low-med | When user count > 500 |
| Non-ads ARQ jobs | Medium | Low-med | Opportunistic (start with email) |
| Pub/Sub events | Medium | Low | When architecture requires event-driven coordination |

The first three (rate limiting, cron dedup, permission cache) are low-effort, high-value, and share the same Redis dependency. They could be bundled into a single "Redis migration" chunk after the ads platform is functional.
