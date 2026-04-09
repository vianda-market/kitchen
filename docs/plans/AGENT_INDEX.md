# Kitchen Roadmap — Agent Index

Planned features and initiatives across all repositories.
Add this file's path to your repo's `CLAUDE.md` to align implementation work with what is planned or in progress on the backend.

```
/Users/cdeachaval/learn/kitchen/docs/plans/AGENT_INDEX.md
```

**Audience key**: `B2C` = kitchen-mobile · `B2B` = kitchen-web · `Backend` = kitchen (this repo) · `Cross-repo` = coordination required across two or more repos

> Before building a feature, check this index for an existing roadmap doc. If one exists, read it — it likely contains schema decisions, API contracts, and sequencing constraints that affect your implementation.

---

## Cross-Repo — Requires Coordination

These features have work items in multiple repos. Read the roadmap doc before starting implementation on any side.

| Affects | File | What Is Planned |
|---------|------|-----------------|
| Marketing + B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/LEADS_MIGRATION_TO_MARKETING_SITE.md` | **Complete** — Leads discovery flow migrated to marketing site. Coverage checker, interest capture, B2C simplification, B2B dashboard |
| B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md` | Full Stripe integration — Setup Session, saved cards, webhooks (Phase 3 live) |
| B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/STRIPE_CUSTOMER_INTEGRATION_FOLLOWUPS.md` | Production hardening — race conditions, webhook sync, idempotency |
| B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/MOBILE_VERIFICATION_ROADMAP.md` | SMS verification for mobile numbers via Twilio Verify |
| B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/MESSAGING_AND_NOTIFICATIONS_ROADMAP.md` | Delivery systems for push, SMS, and email notification channels |
| B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md` | Language-aware enum labels and market language support for localized UI |
| B2C + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/b2c_client/MULTI_LANGUAGE_ROADMAP.md` | Spanish language toggle — UI strings and locale-aware API responses |
| B2B + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/VIANDA_EMPLOYER_BENEFITS_PROGRAM.md` | Employer benefit institutions — onboarding, employee enrollment, benefit limits |
| B2B + Backend | `/Users/cdeachaval/learn/kitchen/docs/plans/SUBSCRIPTION_MANAGEMENT_FUTURE.md` | Employee cancel/hold/resume on behalf of customer, cron reconciliation |
| B2B + Backend | _(Archived)_ `docs/zArchive/roadmap/SUPPLIER_TERMS_ROADMAP.md` | Implemented — Supplier terms table, pipeline wiring, B2B API. See `docs/api/b2b_client/SUPPLIER_TERMS_B2B.md` for client guide |

---

## B2C (kitchen-mobile)

| File | What Is Planned |
|------|-----------------|
| _(Archived)_ `docs/zArchive/roadmap/STATIC_MAP_CITY_SNAPSHOT_ROADMAP.md` | Implemented — Static map images via `GET /maps/city-snapshot`. See `docs/api/b2c_client/STATIC_MAP_SNAPSHOT_B2C.md` for client guide |
| `/Users/cdeachaval/learn/kitchen/docs/plans/B2C_EXPLORE_ZIPCODE.md` | Scope Explore to city, then refine search by zipcode |
| `/Users/cdeachaval/learn/kitchen/docs/plans/b2c_client/EXPLORE_FILTERS_ROADMAP.md` | Radius, cuisine, and dietary filters on the restaurant Explore screen |
| `/Users/cdeachaval/learn/kitchen/docs/plans/b2c_client/ACCESSIBILITY_ROADMAP.md` | WCAG 2.1 AA accessibility standards for mobile |

---

