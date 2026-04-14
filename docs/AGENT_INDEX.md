# Agent Index

Quick-reference index of client-facing and internal documentation. Start here to find the right doc for any feature or API contract.

---

## Shared Client Docs (`docs/api/shared_client/`)

Docs shared by both B2B (kitchen-web) and B2C (kitchen-mobile). Single source of truth.

| Doc | Summary |
|-----|---------|
| [README](api/shared_client/README.md) | Copy instructions, folder structure, full contents list |
| [API_PERMISSIONS_BY_ROLE](api/shared_client/API_PERMISSIONS_BY_ROLE.md) | Permission matrix by role |
| [USERNAME_RECOVERY](api/shared_client/USERNAME_RECOVERY.md) | Forgot username flow: `POST /api/v1/auth/forgot-username` (no auth, rate-limited). Optionally sends password-reset link. |
| [PASSWORD_RECOVERY_CLIENT](api/shared_client/PASSWORD_RECOVERY_CLIENT.md) | Forgot password flow |
| [EMAIL_REGISTERED_CHECK_CLIENT](api/shared_client/EMAIL_REGISTERED_CHECK_CLIENT.md) | Check if email is already registered |
| [USERNAME_IMMUTABLE_CLIENT](api/shared_client/USERNAME_IMMUTABLE_CLIENT.md) | Username is read-only after creation |
| [USER_MODEL_FOR_CLIENTS](api/shared_client/USER_MODEL_FOR_CLIENTS.md) | User model shape for clients |
| [USER_UPDATE_PATTERN](api/shared_client/USER_UPDATE_PATTERN.md) | User updates: self (/me) and by others; immutable fields |
| [USER_SELF_UPDATE_PATTERN](api/shared_client/USER_SELF_UPDATE_PATTERN.md) | `/me` endpoint for self-updates |
| [USER_AND_MARKET_API_CLIENT](api/shared_client/USER_AND_MARKET_API_CLIENT.md) | User-market storage and API |
| [MARKET_AND_SCOPE_GUIDELINE](api/shared_client/MARKET_AND_SCOPE_GUIDELINE.md) | Markets API, scope, subscriptions, country-flag UI |
| [LEADS_API_SCOPE](api/shared_client/LEADS_API_SCOPE.md) | All unauthenticated `/api/v1/leads/` endpoints |
| [ZIPCODE_METRICS_LEAD_API](api/shared_client/ZIPCODE_METRICS_LEAD_API.md) | Lead encouragement: `GET /api/v1/leads/zipcode-metrics` |
| [ENRICHED_ENDPOINT_PATTERN](api/shared_client/ENRICHED_ENDPOINT_PATTERN.md) | `/enriched/` denormalized data pattern |
| [ENRICHED_ENDPOINT_UI_IMPLEMENTATION](api/shared_client/ENRICHED_ENDPOINT_UI_IMPLEMENTATION.md) | TypeScript/React examples for enriched endpoints |
| [ARCHIVED_RECORDS_PATTERN](api/shared_client/ARCHIVED_RECORDS_PATTERN.md) | `include_archived` query behavior |
| [SCOPING_BEHAVIOR_FOR_UI](api/shared_client/SCOPING_BEHAVIOR_FOR_UI.md) | Institution/user scoping |
| [BULK_API_PATTERN](api/shared_client/BULK_API_PATTERN.md) | Bulk operations |
| [COUNTRY_CODE_API_CONTRACT](api/shared_client/COUNTRY_CODE_API_CONTRACT.md) | Country code normalization (alpha-2/alpha-3) |
| [ADDRESSES_API_CLIENT](api/shared_client/ADDRESSES_API_CLIENT.md) | Address suggest, create (place_id or structured), CRUD |
| [PROVINCES_API_CLIENT](api/shared_client/PROVINCES_API_CLIENT.md) | Provinces/states: Country -> Province -> City cascade |
| [CUISINES_API_CLIENT](api/shared_client/CUISINES_API_CLIENT.md) | Cuisines API |
| [PLATE_API_CLIENT](api/shared_client/PLATE_API_CLIENT.md) | Plate: enriched, create/update, selection, pickup pending |
| [PLANS_FILTER_CLIENT_INTEGRATION](api/shared_client/PLANS_FILTER_CLIENT_INTEGRATION.md) | Plans filtering |
| [ENUM_SERVICE_API](api/shared_client/ENUM_SERVICE_API.md) | Enum service endpoints |
| [ENUM_SERVICE_SPECIFICATION](api/shared_client/ENUM_SERVICE_SPECIFICATION.md) | Enum service specification |
| [CUSTOMER_PAYMENT_METHODS_API](api/shared_client/CUSTOMER_PAYMENT_METHODS_API.md) | Payment methods: list, add, delete, set default |
| [PAYMENT_AND_BILLING_CLIENT_CHANGES](api/shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md) | Payment atomic with billing; fintech link deprecation |
| [RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS](api/shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md) | Restaurant status and plate kitchen days |
| [STATUS_ON_CREATE](api/shared_client/STATUS_ON_CREATE.md) | Status on create: omit or null, backend assigns default |
| [DEBUG_LOGGING_STRATEGY](api/shared_client/DEBUG_LOGGING_STRATEGY.md) | Debug logging: `DEBUG_PASSWORD_RECOVERY` env var |

