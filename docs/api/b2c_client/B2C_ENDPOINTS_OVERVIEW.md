# B2C Customer-Endpoints Overview

**Last Updated**: 2026-03-07  
**Audience**: B2C React Native app (Customer role only)

This document summarizes APIs that **Customers** can access. For full matrices, see [API_PERMISSIONS_BY_ROLE.md](../shared_client/API_PERMISSIONS_BY_ROLE.md).

---

## Customer-Accessible APIs

| API | Methods | Notes |
|-----|---------|-------|
| **Lead encouragement (zipcode metrics)** | **GET** `/api/v1/leads/zipcode-metrics` | Pre-signup: pass `zip` and optional `country_code`; returns restaurant count, has_coverage, matched_zipcode. **No auth**; rate-limited. Full spec: [../shared_client/ZIPCODE_METRICS_LEAD_API.md](../shared_client/ZIPCODE_METRICS_LEAD_API.md). |
| **Restaurant explore (authorized)** | **GET** `/api/v1/restaurants/cities`, **GET** `/api/v1/restaurants/by-city`, **GET** `/api/v1/restaurants/explore/kitchen-days`, **GET** `/api/v1/restaurants/explore/pickup-windows`, **GET** `/api/v1/restaurants/{id}/coworker-pickup-windows` | City dropdown then list/map + plates. **Auth required.** When using a market, **`kitchen_day` is required** (Monday–Friday); omit → 400. **kitchen-days**: allowed kitchen days for dropdown (closest first). **pickup-windows**: 15-min windows for "Select pickup window" modal. **has_volunteer**, **has_coworker_offer**, **has_coworker_request**: per restaurant when kitchen_day set. **coworker-pickup-windows**: pickup time ranges from coworkers (offer/request); call only when has_coworker_offer or has_coworker_request. **is_already_reserved**, **existing_plate_selection_id**: per plate. **Plates**: lean payload (plate_id, product_name, image_url thumbnail, credit, savings, badges). **GET /plates/enriched/{plate_id}?kitchen_day=** adds coworker flags for Reservations-flow modal. Full spec: [RESTAURANT_EXPLORE_B2C.md](./RESTAURANT_EXPLORE_B2C.md), [POST_RESERVATION_PICKUP_B2C.md](./POST_RESERVATION_PICKUP_B2C.md). |
| **Auth** | POST `/api/v1/auth/token` | Login |
| **Username recovery** | POST `/api/v1/auth/forgot-username` | Forgot username; optional "also send password reset". **Full spec**: [USER_MODEL_FOR_CLIENTS.md §8](../shared_client/USER_MODEL_FOR_CLIENTS.md#8-forgot-username). |
| **Customer signup (email verification)** | POST `/api/v1/customers/signup/request`, POST `/api/v1/customers/signup/verify` | Two-step: request sends verification email; verify with token creates user and returns JWT. **Full spec**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](./CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md). Summary below. |
| **Users (self)** | GET/PUT `/api/v1/users/me` | Profile, terminate, employer. **GET** returns `market_id` (primary) and `market_ids` (all, primary first) — use to restore market selector after login. **`mobile_number` (E.164)** and read-only verification flags: [USER_MODEL_FOR_CLIENTS.md](../shared_client/USER_MODEL_FOR_CLIENTS.md). |
| **Messaging preferences** | GET/PUT `/api/v1/users/me/messaging-preferences` | Configure coworker pickup, plate readiness, promotions push, and promotions email toggles. See [MESSAGING_PREFERENCES_B2C.md](./MESSAGING_PREFERENCES_B2C.md). |
| **Plans** | GET `/api/v1/plans/`, `/enriched/` | Browse plans (read-only) |
| **Subscriptions** | GET/POST/PUT `/api/v1/subscriptions/`, `/me` | Own subscriptions. **Payment**: Use **POST /with-payment** and **POST /{id}/confirm-payment** (mock) or poll GET when using Stripe. See [SUBSCRIPTION_PAYMENT_API.md](./SUBSCRIPTION_PAYMENT_API.md). Fintech Link deprecated; do not use. |
| **Plates** | GET `/api/v1/plates/`, `/enriched/` | Browse plates (read-only) |
| **Plate Selection** | **POST** `/api/v1/plate-selections/`, **GET** `/api/v1/plate-selections/`, **GET** `/api/v1/plate-selections/{id}`, **PATCH** `/{id}`, **DELETE** `/{id}` | Create selection (plate_id, pickup_time_range, target_kitchen_day, optional pickup_intent, flexible_on_time); list/get own. **Editable** until 1h before kitchen day opens. Credits **validated** at reservation, **charged** at kitchen start (11:30); no refund after lock. Full flow: [../shared_client/PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md). See [POST_RESERVATION_PICKUP_B2C.md](./POST_RESERVATION_PICKUP_B2C.md) for volunteer/coworker flow, [PICKUP_AVAILABILITY_AT_KITCHEN_START.md](./PICKUP_AVAILABILITY_AT_KITCHEN_START.md) for charging/availability. |
| **Plate Selection — Coworkers** | **GET** `/api/v1/plate-selections/{id}/coworkers`, **POST** `/api/v1/plate-selections/{id}/notify-coworkers` | List coworkers (same employer) with eligibility; notify selected coworkers. For "Offer to pick up" flow. See [POST_RESERVATION_PICKUP_B2C.md](./POST_RESERVATION_PICKUP_B2C.md). |
| **Plate Pickup** | GET `/api/v1/plate-pickup/pending`, POST `/api/v1/plate-pickup/scan-qr`, POST `/api/v1/plate-pickup/{id}/complete` | Pending order (includes plate_pickup_ids, total_plate_count); QR scan returns `plates` (plate_name, quantity, plate_pickup_id) for "what you can pickup" screen; complete pickup. Availability: [PICKUP_AVAILABILITY_AT_KITCHEN_START.md](./PICKUP_AVAILABILITY_AT_KITCHEN_START.md). [PLATE_API_CLIENT](../shared_client/PLATE_API_CLIENT.md). |
| **Addresses** | GET/POST/PUT/DELETE | Own addresses only. **B2C:** Omit `institution_id` and `user_id` on create; backend sets them from JWT. **Allowed types**: Customer Home, Customer Billing, Customer Employer only. [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md). |
| **Client Bills** | GET | Own bills |
| **Markets** | GET (if exposed to Customer) | Market selection for plans |
| **Enums** | GET | Status, types, etc. |

