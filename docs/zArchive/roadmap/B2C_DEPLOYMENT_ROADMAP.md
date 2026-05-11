# B2C Deployment Roadmap

**Last Updated**: 2026-02-10  
**Purpose**: Plan deployment of B2C TypeScript apps for customer subscribers: data into Postgres, backoffice capture from API calls, small codebase for solo developer.

---

## Executive Summary

- **Backend**: FastAPI (kitchen repo) – single backend, shared by all apps
- **Frontend**: Multi-repo (kitchen-web, kitchen-mobile), coordinated via OpenAPI + docs
- **Strategy**: Keep repos separate; share contract via OpenAPI spec and handoff docs

---

## 1. Repo Architecture

### Multi-Repo (Chosen)

| Repo | Tech | Audience | Entry Point |
|------|------|----------|-------------|
| **kitchen** | FastAPI | All | `/api/v1/` |
| **kitchen-web** | React TS | Restaurant + Employee | Backoffice, Restaurant admin |
| **kitchen-mobile** | React Native + RN Web | B2C Customers | iOS, Android, Web |

**Why multi-repo**:
- Existing kitchen-web is already separate; no migration needed
- Independent deployments: merge to kitchen only deploys backend; merge to kitchen-web only deploys web; merge to kitchen-mobile only deploys mobile
- Smaller context per repo; easier to reason about
- Shared contract via OpenAPI + docs (see Section 3)

### Monorepo Alternative (Not chosen)

A monorepo would require path-based CI and migrating existing repos. For a solo dev with an existing React TS repo, multi-repo is simpler. If you later consolidate, path-based deploy rules can isolate deploys (e.g. only deploy `backend/` when `backend/**` changes).

---

## 2. Shared Contract: OpenAPI + Docs

### No Shared TypeScript Packages Across Repos

There are no `packages/api`, `packages/types`, `packages/utils` shared across repos. Those were ChatGPT-style monorepo concepts; we use OpenAPI as the contract instead.

### OpenAPI as Contract

- **Backend (FastAPI)**: Exposes `/openapi.json` and `/docs` by default
- **Frontend (each repo)**: Runs codegen (e.g. `openapi-typescript`, `orval`) against the spec URL
- **Spec source**: `http://localhost:8000/openapi.json` (dev) or deployed backend URL

### Docs for Handoffs

- **kitchen repo docs**: `docs/api/overview.md`, `docs/api/handoffs.md`, `docs/api/BREAKING_CHANGES.md`, `docs/deployment/handshake-checklist.md`
- **B2B client docs**: `docs/api/b2b_client/` – Restaurant + Employee
- **B2C client docs**: `docs/api/b2c_client/` – B2C React Native (Customer)
- **B2C feedback**: `docs/api/b2c_client/feedback_from_client/` – B2C issues and specs

---

## 3. Frontend Architecture

### kitchen-web (React TS) – Restaurant + Employee

- **Already exists** in separate repo
- Uses: Auth, CRUD, enriched endpoints, institution-scoped APIs, discretionary, archival, markets
- Copy client docs from kitchen `docs/api/b2c_client/` (B2C) or `docs/api/b2b_client/` (B2B)
- Codegen from OpenAPI for shared types

### kitchen-mobile (React Native) – B2C

- **New repo** when built
- **Tech**: React Native + React Native Web (Expo)
- **Platforms**: iOS, Android, Web (one codebase for B2C)
- Uses: Auth, signup, plans, subscriptions, payment methods, plates, plate selection, plate pickup, addresses, client bills, markets, enums
- Same OpenAPI codegen and client docs as kitchen-web
- Focus on Customer-accessible endpoints per [API_PERMISSIONS_BY_ROLE.md](../api/API_PERMISSIONS_BY_ROLE.md)

**React Native Web choice**: Avoids a separate B2C React TS web app; one B2C codebase for mobile + web. UX for browse-plans/subscribe/profile fits well. Backoffice stays React TS (tables, admin workflows).

### Separate Apps per Audience (Security)

