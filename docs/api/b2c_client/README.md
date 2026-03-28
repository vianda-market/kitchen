# B2C React Native Client Docs

**Audience**: B2C React Native app (Customer role only)

- **For agents**: [FRONTEND_AGENT_README.md](./FRONTEND_AGENT_README.md)
- **For developers**: [B2C_ENDPOINTS_OVERVIEW.md](./B2C_ENDPOINTS_OVERVIEW.md)
- **Customer registration (email verification)**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](./CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) — two-step signup flow for app implementation
- **User model (profile, `/users/me`, markets, forgot-username, password recovery)**: [../shared_client/USER_MODEL_FOR_CLIENTS.md](../shared_client/USER_MODEL_FOR_CLIENTS.md)
- **Lead encouragement (zipcode metrics)**: [../shared_client/ZIPCODE_METRICS_LEAD_API.md](../shared_client/ZIPCODE_METRICS_LEAD_API.md) — **GET** `/api/v1/leads/zipcode-metrics` (exact path; no auth)
- **Payment, billing, fintech link changes**: [../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md) — Remove fintech link pages/modals; no manual create/process bill; use subscription with-payment only.
- **Subscription payment (with-payment + confirm-payment)**: [SUBSCRIPTION_PAYMENT_API.md](./SUBSCRIPTION_PAYMENT_API.md) — Atomic flow, success/failure semantics (200 = success, full subscription returned), types, and Stripe polling.
- **Manage payment methods (mock endpoints)**: [CUSTOMER_PAYMENT_METHODS_B2C.md](./CUSTOMER_PAYMENT_METHODS_B2C.md) — List, add, delete, set default. Mock for UI dev; status and roadmap for agents.
- **Restaurant explore (authorized users)**: [EXPLORE_KITCHEN_DAY_B2C.md](./EXPLORE_KITCHEN_DAY_B2C.md) — Enforced kitchen day when exploring restaurants. Full spec: [feedback_from_client/RESTAURANT_EXPLORE_B2C.md](./feedback_from_client/RESTAURANT_EXPLORE_B2C.md).
- **Plate recommendation and favorites**: [PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md](./PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md) — Recommended badges, favorite hearts, favorites API; explore integration for Customers.
- **Employer management**: [EMPLOYER_MANAGEMENT_B2C.md](./EMPLOYER_MANAGEMENT_B2C.md) — Search/assign existing employer, create new, add address; address protection; cities API. **Important:** When user selects existing employer + existing address, client must call `PUT /users/me/employer` with body `{ employer_id, address_id }` to complete assignment.
- **Address autocomplete and create**: [../shared_client/ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Suggest, create with place_id or structured fields, for any B2C address input (home, billing, employer). Same API for all platforms; no Google keys on client.
- **Pickup availability and charging**: [PICKUP_AVAILABILITY_AT_KITCHEN_START.md](./PICKUP_AVAILABILITY_AT_KITCHEN_START.md) — When plates become ready (11:30), deferred charging, no refund after lock.
- **feedback_from_client/**: B2C team feedback for the agent
- **investigations/**: Specific investigations

Shared patterns: see [shared_client](../shared_client/).
