# User–Market Assignment: Design and Implementation Plan (v1)

**Status**: Implemented (v1 + v2)  
**Purpose**: Define how market assignment works, where it is stored, and how Super Admin assigns a market when registering users (and after).  
**v2**: Multi-market and **Global Manager** are planned in [USER_MARKET_AND_GLOBAL_MANAGER_V2.md](USER_MARKET_AND_GLOBAL_MANAGER_V2.md).  
**v3**: Cross-country plans (multi-plan signup) and **travel mode** (open periods to consume in other countries) are in the same roadmap doc. This v1 design is structured so v2 and v3 extend it without breaking changes.

---

## Implementation plan: v1 only, or v1+v2+v3 in one go?

**Recommendation: implement v1 in this pass; keep v2 and v3 on the roadmap and design so we retain context when we add them.**

| Approach | Pros | Cons |
|----------|------|------|
| **v1 only now** | Clear scope (schema + seed + create/update + auth + GET /users/me). Ship and validate. v2/v3 are additive later with same design. | Two or three later efforts for v2 and v3. |
| **v1 + v2 + v3 in one go** | Single implementation cycle; full context; no “re-opening” the feature. | Large scope: multi-market table, Global Manager role, multi-plan signup, travel-mode/eligibility logic. Higher risk and longer cycle. |

**Suggested path**: Implement **v1 fully** (see §4 checklist). The schema and API are already designed so that:
- **v2** only adds `user_market_assignment` (and Global Manager role); no breaking change to `user_info.market_id`.
- **v3** adds plan/subscription and consumption-eligibility rules (multi-plan, open periods); no change to user–market storage.

If you prefer to do **v1 and v2 in one go** (same feature area, better context), we can add the `user_market_assignment` table and Global Manager role in the same pass as v1, and leave **v3** (cross-country plans, travel mode) for a follow-up. Doing **v1+v2+v3** in one go is possible but spreads into plans/billing and eligibility—better as a separate phase after v1 (and optionally v2) is live.

---

## 1. What will the market assignment be like?

- **One market per user (v1)**: Each user has **exactly one** assigned market. Multi-market assignment is planned for v2.
- **Who has an assigned market**:
  - **Employees** (Manager, Operator, Admin, Super Admin): Assigned market drives scope (e.g. “restaurants to support”). **Employee Admin, Super Admin, Supplier Admin** get the **Global Marketplace** so they see all markets. **Manager / Operator** get a single country market.
  - **Suppliers**: One assigned market (country or Global).
  - **Customers**: Stored for consistency (NOT NULL); use a sensible default at signup (e.g. US or first available). B2C continues to use in-app `selectedMarket`; optional later: persist `preferred_market_id` for UX.
- **Semantics**:
  - **Assigned market = country market** (e.g. Argentina, US): user’s scope is that market.
  - **Assigned market = Global Marketplace** (`00000000-0000-0000-0000-000000000001`): user has global scope (no market filter). In v2, a **Global Manager** will also see all markets but with fewer privileges than Admin (see v2 roadmap).
- **Default at creation**:
  - If **role** is Employee **Admin**, **Super Admin**, or Supplier **Admin** → default `market_id` to **Global Marketplace** when not provided.
  - If **role** is **Manager** or **Operator** → **require** `market_id` (no Global unless explicitly allowed by policy); Super Admin / Admin chooses the market.
  - **Customers**: Assign default market at signup (e.g. from `selectedMarket` or US).

---

## 2. Where is it stored?

**Single required column on `user_info` (v1).**

| Option | Storage | Pros | Cons |
|--------|---------|------|------|
| **A (v1)** | `user_info.market_id UUID NOT NULL REFERENCES market_info(market_id)` | Simple, one place, enforced; every user has a market. | One market per user only (v2 adds multi-market). |
| B (v2) | Separate table `user_market_assignment (user_id, market_id, ...)` | Multi-market, history. | v2; more joins. |

**Choice for v1: `user_info.market_id` NOT NULL.** (DB will be torn down; no migration from nullable.)

