# Pydantic v2 and FastAPI migration

**Last updated**: 2026-02-25  
**Status**: Plan  
**Scope**: Kitchen backend — migrate from Pydantic v1 to v2 and upgrade FastAPI; update validators, config, serialization, and settings.

---

## Current state

- **FastAPI**: 0.109.0 (requirements.txt)
- **Pydantic**: v1 (pydantic[email]>=1.10)
- **Settings**: `BaseSettings` from `pydantic` (v1); in v2 this lives in the `pydantic-settings` package.

Pydantic v2 and FastAPI compatibility: FastAPI 0.100+ supports Pydantic v2. FastAPI 0.109 works with Pydantic v2; upgrading to FastAPI 0.115+ is recommended for the latest fixes and OpenAPI behavior.

---

## 1. Dependency changes

**File:** `requirements.txt`

| Current | Target |
|--------|--------|
| `fastapi==0.109.0` | `fastapi>=0.115.0,<0.116` (or `>=0.109.0` minimum for Pydantic v2) |
| `pydantic[email]>=1.10` | `pydantic[email]>=2.5,<3` |
| — | `pydantic-settings>=2.0` (for `BaseSettings`) |

Optional: pin exact versions after testing (e.g. `fastapi==0.115.6`, `pydantic==2.10.3`).

---

## 2. Settings (BaseSettings)

**File:** `app/config/settings.py`

- Replace `from pydantic import BaseSettings` with `from pydantic_settings import BaseSettings`.
- Replace inner `class Config: env_file = ".env"` with:
  - `model_config = {"env_file": ".env"}` or `model_config = SettingsConfigDict(env_file=".env")` (from `pydantic_settings import SettingsConfigDict`).

No other logic changes needed; field definitions stay the same.

---

## 3. Model config (class Config → model_config)

In Pydantic v2, `class Config:` is replaced by `model_config = ConfigDict(...)` (from `pydantic import ConfigDict`).

| v1 Config | v2 ConfigDict |
|-----------|----------------|
| `orm_mode = True` | `from_attributes = True` |
| `extra = "forbid"` | `extra = "forbid"` |
| `schema_extra = {...}` | `json_schema_extra = {...}` |

**Files with `class Config:` (many):**

- `app/dto/models.py` – many DTOs with `orm_mode = True`
- `app/schemas/consolidated_schemas.py` – many schemas with `orm_mode` and one `json_schema_extra`
- `app/schemas/geolocation.py`, `subscription.py`, `payment_method.py`, `restaurant_holidays.py`, `institution_bank_account.py`, `institution_entity.py`, `billing/institution_bill.py`, `payment_methods/*` – same pattern
- `app/config/market_config.py` – `Config` with `json_encoders`
- `app/schemas/credit_validation.py` – `schema_extra` examples
- Test schemas in `app/tests/services/test_crud_service.py`, `test_enriched_service.py`

Add at top of each file that uses `ConfigDict`: `from pydantic import ConfigDict` (and keep `BaseModel`, etc.). Then replace each `class Config:` block with a single line: `model_config = ConfigDict(from_attributes=True)` (or the appropriate options).

**Special case – `app/config/market_config.py`:**  
v1 uses `Config.json_encoders = { time: lambda v: v.strftime("%H:%M") }`. In v2, use a **field serializer** instead of `json_encoders`:

- `from pydantic import field_serializer`
- Add `@field_serializer('field_name')` (or the field holding `time`) so that `time` values are serialized as `"%H:%M"` (and ensure the field type is correct for serialization).

---

## 4. Validators: v1 → v2

### 4.1 Import and decorator mapping

| v1 | v2 |
|----|-----|
| `from pydantic import validator, root_validator` | `from pydantic import field_validator, model_validator` |
| `@validator("x", pre=True)` | `@field_validator("x", mode="before")` |
| `@validator("x")` (single field, no `values`) | `@field_validator("x")` |
| `@validator("x")` with `values` (depends on other fields) | `@model_validator(mode="after")` and use `self` |
| `@root_validator` | `@model_validator(mode="after")`; signature becomes `def fn(self): return self` (or mutate and return self) |

### 4.2 Signature changes

- **field_validator**: `(cls, v) -> v` (or transformed value). No `values`; for multi-field logic use `model_validator(mode="after")`.
- **model_validator(mode="after")**: receives `self` (the model instance). Use `self.field_name`; return `self`. For "before" (raw dict), use `model_validator(mode="before")` and return the dict.

### 4.3 Files to update

- **`app/routes/user_public.py`**  
  Already uses `model_validator(mode="after")`; only the import will work after upgrading Pydantic. No signature change if it already uses `self` and returns `self`.

- **`app/schemas/consolidated_schemas.py`**  
  Many `@validator` and `@root_validator` usages. Convert each to either `@field_validator` (single-field, no other fields) or `@model_validator(mode="after")` (multi-field or root logic). Replace any `values.get(...)` with `self....` in after-validators.

- **`app/schemas/payment_method.py`**  
  One `@root_validator` → `@model_validator(mode="after")`; use `self` and return `self`.

- **`app/schemas/subscription.py`**  
  Same: `@root_validator` → `@model_validator(mode="after")`.

