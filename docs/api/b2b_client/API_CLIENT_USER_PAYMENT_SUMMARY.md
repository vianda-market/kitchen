# User Payment Summary — B2B Employee Portal

**Audience**: vianda-platform (kitchen-web) — Internal employees only.
**Purpose**: Read-only view of which customers have Stripe payment methods registered. Used in the "Payment Methods" admin portal.

---

## Access Control

- **Internal role only** — requires `role_type === "Internal"` (JWT). Suppliers, Customers, and Employers receive **403**.
- **Global scope** — returns all non-archived customers across all markets. No institution filter is applied (Internal users have global scope).
- **Read-only** — there are no mutation endpoints in this view. Card management is customer-initiated only (via the B2C app).

---

## Endpoint

```
GET /api/v1/user-payment-summary
Authorization: Bearer <employee_token>
```

**Response (200 OK)**: Array of customer payment summary objects. Returns an entry for every non-archived customer, including those who have never added a card.

```json
[
  {
    "user_id": "uuid",
    "username": "jane.doe",
    "email": "jane@example.com",
    "full_name": "Jane Doe",
    "status": "Active",
    "has_stripe_provider": true,
    "provider_connected_date": "2026-03-01T14:00:00Z",
    "payment_method_count": 2,
    "default_last4": "4242",
    "default_brand": "visa"
  },
  {
    "user_id": "uuid",
    "username": "john.smith",
    "email": "john@example.com",
    "full_name": "John Smith",
    "status": "Active",
    "has_stripe_provider": false,
    "provider_connected_date": null,
    "payment_method_count": 0,
    "default_last4": null,
    "default_brand": null
  }
]
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | UUID | Customer identifier |
| `username` | string | Lowercase username |
| `email` | string | Lowercase email |
| `full_name` | string | First + last name concatenated; empty string if not set |
| `status` | string | User account status (`Active`, `Inactive`) |
| `has_stripe_provider` | boolean | `true` if the customer has connected Stripe at least once |
| `provider_connected_date` | datetime \| null | When the customer first added a card (first Setup Session). `null` if never connected. |
| `payment_method_count` | int | Number of active (non-archived) saved cards. `0` if none. |
| `default_last4` | string \| null | Last 4 digits of the default card. `null` if no default card. |
| `default_brand` | string \| null | Card brand of the default card (`visa`, `mastercard`, `amex`, etc.). `null` if no default card. |

**Not exposed**: `provider_customer_id` (`cus_xxx`) — internal Stripe identifier. Do not display or store this in the UI.

---

## UI Guidance

### Table columns (recommended)

| Column | Source field | Notes |
|--------|-------------|-------|
| Name | `full_name` | Fall back to `username` if empty string |
| Email | `email` | |
| Status | `status` | Badge: green for Active, grey for Inactive |
| Payment setup | `has_stripe_provider` | "Connected" / "Not connected" badge |
| Cards | `payment_method_count` | Show count; "—" if 0 |
| Default card | `default_brand` + `default_last4` | e.g. "Visa ···· 4242"; "—" if null |
| Connected since | `provider_connected_date` | Format as date only; "—" if null |

### Empty state

Customers where `has_stripe_provider = false` and `payment_method_count = 0` have never added a card. These are expected — most customers will be in this state before the B2C app guides them through the Setup Session flow.

### Filtering suggestions

Client-side filtering on this response is sufficient for typical customer volumes:
- **Has payment method**: filter `payment_method_count > 0`
- **No payment method**: filter `payment_method_count === 0`
- **Connected / not connected**: filter on `has_stripe_provider`

### No mutation from this view

This endpoint is read-only. There are no admin endpoints to add, remove, or modify a customer's payment methods. Card management is customer-initiated only through the B2C app. If a customer needs help, they must use the B2C app to manage their own cards.

---

## Related

- [CUSTOMER_PAYMENT_METHODS_API.md](../shared_client/CUSTOMER_PAYMENT_METHODS_API.md) — Full API contract for the B2C card management endpoints
- [PAYMENT_PROVIDERS_B2C.md](../b2c_client/PAYMENT_PROVIDERS_B2C.md) — How customers connect and disconnect Stripe in the B2C app
- [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](../../roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md) — Phasing plan — what is live vs. planned
