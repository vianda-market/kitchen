# Roadmap

Future features and follow-up work.

| Document | Description |
|----------|-------------|
| [ADDRESS_AUTOCOMPLETE_SESSION_TOKENS.md](ADDRESS_AUTOCOMPLETE_SESSION_TOKENS.md) | Session tokens for suggest/create to reduce Google Places API cost |
| [ADDRESS_VALIDATE_FLOW_REMOVAL.md](ADDRESS_VALIDATE_FLOW_REMOVAL.md) | Validate endpoint removed; all creation via autocomplete + place_id |
| [ADDRESS_SUBPREMISE_FLOOR_UNIT_ROADMAP.md](ADDRESS_SUBPREMISE_FLOOR_UNIT_ROADMAP.md) | Store floor/unit in separate table; keep building-level address_id for coworker scoping |
| [ADDRESS_RATE_LIMITING_AND_CACHING.md](ADDRESS_RATE_LIMITING_AND_CACHING.md) | Rate limiting and caching for address suggest |
| [ADDRESS_CITY_BOUNDS_SCOPING.md](ADDRESS_CITY_BOUNDS_SCOPING.md) | Lat/lng bounds per supported city for Autocomplete |
| [GOOGLE_MAPS_OTHER_APIS_ROADMAP.md](GOOGLE_MAPS_OTHER_APIS_ROADMAP.md) | Other Google Maps APIs: Distance Matrix, Nearby Search, delivery zones, store locator, analytics |
| [B2C_EXPLORE_ZIPCODE.md](B2C_EXPLORE_ZIPCODE.md) | Scope B2C explore to a city then search by zipcode within that city (future) |
| [LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md) | Add `language` to Markets; expose enum display labels per language for localized dropdowns |
| [USER_MARKET_ASSIGNMENT_DESIGN.md](USER_MARKET_ASSIGNMENT_DESIGN.md) | v1: User–market assignment (one market per user, NOT NULL); how Super Admin assigns market at registration and update |
| [USER_MARKET_AND_GLOBAL_MANAGER_V2.md](USER_MARKET_AND_GLOBAL_MANAGER_V2.md) | v2: Multi-market assignment; Global Manager. v3: Cross-country plans (multi-plan signup), travel mode (open periods to consume in other countries). |
| [VIANDA_EMPLOYER_BENEFITS_PROGRAM.md](VIANDA_EMPLOYER_BENEFITS_PROGRAM.md) | Employer institutions (`institution_type = Employer`); onboarding benefits-program employees via a different route than standard B2C subscription path; institution-scoped subscription list later. |
| [SUBSCRIPTION_MANAGEMENT_FUTURE.md](SUBSCRIPTION_MANAGEMENT_FUTURE.md) | Out-of-scope follow-ups for B2C subscription actions: Employee cancel/hold/resume, cron for hold reconciliation, generic PUT for status/hold dates. |
| [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md) | Full Stripe integration per customer (Stripe Customer + saved payment methods); mock endpoints for UI; phased implementation. |
| [RESTAURANT_KITCHEN_HOURS_OVERRIDE_ROADMAP.md](RESTAURANT_KITCHEN_HOURS_OVERRIDE_ROADMAP.md) | Future: restaurant-level kitchen hours override (B2B); per-restaurant open/close times instead of market-only. |
| [DEV_STAGING_PROD_ENVIRONMENTS.md](DEV_STAGING_PROD_ENVIRONMENTS.md) | Dev/Staging/Prod configuration: Dev with time constraints removed (e.g. kitchen promotion); Staging/Prod with production behavior. |
