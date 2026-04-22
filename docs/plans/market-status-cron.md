# Market Status Cron — Plan (pending implementation)

**Status:** Deferred. Not implemented. This doc seeds the decisions-to-make so the cron work starts from an agreed design instead of re-litigating scope.

**Related shipped work:** `market_info.status` now carries `inactive` as a semantic value (surfaces only in `/leads/supplier-countries`). Admin override validation is in place (see `app/routes/admin/markets.py:update_market`). The /leads/countries + /leads/supplier-countries endpoints already read from `status`. What is missing is the automation that keeps `status` honest as coverage changes over time.

**Interim operational model (until this cron ships):** admins are the sole source of status flips. The admin override guardrails (refuse `→ active` without coverage; warn + second-confirm on `→ inactive` when coverage exists) keep the invariant. Admin discipline covers freshness during the gap.

---

## Goal

Maintain `market_info.status` automatically so the customer-facing `/leads/countries` endpoint always reflects actual operational reality:

- **`active`** iff the market has operational coverage in the near-term forward window.
- **`inactive`** otherwise.

## Decisions to make at implementation time

### 1. Window definition

**Default:** rolling 30-day forward — market is `active` iff it has ≥1 active kitchen-day with ≥1 active plate within the next 30 days.

**Open variants to evaluate:**
- **Forward-only (30 days):** baseline. Simple, predictable, what most people picture.
- **Forward + 7-day backward:** smooths over brief coverage gaps (a market that paused for a week shouldn't flip off). Reduces churn at the cost of lagging genuine wind-downs.
- **Weekly-recurring existence:** `plate_kitchen_days.kitchen_day` is a day-of-week enum, not a calendar date. One active row implies continuous forward coverage. If the schema never gets a calendar-date dimension, the "30-day" framing collapses to a simple existence check — and the current admin override validation already uses exactly that predicate (`market_has_active_plate_coverage` in `app/services/market_service.py`).

Pick the window based on whether calendar-date coverage columns have been introduced by the time the cron ships. If they haven't, the cron is thin: just re-run the same existence check that the admin override uses. If they have, the cron does real date arithmetic.

### 2. Admin-override conflict semantics

- **Cron always wins on its next run.** Admin flips that contradict the window check are transient by design — the admin's use case is "react before the next cron run" (incident response, scheduled launch day, ops correction), not "permanently override the check."
- **Do not add `status_override_by_admin_at`, TTL columns, or any lock.** Keep `market_info` lean. The admin validation (refuse activation without coverage; warn on deactivation) is the guardrail that keeps the state honest between runs.
- If this produces visible flapping in practice, the fix is to lengthen the window, not to add override-protection plumbing.

### 3. Cadence and scheduling

- **Frequency:** once per day.
- **Time:** pick a low-traffic UTC window and **document the exact time** in the cron module and this file. Support needs to be able to answer "why did AR flip at 03:00?" without digging through code.
- **Registration:** wherever existing scheduled jobs live in this repo (`app/jobs/` or its equivalent — locate at implementation time; see also `docs/plans/LEAD_INTEREST_ALERT_CRONS.md` for a precedent of a scheduled job touching marketing-site data).

### 4. Backfill (first run)

- Enumerate every non-archived market including `inactive` ones and run the window check.
- Flip to the computed value regardless of current state. This reconciles the gap between shipping this ticket (admin-only) and the cron's first real run.

### 5. Logging and audit

- **Structured log per flip:** `market_id`, `country_code`, `old_status`, `new_status`, `reason`, `timestamp`. Use the existing `logger` infrastructure.
- **No dedicated audit table in v1.** The `audit.market_history` trigger (see `app/db/trigger.sql`) already captures every row mutation — the cron's flips are covered there. Structured application logs add the "why" that the history table doesn't carry.
- **v2 consideration:** if log-based history proves insufficient (e.g. ops needs queryable flip history across markets), add an `audit.market_status_transitions` table with the structured fields above. Defer until that need is real.

### 6. Failure modes and monitoring

- **Cron failure:** on error, status stays stale until the next successful run. Acceptable because:
  - Admin override is still available.
  - The customer-facing impact of a stale `active` row is an empty plans/restaurants response on the frontend, which is handled gracefully.
  - A stale `inactive` row means a market that just started serving is invisible for up to one cron cycle — acceptable for a daily cadence.
- **Alerting:** add freshness monitoring — alert if the cron hasn't run successfully in N days (pick N based on existing cron-monitoring conventions in `infra-kitchen-gcp`).

### 7. Idempotency and concurrency

- Safe to run twice in the same day — the window check is deterministic against the DB state at query time.
- No lock required unless two crons overlap. Pick a cadence that guarantees they don't (e.g. hourly would need a lock; daily doesn't).

### 8. Interaction with `/leads/countries` cache

- The country endpoints have a 10-minute process-local cache plus a 1h browser stale-while-revalidate window. A cron flip reaches end-users within ~1h + one cache cycle. Acceptable at this change frequency — don't over-engineer cross-worker invalidation.
- The ETag already derives from `market_info.modified_date`, which the cron bumps on every flip. Browser revalidation picks up changes naturally.

---

## Out of scope for the cron work

- Changing the `/leads/countries` or `/leads/supplier-countries` contracts.
- Adding Redis or push-based invalidation.
- The 429 → reCAPTCHA-unlock handshake for country-scoped reads (separate v2 ticket).
- Deprecating or removing the admin override — it stays as both a break-glass mechanism and the invariant enforcer for manual ops.

## Prior context

- Original feature plan: `docs/plans/` (country-filter work, consumed by vianda-home).
- Shipped contract and semantics: `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`.
- Admin override predicate (already in code): `market_has_active_plate_coverage` in `app/services/market_service.py`.
- vianda-home frontend spec: `/Users/cdeachaval/learn/vianda/vianda-home/docs/plans/country-filter.md`.
