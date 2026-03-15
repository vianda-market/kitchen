# City Required at Signup – Implementation Plan

**Status:** Planned  
**Last updated:** 2026-03

---

## Summary

1. **All users** have `city_id` NOT NULL. B2B users (Employee, Supplier) get a **Global city** (no city filter). Customer Comensals get a **real city** at signup and can change it later but cannot remove it.
2. **Global city** – Sentinel like Global Marketplace: one city row with `country_code = 'GL'`. Users with this city are not limited by city in queries.
3. **API enforcement** – Customers cannot set `city_id` to null or to the Global city. They can change to another real city in their market.

---

## Design: Global City (like Global Market)

| Concept | Market | City |
|---------|--------|------|
| **Sentinel** | Global Marketplace (`market_id`, `country_code='GL'`) | Global city (`city_id`, `country_code='GL'`) |
| **Purpose** | User not limited by country | User not limited by city |
| **Who gets it** | Admin, Super Admin, Supplier Admin (B2B) | Employee, Supplier (B2B) |
| **Who must have real value** | Manager, Operator, Customer | Customer Comensal only |

---

## Schema Changes

### 1. Add Global city to seed

**`app/config/supported_cities.py`** – Add Global city (or handle in seed only):

```python
# Global city for B2B users (no city filter). country_code 'GL' matches Global Marketplace.
GLOBAL_CITY_COUNTRY_CODE = "GL"
GLOBAL_CITY_NAME = "Global"
```

**`app/db/seed.sql`** – Insert Global city (before other cities, or with fixed UUID for config reference):

```sql
-- Global city for B2B users (Employee, Supplier). country_code GL matches Global Marketplace.
INSERT INTO city_info (city_id, name, country_code, is_archived, status, created_date, modified_by, modified_date) VALUES
('00000000-0000-0000-0000-000000000001', 'Global', 'GL', FALSE, 'Active'::status_enum, CURRENT_TIMESTAMP, 'dddddddd-dddd-dddd-dddd-dddddddddddd', CURRENT_TIMESTAMP);
```

**Note:** Use a fixed UUID (e.g. `00000000-0000-0000-0000-000000000001`) for the Global city so we can reference it in config. Ensure `market_info` has `country_code='GL'` for the Global market (already in seed).

**Conflict:** `city_id` is UUID primary key with `DEFAULT uuidv7()`. For seed we need to explicitly set the UUID. The Global market uses `00000000-0000-0000-0000-000000000001` – we should use a different fixed UUID for Global city to avoid collision with other tables. Use e.g. `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa` for Global city.

### 2. `pending_customer_signup` – add `city_id`

```sql
ALTER TABLE pending_customer_signup
ADD COLUMN city_id UUID NOT NULL REFERENCES city_info(city_id) ON DELETE RESTRICT;
```

Or in full table definition (tear-down rebuild):

```sql
CREATE TABLE pending_customer_signup (
    ...
    market_id UUID NOT NULL REFERENCES market_info(market_id) ON DELETE RESTRICT,
    city_id UUID NOT NULL REFERENCES city_info(city_id) ON DELETE RESTRICT
);
```

### 3. `user_info` – make `city_id` NOT NULL, add default for backfill

Current: `city_id UUID NULL`

Change to:

```sql
-- Remove nullable, add NOT NULL with default for existing rows (tear-down = no existing rows)
ALTER TABLE user_info ALTER COLUMN city_id SET NOT NULL;
-- Default: Global city for seed users (superadmin, system_bot). New B2B users get Global; Customers get real city from signup.
ALTER TABLE user_info ALTER COLUMN city_id SET DEFAULT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';  -- GLOBAL_CITY_ID
```

**Seed users (superadmin, bot):** Set `city_id` to Global city in the INSERT.

---

## Config

**`app/config/settings.py` or new `app/config/city_config.py`:**

```python
GLOBAL_CITY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")  # Must match seed

def is_global_city(city_id: Optional[UUID]) -> bool:
    return city_id is not None and city_id == GLOBAL_CITY_ID
```

---

## API / Service Changes

### 1. Customer signup – `request_customer_signup`

- **Schema:** `CustomerSignupSchema` – add `city_id: UUID` (required).
- **Validation:**
  - `city_id` must exist in `city_info`, not archived.
  - `city_id` must NOT be the Global city.
  - City's `country_code` must match market's `country_code`.
- **Insert:** Include `city_id` in `INSERT INTO pending_customer_signup`.

### 2. Customer signup – `verify_and_complete_signup`

- **SELECT:** Add `city_id` to the query.
- **user_data:** Include `city_id` when calling `create_user_with_validation`.

### 3. User creation – `create_user_with_validation` / `user_service.create`

