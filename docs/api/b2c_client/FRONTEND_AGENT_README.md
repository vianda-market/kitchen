# B2C React Native – Frontend Agent README

**Last Updated**: 2026-02-10

## Start Here

1. OpenAPI: `http://localhost:8000/openapi.json`
2. B2C users = Customer role only. See [B2C_ENDPOINTS_OVERVIEW.md](./B2C_ENDPOINTS_OVERVIEW.md).
3. Auth: `POST /api/v1/auth/token`; use `Authorization: Bearer {token}`

## Customer Only

B2C app users are Customers. Do NOT call Employee-only or Supplier-only APIs.

## Essential Docs

1. [B2C_ENDPOINTS_OVERVIEW.md](./B2C_ENDPOINTS_OVERVIEW.md)
2. [API_PERMISSIONS_BY_ROLE.md](../shared_client/API_PERMISSIONS_BY_ROLE.md) (Customer rows)
3. [USER_MODEL_FOR_CLIENTS.md](../shared_client/USER_MODEL_FOR_CLIENTS.md) — roles, `mobile_number` (E.164), `/users/me`, markets, recovery
4. [ENRICHED_ENDPOINT_PATTERN.md](../shared_client/ENRICHED_ENDPOINT_PATTERN.md)
5. [ARCHIVED_RECORDS_PATTERN.md](../shared_client/ARCHIVED_RECORDS_PATTERN.md)
6. [MARKET_CITY_COUNTRY.md](./MARKET_CITY_COUNTRY.md) — Country dropdown for signup: use GET /leads/markets (returns `country_code`, `country_name` only); send `country_code` in signup request. Do not persist or hardcode; refresh when entering signup.
7. [CUSTOMER_PAYMENT_METHODS_B2C.md](./CUSTOMER_PAYMENT_METHODS_B2C.md) — Saved cards (list, add via Setup Session, delete, set default)
8. [PAYMENT_PROVIDERS_B2C.md](./PAYMENT_PROVIDERS_B2C.md) — Connected payment provider accounts (Stripe link, disconnect flow)

## Subfolders

- **feedback_from_client/**: B2C team feedback for the agent
- **investigations/**: Specific investigations

## Codegen

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```
