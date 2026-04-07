# Rate Limit Middleware — Infrastructure Requirements

**Feature**: Authenticated user rate limiting (per-user sliding window)  
**Status**: Implemented, feature-flagged (`RATE_LIMIT_ENABLED=False` by default)

---

## New Environment Variables

| Variable | Type | Default | Required | Description |
|---|---|---|---|---|
| `RATE_LIMIT_ENABLED` | bool | `False` | No | Master toggle. Set to `True` to activate per-user rate limiting on authenticated endpoints. |
| `RATE_LIMIT_MAX_TRACKED_USERS` | int | `10000` | No | Max concurrent user buckets in memory before stale eviction runs. Increase for high-traffic deployments. |
| `RATE_LIMIT_EVICTION_AGE_SECONDS` | int | `120` | No | Buckets with no activity for this many seconds are evicted when over `MAX_TRACKED_USERS`. |

---

## Activation Checklist

### Staging
1. Set `RATE_LIMIT_ENABLED=True` in Cloud Run environment
2. Monitor logs for `429` responses — search for `"Too many requests"` in structured logs
3. Verify `X-RateLimit-*` headers appear on authenticated responses
4. No new secrets, buckets, or external services required

### Production
1. After staging validation, set `RATE_LIMIT_ENABLED=True`
2. Default limits are conservative — no tuning needed initially:
   - Free-tier users (no subscription): 120 req/min
   - Subscribed users: 600 req/min
   - Internal users: exempt
3. Per-endpoint overrides for expensive routes (address autocomplete, restaurant explorer) are hardcoded in application config — not env vars

---

## Notes

- **No Redis dependency** — rate limiting is in-memory per process. In a single-container Cloud Run deployment, this is correct. If we scale to multiple containers, limits are per-container (effectively multiplied by container count). Redis-backed rate limiting is a planned future upgrade.
- **No new ports, secrets, or IAM permissions** — purely application-level, reads only from env vars.
- **Rollback**: Set `RATE_LIMIT_ENABLED=False` to disable instantly without redeployment (requires env var update + restart).