- Ensure `user_data` can include `city_id` and it is persisted to `user_info`.
- **B2B user creation** (Employee, Supplier): If `city_id` not provided, set `city_id = GLOBAL_CITY_ID`.
- **Customer creation** (from signup): `city_id` comes from `user_data` (from pending).

### 4. PUT /users/me – Customer city update

- **Rule:** Customers can change `city_id` to another real city but cannot:
  - Set `city_id` to `null`.
  - Set `city_id` to the Global city.
- **Validation:** Reuse `_validate_user_update_city_id` but add:
  - Reject `city_id is None` for Customers (400: "City is required and cannot be removed").
  - Reject `city_id == GLOBAL_CITY_ID` for Customers (400: "Customers must have a specific city").
- **Existing:** `_validate_user_update_city_id` already validates city exists, not archived, and matches market country.

### 5. PUT /users/{id} – B2B updating a Customer

- When an Employee/Admin updates a Customer's `city_id`:
  - Same rules: cannot set to null or Global.
  - Validate city matches Customer's market country.

### 6. GET /cities/ – Exclude Global from B2C picker

- When used for Customer signup or profile city picker: exclude the Global city from results.
- Add query param `exclude_global=true` (default for unauthenticated or Customer) or infer from context.
- B2B typically does not call this for a city picker (they assign Global by default).

---

## City-scoped queries

- **User has Global city:** Do not filter by city (same as current "no city" behavior).
- **User has real city:** Filter by city (e.g. `GET /employers/{id}/addresses?city_id=...`, restaurant by-city, etc.).

Helper:

```python
def should_filter_by_city(user: dict, user_city_id: UUID) -> bool:
    return not is_global_city(user_city_id)
```

---

## B2B user creation flow

- **Employee, Supplier:** Set `city_id = GLOBAL_CITY_ID` when creating user (in `_apply_admin_user_rules` or equivalent).
- **Customer** (if B2B ever creates one): Require `city_id` in request, validate not Global, matches market.

---

## Implementation Checklist

### Schema & seed
- [ ] Add Global city to `city_info` seed (fixed UUID, `country_code='GL'`).
- [ ] Add `GLOBAL_CITY_ID` and `is_global_city()` to config.
- [ ] Add `city_id` to `pending_customer_signup` (NOT NULL, FK to city_info).
- [ ] Change `user_info.city_id` to NOT NULL, default Global city.
- [ ] Update seed `user_info` INSERTs to include `city_id` (Global for superadmin, bot).

### Signup
- [ ] Add `city_id` to `CustomerSignupSchema` (required).
- [ ] Add `_validate_and_resolve_city_id()` in user_signup_service: exists, not archived, not Global, matches market.
- [ ] Update `request_customer_signup`: validate city, include in INSERT.
- [ ] Update `verify_and_complete_signup`: SELECT city_id, pass to user_data.
- [ ] Ensure `create_user_with_validation` / user_service persists `city_id`.

### B2B user creation
- [ ] In admin user creation logic: set `city_id = GLOBAL_CITY_ID` for Employee, Supplier when not provided.
- [ ] If Customer created via B2B: require `city_id`, validate not Global.

### PUT /users/me (Customer)
- [ ] Reject `city_id is None` for Customers (400).
- [ ] Reject `city_id == GLOBAL_CITY_ID` for Customers (400).
- [ ] Keep existing `_validate_user_update_city_id` (exists, not archived, matches market).
- [ ] Allow changing to another valid city.

### PUT /users/{id} (B2B updating Customer)
- [ ] Same rules when updating Customer's `city_id`: no null, no Global, must match market.

### GET /cities/
- [ ] Exclude Global city when used for Customer signup/profile picker (e.g. `?exclude_global=true` or default for Customer context).

### City-scoped queries
- [ ] Use `is_global_city(user.city_id)` to decide whether to apply city filter.
- [ ] Update any endpoints that scope by city (employer addresses, restaurants by-city, etc.).

### Docs
- [ ] Update `CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md` – add `city_id` to request body.
- [ ] Update `EMPLOYER_ADDRESS_PROTECTION_AND_CITIES_B2C.md` – city required at signup, cannot remove.
- [ ] Update B2B employer/user docs – B2B users get Global city by default.

---

## UUID for Global city

To avoid collision with `market_id` (Global = `00000000-0000-0000-0000-000000000001`), use a distinct UUID for Global city, e.g.:

- `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa` (config: `GLOBAL_CITY_ID`)

Ensure this is used consistently in seed and config.

---

## References

- `app/services/user_signup_service.py` – signup flow
- `app/routes/user.py` – PUT /users/me, _validate_user_update_city_id
- `app/config/supported_cities.py` – city list
- `app/db/seed.sql` – seed data
- `app/services/market_service.py` – GLOBAL_MARKET_ID pattern