---

## B2B Client Docs (`docs/api/b2b_client/`)

B2B-specific docs for kitchen-web (Restaurant + Employee backoffice).

| Doc | Summary |
|-----|---------|
| [README](api/b2b_client/README.md) | B2B overview, copy instructions, shared doc links |
| [FRONTEND_AGENT_README](api/b2b_client/FRONTEND_AGENT_README.md) | Agent onboarding for B2B |
| [LOCAL_NETWORK_DEV](api/b2b_client/LOCAL_NETWORK_DEV.md) | Local backend run scripts; API URL config |
| [B2B_USER_INVITE_FLOW](api/b2b_client/B2B_USER_INVITE_FLOW.md) | User invite flow |
| [CHANGE_PASSWORD_AND_ADMIN_RESET](api/b2b_client/API_CLIENT_PASSWORD_MANAGEMENT.md) | Password change, admin reset |
| [ROLE_AND_FIELD_ACCESS_CLIENT](api/b2b_client/API_CLIENT_ROLE_FIELD_ACCESS.md) | Role/field access for B2B |
| [API_CLIENT_MARKETS](api/b2b_client/API_CLIENT_MARKETS.md) | Markets API for B2B |
| [API_CLIENT_INSTITUTIONS](api/b2b_client/API_CLIENT_INSTITUTIONS.md) | Institution market_id |
| [INSTITUTION_NO_SHOW_DISCOUNT](api/b2b_client/INSTITUTION_NO_SHOW_DISCOUNT.md) | Institution no-show discount |
| [PLAN_API_MARKET_CURRENCY](api/b2b_client/PLAN_API_MARKET_CURRENCY.md) | Plan create/update: currency from market |
| [PLAN_ROLLOVER_UI_HIDDEN](api/b2b_client/PLAN_ROLLOVER_UI_HIDDEN.md) | Plan rollover UI hidden |
| [CREDIT_CURRENCY_EDIT_IMMUTABLE_CURRENCY](api/b2b_client/CREDIT_CURRENCY_EDIT_IMMUTABLE_CURRENCY.md) | Credit currency: immutable currency field |
| [SUPPORTED_CURRENCIES_API](api/b2b_client/SUPPORTED_CURRENCIES_API.md) | Supported currencies list (dropdown) |
| [RESTAURANT_AND_INSTITUTION_ENTITY_CREDIT_CURRENCY](api/b2b_client/RESTAURANT_AND_INSTITUTION_ENTITY_CREDIT_CURRENCY.md) | Entity create: currency derived from address -> market |
| [EMPLOYER_ASSIGNMENT_WORKFLOW](api/b2b_client/API_CLIENT_EMPLOYER_ASSIGNMENT.md) | Backoffice employer management |
| [EMPLOYER_ADDRESS_PROTECTION_AND_CITIES_B2B](api/b2b_client/API_CLIENT_EMPLOYER_ADDRESSES_CITIES.md) | Employer address protection; Cities API |
| [DISCRETIONARY_REQUEST_FORM_GUIDE](api/b2b_client/DISCRETIONARY_REQUEST_FORM_GUIDE.md) | Discretionary credit requests |
| [PRODUCT_API_B2B](api/b2b_client/API_CLIENT_PRODUCTS.md) | Product CRUD, image upload (thumbnail + full-size) |
| [QR_CODE_B2B](api/b2b_client/API_CLIENT_QR_CODES.md) | QR code create, display, restaurant activation |
| [SUPPLIER_DASHBOARD_METRICS_B2B](api/b2b_client/SUPPLIER_DASHBOARD_METRICS_B2B.md) | Supplier dashboard metrics |
| [PAYMENT_METHOD_CHANGES_B2B](api/b2b_client/PAYMENT_METHOD_CHANGES_B2B.md) | Bank account and fintech removed; subscription payment |
| [TIMEZONE_AUTO_DEDUCTION_UI_GUIDE](api/b2b_client/TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md) | Timezone deduction UI |
| [PORTION_SIZE_DISPLAY_B2B](api/b2b_client/PORTION_SIZE_DISPLAY_B2B.md) | Portion size display |

