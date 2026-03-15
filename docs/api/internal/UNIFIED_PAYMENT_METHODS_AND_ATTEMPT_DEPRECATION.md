# Unified Payment Methods and Payment Attempt Deprecation

## Overview

- **Unified payment methods**: A single list of payment methods is backed only by aggregators (Stripe first; later Mercado Pago, PayU). Direct storage tables (`credit_card`, `bank_account`, `appstore_account`, `fintech_wallet`, `fintech_wallet_auth`) have been removed.
- **Payment attempts deprecated**: `client_payment_attempt` and `institution_payment_attempt` have been removed. Client bills are tied only to `subscription_payment`; institution bills are marked paid by resolution only (no `payment_id`).

## Payment methods (Part 1)

- **`payment_method`**: Kept; `method_type` holds the provider name only (e.g. Stripe).
- **`external_payment_method`**: Holds aggregator-specific data: `payment_method_id`, `provider`, `external_id`, `last4`, `brand`, `provider_customer_id`.
- Enums, services, schemas, and listing use provider-only types and join to `external_payment_method` for display (e.g. `provider`, `last4`, `brand` in enriched payment method responses).

## Payment attempts (Part 2)

- **Client bills**: Only `subscription_payment_id`; no `payment_id`. B2C payments are atomic via `subscription_payment`; no client payment attempt table.
- **Institution bills**: No `payment_id`. Marking a bill paid updates only status/resolution (and `modified_by`/`modified_date`). Manual payment recording no longer creates an attempt record.
- Removed: routes, services, DTOs, and schemas for `client_payment_attempt` and `institution_payment_attempt`; `mark_paid` no longer takes or sets `payment_id`.

## Reference

- Schema: `payment_method`, `external_payment_method` in `app/db/schema.sql`; attempt tables dropped and not re-created.
- Enriched payment method listing: `get_enriched_payment_methods` / `get_enriched_payment_method_by_id` in `entity_service` LEFT JOIN `external_payment_method` for `provider`, `last4`, `brand`.
