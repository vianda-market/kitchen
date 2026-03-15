# Customer Employer Address → Vianda Customers Institution Only (Plan)

**Status**: Plan (not yet implemented)  
**Scope**: Every **customer-reported** Customer Employer address (current employer flows) must be assigned to the **Vianda Customers** institution only. A separate, future path will handle **employer-reported** addresses (Vianda Employer Benefits program).

---

## 1. Rule and separation of flows

- **Current flows** (POST /employers/, POST /employers/{id}/addresses): These create addresses that Comensals or Employees associate with “my employer” (company). Those addresses derive to type **Customer Employer** and must have **`institution_id` = Vianda Customers**. No hardcoded IDs in code — use config only.
- **Future (Vianda Employer Benefits program)**: When we onboard Employers for the benefits program, we will provide a **new avenue** for those employers to store their addresses (company-reported / self-reported). That path will use **Employer institutions** (or similar) and stay separate from customer-reported employer addresses. This plan does not implement that; it only enforces Vianda Customers for the existing employer address flows.

Result: **Customer-reported** employer addresses → Vianda Customers. **Employer-reported** (benefits program) → separate path later.

---

## 2. No hardcoded IDs

- **Institution IDs** (e.g. Vianda Customers, Vianda Enterprises) must **not** be hardcoded in application code. At most they live in a **config file** (e.g. `.env` or a dedicated config module loaded from env) and are **referred to by seed and services**.
- **Seed**: Seed data (e.g. `seed.sql`) must use the same institution UUIDs as config. Document that seed’s institution IDs must match the config values (or generate seed from config if you introduce a seed generator). DB will be torn down and rebuilt — no migration.

---

## 3. Where Customer Employer addresses are created (current flows)

| Flow | Entry point | Where institution_id is set today |
|------|-------------|-----------------------------------|
| **Create employer (with address)** | `POST /api/v1/employers/` | Route builds `address_data`; Customer uses `current_user.institution_id`; Employee/Supplier require `institution_id` and `user_id` in payload. |
| **Add address to existing employer** | `POST /api/v1/employers/{employer_id}/addresses` | Route sets `address_data["employer_id"]`; when `institution_id` is missing uses `employer.institution_id` (EmployerDTO has no `institution_id` — likely bug; see implementation). |

Enforcement: in both flows, set `address_data["institution_id"]` from **config** (Vianda Customers).

---

## 4. Config-based institution ID

- **Single source of truth**: Add to config (e.g. `app/config/settings.py` or a small `app/config/institution_ids.py`) a setting such as **`VIANDA_CUSTOMERS_INSTITUTION_ID`**, loaded from environment (e.g. `VIANDA_CUSTOMERS_INSTITUTION_ID` in `.env`) so it can vary per environment if needed.
- **Seed**: Seed SQL uses the same UUID that matches the config value. Document in seed or in a README that the Vianda Customers (and any other fixed) institution UUIDs in seed must match the values in config.
- **Services**: Any service that needs “Vianda Customers” (e.g. employer routes, user signup) **reads from config** (e.g. `get_settings().VIANDA_CUSTOMERS_INSTITUTION_ID` or a dedicated `get_vianda_customers_institution_id()`). Refactor existing hardcoded use (e.g. `UserSignupService.CUSTOMER_INSTITUTION`) to use this config so there is one place for the ID.

---

## 5. Proposed implementation (no code yet)

### 5.1 Config

- Add to `app/config/settings.py` (or a config module loaded from env):
  - `VIANDA_CUSTOMERS_INSTITUTION_ID: UUID` (from env, with a sensible default for dev that matches current seed, e.g. `22222222-2222-2222-2222-222222222222`).
  - Optionally `VIANDA_ENTERPRISES_INSTITUTION_ID` for consistency if other code needs it; otherwise add when needed.
- Document in config or in `docs/` that **seed must use the same UUIDs** as these settings (no migration; DB tear-down/rebuild).

### 5.2 POST /employers/ (create employer with address)

- **Route** (`app/routes/employer.py`): Before calling `create_employer_with_address`, set `address_data["institution_id"] = <from config: VIANDA_CUSTOMERS_INSTITUTION_ID>`.
- **user_id**: Keep current behavior (Customer: current_user; Employee/Supplier: required in body). Optionally document that for B2B the client should send a user_id that belongs to Vianda Customers.

### 5.3 POST /employers/{employer_id}/addresses (add address to employer)

- **Route** (`app/routes/employer.py`): Always set `address_data["institution_id"] = <from config: VIANDA_CUSTOMERS_INSTITUTION_ID>` (override any client value). Fix the current use of `employer.institution_id` (EmployerDTO has no such field) by replacing it with the config value.

### 5.4 Optional: enforce in entity_service

- In `create_employer_with_address()` (`app/services/entity_service.py`), before creating the address, set `address_data["institution_id"]` from config as a safety net so no caller can pass a different institution.

### 5.5 No validation at read/derive

- No validation in `derive_address_type_from_linkages` or on address read; enforcement only at **write time** for these two employer flows.

### 5.6 No migration

- DB will be torn down and rebuilt; no migration. Seed and config must align.

---

## 6. Summary

| Item | Action |
|------|--------|
| **Config** | Add `VIANDA_CUSTOMERS_INSTITUTION_ID` (and optionally `VIANDA_ENTERPRISES_INSTITUTION_ID`) in config, loaded from env; document that seed must use the same UUIDs. |
| **Refactor** | Replace existing hardcoded Vianda Customers (e.g. in `UserSignupService`) with config so one source of truth. |
| **POST /employers/** | Set `address_data["institution_id"]` from config (Vianda Customers) before `create_employer_with_address`. |
| **POST /employers/{id}/addresses** | Set `address_data["institution_id"]` from config; remove/fix `employer.institution_id` usage. |
| **Optional** | In `create_employer_with_address()`, set `address_data["institution_id"]` from config. |
| **Future** | Employer Benefits program: new path for employer-reported addresses (separate from Vianda Customers). |
| **Migration** | None; DB tear-down and rebuild; seed and config aligned. |

Once this plan is approved, implementation can proceed.