---

## B2C Client Docs (`docs/api/b2c_client/`)

B2C-specific docs for kitchen-mobile (Customer app, React Native).

| Doc | Summary |
|-----|---------|
| [README](api/b2c_client/README.md) | B2C overview, key links, shared patterns |
| [FRONTEND_AGENT_README](api/b2c_client/FRONTEND_AGENT_README.md) | Agent onboarding for B2C |
| [B2C_ENDPOINTS_OVERVIEW](api/b2c_client/B2C_ENDPOINTS_OVERVIEW.md) | Full B2C endpoint listing |
| [CUSTOMER_SIGNUP_EMAIL_VERIFICATION](api/b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) | Two-step signup flow with email verification |
| [MARKET_CITY_COUNTRY](api/b2c_client/MARKET_CITY_COUNTRY.md) | Market selection at signup |
| [SUBSCRIPTION_PAYMENT_API](api/b2c_client/SUBSCRIPTION_PAYMENT_API.md) | Subscription with-payment + confirm-payment; Stripe |
| [SUBSCRIPTION_ACTIONS_API](api/b2c_client/SUBSCRIPTION_ACTIONS_API.md) | Subscription actions |
| [CUSTOMER_PAYMENT_METHODS_B2C](api/b2c_client/CUSTOMER_PAYMENT_METHODS_B2C.md) | Payment methods: list, add, delete, set default (mock) |
| [EXPLORE_KITCHEN_DAY_B2C](api/b2c_client/EXPLORE_KITCHEN_DAY_B2C.md) | Restaurant explore with enforced kitchen day |
| [EXPLORE_AND_SAVINGS](api/b2c_client/EXPLORE_AND_SAVINGS.md) | Explore and savings |
| [PLATE_RECOMMENDATION_AND_FAVORITES_B2C](api/b2c_client/PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md) | Recommended badges, favorites, explore integration |
| [PLATE_SELECTION_DUPLICATE_REPLACE](api/b2c_client/PLATE_SELECTION_DUPLICATE_REPLACE.md) | Plate selection duplicate/replace |
| [PLATE_ALREADY_RESERVED_EXPLORE_UI](api/b2c_client/PLATE_ALREADY_RESERVED_EXPLORE_UI.md) | Plate already reserved UI in explore |
| [POST_RESERVATION_PICKUP_B2C](api/b2c_client/POST_RESERVATION_PICKUP_B2C.md) | Post-reservation pickup flow |
| [PICKUP_AVAILABILITY_AT_KITCHEN_START](api/b2c_client/PICKUP_AVAILABILITY_AT_KITCHEN_START.md) | Pickup availability, deferred charging, lock |
| [PORTION_SIZE_DISPLAY_B2C](api/b2c_client/PORTION_SIZE_DISPLAY_B2C.md) | Portion size display |
| [CREDIT_ROLLOVER_DISPLAY_B2C](api/b2c_client/CREDIT_ROLLOVER_DISPLAY_B2C.md) | Credit rollover display |
| [EMPLOYER_MANAGEMENT_B2C](api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md) | Employer search/assign/create, address protection |
| [EMPLOYER_ADDRESS_SCOPING_FEEDBACK](api/b2c_client/EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md) | Employer address scoping feedback |
| [MESSAGING_PREFERENCES_B2C](api/b2c_client/MESSAGING_PREFERENCES_B2C.md) | Messaging preferences |
| [LEADS_ENDPOINTS_MIGRATION](api/b2c_client/LEADS_ENDPOINTS_MIGRATION.md) | Leads endpoint migration |

