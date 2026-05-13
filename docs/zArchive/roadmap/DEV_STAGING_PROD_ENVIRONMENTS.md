# Dev / Staging / Prod Environment Configuration

**Last Updated**: 2026-03-09  
**Purpose**: Plan for configuring Dev, Staging, and Prod environments with environment-specific behavior. Implementation is future work; this document captures the roadmap.

---

## Executive Summary

- **Dev**: Relax time constraints (e.g. kitchen promotion, business hours) so E2E and local testing work deterministically regardless of when tests run.
- **Staging**: Mirror production behavior for pre-release validation.
- **Prod**: Production behavior; no relaxations.

---

## 1. Kitchen Start Promotion (vianda_pickup_live)

### Current Behavior

`kitchen_start_promotion` promotes `vianda_selection_info` rows to `vianda_pickup_live` only when:

- Current day is Monday–Friday (kitchen day)
- Current time in market timezone >= `business_hours.open` (e.g. 11:30 AM Argentina)

This causes E2E and local flows to fail when run outside business hours or on weekends.

### Dev Environment (Planned)

- **Time constraints removed**: Kitchen promotion runs regardless of time-of-day and day-of-week.
- **Implementation**: Config flag (e.g. `DEV_RELAX_KITCHEN_HOURS=true`) or environment detection; when set, skip the `now_local.time() < open_time` and weekend checks in `run_kitchen_start_promotion`.
- **Benefit**: E2E collection 000 and local testing work at any time.

### Staging and Prod

- Keep production behavior: promotion runs only during configured kitchen hours.
- Staging and Prod must reflect real-world timing for accurate validation.

---

## 2. Other Environment-Specific Settings

### Possible Future Additions

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| Kitchen hours bypass | Yes | No | No |
| Cron job intervals | Shorter (faster feedback) | Normal | Normal |
| Log level | DEBUG | INFO | WARN/ERROR |
| Feature flags | All enabled for testing | Per-release | Per-release |
| Payment provider | Mock | Sandbox/Test | Live |
| Email/sms | Console/log | Sandbox | Live |

### Configuration Approach

- Use environment variables or a config file (e.g. `app/config/settings.py`) to distinguish env.
- Avoid hardcoding; support `ENV=dev|staging|prod` or similar.
- Document required env vars per environment in deployment docs.

---

## 3. Implementation Order (Future)

1. Add `DEV_RELAX_KITCHEN_HOURS` (or equivalent) to settings.
2. Update `run_kitchen_start_promotion` to bypass time checks when the flag is set.
3. Set the flag in Dev deployment / local `.env`; leave unset in Staging/Prod.
4. Optionally: add similar relaxations for other time-sensitive crons (e.g. billing, subscription renewal).
5. Document in deployment and developer setup guides.

---

## 4. Related Documents

- [billing/MARKET_SPECIFIC_KITCHEN_DAY_CONFIGURATION.md](../billing/MARKET_SPECIFIC_KITCHEN_DAY_CONFIGURATION.md) — Kitchen day and business hours configuration
- [postman/collections/000 E2E Vianda Selection](../postman/collections/) — E2E collection; resilient to outside-kitchen-hours via `pm.execution.skipRequest` when no pickups
