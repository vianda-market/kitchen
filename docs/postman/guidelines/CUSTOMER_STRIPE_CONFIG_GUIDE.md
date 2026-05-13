# Customer Stripe Config Collection (010) – Setup Guide

E2E Customer Stripe payment method management. **Phase 2 mock only** – requires `PAYMENT_PROVIDER=mock`.

## Prerequisites

1. **Environment**
   - `baseUrl`: API base URL (default `http://localhost:8000`)
   - `PAYMENT_PROVIDER=mock` on the API server

2. **Customer Auth**
   - Run **000 E2E Vianda Selection** → Client Setup (Customer Signup, Login Customer User), or
   - Manually create a Customer user and run **Login Customer User** in Prerequisites
   - The collection uses `clientUserAuthToken` from environment or the Login step

## Flow (run in order)

| Step | Request | Purpose |
|------|---------|---------|
| 1 | **Login Customer User** | OAuth login; sets `customerAuthToken` |
| 2 | GET payment methods (empty) | Initial state |
| 3 | POST setup-session | Creates Stripe setup URL; assigns `stripe_customer_id` if mock |
| 4 | POST mock-add | Simulates returning from Stripe; inserts payment_method + external_payment_method |
| 5 | GET payment methods (has 1) | Asserts one card with last4=4242 |
| 6 | PUT set default | Updates default |
| 7 | DELETE payment method | Archives the card |
| 8 | GET payment methods (empty after delete) | Asserts empty list |

## Variables

- `baseUrl` – from environment or default `http://localhost:8000`
- `customerAuthToken` – set by Login or prerequest from `clientUserAuthToken`
- `customerUsername`, `customerPassword` – for Login (default: customer / Customer123!)
- `paymentMethodId` – set by mock-add response; used for PUT and DELETE

## API Reference

- [CUSTOMER_PAYMENT_METHODS_B2C.md](../../api/b2c_client/CUSTOMER_PAYMENT_METHODS_B2C.md)
- [CUSTOMER_PAYMENT_METHODS_API.md](../../api/shared_client/CUSTOMER_PAYMENT_METHODS_API.md)
