# Customer Payment Methods API

**Audience**: B2C (kitchen-mobile) and B2B (kitchen-web) frontend agents and developers.  
**Purpose**: Manage saved payment methods (cards) for Stripe. Enables "Manage payment methods" UI for customers who pay subscriptions.

---

## Status and Roadmap (Agent-Aware)

| Status | Description |
|--------|-------------|
| **Phase 1** | **Live** — Mock endpoints. Returns fixture data or no-op. |
| **Phase 2** | **Live** — Database-backed. `user_payment_provider` table stores payment provider link (replaces `stripe_customer_id` on user). New endpoints: `GET /customer/payment-providers`, `DELETE /customer/payment-providers/{id}`. See [PAYMENT_PROVIDERS_B2C.md](../b2c_client/PAYMENT_PROVIDERS_B2C.md). |
| **Phase 3** | Planned — Live Stripe: real Setup Session, webhooks, detach, set default. |
| **Phase 4** | Planned — Subscription integration: reuse saved card for with-payment (skip card form when default exists). |

**Roadmap**: [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](../../roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md)

---

## Access Control

- **Customer role only** — Endpoints require `role_type === "Customer"` (JWT). Suppliers and Employees receive **403**.
- **User-scoped** — All operations are scoped to `current_user["user_id"]`. No institution scoping.

---

## B2B vs B2C — Same Endpoints?

**Currently**: These endpoints are **Customer-only**. Only the B2C app (kitchen-mobile) should call them; B2B (kitchen-web) users are typically Employees or Suppliers, not Customers.

**B2B Supplier Stripe**: A **separate** concern. Suppliers receive payouts via the settlement pipeline (see [SUPPLIER_INSTITUTION_PAYMENT](../../internal/SUPPLIER_INSTITUTION_PAYMENT.md)) — there is no "manage payment methods" for suppliers today. Payout is Stripe-only and automatic.

**Future**: If we add:
- Supplier Stripe Connect onboarding (bank account for receiving payouts), that would use **different endpoints** (institution-scoped).
- Employee access to view a customer's payment methods (support), we may extend these endpoints with role checks.

Until then, **shared_client** contains the API contract so both B2C and B2B agents can reference it; only B2C implements the UI for now.

---

## Base Path

All endpoints: `GET /api/v1/customer/payment-methods` (note: router prefix `/customer`, sub-router `/payment-methods`).

Full paths:

- `GET /api/v1/customer/payment-methods/`
- `POST /api/v1/customer/payment-methods/setup-session`
- `DELETE /api/v1/customer/payment-methods/{payment_method_id}`
- `PUT /api/v1/customer/payment-methods/{payment_method_id}/default`

---

## 1. GET /api/v1/customer/payment-methods/

List saved payment methods for the current customer.

**Request**

```http
GET /api/v1/customer/payment-methods/
Authorization: Bearer <token>
```

**Success (200 OK)**

```json
{
  "payment_methods": [
    {
      "payment_method_id": "uuid",
      "last4": "4242",
      "brand": "visa",
      "is_default": true,
      "external_id": "pm_xxx"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `payment_method_id` | UUID | Use for DELETE, PUT default. |
| `last4` | string \| null | Last 4 digits of card. |
| `brand` | string \| null | Card brand (visa, mastercard, amex, etc.). |
| `is_default` | boolean | Use for renewal and new payments when available. |
| `external_id` | string \| null | Stripe `pm_xxx` (or mock placeholder). |

**Mock behavior**: If no DB rows for the user, returns one fixture (Visa •••• 4242). Use this to build list UI before live Stripe.

**Errors**: 403 (not Customer).

---

## 2. POST /api/v1/customer/payment-methods/setup-session

Create a Stripe Checkout Setup session URL so the user can add or update a payment method.

**Request**

```http
POST /api/v1/customer/payment-methods/setup-session
Authorization: Bearer <token>
Content-Type: application/json

{
  "return_url": "https://yourapp.com/settings/payment"   // optional
}
```

**Success (200 OK)**

```json
{
  "setup_url": "https://checkout.stripe.com/...",
  "expires_at": "2026-03-04T12:30:00Z"
}
```

**Client behavior**:

1. Call this endpoint.
2. Redirect user to `setup_url` (Stripe Checkout).
3. After user completes, Stripe redirects to `return_url` (or success_url from session).
4. Call `GET /api/v1/customer/payment-methods/` to refresh the list (live: webhook will have synced; mock: no change until Phase 3).

**Mock behavior**: Returns `setup_url: "https://mock-stripe-setup.example"` and `expires_at` 1 hour ahead. Redirect to this URL for flow testing; it will not complete real Stripe setup.

**Errors**: 403 (not Customer).

---

## 2b. POST /api/v1/customer/payment-methods/mock-add (Mock only)

**[Phase 2 mock]** Simulate adding a payment method after returning from Stripe setup. Creates `payment_method` + `external_payment_method` in DB. Only when `PAYMENT_PROVIDER=mock`. Use for E2E and local dev.

**Request**

```http
POST /api/v1/customer/payment-methods/mock-add
Authorization: Bearer <token>
```

**Success (200 OK)**: Returns the created payment method (same shape as list item).

**Errors**: 400 when `PAYMENT_PROVIDER` is not `mock`, 403 (not Customer).

---

## 3. DELETE /api/v1/customer/payment-methods/{payment_method_id}

Remove a payment method.

**Request**

```http
DELETE /api/v1/customer/payment-methods/{payment_method_id}
Authorization: Bearer <token>
```

**Success (200 OK)**

```json
{
  "detail": "Payment method removed."
}
```

**Live behavior (Phase 3)**: Will not allow deleting the only payment method if the user has an active subscription (business rule). Mock: always 200, no-op.

**Errors**: 403 (not Customer), 404 (not found or not owned).

---

## 4. PUT /api/v1/customer/payment-methods/{payment_method_id}/default

Set a payment method as the default for future charges.

**Request**

```http
PUT /api/v1/customer/payment-methods/{payment_method_id}/default
Authorization: Bearer <token>
```

**Success (200 OK)**

```json
{
  "detail": "Default payment method updated."
}
```

**Mock behavior**: 200 no-op. Live: updates `payment_method.is_default` and Stripe Customer default.

**Errors**: 403 (not Customer), 404 (not found or not owned).

---

## B2C Client Usage

See [CUSTOMER_PAYMENT_METHODS_B2C.md](../b2c_client/CUSTOMER_PAYMENT_METHODS_B2C.md) for B2C-specific integration notes and UI flow.

---

## Related

- [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](../../roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md)
- [SUBSCRIPTION_PAYMENT_API.md](../b2c_client/SUBSCRIPTION_PAYMENT_API.md)
- [PAYMENT_AND_BILLING_CLIENT_CHANGES.md](./PAYMENT_AND_BILLING_CLIENT_CHANGES.md)
