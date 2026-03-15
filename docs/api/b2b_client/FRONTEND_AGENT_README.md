# Frontend Agent README

**Last Updated**: 2026-02-10  
**Purpose**: Quick orientation for AI agents or developers integrating with the Kitchen API.

---

## Start Here

1. **API contract**: OpenAPI spec at `{BASE_URL}/openapi.json` (local: `http://localhost:8000/openapi.json`)
2. **Permissions**: [API_PERMISSIONS_BY_ROLE.md](../shared_client/API_PERMISSIONS_BY_ROLE.md) – which role (Employee, Supplier, Customer) can access which endpoints
3. **Auth**: `POST /api/v1/auth/token` with `username` + `password`; use `Authorization: Bearer {token}`

---

## Essential Docs (read in order)

| Priority | Doc | Use |
|----------|-----|-----|
| 1 | [API_PERMISSIONS_BY_ROLE.md](../shared_client/API_PERMISSIONS_BY_ROLE.md) | Role-based access matrix |
| 2 | [USER_SELF_UPDATE_PATTERN.md](../shared_client/USER_SELF_UPDATE_PATTERN.md) | Use `/me` for self-updates; avoid `/{user_id}` for self |
| 3 | [ENRICHED_ENDPOINT_PATTERN.md](../shared_client/ENRICHED_ENDPOINT_PATTERN.md) | Use `/enriched/` for denormalized data (no N+1) |
| 4 | [ARCHIVED_RECORDS_PATTERN.md](../shared_client/ARCHIVED_RECORDS_PATTERN.md) | Default excludes archived; omit `include_archived` unless needed |
| 5 | [SCOPING_BEHAVIOR_FOR_UI.md](../shared_client/SCOPING_BEHAVIOR_FOR_UI.md) | Institution/user scoping; backend enforces |
| 6 | [BULK_API_PATTERN.md](../shared_client/BULK_API_PATTERN.md) | Bulk operations are atomic |
| 7 | [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md) | Plate create/update and tables/modals: do not include savings; enriched endpoint (ingredients, pickup_instructions); plate selection and pickup pending |
| 8 | [PLAN_API_MARKET_CURRENCY.md](./PLAN_API_MARKET_CURRENCY.md) | Plan create/update: do not send credit_currency_id; currency is derived from the selected market |
| 9 | [PAYMENT_METHOD_CHANGES_B2B.md](./PAYMENT_METHOD_CHANGES_B2B.md) | **Institution bank account and fintech links removed.** Remove all related pages, modals, and API calls. Use subscription with-payment and institution settlement pipeline only. |

---

## Codegen

Generate types from OpenAPI:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

---

## Repo layout

- **kitchen** (this repo): FastAPI backend; source of truth for API
- **kitchen-web**: React TS (Restaurant + Employee)
- **kitchen-mobile**: React Native B2C (future)

Client docs live in this folder; copy to frontend repos or reference from them.

---

## Related docs

- [../overview.md](../overview.md) – Base URLs, versioning, auth overview
- [../handoffs.md](../handoffs.md) – Backend ↔ frontend coordination
- [README.md](./README.md) – Full client docs index
