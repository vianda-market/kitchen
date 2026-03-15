# Institution Market and Multi-Market Scope (Roadmap)

**Status**: v1 implemented; v2 roadmap  
**Single source**: This doc is the single roadmap for institution market, user market, multi-market assignment, and paid upgrade. Content from USER_MARKET_ASSIGNMENT_DESIGN.md and USER_MARKET_AND_GLOBAL_MANAGER_V2.md has been merged here; those files are archived in `docs/zArchive/roadmap/`.

This document describes the roadmap for introducing **market_id** (and eventually multi-market) at the **institution** level, and how institution scope combines with user scope. It enables distinguishing **Global** vs **local** institutions and controls bloat when many institutions are 1:1 with a restaurant.

---

## 1. Current state (after v1)

- **Institution**: `institution_info.market_id` (optional). NULL or Global = all markets; one UUID = local market. v1 implemented.
- **User**: `user_info.market_id` NOT NULL (one market per user). `user_market_assignment` exists for v2 multi-market; scope is user’s assigned market(s) or Global.
- **Restaurant**: No `market_id` column; market is derived from address (`address.country_code` → `market_info.country_code`).
- **Scoping**: When listing restaurants or institution entities by `institution_id`, if the institution has a local `market_id`, results are restricted to that market (bloat control).

---

## 2. Goals

1. **Institution-level market**: Add a market dimension to institutions so some are **Global** (all countries) and others **local** (one or more specific markets), and use this to control bloat when many institutions are 1:1 with a restaurant.
2. **Multi-market for institutions and users**: Allow both institutions and users to be assigned **more than one** `market_id` (other than Global), so scope = **union** of those market_ids — not “all available markets,” but an **explicit set** per institution/user.

---

## 3. Institution market: v1

- **Storage**: Add optional `market_id` to `institution_info` (e.g. `market_id UUID NULL REFERENCES market_info(market_id)`).
- **Semantics**:
  - **NULL or Global marketplace**: institution is Global (all markets); behavior unchanged (all its restaurants in all markets).
  - **One UUID** (country market): institution is local to that market; restrict visibility and operations to restaurants whose address falls in that market (e.g. `address.country_code` → that market).
- **Bloat control (1:1 institution:restaurant)**: For local institutions, list/enriched endpoints that return restaurants (or entities) for an institution apply a filter: only restaurants whose derived market matches the institution’s `market_id`. Implementation touchpoints: any “institution scope” logic that today ignores market (e.g. restaurant list, institution-entity list).

---

## 4. Institution multi-market: v2

- **Storage**: Add table `institution_market_assignment` (e.g. `institution_id`, `market_id`, optional `is_primary`, `created_at`). Mirrors `user_market_assignment`.
- **Semantics**: An institution can have **multiple** market_ids (e.g. Argentina + Chile). Scope for that institution = **union** of those market_ids (not all markets).
- **Migration**: Existing single `institution_info.market_id` can be migrated into this table; keep or deprecate the column for backward compatibility.

---

## 5. User multi-market and user_market_assignment

**The `user_market_assignment` table is the mechanism we use to allow users to have access to more than their initial market.** Today (v1) each user has one market (stored in `user_info.market_id` and, for consistency, one row in `user_market_assignment` with `is_primary = true`). The **paid multi-market upgrade** adds additional rows to `user_market_assignment` for that user; scope is then the **union** of all assigned market_ids (not all available markets).

- **Storage**: Table `user_market_assignment` (e.g. `user_id`, `market_id`, `is_primary`, `created_at`). `user_info.market_id` is kept as the primary market for backward compatibility (v1 clients read it; v2 APIs also return `market_ids[]` from this table, primary first).
- **API**: GET /users/me returns `market_id` (primary) and `market_ids[]` (all assigned, primary first). Market-scoped APIs (e.g. GET /restaurants/by-city) treat the user as assigned to a market if it appears in `user_market_assignment` (or, when the table is empty, fallback to `user_info.market_id`).
- **Paid upgrade**: The upgrade flow (middle table to onboarding) results in inserting additional rows into `user_market_assignment` for the user (and, for institutions, into `institution_market_assignment`). No default to all markets; both user and institution have an **explicit set** of market_ids (or Global).
- **Global Marketplace**: The sentinel `market_id` for see-all-markets is used for Admin / Super Admin / Supplier Admin (and, in v2, **Global Manager**). See §5.1 below.

### 5.1 Global Manager (v2)

**Business intent**: A **Global Manager** sees all restaurants for the institution across the globe (same visibility as all markets) but has **less privilege than Admin** (no user management beyond creating other Global Managers, no config, no billing).

| Aspect | Admin / Super Admin | Global Manager (v2) |
|--------|----------------------|---------------------|
| **Market visibility** | All markets (Global) | All markets |
| **Privileges** | Full | Reduced: can create **Global Manager** users only; cannot assign Global to Manager/Operator |
| **Who can create Global Manager** | Super Admin, Admin | Super Admin, Admin, or existing Global Manager (Managers cannot create or assign Global Manager) |