- **B2C app**: Customers only
- **kitchen-web**: Restaurant (Supplier) + Employee (Backoffice)
- **kitchen-mobile**: B2C Customers

Restaurants and customers should not share the same frontend app. Different audiences → different apps → smaller attack surface and clearer UX boundaries. Backend enforces auth; frontend separation reduces exposure and complexity.

---

## 4. FastAPI Repo Work (This Repo)

### Phase 1: API Contract and Docs (Done)

- [x] `docs/api/overview.md` – Auth, base URLs, OpenAPI
- [x] `docs/api/handoffs.md` – Backend ↔ frontend expectations
- [x] `docs/api/BREAKING_CHANGES.md` – Breaking changes log
- [x] `docs/deployment/handshake-checklist.md` – Pre-deploy checklist

### Phase 2: OpenAPI Hygiene

- [ ] Verify `/openapi.json` and `/docs` cover all public routes
- [ ] Add tags and descriptions where missing
- [ ] Optional: CI job to publish OpenAPI spec (e.g. GitHub Actions artifact) for frontend codegen

### Phase 3: B2C Readiness

- [ ] Validate [API_PERMISSIONS_BY_ROLE.md](../api/API_PERMISSIONS_BY_ROLE.md) against implementation
- [ ] Ensure B2C endpoints are stable: auth, signup, plans, subscriptions, payment methods, plates, plate selection, plate pickup, addresses, client bills, markets, enums
- [ ] Route organization: consider grouping by consumer (client, employee, supplier) via tags or folders

### Phase 4: Technical Roadmap Alignment

- [ ] Complete Phase 1 items from [TECHNICAL_ROADMAP_2026.md](../zArchive/roadmap/TECHNICAL_ROADMAP_2026.md) (password recovery, etc.) as needed for B2C — geolocation/geocoding/autocomplete done; roadmap archived

---

## 5. Deployment Strategy

### Independent Deploys

- **kitchen** merge → deploy backend only
- **kitchen-web** merge → deploy web only
- **kitchen-mobile** merge → deploy mobile (iOS/Android/Web)

No cross-deploy coupling. Each repo owns its pipeline.

### Handshake for Breaking Changes

- Add entry to `docs/api/BREAKING_CHANGES.md`
- Coordinate with kitchen-web and kitchen-mobile
- Either: (1) frontend migrates first, then backend removes deprecated; or (2) backend + frontend deploy in same window

See [docs/deployment/handshake-checklist.md](../deployment/handshake-checklist.md).

---

## 6. Security Principles

- **Frontend is UX only**: Auth and authorization are enforced by FastAPI. Frontend route guards improve UX, not security.
- **Backend enforces role**: Every request validated by `get_client_user`, `get_employee_user`, `get_client_or_employee_user`, etc.
- **Separate apps per audience**: Reduces exposure, avoids mixing customer and restaurant flows in one bundle.
- **CORS**: Restrict `allow_origins` in production to known frontend domains.

---

## 7. Route → Consumer Map (Reference)

| Consumer | Routes / APIs |
|----------|----------------|
| **B2C (Customer)** | Auth, signup, plans, subscriptions, payment methods, plates, plate selection, plate pickup, addresses, client bills, markets, enums |
| **Restaurant (Supplier)** | Restaurants, products, QR codes, institution bank/entity, restaurant balance/transactions, plate kitchen days, holidays |
| **Backoffice (Employee)** | Credit currencies, discretionary, archival, markets, all CRUD + enriched endpoints |

See [API_PERMISSIONS_BY_ROLE.md](../api/API_PERMISSIONS_BY_ROLE.md) for detailed permission matrices.

---

## 8. Next Steps

1. **Immediate**: Ensure kitchen-web uses OpenAPI codegen and copies client docs
2. **Next**: Create kitchen-mobile repo with React Native + RN Web; configure codegen
3. **Ongoing**: Maintain `BREAKING_CHANGES.md` and `handshake-checklist.md` for cross-repo coordination
