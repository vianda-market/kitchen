# User–Market and Global Manager (v2 Roadmap)

**Status**: Implemented (v2)  
**Depends on**: [USER_MARKET_ASSIGNMENT_DESIGN.md](USER_MARKET_ASSIGNMENT_DESIGN.md) (v1: one market per user, NOT NULL, enforced)

This document describes **v2** features: **multi-market assignment** and the **Global Manager**. The v1 design is intentionally kept compatible so v2 can extend it without breaking changes.

---

## 1. Multi-market assignment (v2)

- **Today (v1)**: Each user has exactly one `user_info.market_id` (NOT NULL).
- **v2**: Support **multiple markets per user** (e.g. a Manager for Argentina + Chile).
  - **Storage**: Introduce `user_market_assignment` (e.g. `user_id`, `market_id`, `is_primary`, `created_at`). Optionally keep `user_info.market_id` as “primary” market for backward compatibility, or derive primary from the join table.
  - **API**: GET /users/me returns `market_ids[]` (or `assigned_markets[]`) in addition or instead of single `market_id`; POST/PUT user can accept `market_ids[]` for roles that allow multi-market.
  - **Scoping**: Restaurant/search and other market-scoped APIs consider user assigned to a market if their `market_ids` contains it (or primary market).
- **Backward compatibility**: v1 clients that only read `market_id` can continue to use “primary” market; v2 clients use the full list.

---

## 2. Global Manager (v2)

**Business intent**: A **Global Manager** sees all restaurants for the institution across the globe (same visibility as “all markets”) but has **less privilege than Admin**. They do not receive Admin powers (e.g. user management, config, billing). Use case: regional or global support visibility without granting full Admin.

### 2.1 Behavior

| Aspect | Admin / Super Admin | Global Manager (v2) |
|--------|----------------------|----------------------|
| **Market visibility** | All markets (Global Marketplace) | All markets (see all restaurants for institution globally) |
| **Privileges** | Full (users, config, billing, etc.) | Reduced: no user creation/assignment of Admin, no config/billing; can create and manage **Global Manager** users only (see below) |
| **Assignment** | Assigned Global market (v1) or multi-market (v2) | Assigned Global market (v1) or “all markets” (v2) |

- **Global Manager** can:
  - See all restaurants for the institution across all markets (read/list only, or within a defined permission set).
  - **Create new Global Manager users** (so the organization can scale “global viewers” without giving Admin).
- **Global Manager** cannot:
  - Create or edit Admin, Super Admin, or assign Global market to Manager/Operator.
  - Perform Admin-only actions (config, billing, etc.).

### 2.2 Who can create or assign Global Manager

| Actor | Can create Global Manager user? | Can assign user to Global market / Global Manager? |
|-------|----------------------------------|----------------------------------------------------|
| **Super Admin** | Yes | Yes |
| **Admin** (Employee Admin, Supplier Admin) | Product decision (e.g. yes) | Yes (for Global Manager only; cannot assign Manager to Global) |
| **Global Manager** | **Yes** — can create new **Global Manager** users only | Yes — for new Global Manager users only (assign Global market) |
| **Manager / Operator** | **No** | **No** — cannot assign themselves or others to Global; cannot create Global Manager users |

So: **Managers cannot assign themselves or create Global Manager users.** Only Super Admin, Admin, or an existing Global Manager can create Global Manager users.

### 2.3 Implementation notes (v2)

- **Role name**: Add a new role name **`Global Manager`** (e.g. `GLOBAL_MANAGER` in enum) for Employee (and optionally Supplier). Permission matrix: Global Manager has a subset of Admin permissions (e.g. read all markets, create Global Manager only).
- **Market assignment**: Global Manager users have `market_id = Global Marketplace` (v1) or “all markets” in the multi-market model (v2). Backend treats them as “see all markets” for restaurant/search and reporting, but applies reduced permission checks elsewhere.
- **Authorization**: In create/update user flows, enforce: if the new or updated role is Global Manager, only Super Admin, Admin, or another Global Manager can create/update that user; **Managers cannot create or assign Global Manager.**

---

## 3. v1 design prepared for v2

- **Single `user_info.market_id` (NOT NULL)** in v1 is sufficient for “primary” market; v2 can add `user_market_assignment` and optionally keep `user_info.market_id` as primary or migrate.
- **Restriction “Managers cannot assign Global”** in v1 aligns with v2 “Managers cannot create or assign Global Manager.”
- **Global Marketplace** as a sentinel market_id is shared: both Admin and (in v2) Global Manager use it for “see all markets”; differentiation is by **role** (Admin vs Global Manager), not by market_id alone.

---

## 4. Summary

| Item | v1 | v2 |
|------|----|----|
| **Market storage** | `user_info.market_id` NOT NULL, one per user | Add `user_market_assignment`; multi-market per user |
| **Global visibility** | Admin / Super Admin / Supplier Admin → Global market | Add **Global Manager**: same visibility, less privilege than Admin |
| **Who can create Global Manager** | N/A | Super Admin, Admin, or existing Global Manager |
| **Managers** | Cannot assign self/others to Global market | Cannot create or assign Global Manager users |

Multi-market and Global Manager are **v2 roadmap** items; v1 implementation should not block on them but should avoid decisions that would prevent these extensions.

---

## 5. Future work: institution market scope

Institution-level market scoping will be introduced so that institutions can be Global or local (one or more markets). When implemented, **institution scope** will be the **union of the institution’s assigned market_ids** (or Global). Combined with user scope (union of user’s market_ids or Global), effective visibility will be the intersection: e.g. restaurants in (user markets) AND (institution markets). See [INSTITUTION_MARKET_AND_MULTI_MARKET_SCOPE.md](INSTITUTION_MARKET_AND_MULTI_MARKET_SCOPE.md).

---

## 6. Cross-country plans and travel mode (v3 roadmap)

**Depends on**: v2 multi-market (user can be associated with multiple markets) and plan/subscription model.

**Business intent**: Support users who operate or consume **cross-country**: e.g. sign up to **more than one Plan at the same time** (one per market), and **travel mode** — open periods during which the user can **consume in other countries** while traveling (e.g. a US subscriber temporarily using a restaurant in Argentina).

- **Multi-plan signup (v3)**: Allow a customer (or employee) to hold active subscriptions/plans in more than one market at once. Eligibility and billing are per-market; backend must support multiple active plan associations per user (or per user+market).
- **Travel mode / open periods (v3)**: Define time-bound “open periods” (e.g. trip dates, or a “travel mode” flag with start/end) during which the user is allowed to consume in a market other than their primary. Rules: which markets are allowed, max duration, and how it interacts with plans (e.g. must have a plan in the destination market, or use a special travel pass). This should be reflected in the roadmap so v1/v2 schema and APIs don’t preclude it (e.g. consumption eligibility checks consider “assigned market(s)” plus “travel mode / open period” for the requested market).
- **v1/v2 compatibility**: v1 (one market per user) and v2 (multi-market assignment) remain the foundation; v3 adds **plan/subscription** and **consumption eligibility** rules (multi-plan, travel windows) without changing the core user–market storage model.