### 5.2 Cross-country plans and travel mode (v3, future)

**Depends on**: v2 multi-market and plan/subscription model. Support users who operate or consume **cross-country**: e.g. **multi-plan signup** (more than one active subscription/plan per user, one per market) and **travel mode** — time-bound periods during which the user can consume in another market (e.g. US subscriber using a restaurant in Argentina). v1/v2 schema and APIs should not preclude this (e.g. consumption eligibility considers assigned market(s) plus travel/open period for the requested market).

---

## 6. Combined scope rule

When both institution and user scope apply (e.g. “list restaurants I can support”):

- **User scope**: user’s assigned market_ids (or Global).
- **Institution scope**: institution’s assigned market_ids (or Global).

**Effective scope**: Restaurants (or other market-scoped resources) are visible if they fall within **both** user and institution scope. For example: “restaurants in (user markets) AND (institution markets)” — i.e. intersection of the two sets. If either side is Global, that side imposes no market filter.

- **Explicit set only**: Neither institution nor user gets “all markets” unless explicitly assigned Global. The system does not default to “all available markets”; both have an explicit set (or Global).

---

## 7. B2C and B2B: initial market non-editable and paid multi-market upgrade

- **B2C users**: `role_type = Customer` with `role_name = Comensal` or **Customer Employer**. Comensal selects market at signup (required from client); Customer Employer accesses via B2B portal and is restricted to their institution’s market(s). Both can pay to upgrade from single-market to multi-market later.
- **B2B users**: `role_type = Supplier` (and Customer Employer when in B2B). Supplier users and Supplier institutions are restricted to the market(s) of the institution; user’s `market_id` must be within the institution’s assigned market(s). Initial market is non-editable until paid upgrade.
- **Non-editable initial market**: The initial `market_id` assigned at signup or creation must be **non-editable** for:
  - **Users**: Customers (Comensal, Customer Employer) cannot change their own `market_id` / `market_ids` via profile update (strip on `PUT /users/me`). Supplier users (and Customer Employer in B2B) same: strip on update; only the upgrade flow can add markets.
  - **Institutions**: B2C-relevant and B2B Supplier institutions—assigned market_id(s) are not editable by the customer/supplier; only the upgrade flow can add markets.
- **Paid upgrade to multi-market**: When a Customer (Comensal or Customer Employer) or Supplier pays to upgrade from single-market to multi-market, onboard through a **single middle table**. This table:
  - Is **one shared table** with a **segment** (or `actor_type`) column (e.g. Comensal | Customer Employer | Supplier) so both B2C and B2B write to it and **analytics can JOIN in SQL** (e.g. upgrade events by segment, geography, time).
  - Sits between "purchase/entitlement" and the actual assignment of additional markets to **institutions and users**.
  - Drives the onboarding flow; after completion, the system adds market assignments (e.g. via `user_market_assignment`, `institution_market_assignment`).
- Include this **middle table** and the upgrade onboarding flow in the multi-market feature roadmap for both **institutions and users**.

---

## 8. Not in scope

- “All available markets” as a default is out of scope; both institution and user have an explicit set (or Global).

---

## 9. Summary

| Item | v1 | v2 |
|------|----|----|
| **Institution market** | Add `institution_info.market_id` (nullable or Global) | Add `institution_market_assignment`; multi-market per institution |
| **Institution scope** | Single market or Global | Union of institution’s assigned market_ids (or Global) |
| **User scope** | `user_info.market_id` + `user_market_assignment` (one row); GET /users/me `market_id` / `market_ids[]` | Multi-market via `user_market_assignment`; Global Manager (v2); cross-country/travel (v3) |
| **Combined scope** | User markets ∩ institution market (or Global = no filter) | User markets ∩ institution markets |
| **B2C** | Initial market non-editable (users + institutions); lock in one market | Paid upgrade via **middle table** → add markets to users and institutions |
| **B2B (Supplier + Customer Employer)** | Same: initial market non-editable; user market must be within institution’s market(s) | Paid upgrade via **same middle table** (segment: Comensal | Customer Employer | Supplier); **SQL-joinable for analytics** |

This roadmap defines institution market_id, multi-market for both institutions and users, bloat control, B2C and B2B non-editable initial market with future paid upgrade via a **single shared middle table** that is SQL-joinable for analytics.

---

## 10. References (archived)

The following roadmap documents have been merged into this file and are no longer updated; they are kept in `docs/zArchive/roadmap/` for reference:

- **USER_MARKET_ASSIGNMENT_DESIGN.md** — v1 user market storage (`user_info.market_id`), API, and Super Admin assignment; v2/v3 prep.
- **USER_MARKET_AND_GLOBAL_MANAGER_V2.md** — Multi-market assignment (`user_market_assignment`), Global Manager role, v3 cross-country/travel mode.

**SUBSCRIPTION_MANAGEMENT_FUTURE.md** (employee cancel/hold, cron, generic PUT subscription) remains in `docs/roadmap/`; it is out of scope for institution/market scope and is not merged here.