- **Schema**: `ALTER TABLE user_info ADD COLUMN market_id UUID NOT NULL REFERENCES market_info(market_id) ON DELETE RESTRICT;` (or use a default FK for seed; RESTRICT avoids deleting a market while users reference it.)
- **Index**: `CREATE INDEX idx_user_info_market_id ON user_info(market_id);` for “users by market” queries.
- **Seed**: Every seeded user gets a valid `market_id` (e.g. Global for Admin/Super Admin, a specific country market for Manager/Operator, default for Customer).
- **v2 prep**: Keep a single column in v1 so that v2 can introduce `user_market_assignment` and treat `user_info.market_id` as “primary” or deprecate it in favor of the join table; design so a future **Global Manager** can see all markets with less privilege than Admin (see v2 roadmap).

**Expose in API**:

- **GET /users/me** (and enriched user): include `market_id` and optionally `market_name` / `country_code` (from `market_info`).
- **GET /users** (list): include `market_id` (and optionally enriched market name) so B2B can show “assigned market”.
- **POST /users** (create): accept **required** `market_id` for Employee/Supplier (optional with default for Admin/Supplier Admin); validation: must be a valid `market_info.market_id` (including Global). **Managers cannot assign Global** (see §3).
- **PUT /users/{user_id}** (update): accept optional `market_id`; only **Super Admin** or **Admin** can set or change it; **Managers cannot assign themselves or others to Global**.

---

## 3. How will Super Admin assign market at registration?

### 3.1 At user creation (POST /users)

- **Request body**: Add **`market_id`** to `UserCreateSchema` (UUID). **Required** for Manager/Operator; required with default (Global) for Admin/Super Admin/Supplier Admin.
- **Who can set it**:
  - **Super Admin**: Can set any `market_id` (including Global) when creating any user.
  - **Employee Admin**: Can set `market_id` when creating users; **cannot assign Global** to new users (only Super Admin can assign Global). Can create Manager/Operator with a country market only.
  - **Supplier Admin**: When creating Supplier users, can set `market_id` (country or Global per policy).
  - **Managers**: Cannot create users (or cannot create users with Global market / Global Manager). v2: Managers cannot create **Global Manager** users (see v2 roadmap).
- **Validation**:
  - `market_id` must exist in `market_info` and not be archived.
  - If role is Employee Admin, Super Admin, or Supplier Admin and `market_id` is **not** provided → backend **defaults** to **Global Marketplace**.
  - If role is **Manager** or **Operator** → **require** `market_id` and **reject Global** (400) when the creator is not Super Admin (so Managers cannot assign Global to themselves or others).
- **Flow**: Super Admin (or Admin) opens “Create user”, selects role, selects **Market**. For Manager/Operator, dropdown excludes Global unless creator is Super Admin. POST /users includes `market_id`. Backend persists `user_info.market_id`.

### 3.2 After registration (PUT /users/{user_id} and PUT /users/me)

- **Request body**: Add optional **`market_id`** to `UserUpdateSchema` (UUID). Omit to leave unchanged.
- **Who can set/change it** (relaxed for all three Admin roles):
  - **Super Admin**: Can set or change `market_id` for **any** user (including to/from Global).
  - **Employee Admin**: Can set or change `market_id` for users they can edit, **including Global** (e.g. self or institution users).
  - **Supplier Admin**: Can set or change `market_id` for users in their institution, **including Global** (e.g. self via PUT /users/me or other institution users).
  - **Managers / Operators**: **Cannot assign themselves or others to Global.** Only Admin and Super Admin can set market to Global. (v2: cannot create or assign Global Manager.)
- **Validation**: Same as create (must exist in `market_info`, not archived). Field is NOT NULL so no “clearing”; omit to leave unchanged.
- **Flow**: Admin or Super Admin opens user detail (or own profile), edits “Assigned market”, saves. PUT /users/{user_id} or PUT /users/me with `market_id`. Backend updates `user_info.market_id`.

### 3.3 Summary table

