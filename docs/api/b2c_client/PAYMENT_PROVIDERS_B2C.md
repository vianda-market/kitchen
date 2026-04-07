# Payment Providers (B2C) — Phase 2

**Audience**: B2C client (kitchen-mobile) — Customer role only.
**Purpose**: Allow customers to see and manage their connected payment provider accounts (e.g. their Stripe connection). Implemented in Phase 2 alongside the `user_payment_provider` table.

---

## Concept

A **payment provider** is the link between a user and a payment processor's customer object. For Stripe, this is the Stripe Customer (`cus_xxx`). It is created automatically the first time a user initiates a Setup Session to add a card.

- One provider account per user per provider (e.g. one Stripe connection)
- A provider account holds zero or more saved payment methods (cards)
- Disconnecting a provider archives it **and** all associated saved cards

This is separate from individual payment methods (cards). Think of it as:
- **Provider** = "Your Stripe account" (the container)
- **Payment method** = "Visa •••• 4242" (a card inside that container)

---

## New Endpoints (Phase 2)

Base path: `/api/v1/customer/payment-providers`
Auth: Customer role required (`Authorization: Bearer <token>`).

---

### GET /api/v1/customer/payment-providers

List connected payment providers for the current user.

**Request**
```http
GET /api/v1/customer/payment-providers
Authorization: Bearer <token>
```

**Success (200 OK)**
```json
[
  {
    "user_payment_provider_id": "uuid",
    "provider": "stripe",
    "created_date": "2026-03-01T14:00:00Z",
    "payment_method_count": 2
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `user_payment_provider_id` | UUID | Use for the DELETE endpoint. |
| `provider` | string | Provider name. Currently always `"stripe"`. |
| `created_date` | datetime | When the user first connected this provider (first Setup Session). |
| `payment_method_count` | int | Number of active (non-archived) saved cards under this provider. |

**Empty list**: Returns `[]` if the user has never completed a Setup Session. This is normal — do not show the provider management section until at least one provider exists.

**Errors**: 403 (not Customer).

---

### DELETE /api/v1/customer/payment-providers/{user_payment_provider_id}

Disconnect a payment provider. Archives the provider record **and all associated saved cards**.

**Request**
```http
DELETE /api/v1/customer/payment-providers/{user_payment_provider_id}
Authorization: Bearer <token>
```

**Success (204 No Content)**: No response body.

**Behavior**:
- Archives the `user_payment_provider` record locally
- Archives all active `payment_method` rows for this user + provider
- Does **not** delete the Stripe Customer object in Stripe — only our local records are archived
- After disconnecting, the user would need to go through Setup Session again to re-add a card

**Errors**: 403 (not Customer), 404 (provider not found or already disconnected).

---

## UI Flow — "Manage Payment Account"

### Where to surface this

Show a "Payment account" or "Connected account" section in the payment settings screen, separate from (and above) the individual cards list. The provider section is the container; the cards list is its contents.

### List view

```
Payment account
┌──────────────────────────────────┐
│  Stripe                          │
│  Connected March 1, 2026         │
│  2 saved cards                   │
│                          [Disconnect] │
└──────────────────────────────────┘

Saved cards
  Visa •••• 4242  [default]  [Delete]
  Mastercard •••• 5555       [Delete]
```

1. Call `GET /api/v1/customer/payment-providers` to get the provider block
2. Call `GET /api/v1/customer/payment-methods` to get the cards list
3. If providers list is empty, show only the "Add card" button (no provider section)

### Disconnect flow

1. User taps "Disconnect" on the provider block
2. Show confirmation: "Disconnect Stripe? This will remove all 2 saved cards."
   - Use `payment_method_count` from the provider response for the count in the message
3. On confirm, call `DELETE /api/v1/customer/payment-providers/{user_payment_provider_id}`
4. On 204: clear both the provider block and the cards list from local state (both are now gone)
5. Show "Add card" button so the user can reconnect

### Provider display name

Map `provider` to a human-readable label:

| `provider` value | Display name |
|-----------------|--------------|
| `"stripe"` | `"Stripe"` |

Keep this mapping in a small utility — new providers will appear as new values in this field.

---

## Relationship to Payment Methods

The existing payment methods endpoints (`/customer/payment-methods`) are unchanged. The provider endpoints are additive — they expose the container, not the cards themselves.

| Concern | Endpoint |
|---------|----------|
| List saved cards | `GET /customer/payment-methods` |
| Add a card | `POST /customer/payment-methods/setup-session` |
| Delete a card | `DELETE /customer/payment-methods/{id}` |
| Set default card | `PUT /customer/payment-methods/{id}/default` |
| View connected provider | `GET /customer/payment-providers` |
| Disconnect provider (+ all cards) | `DELETE /customer/payment-providers/{id}` |

---

## Related

- [CUSTOMER_PAYMENT_METHODS_B2C.md](./CUSTOMER_PAYMENT_METHODS_B2C.md) — Individual card management
- [STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md](../../roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md)
