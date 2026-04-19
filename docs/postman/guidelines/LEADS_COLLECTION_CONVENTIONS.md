# Leads Collection Conventions

This file is the source of truth for how Postman collections covering the public `/leads/*` surface are organized. It applies to any collection that exercises endpoints under `/api/v1/leads/*` or admin endpoints whose contract is consumed by a marketing/lead-capture frontend.

## 1. One collection per frontend consumer

Organize leads-adjacent collections by the **frontend that consumes them**, not by the endpoint group they touch.

| Collection | Consumer | Surface |
|---|---|---|
| `006 LEADS_MARKETING_SITE` | vianda-home | Country selectors, zipcode metrics, country-scoped plans/restaurants/featured-restaurant, admin override guardrails |
| `LEADS_B2C_APP` *(create when needed)* | vianda-app | B2C onboarding lead capture, if/when it diverges from the marketing site |

Rationale: a single frontend release ships one set of contract expectations. When `country_code` becomes required on `/leads/plans`, that change lands in the same release as the country selector — and the same collection covers it. Splitting by endpoint group (`ZIPCODE_LEAD_METRICS`, `LEADS_COUNTRY_FILTER`, …) creates one-to-three-request collections that drift apart and force every contract change to touch multiple files.

**Don't add a new "017 LEADS_X" or "018 LEADS_Y".** Add the requests to the existing per-consumer collection.

## 2. Shared super-admin auth

Several collections need a super-admin token. Don't duplicate the `Login Super Admin` request body. Pick one of:

### Option A — idempotent in-collection login (default)

The collection's `Login Super Admin` request has a pre-request script that checks `pm.globals.get('superAdminAuthToken')` and skips itself if a token is already present (using `postman.setNextRequest(...)` to jump to the next step). This is what `006 LEADS_MARKETING_SITE` does.

Cost: one identical request per collection. Benefit: each collection still runs standalone in Postman with no setup.

### Option B — Newman `--globals` (CI / multi-collection runs)

When running multiple collections together in CI, run a one-shot login first and pass the token as a global:

```bash
# 1. Login once, dump globals to disk.
newman run docs/postman/collections/_seed_super_admin_login.postman_collection.json \
  --env-var baseUrl=$BASE_URL \
  --env-var superAdminUsername=$SUPER_ADMIN_USER \
  --env-var superAdminPassword=$SUPER_ADMIN_PASS \
  --export-globals /tmp/super-admin.globals.json

# 2. Reuse for all subsequent collections.
newman run "docs/postman/collections/006 LEADS_MARKETING_SITE.postman_collection.json" \
  --globals /tmp/super-admin.globals.json
```

The pre-request guard from Option A makes the in-collection `Login Super Admin` a no-op when the global is already set — no special flag needed.

> A `_seed_super_admin_login.postman_collection.json` seed collection is **not** in the repo yet. Add it the first time CI runs more than two leads-adjacent collections in sequence.

## 3. Variable naming

| Variable | Canonical name | Notes |
|---|---|---|
| reCAPTCHA v3 token | `recaptchaToken` | Use this exact name in every leads-adjacent collection. **Do not** invent variants like `recaptchaTokenOrEmpty`, `captcha`, `recaptcha_v3`. |
| Super admin bearer | `superAdminAuthToken` | Set as collection variable, environment variable, **and** global by the login request — so consumers using any scope find it. |
| Base URL | `baseUrl` | Default `http://localhost:8000`. Override per environment file under `docs/postman/environments/`. |

### `recaptchaToken` value strategy

- **Local dev:** any non-empty string works (`dev-bypass`) when `RECAPTCHA_SECRET_KEY` is unset — `verify_recaptcha` short-circuits.
- **Staging / prod:** must be a real reCAPTCHA v3 token issued by the configured site key. Generate from the `vianda-home` test page, paste into the environment file, and run within the token's TTL (~2 min).

If the variable name diverges across collections, every staging run requires editing N files instead of one environment file.

## 4. Where the contracts live

- `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` — full country-filter contract (countries / supplier-countries / country_code semantics / admin override guardrails).
- `docs/api/b2c_client/feedback_from_client/RESTAURANTS_BY_ZIPCODE.md` — zipcode-metrics contract.
- `docs/plans/market-status-cron.md` — pending follow-up for the auto-deactivation cron (the admin override is the manual-path counterpart).

When a `/leads/*` contract changes, update the matching API doc **and** the test in `006 LEADS_MARKETING_SITE` in the same PR.
