# User and Market — API Client Guide

**Audience**: B2C and B2B client apps  
**Purpose**: What is stored where (backend), and how to use user–market data in the API (GET /users/me, user create/update, market selector).  
**Backend**: v1 (one market per user) + v2 (multi-market, Global Manager) implemented.

---

## 1. What is stored where (backend)

| Storage | Meaning | Used by |
|--------|---------|--------|
| **`user_info.market_id`** | **Primary** assigned market (UUID, NOT NULL). One value per user. | All users. Backend keeps it in sync with the “primary” assignment. |
| **`user_market_assignment`** (v2) | **All** assigned markets per user: `(user_id, market_id, is_primary)`. One row per (user, market); `is_primary` marks which one is the primary. | Users with multiple markets (e.g. Manager for Argentina + Chile). When present, `user_info.market_id` equals the row with `is_primary = true`. |

**Summary**

- **Primary market** is always in `user_info.market_id`.
- **Full list** of assigned markets (primary first) comes from `user_market_assignment` when it exists; if the table has no rows for the user, the backend treats `user_info.market_id` as the only assigned market.
- **Customers**: One market per user (default at signup, e.g. US). B2C can treat `market_id` (or first element of `market_ids`) as the user’s “home” market for plans and subscriptions.
- **B2B (Employees/Suppliers)**: May have one market (v1) or multiple (v2). **Global** users (Admin, Super Admin, Supplier Admin, Global Manager) are assigned the **Global Marketplace** (`00000000-0000-0000-0000-000000000001`), which means “see all markets.”

---

## 2. API: User responses (market_id and market_ids)

### GET /api/v1/users/me

**Auth**: Required (Bearer).

**Response** includes:

- **`market_id`** (UUID): Primary assigned market. Use this for “user’s market” (e.g. B2C preferred market, B2B assigned market for scoping).
- **`market_ids`** (array of UUID): All assigned markets, **primary first**. v2 only; if backend has no multi-market rows, it returns `[market_id]`.

**B2C**: Use `market_id` (or `market_ids[0]`) as the user’s **preferred/home market** to restore the market selector after login (see [MARKET_SCOPE_FOR_CLIENTS.md](./MARKET_SCOPE_FOR_CLIENTS.md)).

**B2B**: Use `market_id` (or first of `market_ids`) as the **assigned market** for restaurant/search and other market-scoped APIs. If it is the **Global Marketplace** UUID, treat as “all markets.”

### GET /api/v1/users/ (list)

Same shape per user: `market_id` (primary) and `market_ids` (all, primary first). B2B can show “Assigned market” from `market_id` or resolve from `market_ids[0]`.

### GET /api/v1/users/enriched/

Enriched user list: each item has `market_id` and `market_ids` as above.

---

## 3. API: User create and update (sending market)

### POST /api/v1/users/ (create user)

**Body** (relevant fields):

- **`market_id`** (UUID, optional for Admin/Super Admin/Supplier Admin): Primary market. Backend defaults to **Global Marketplace** for Admin/Super Admin/Supplier Admin when omitted. **Required** for Manager/Operator (and must not be Global unless creator is Super Admin).
- **`market_ids`** (array of UUID, optional, v2): All assigned markets; first element is primary. If provided, backend writes `user_market_assignment` and sets `user_info.market_id` to the first. All IDs must exist and not be archived.

**Customers**: Not created via this endpoint (use customer signup). Customer signup assigns a default market (e.g. US).

### PUT /api/v1/users/me and PUT /api/v1/users/{user_id} (update user)

**Body** (relevant fields):

- **`market_id`** (UUID, optional): Set primary market. Only Admin/Super Admin/Supplier Admin (and v2 Global Manager for appropriate targets) can set **Global**; Managers/Operators cannot assign Global.
- **`market_ids`** (array of UUID, optional, v2): Replace all assignments; first is primary. Same validation as create.

**B2C**: Customers can update their own profile via PUT /users/me; typically they do **not** send `market_id` or `market_ids` (market is assigned at signup). If the backend later supports “preferred market” for customers, it could be a field on PUT /users/me and reflected in GET /users/me.

---

## 4. Global Marketplace and Global Manager

