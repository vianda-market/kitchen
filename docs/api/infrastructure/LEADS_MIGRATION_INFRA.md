# Leads Migration — Infrastructure Changes

**Audience:** infra-kitchen-gcp agent  
**Scope:** New environment variables for Cloud Run config

---

## New Environment Variables

### reCAPTCHA v3

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RECAPTCHA_SECRET_KEY` | Yes (prod/staging) | `""` (empty = disabled) | Server-side secret key from Google reCAPTCHA v3 admin console. Empty disables CAPTCHA (local dev convenience). |
| `RECAPTCHA_SCORE_THRESHOLD` | No | `0.3` | Minimum reCAPTCHA score to pass (0.0 = bot, 1.0 = human). Start with 0.3, tighten if bots get through. |

**Setup:** Create a reCAPTCHA v3 project in the Google Cloud console (same project as the existing Firebase/GCS setup). This generates a **site key** (public, for vianda-home frontend) and a **secret key** (server-side, for the backend).

- **Secret key** → `RECAPTCHA_SECRET_KEY` env var on Cloud Run
- **Site key** → vianda-home's `VITE_RECAPTCHA_SITE_KEY` env var (not a backend concern)

### CORS

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ALLOWED_ORIGINS` | Yes (prod/staging) | `""` (empty = allow all) | Comma-separated list of allowed origins. Empty allows all origins (local dev). |

**Per-environment values:**

| Environment | Value |
|-------------|-------|
| **dev** | `https://dev.vianda.market,https://platform.dev.vianda.market,https://api.dev.vianda.market,http://localhost:8081,http://localhost:3000,http://localhost:5173` |
| **staging** | `https://staging.vianda.market,https://platform.staging.vianda.market,https://api.staging.vianda.market` |
| **prod** | `https://vianda.market,https://platform.vianda.market,https://api.vianda.market` |

**Note on mobile apps:** Native iOS/Android apps do not send an `Origin` header. Starlette CORS middleware only acts on requests that include an `Origin` header, so mobile traffic passes through unaffected regardless of the allowlist.

---

## No Other Infrastructure Changes

- **No new Cloud Run services** — all endpoints run on the existing kitchen API
- **No new GCS buckets** — lead interest data is stored in PostgreSQL
- **No new Cloud Scheduler jobs** — alert cron jobs are Phase 3 (future)
- **No new databases** — uses the existing `kitchen` PostgreSQL database
- **No new secrets in Secret Manager** — `RECAPTCHA_SECRET_KEY` can be a plain env var or a Secret Manager reference, at your discretion

---

## Database Changes (for awareness, not infra action)

The backend added:
- 3 new PostgreSQL enum types (`interest_type_enum`, `lead_interest_status_enum`, `lead_interest_source_enum`)
- 1 new table (`core.lead_interest`)
- 1 new column on `customer.plan_info` (`highlighted`)
- 3 new indexes on `core.lead_interest`

These are applied via `bash app/db/build_kitchen_db.sh` (teardown + rebuild). No migration scripts to run in deployed environments — the build script handles it.