---

## Customer signup (email verification)

**→ Full documentation for app development**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](./CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md)

Customer registration uses a **two-step flow** so that a row in `user_info` is created only after the email is verified.

| Step | Endpoint | Purpose |
|------|----------|---------|
| 1 | `POST /api/v1/customers/signup/request` | Send signup payload (username, password, email, **country_code**, city_id or city_name, mobile_number (optional E.164), first_name, last_name). Backend validates, stores a pending signup, and sends a verification email. Response is always a generic success message (no email enumeration). Use GET /leads/markets for `country_code` values. |
| 2 | `POST /api/v1/customers/signup/verify` | Send `{"token": "..."}` (from the link in the email). Backend creates the user, marks the token used, and returns the user object plus `access_token` so the client can log the user in immediately. |

**UI flow**

1. User submits the signup form → call `POST /customers/signup/request` → show “Check your email to verify”.
2. User opens the link in the email (e.g. `https://app.example.com/verify-signup?token=...` or deep link `myapp://verify-signup?token=...`).
3. App calls `POST /customers/signup/verify` with the `token` from the URL.
4. On success, store the returned `access_token` and show the user as logged in.

**Dev / E2E**

- When `DEV_MODE` is true, `GET /api/v1/customers/signup/dev-pending-token?email=<email>` returns the current verification token for that email so E2E or Postman can run the verify step without reading the email.

---

## APIs Customers Cannot Access

- Credit Currencies
- Discretionary (admin)
- Restaurants, Products, QR Codes (management)
- Institution Bank Accounts, Institution Entities
- User management (create/edit other users)

---

## Shared Pattern Docs (in shared_client/)

- [USER_MODEL_FOR_CLIENTS](../shared_client/USER_MODEL_FOR_CLIENTS.md) – Use `/me` for self-updates; `mobile_number` (E.164); markets
- [ENRICHED_ENDPOINT_PATTERN](../shared_client/ENRICHED_ENDPOINT_PATTERN.md) – Use `/enriched/` for plates, addresses
- [ARCHIVED_RECORDS_PATTERN](../shared_client/ARCHIVED_RECORDS_PATTERN.md) – Default excludes archived
- [SCOPING_BEHAVIOR_FOR_UI](../shared_client/SCOPING_BEHAVIOR_FOR_UI.md) – Customer = user-scoped
- [ADDRESSES_API_CLIENT](../shared_client/ADDRESSES_API_CLIENT.md) – Suggest, create (place_id or structured); Address CRUD; **B2C:** omit `institution_id` and `user_id` on create; **address types by role** (B2C: only Customer Home, Billing, Employer in forms)
- [MARKET_BASED_SUBSCRIPTIONS](../shared_client/MARKET_BASED_SUBSCRIPTIONS.md) – Multi-market
- [USER_MODEL_FOR_CLIENTS §7](../shared_client/USER_MODEL_FOR_CLIENTS.md#7-user-and-market-market_id--market_ids) – `market_id` / `market_ids` from GET /users/me; restore market selector
- [PLATE_API_CLIENT](../shared_client/PLATE_API_CLIENT.md) – Plate selection, plate pickup pending, enriched endpoint (ingredients, pickup_instructions)
- [POST_RESERVATION_PICKUP_B2C](./POST_RESERVATION_PICKUP_B2C.md) – Volunteer pickup, coworker list/notify, notifications, editability
