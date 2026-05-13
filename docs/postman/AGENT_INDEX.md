# Postman Collections — Agent Index

## Environment Setup

All collections use `{{baseUrl}}` from either collection variables or a Postman environment.
- **Local:** `http://localhost:8000`
- **GCP:** Set `baseUrl` in a dedicated Postman environment to your Cloud Run URL

**Credentials:** Currently hardcoded in collection form-data bodies (see "Credential Migration" below).

---

## Collections

| # | Collection | Tests | Key Endpoints |
|---|---|---|---|
| 000 | E2E Vianda Selection | Full E2E: auth, supplier setup, menu, customer signup, subscription, vianda selection, QR, pickup, reviews, billing settlement | `/auth/token`, `/addresses`, `/markets`, `/plans`, `/institutions`, `/restaurants`, `/products`, `/viandas`, `/kitchen-days`, `/users`, `/subscriptions`, `/vianda-selections`, `/qr-codes`, `/pickups`, `/reviews`, `/billing` |
| 001 | Discretionary Credit System | Admin creates credit requests, super-admin approves/rejects, request lifecycle | `/auth/token`, `/admin/discretionary-credits`, `/super-admin/discretionary-credits` |
| 002 | Address Autocomplete & Validation | Address suggest, structured creation, country/city filtering | `/auth/token`, `/addresses/suggest`, `/addresses` |
| 003 | Enum Service | All enums with labels, individual enums, cuisines, customer access | `/auth/token`, `/enums`, `/cuisines` |
| 004 | Restaurant Explorer B2C | City dropdown, restaurant list by city with geolocation | `/auth/token`, `/restaurants/cities`, `/restaurants/by-city` |
| 005 | Timezone Deduction Tests | Address creation with automatic timezone, Argentina-specific validation | `/auth/token`, `/addresses` |
| 006 | Zipcode Lead Metrics | Unauthenticated zipcode coverage metrics | `/leads/zipcode-metrics` |
| 007 | Geolocation Testing | Geocoding gateway, DEV_MODE mock vs real API | `/auth/token`, geolocation gateway |
| 008 | Role and Field Access | Address type restrictions by role, user creation permissions, institution field-level access | `/auth/token`, `/addresses`, `/users`, `/institutions` |
| 009 | Customer Stripe Config | Payment method lifecycle: list, setup-session, mock-add, delete, set default | `/auth/token`, `/customer/payment-methods` |
| 010 | Permissions - Employee-Only Access | Employee-only endpoint access, employer assignment, plans, credit currencies, markets | `/auth/token`, `/employers`, `/plans`, `/credit-currencies`, `/markets` |
| 011 | Employer Program | Full employer lifecycle: institution, entity CRUD, program config, employee enrollment (single + bulk CSV), domain management, billing generation, cron | `/auth/token`, `/institutions`, `/employers`, `/employer/program`, `/employer/employees`, `/employer/domains`, `/employer/billing` |
| 012 | Billing, Payout & Stripe Connect | Institution bills (CRUD, settlement pipeline, summary), client bills, supplier invoices (create, review, match), W-9, Stripe Connect (onboarding, status, payout), enriched payouts | `/institution-bills`, `/client-bills`, `/supplier-invoices`, `/supplier-w9`, `/institution-entities/{id}/stripe-connect/*`, `/payouts` |
| 013 | Subscription Actions | Payment details, confirm, hold/resume, cancel, renewal preferences, enriched views | `/subscriptions/{id}/hold`, `/subscriptions/{id}/resume`, `/subscriptions/{id}/cancel`, `/subscriptions/me/renewal-preferences`, `/subscriptions/enriched` |
| 014 | Ingredients & Favorites | Ingredient search (local + OFF), custom ingredient creation, favorite CRUD (vianda + restaurant) | `/ingredients/search`, `/ingredients/custom`, `/favorites`, `/favorites/me`, `/favorites/me/ids` |

---

## Coverage Gap Summary

Services tested only via Postman (per CLAUDE.md) that currently **lack** dedicated collection coverage:

| Gap Area | Services / Routes | Priority |
|---|---|---|
| ~~Employer Program~~ | ~~`employer/program_service`, `employer/enrollment_service`, `employer/billing_service`~~ | ~~Covered by 011~~ |
| ~~Supplier Billing~~ | ~~`billing/supplier_invoice_service`, `billing/supplier_w9_service`, `billing/tax_doc_service`~~ | ~~Covered by 012~~ |
| ~~Client Billing~~ | ~~`billing/client_bill`, `billing/institution_billing`~~ | ~~Covered by 012~~ |
| ~~Payout & Settlement~~ | ~~`routes/billing/payout`~~ | ~~Covered by 012~~ |
| ~~Stripe Connect~~ | ~~`payment_provider/stripe/connect_gateway`~~ | ~~Covered by 012~~ |
| ~~Ingredients~~ | ~~`ingredient_service`, `open_food_facts_service`~~ | ~~Covered by 014~~ |
| ~~Subscription Actions~~ | ~~`subscription_action_service` (hold/resume/cancel)~~ | ~~Covered by 013~~ |
| ~~Favorites & Recommendations~~ | ~~`favorite_service`, `recommendation_service`~~ | ~~Covered by 014 (recommendations are embedded in explore, not standalone)~~ |
| Messaging Preferences | `messaging_preferences_service` | Low |
| Webhooks | `routes/webhooks` (Stripe callbacks) | Low |
| Coworker Management | `coworker_service` | Low |

**Already covered by pytest** (not needed in Postman): `app/utils/`, `app/gateways/`, `app/auth/`, `app/security/`, `app/services/error_handling.py`, route factories.

**Cron jobs** are background-triggered and not HTTP-testable via Postman.

---

## Credential Migration (DONE)

All collections now use environment variables for credentials. No hardcoded passwords remain in collection variables.
- **Super Admin:** `{{superAdminUsername}}` / `{{superAdminPassword}}` — set in `local` and `gcp_kitchen_dev` environments
- **Admin:** `{{adminUsername}}` / `{{adminPassword}}` — created by 000 "Register Admin User" request (Internal/Admin at Vianda Enterprises). Used by 001, 008, 010 for permissions testing
- **Customer/Supplier:** `{{customerUsername}}` / `{{supplierUsername}}` etc. — set by 000 E2E Vianda Selection run
- Collections 002, 003, 004, 005, 007 switched from admin to superAdmin credentials (admin was only used for generic auth)
