# Kitchen Roadmap — Agent Index

Planned features and initiatives across all repositories.
Add this file's path to your repo's `CLAUDE.md` to align implementation work with what is planned or in progress on the backend.

```
/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/AGENT_INDEX.md
```

**Audience key**: `B2C` = kitchen-mobile · `B2B` = kitchen-web · `Backend` = kitchen (this repo) · `Cross-repo` = coordination required across two or more repos

> Before building a feature, check this index for an existing roadmap doc. If one exists, read it — it likely contains schema decisions, API contracts, and sequencing constraints that affect your implementation.

---

## Cross-Repo — Requires Coordination

These features have work items in multiple repos. Read the roadmap doc before starting implementation on any side.

| Affects | File | What Is Planned |
|---------|------|-----------------|
| B2C + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md` | Full Stripe integration — Setup Session, saved cards, webhooks (Phase 3 live) |
| B2C + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/STRIPE_CUSTOMER_INTEGRATION_FOLLOWUPS.md` | Production hardening — race conditions, webhook sync, idempotency |
| B2C + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/MOBILE_VERIFICATION_ROADMAP.md` | SMS verification for mobile numbers via Twilio Verify |
| B2C + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/MESSAGING_AND_NOTIFICATIONS_ROADMAP.md` | Delivery systems for push, SMS, and email notification channels |
| B2C + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md` | Language-aware enum labels and market language support for localized UI |
| B2C + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/b2c_client/MULTI_LANGUAGE_ROADMAP.md` | Spanish language toggle — UI strings and locale-aware API responses |
| B2B + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/VIANDA_EMPLOYER_BENEFITS_PROGRAM.md` | Employer benefit institutions — onboarding, employee enrollment, benefit limits |
| B2B + Backend | `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/SUBSCRIPTION_MANAGEMENT_FUTURE.md` | Employee cancel/hold/resume on behalf of customer, cron reconciliation |

---

## B2C (kitchen-mobile)

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/B2C_EXPLORE_ZIPCODE.md` | Scope Explore to city, then refine search by zipcode |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/b2c_client/EXPLORE_FILTERS_ROADMAP.md` | Radius, cuisine, and dietary filters on the restaurant Explore screen |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/b2c_client/ACCESSIBILITY_ROADMAP.md` | WCAG 2.1 AA accessibility standards for mobile |

---

## B2B (kitchen-web)

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/RESTAURANT_KITCHEN_HOURS_OVERRIDE_ROADMAP.md` | Restaurant-level overrides of market-wide kitchen hours |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/b2b_client/SETUP_WIZARD_POST_CREATE_FLOW_ROADMAP.md` | Multi-step wizard pattern for dependent entity creation flows |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/b2b_client/BULK_OPERATIONS_AUDIT.md` | Entities and workflows where bulk operations would reduce friction |

---

## Backend (kitchen)

These are backend-only planned changes. Client agents should read them when they may affect API contracts or response shapes.

### Payments & Billing

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/STRIPE_SUPPLIER_OUTBOUND_CONNECT_ROADMAP.md` | Stripe Connect infrastructure for automated supplier payouts |

### Address & Geolocation

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/database/ADDRESS_AUTOCOMPLETE_SESSION_TOKENS.md` | Google session tokens for address autocomplete to reduce API cost |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/database/ADDRESS_RATE_LIMITING_AND_CACHING.md` | Rate limiting and caching for address suggest and create endpoints |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/database/ADDRESS_CITY_BOUNDS_SCOPING.md` | _(Superseded)_ Scoped address search to supported cities — kept for context |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/GOOGLE_MAPS_OTHER_APIS_ROADMAP.md` | Evaluating Distance Matrix, Nearby Search, delivery zones APIs |

### Configuration & Data

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/CONFIG_TO_DB_MIGRATION.md` | Move kitchen hours, timezones, and operational config from Python files to DB |

### Security & Infrastructure

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md` | CAPTCHA and rate limiting for address suggest, leads, and signup endpoints |
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/efficiencies/EXISTENCE_VS_ACCESS_CONTROL.md` | Security pattern — existence checks vs. access control checks analysis |

### Observability

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/Desktop/local/kitchen/docs/roadmap/dynamic-logging.md` | Runtime log level control via environment variables without redeploy |
