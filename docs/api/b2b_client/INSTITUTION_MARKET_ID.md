# Institution `market_id` — Client Integration

## Overview

Every institution **must** have a **`market_id`** (UUID). The database enforces this: `institution_info.market_id` is `NOT NULL`. Institutions can be **single-market** (one country), **global** (Global Marketplace UUID = all markets), or in the future **multi-market**; they can **never** have “no market.”

**Key concept**:  
- **`market_id` = Global Marketplace UUID** (e.g. `00000000-0000-0000-0000-000000000001`) → institution is “global”; list endpoints do not filter by market when this institution is selected.  
- **`market_id` = any other market UUID** → institution is scoped to that market; when the user selects this institution, the backend restricts restaurants/entities to that market’s country.

**Client agents (e.g. UI, API clients, automation) must enforce the use of `market_id` on institution creation and updates** so that there are no barriers to missing it: treat `market_id` as a required field in forms and payloads, validate before submit, and do not allow creating or saving an institution without a valid `market_id`.

---

## SQL and API Contract

- **Database**: `institution_info.market_id` is **NOT NULL** and references `market_info(market_id)`. Every institution record has a value (Global or a specific market).
- **POST /api/v1/institutions/** (create): **`market_id` is required** in the request body. The API returns 422 if it is missing or invalid.
- **PUT /api/v1/institutions/{id}** (update): `market_id` is optional; when provided it must be a valid market UUID.
- **GET responses**: Every institution object includes **`market_id`** (always present, never null).

---

## Where `market_id` Appears

### Response: GET /api/v1/institutions/ and GET /api/v1/institutions/{institution_id}

| Field       | Type  | Description |
|------------|-------|-------------|
| `market_id` | UUID  | **Required.** Global Marketplace UUID = all markets; any other UUID = institution scoped to that market. |

**Example (local market):**

```json
{
  "institution_id": "33333333-3333-3333-3333-333333333333",
  "name": "La Parrilla Argentina",
  "institution_type": "Supplier",
  "market_id": "11111111-1111-1111-1111-111111111111",
  "is_archived": false,
  "status": "Active",
  "created_date": "2026-01-15T10:00:00Z",
  "modified_date": "2026-01-15T10:00:00Z"
}
```

**Example (global):**

```json
{
  "institution_id": "11111111-1111-1111-1111-111111111111",
  "name": "Vianda Enterprises",
  "institution_type": "Employee",
  "market_id": "00000000-0000-0000-0000-000000000001",
  "is_archived": false,
  "status": "Active",
  "created_date": "2026-01-15T10:00:00Z",
  "modified_date": "2026-01-15T10:00:00Z"
}
```

---

### Create: POST /api/v1/institutions/

**Request body** — **`market_id` is required**:

| Field             | Type   | Required | Description |
|-------------------|--------|----------|-------------|
| `name`            | string | Yes      | Institution name. |
| `institution_type`| string | No       | One of: `Employee`, `Supplier`, `Customer`, `Employer`. **Use `GET /api/v1/enums/institution-types/assignable`** to populate the dropdown; do not hardcode. |
| `market_id`       | UUID   | **Yes**  | **Required.** From GET /api/v1/markets/available or enriched; use Global Marketplace UUID for “all markets”. |

---

**Institution type dropdown**: Use `GET /api/v1/enums/institution-types/assignable`. Returns role-filtered values: **Super Admin** gets Employee, Supplier, Customer, Employer (all four); **Admin** gets Supplier, Employer only (Employee and Customer restricted to Super Admin).

---

### Update: PUT /api/v1/institutions/{institution_id}

**Request body** may include optional `market_id` (when provided, must be a valid market UUID). Only roles with permission to update institutions can change it.

**Supplier institutions**: The backend treats the initial `market_id` of a **Supplier** institution as **non-editable**. On PUT, `market_id` is stripped for Supplier institutions; only the paid multi-market upgrade flow can add or change markets. Do not rely on updating `market_id` for Supplier institutions via this endpoint.

---

## Supplier and Customer Employer: institution-bound market

- **Supplier users** and **Customer Employer** users (B2B portal) must be assigned a `market_id` that matches their **institution’s** `market_id`. The backend rejects user create/update if the user’s market is not the same as the institution’s market (single-market v1). Supplier institutions cannot have personnel assigned to markets the institution is not registered for.
- **Initial market non-editable**: For both Supplier and Customer Employer users, the assigned market cannot be changed via `PUT /users/me` or `PUT /users/{user_id}`; only the paid upgrade flow can add markets. See roadmap: [INSTITUTION_MARKET_AND_MULTI_MARKET_SCOPE.md](../../roadmap/INSTITUTION_MARKET_AND_MULTI_MARKET_SCOPE.md).

---

## How the Backend Uses Institution `market_id`

When the client sends **`institution_id`** as a filter (e.g. on list endpoints), the backend uses that institution’s `market_id` to scope results:

1. **GET /api/v1/restaurants/enriched/?institution_id=...**  
   If the institution has a **local** `market_id` (not Global), only restaurants in that market’s country are returned. If **global** (Global Marketplace UUID), no extra market filter is applied.

2. **GET /api/v1/institution-entities/enriched/?institution_id=...**  
   Same rule: local `market_id` restricts to that market’s country; global shows all.

The client does **not** send `market_id` on these list endpoints — sending `institution_id` is enough.

---

## Client / Agent Integration Checklist

1. **Treat `market_id` as required**  
   In institution create flows (UI, API clients, automation), **always** collect or set `market_id`. Do not allow creating an institution without it; validate before calling POST /api/v1/institutions/.

2. **Types / interfaces**  
   Use `market_id: string` (never `string | null`) in your Institution type for responses. For create, require `market_id` in the request type.

3. **Institution list / cards**  
   Show which market an institution uses by resolving `market_id` with **GET /api/v1/markets/available** or **GET /api/v1/markets/enriched/** (match by `market_id` to get `country_code` / `country_name`). Treat Global Marketplace UUID as “All markets”.

4. **Create / Edit institution**  
   **Required:** Include a market selector (or equivalent) and send **`market_id`** in every create request. Use the markets list from the API; for “all markets” use the Global Marketplace UUID. Recommend client agents enforce this so there are no barriers to missing `market_id` (e.g. required field, validation, no default “skip” or “none”).

5. **Filtering by institution**  
   When the user picks an institution and you call e.g. **GET /api/v1/restaurants/enriched/?institution_id=...**, no change is needed; the backend uses the institution’s `market_id` to scope.

6. **B2C / Explore**  
   B2C explore is not institution-scoped; institution `market_id` matters for **B2B** flows (institution-scoped lists).

---

## TypeScript Interfaces

```typescript
interface Institution {
  institution_id: string;
  name: string;
  institution_type: string;
  market_id: string;  // Required; never null (Global or specific market UUID)
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}

/** Create: market_id required */
interface InstitutionCreateRequest {
  name: string;
  institution_type?: string;
  market_id: string;  // Required; use GET /api/v1/markets/available to get valid UUIDs
}

/** Update: market_id optional */
interface InstitutionUpdateRequest {
  name?: string;
  institution_type?: string;
  market_id?: string;
}
```

---

## Related Documentation

- [Markets API — Client](MARKETS_API_CLIENT.md): list markets, resolve `market_id` to country/currency.
- [Enriched Endpoint Pattern](../shared_client/ENRICHED_ENDPOINT_PATTERN.md): how enriched list endpoints work.
- Backend roadmap: [USER_MARKET_AND_GLOBAL_MANAGER_V2.md](../../roadmap/USER_MARKET_AND_GLOBAL_MANAGER_V2.md) (future institution market scope).