---

## Internal / Backend Docs

| Doc | Summary |
|-----|---------|
| [docs/api/README](api/README.md) | API docs overview: internal, roadmap, archive |
| [CLAUDE.md](../CLAUDE.md) | Project rules, architecture, patterns |
| [CLAUDE_ARCHITECTURE.md](../CLAUDE_ARCHITECTURE.md) | Directory structure, route flow, entry points |
| [docs/api/API_VERSIONING_GUIDE](api/API_VERSIONING_GUIDE.md) | API versioning strategy |
| [docs/api/USER_DEPENDENT_ROUTES_PATTERN](api/USER_DEPENDENT_ROUTES_PATTERN.md) | Admin vs user routes |
| [docs/database/DATABASE_CONNECTION_PATTERNS](database/DATABASE_CONNECTION_PATTERNS.md) | `connection=db` vs positional |
| [docs/database/DATABASE_TABLE_NAMING_PATTERNS](database/DATABASE_TABLE_NAMING_PATTERNS.md) | `_info` suffix conventions |
| [docs/database/DATABASE_REBUILD_PERSISTENCE](database/DATABASE_REBUILD_PERSISTENCE.md) | DB rebuild process |
| [docs/database/ENUM_MAINTENANCE](database/ENUM_MAINTENANCE.md) | Enum management guide |

---

## Postman / Testing

| Doc | Summary |
|-----|---------|
| [docs/postman/README](postman/README.md) | Postman overview |
| [QUICK_SETUP_GUIDE](postman/guidelines/QUICK_SETUP_GUIDE.md) | Quick Postman setup |
| [TESTING_STRATEGY](postman/guidelines/TESTING_STRATEGY.md) | Testing strategy |
| [PERMISSIONS_TESTING_GUIDE](postman/guidelines/PERMISSIONS_TESTING_GUIDE.md) | Permission testing |
| [COLLECTION_UPDATE_VERIFICATION](postman/guidelines/COLLECTION_UPDATE_VERIFICATION.md) | Collection update verification |
| [ROLE_COVERAGE_ANALYSIS](postman/guidelines/ROLE_COVERAGE_ANALYSIS.md) | Role coverage analysis |
| [CUSTOMER_STRIPE_CONFIG_GUIDE](postman/guidelines/CUSTOMER_STRIPE_CONFIG_GUIDE.md) | Customer Stripe config |
| [GEOLOCATION_TESTING_SETUP](postman/guidelines/GEOLOCATION_TESTING_SETUP.md) | Geolocation testing setup |
| [ADDRESS_COLLECTIONS_REFERENCE](postman/guidelines/ADDRESS_COLLECTIONS_REFERENCE.md) | Address collections reference |
| [POSTMAN_MARKET_UPDATE](postman/guidelines/POSTMAN_MARKET_UPDATE.md) | Market update scripts |
| [POSTMAN_INSTITUTION_ENTITY_SCRIPTS](postman/guidelines/POSTMAN_INSTITUTION_ENTITY_SCRIPTS.md) | Institution entity scripts |
| [POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS](postman/guidelines/POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS.md) | Institution payment attempt scripts |
| [DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE](postman/guidelines/DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md) | Discretionary credit system guide |