## B2B (kitchen-web)

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/RESTAURANT_KITCHEN_HOURS_OVERRIDE_ROADMAP.md` | Restaurant-level overrides of market-wide kitchen hours |
| `/Users/cdeachaval/learn/kitchen/docs/plans/b2b_client/SETUP_WIZARD_POST_CREATE_FLOW_ROADMAP.md` | Multi-step wizard pattern for dependent entity creation flows |
| `/Users/cdeachaval/learn/kitchen/docs/plans/b2b_client/BULK_OPERATIONS_AUDIT.md` | Entities and workflows where bulk operations would reduce friction |

---

## Backend (kitchen)

These are backend-only planned changes. Client agents should read them when they may affect API contracts or response shapes.

### Payments & Billing

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/SUPPLIER_BILLING_COMPLIANCE_ROADMAP.md` | Supplier invoice compliance — AR/PE/US invoice tracking, bill matching, payout gate, validation progression |
| `/Users/cdeachaval/learn/kitchen/docs/plans/PAYOUT_DRILL_DOWN_VIEW_ROADMAP.md` | Drill-down view: click payout → bill → settlements → restaurants → transactions |

> **Completed and archived:**
> - `SUPPLIER_TERMS_ROADMAP.md` → `docs/zArchive/roadmap/` — Supplier terms table (`no_show_discount`, `payment_frequency`, `require_invoice`, `invoice_hold_days`), pipeline wiring, B2B API
> - `STRIPE_SUPPLIER_OUTBOUND_CONNECT_ROADMAP.md` → `docs/zArchive/roadmap/` — Stripe Connect outbound payouts, `institution_bill_payout` table, settlement pipeline, webhook handlers, error mapping, admin visibility
> - `STRIPE_CONNECT_EMBEDDED_ONBOARDING.md` → `docs/zArchive/roadmap/` — Embedded onboarding via AccountSession, aggregator-per-market model, `payout_onboarding_status`

### Address & Geolocation

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/MAPBOX_MIGRATION_ROADMAP.md` | **Active** — Migrate from Google to Mapbox for geocoding, autocomplete, maps. Three phases: ephemeral → permanent storage → Google place_id fallback |
| `/Users/cdeachaval/learn/kitchen/docs/plans/database/ADDRESS_AUTOCOMPLETE_SESSION_TOKENS.md` | Google session tokens for address autocomplete to reduce API cost (feeds into Mapbox Phase 3) |
| `/Users/cdeachaval/learn/kitchen/docs/plans/database/ADDRESS_RATE_LIMITING_AND_CACHING.md` | Rate limiting and caching for address suggest and create endpoints |
| `/Users/cdeachaval/learn/kitchen/docs/plans/database/ADDRESS_CITY_BOUNDS_SCOPING.md` | _(Superseded)_ Scoped address search to supported cities — Mapbox handles natively |
| `/Users/cdeachaval/learn/kitchen/docs/plans/GOOGLE_MAPS_OTHER_APIS_ROADMAP.md` | Evaluating Distance Matrix, Nearby Search, delivery zones APIs — future evaluation for Mapbox equivalents |

### Configuration & Data

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/CUISINE_MANAGEMENT_ROADMAP.md` | DB-managed cuisine lookup table, supplier suggestion flow, admin curation, AI review agent |
| `/Users/cdeachaval/learn/kitchen/docs/plans/CONFIG_TO_DB_MIGRATION.md` | Move kitchen hours, timezones, and operational config from Python files to DB |

### Supplier Success & Onboarding

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | **Active** — Onboarding status endpoint, JWT claim, stall detection cron, email infrastructure upgrade (Gmail → SendGrid), employer onboarding |

### Lead Interest Alerts

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/LEAD_INTEREST_ALERT_CRONS.md` | Zipcode + city alert crons — notify leads when new restaurants open in their area |

### Security & Infrastructure

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md` | CAPTCHA and rate limiting for address suggest, leads, and signup endpoints |
| `/Users/cdeachaval/learn/kitchen/docs/plans/efficiencies/EXISTENCE_VS_ACCESS_CONTROL.md` | Security pattern — existence checks vs. access control checks analysis |

### Observability

| File | What Is Planned |
|------|-----------------|
| `/Users/cdeachaval/learn/kitchen/docs/plans/dynamic-logging.md` | Runtime log level control via environment variables without redeploy |
