# API Handoffs: Backend and Frontend Coordination

**Last Updated**: 2026-02-10  
**Purpose**: Expectations between the Kitchen backend (FastAPI) and frontend repos (React TS, React Native).

## Repo Layout

| Repo | Tech | Audience |
|------|------|----------|
| kitchen (this repo) | FastAPI | All |
| kitchen-web | React TS | Restaurant + Employee |
| kitchen-mobile | React Native | B2C Customers |

Shared contract: OpenAPI spec at `/openapi.json` and docs in this repo.

## Shared Contract: OpenAPI

**Backend**: Exposes `/openapi.json` and `/docs` by default. Ensure routes have tags and schemas.

**Frontend**: Run codegen against the spec URL:
```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts
```

## Handoff Rules

**When backend adds a new endpoint**: Document in API_PERMISSIONS_BY_ROLE.md if role-dependent. Add to BREAKING_CHANGES.md if breaking.

**When backend changes a response shape**: Add entry to BREAKING_CHANGES.md. Notify frontend before deploy.

**When frontend integrates**: Re-run codegen. Use types from codegen. Follow b2b_client/ or b2c_client/ patterns.

**Deployment order**: Additive changes = backend first. Breaking changes = coordinate deploy window.

## Per-Repo Expectations

- **kitchen-web** (B2B): Auth, CRUD, enriched endpoints, institution-scoped, discretionary, archival, markets. Docs: [b2b_client/](./b2b_client/README.md)
- **kitchen-mobile** (B2C): Auth, signup, plans, subscriptions, payment methods, viandas, vianda selection, vianda pickup, addresses, client bills, markets, enums. Docs: [b2c_client/](./b2c_client/README.md)

## Pre-Deploy Checklist

See docs/deployment/handshake-checklist.md before deploying backend changes.
