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
3. [USER_SELF_UPDATE_PATTERN.md](../shared_client/USER_SELF_UPDATE_PATTERN.md)
4. [ENRICHED_ENDPOINT_PATTERN.md](../shared_client/ENRICHED_ENDPOINT_PATTERN.md)
5. [ARCHIVED_RECORDS_PATTERN.md](../shared_client/ARCHIVED_RECORDS_PATTERN.md)
6. [MARKET_SELECTION_AT_SIGNUP.md](./MARKET_SELECTION_AT_SIGNUP.md) — Market dropdown for signup: use GET /markets/available only; do not persist market_id (avoids "Invalid or archived market_id"). After a DB rebuild, UUIDs change — validate any stored selection against the current list and clear it if missing; show "Your selected country is no longer available. Please select your country again." so the user picks from the current list.

## Subfolders

- **feedback_from_client/**: B2C team feedback for the agent
- **investigations/**: Specific investigations

## Codegen

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```