- **Global Marketplace**  
  - `market_id = 00000000-0000-0000-0000-000000000001`  
  - **Not** returned by the public **GET /api/v1/leads/markets** (it’s for assignment only).  
  - Assigned to Admin, Super Admin, Supplier Admin, and (v2) Global Manager. Backend treats it as “no market filter” / all markets.

- **Global Manager** (v2)  
  - Role name: `"Global Manager"` (Employee only).  
  - Same “see all markets” visibility as Admin, but **cannot** manage config/billing or create Admin; can only create/edit Global Manager users.  
  - B2B: If the current user’s `role_name` is `"Global Manager"`, use the same scoping as Admin (e.g. send Global market_id for restaurant search so backend does not filter by market).

---

## 5. B2C: Using user–market data

| Need | Source | Notes |
|------|--------|-------|
| **Market selector list** | **GET /api/v1/leads/markets** | No auth; returns `country_code` and `country_name` only. Use for signup country dropdown. For plans/subscriptions (need `market_id`), use GET /markets/enriched/ after login. |
| **Restore selected market after login** | **GET /api/v1/users/me** → `market_id` or `market_ids[0]` | Resolve this UUID against the list from GET /markets/enriched/ and set `selectedMarket` (or preferred market). If the user’s market is not in the public list (e.g. Global), ignore for B2C selector. |
| **Plans / subscriptions** | Use `selectedMarket.market_id` (from selector or from GET /users/me) | Pass to GET /plans/enriched/?market_id=… and for subscription creation. **Do not send** `market_id` when empty (omit param); sending `''` returns **422**. Prefer calling plans only when you have a valid market_id; when none selected, show “Select a country to see plans” and do not call. Do not use Global Marketplace for plan create/update (backend returns 400). See [MARKET_SCOPE_FOR_CLIENTS.md](./MARKET_SCOPE_FOR_CLIENTS.md). |
| **Leads / explore (cities, by-city)** | Use `selectedMarket.country_code` | Pass as `country_code` to leads and restaurant endpoints. |

**Customer signup**: Client sends `country_code` (from GET /leads/markets) in signup request; backend resolves to market. After signup, GET /users/me returns that user’s `market_id`; B2C can set the initial market selector from it.

---

## 6. B2B: Using user–market data

| Need | Source | Notes |
|------|--------|-------|
| **Assigned market for scoping** | **GET /api/v1/users/me** → `market_id` (or `market_ids[0]`) | Use when calling market-scoped APIs (e.g. restaurant search/list). |
| **Global users** | `market_id === "00000000-0000-0000-0000-000000000001"` | Do not filter by market; backend treats as “all markets.” |
| **Create/update user (Admin)** | POST /users with `market_id` and optionally `market_ids` | Managers/Operators cannot assign Global; only Admin/Super Admin/Supplier Admin (and Global Manager for Global Manager targets) can assign Global or Global Manager. |

---

## 7. TypeScript (example)

```typescript
// User profile including market (from GET /users/me)
interface UserMe {
  user_id: string;
  email: string;
  role_type: string;
  role_name: string;
  institution_id: string;
  market_id: string;           // Primary assigned market
  market_ids: string[];       // All assigned markets (primary first)
  // ... other fields
}

// Restore B2C market selector after login
async function restoreSelectedMarket(
  marketsFromAvailable: { market_id: string; country_code: string }[]
): Promise<{ market_id: string; country_code: string } | null> {
  const me = await fetch('/api/v1/users/me', { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json());
  const primaryId = me.market_id ?? me.market_ids?.[0];
  if (!primaryId) return null;
  const found = marketsFromAvailable.find(m => m.market_id === primaryId);
  return found ?? null;  // If user's market not in public list (e.g. Global), return null
}
```

---

## 8. Related docs

- [MARKET_SCOPE_FOR_CLIENTS.md](./MARKET_SCOPE_FOR_CLIENTS.md) — Markets API and market scope (list, selector, public `/leads/markets`, Global rule, B2B/B2C).
- [MARKET_BASED_SUBSCRIPTIONS.md](./MARKET_BASED_SUBSCRIPTIONS.md) — Multi-market subscriptions.
- Backend roadmap: [USER_MARKET_ASSIGNMENT_DESIGN.md](../../roadmap/USER_MARKET_ASSIGNMENT_DESIGN.md), [USER_MARKET_AND_GLOBAL_MANAGER_V2.md](../../roadmap/USER_MARKET_AND_GLOBAL_MANAGER_V2.md).