- **`app/schemas/institution_bank_account.py`**  
  Multiple `@validator(...)` → `@field_validator(...)` with `(cls, v)`.

- **`app/schemas/restaurant_holidays.py`**  
  Same: `@validator` → `@field_validator`.

- **`app/schemas/payment_methods/client_payment_attempt.py`**  
  `@validator("amount", pre=True)` → `@field_validator("amount", mode="before")`.

- **`app/schemas/payment_methods/institution_payment_attempt.py`**  
  `@validator(...)` → `@field_validator(...)`.

- **`app/schemas/billing/institution_bill.py`**  
  `@validator(...)` → `@field_validator(...)`.

---

## 5. Serialization: .dict() → .model_dump()

Replace every `.dict(...)` call with `.model_dump(...)`.

- `.dict()` → `.model_dump()`
- `.dict(exclude_unset=True)` → `.model_dump(exclude_unset=True)`
- `.dict(exclude_none=True)` → `.model_dump(exclude_none=True)`

**Files (representative):**

- `app/routes/user_public.py` (e.g. `user.dict()`)
- `app/routes/user.py` (e.g. `user.dict()`, `user_update.dict(exclude_unset=True)`)
- `app/routes/address.py`, `restaurant.py`, `employer.py`, `institution_bank_account.py`, `admin/discretionary.py`
- `app/routes/payment_methods/*` (payload/update `.dict()`)
- `app/routes/billing/client_bill.py`
- `app/services/entity_service.py` (`u.dict()`)
- `app/services/route_factory.py` (many `create_data.dict()`, `update_data.dict(exclude_unset=True)`)
- `app/services/plate_selection_service.py`, `archival.py`
- `app/tests/services/test_employer_address_service.py`

Search the repo for `.dict(` and replace with `.model_dump(` everywhere.

---

## 6. Dynamic models (create_model)

**File:** `app/dto/dynamic_models.py`

- v1: `schema_class.__fields__`, `create_model(..., __config__=...)`.
- v2: use `model_fields` instead of `__fields__`; field structure differs (e.g. `FieldInfo` with `.annotation`, `.default`, etc.). `create_model` in v2 does not use `__config__`; use `model_config` in the created model or pass config via a base class.

Options:

- **A)** Refactor to avoid dynamic creation (e.g. explicitly define the DTOs that are actually used).
- **B)** Adapt to v2: build fields from `Model.model_fields`, use `create_model(..., __config__=ConfigDict(from_attributes=True))` or equivalent v2 API (see Pydantic v2 docs for `create_model` and `model_config`).

If this module is not used in production paths, consider skipping it in the first pass and fixing or removing it after the rest of the migration.

---

## 7. Tests

- Run the full test suite after dependency and code changes; fix any assertions that rely on v1 behavior (e.g. error messages, validation order).
- Tests that instantiate or compare Pydantic models: ensure they use `.model_dump()` where they currently use `.dict()`.
- `app/tests/services/test_user_signup_service.py` and other tests that touch schemas: no structural change needed if validators and config are correctly migrated.

---

## 8. Execution order (recommended)

```mermaid
flowchart LR
  A[Deps + pydantic-settings] --> B[Settings + ConfigDict]
  B --> C[All model_config]
  C --> D[Validators]
  D --> E[.dict to .model_dump]
  E --> F[Dynamic models]
  F --> G[Tests + manual smoke]
```

1. Update `requirements.txt` and install (including `pydantic-settings`).
2. Migrate `app/config/settings.py`.
3. Add `ConfigDict` and replace all `class Config` with `model_config` (and fix `market_config` serialization).
4. Migrate all validators (consolidated_schemas first, then other schemas and user_public as needed).
5. Global find/replace `.dict(` → `.model_dump(` and fix any edge cases.
6. Update or isolate `app/dto/dynamic_models.py`.
7. Run tests and fix failures; do a quick Postman smoke test (e.g. login, one CRUD flow).

---

## 9. Risk and rollback

- **Risk**: Large number of validator and config touchpoints; one missed `.dict()` or wrong validator signature can cause runtime or test failures.
- **Mitigation**: Do the migration in a branch; run tests after each logical group (config, validators, dump); keep a list of modified files for easy review.
- **Rollback**: Revert the branch; or re-pin Pydantic v1 and FastAPI 0.109 and revert code changes if needed.

---

## 10. Summary of file groups

| Group | Action |
|-------|--------|
| requirements.txt | Bump FastAPI, Pydantic v2, add pydantic-settings |
| app/config/settings.py | BaseSettings from pydantic_settings, model_config |
| app/config/market_config.py | ConfigDict + field_serializer for time |
| app/dto/models.py | Config → model_config (from_attributes) |
| app/dto/dynamic_models.py | Adapt to v2 model_fields/create_model or refactor |
| app/schemas/*.py (all) | Config + validators → ConfigDict + field/model_validator |
| app/routes/*.py | .dict() → .model_dump() |
| app/services/*.py | .dict() → .model_dump() |
| app/tests (any schema/dict usage) | .dict() → .model_dump(); fix assertions if needed |

No database or API contract changes are required; this is a library and in-process serialization/validation migration.