| Actor           | At create (POST /users)     | At update (PUT /users/{id}, PUT /users/me) |
|----------------|-----------------------------|--------------------------------------------|
| Super Admin    | Set any market (incl. Global) | Set/change any market (incl. Global)       |
| Employee Admin | Set market (default Global for Admin); cannot assign Global to others at create | Set/change any market (incl. Global) for users they can edit |
| Supplier Admin | Set market for institution users (default Global for Supplier Admin) | Set/change any market (incl. Global) for own institution users (e.g. self) |
| Manager / Operator | Cannot create users | Cannot assign self or others to Global |

---

## 4. Implementation checklist

- [ ] **Schema**: Add `market_id UUID NOT NULL REFERENCES market_info(market_id) ON DELETE RESTRICT` to `user_info`; add to history/trigger if user has history table.
- [ ] **Seed**: Every seeded user gets a valid `market_id` (Global for Admin/Super Admin, specific market for Manager/Operator, default for Customer).
- [ ] **DTO**: Add `market_id: UUID` to `UserDTO` (required).
- [ ] **Schemas**: Add `market_id: UUID` (required for create where role is Manager/Operator; optional with default for Admin/Supplier Admin) to `UserCreateSchema`; add optional `market_id` to `UserUpdateSchema`; add `market_id: UUID` to response schemas.
- [ ] **Create flow**: In `process_admin_user_creation`, require `market_id` for Manager/Operator; reject Global if creator is not Super Admin. Default to Global for Admin/Super Admin/Supplier Admin when omitted. Validate `market_id` against `market_info`.
- [ ] **Update flow**: In user update handler, allow Super Admin to set any market; Admin only non-Global. **Managers cannot assign self or others to Global.**
- [ ] **GET /users/me** (and enriched): Include `market_id` (and optionally `market_name` / `country_code` from `market_info`).
- [ ] **Authorization**: Enforce: Super Admin can set any market; Admin and Supplier Admin cannot assign Global; Managers cannot assign Global to anyone (including themselves).
- [ ] **Docs**: Update [MARKET_SCOPE_FOR_CLIENTS.md](../api/shared_client/MARKET_SCOPE_FOR_CLIENTS.md) and B2B client docs. Reference [USER_MARKET_AND_GLOBAL_MANAGER_V2.md](USER_MARKET_AND_GLOBAL_MANAGER_V2.md) for v2 (multi-market, Global Manager).

---

## 5. B2B usage (after implementation)

- **GET /users/me** returns `market_id` (and optionally market name/country_code). B2B uses this as the **assigned market** for the current user.
- For **restaurant search/list** (support flow): B2B sends this `market_id` (or omits for “global” if backend supports omit = global). Backend filters by market when `market_id` is a country market; when it is Global, backend does not filter.
- **Managers / Operators** will have `market_id` = a country market (e.g. Argentina). **Employee Admin, Super Admin, Supplier Admin** will have `market_id` = Global Marketplace so they see all restaurants. **v2** will add a **Global Manager** (see [USER_MARKET_AND_GLOBAL_MANAGER_V2.md](USER_MARKET_AND_GLOBAL_MANAGER_V2.md)): same “see all markets” visibility with less privilege than Admin; Global Manager can create Global Manager users; Managers cannot create or assign Global Manager.

This design enforces one market per user (NOT NULL), stores it on `user_info`, and lets Super Admin assign at registration (POST /users with required/ defaulted `market_id`) and later (PUT /users/{user_id}). v1 is structured so v2 multi-market and Global Manager can extend it cleanly.

---

## 6. Future work: institution market scope

Institution-level market scoping is planned so that institutions can be Global or local (one or more markets). When implemented, **institution scope** will be the **union of the institution’s assigned market_ids** (or Global), and will be combined with user’s market scope (union of user’s market_ids or Global) for effective visibility. See [INSTITUTION_MARKET_AND_MULTI_MARKET_SCOPE.md](INSTITUTION_MARKET_AND_MULTI_MARKET_SCOPE.md).
