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
| 2 | [USER_MODEL_FOR_CLIENTS.md](../shared_client/USER_MODEL_FOR_CLIENTS.md) | Use `/me` for self-updates; avoid `/{user_id}` for self; see §6 |
| 3 | [ENRICHED_ENDPOINT_PATTERN.md](../shared_client/ENRICHED_ENDPOINT_PATTERN.md) | Use `/enriched/` for denormalized data (no N+1) |
| 4 | [ARCHIVED_RECORDS_PATTERN.md](../shared_client/ARCHIVED_RECORDS_PATTERN.md) | Default excludes archived; omit `include_archived` unless needed |
| 5 | [USER_MODEL_FOR_CLIENTS.md](../shared_client/USER_MODEL_FOR_CLIENTS.md#3-username-and-email-lowercase) | Username/email normalized to lowercase; apply `.toLowerCase().trim()` before sending |
| 6 | [SCOPING_BEHAVIOR_FOR_UI.md](../shared_client/SCOPING_BEHAVIOR_FOR_UI.md) | Institution/user scoping; backend enforces |
| 7 | [BULK_API_PATTERN.md](../shared_client/BULK_API_PATTERN.md) | Bulk operations are atomic |
| 8 | [PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md) | Plate create/update and tables/modals: do not include savings; enriched endpoint (ingredients, pickup_instructions); plate selection and pickup pending |
| 9 | [CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) | Credit currency, plan/restaurant/entity currency from market, plate payouts, B2C savings |
| 10 | [PAYMENT_METHOD_CHANGES_B2B.md](./PAYMENT_METHOD_CHANGES_B2B.md) | **Institution bank account and fintech links removed.** Remove all related pages, modals, and API calls. Use subscription with-payment and institution settlement pipeline only. |
| 11 | [API_CLIENT_USER_PAYMENT_SUMMARY.md](./API_CLIENT_USER_PAYMENT_SUMMARY.md) | Employee payment portal — `GET /api/v1/user-payment-summary` (Internal only); read-only table showing which customers have Stripe cards registered |

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
