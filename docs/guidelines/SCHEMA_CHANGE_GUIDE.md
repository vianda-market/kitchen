# Database Schema Change Guide

When adding, modifying, or removing columns you MUST update all layers in order. Missing any one causes runtime failures.

## Layer Sync Order

```
1. app/db/schema.sql          — table definition + history table
2. app/db/trigger.sql         — history trigger INSERT (if table has history)
3. app/db/seed.sql            — seed data (if seeding the table)
4. app/dto/models.py          — DTO fields (MOST COMMONLY FORGOTTEN)
5. app/schemas/consolidated_schemas.py — Pydantic request/response schemas
6. Postman collection         — update test requests/assertions
```

## Why Each Layer Matters

**schema.sql** — defines structure, constraints (NOT NULL, UNIQUE, FK)

**trigger.sql** — history tables mirror main table; trigger copies rows on change
- Missing field in trigger = `null value in column 'x' of relation 'y_history'` error

```sql
-- ❌ BAD: Missing market_id
INSERT INTO audit.plan_history (event_id, plan_id, name, ...)

-- ✅ GOOD: Includes market_id
INSERT INTO audit.plan_history (event_id, plan_id, market_id, name, ...)
VALUES (new_event_id, NEW.plan_id, NEW.market_id, ...)
```

**DTOs (`app/dto/models.py`)** — define which fields CRUDService writes to DB
- Missing field in DTO = field stripped before INSERT even if it's in the API request

```
Request → Pydantic Schema ✅ → Route ✅ → DTO ❌ → Database ❌
                                          ↑ Missing field here breaks everything
```

```python
# ❌ BAD: Missing market_id — will be silently dropped on insert
class PlanDTO(BaseModel):
    plan_id: UUID
    name: str

# ✅ GOOD
class PlanDTO(BaseModel):
    plan_id: UUID
    market_id: UUID   # ← must match schema.sql
    name: str
```

**Pydantic schemas** — only needed if the field is exposed via API
- Fields with `DEFAULT` or set by triggers (`modified_by`, `created_date`, etc.) usually don't belong in API schemas

## Common Failure Scenarios

| Error | Root cause |
|---|---|
| `null value in column 'x' violates not-null constraint` | Field in schema but not in DTO → stripped before INSERT |
| `null value in column 'x' of relation 'y_history'` | Main table updated but trigger not updated |
| `Validation error: field 'x' is required` | DB + DTO have field, but Pydantic schema doesn't accept it |

## Fields That Don't Belong in API Schemas

These are set automatically — include in DTO, omit from request/response schemas:
- `modified_by` — set from `current_user`
- `modified_date` — set by database
- `created_date` — set by database
- Internal audit flags

## Verification Checklist

After making schema changes, always verify:

```bash
# 1. Column exists in main table
psql kitchen -c "\d plan_info"

# 2. Trigger includes new field (if table has history)
psql kitchen -c "\sf plan_history_trigger_func"

# 3. Application imports cleanly
python3 -c "from application import app; print('OK')"

# 4. Rebuild and spot-check
bash app/db/build_kitchen_db.sh
psql kitchen -c "SELECT * FROM plan_history LIMIT 1"
```

## Worked Example: Adding `market_id` to `plan_info`

**1. schema.sql**
```sql
ALTER TABLE customer.plan_info
    ADD COLUMN market_id UUID NOT NULL REFERENCES core.market_info(market_id);

-- Also add to audit.plan_history:
ALTER TABLE audit.plan_history
    ADD COLUMN market_id UUID NULL;
```

**2. trigger.sql** — update `plan_history_trigger_func`:
```sql
INSERT INTO audit.plan_history (event_id, plan_id, market_id, ...)
VALUES (new_event_id, NEW.plan_id, NEW.market_id, ...)
```

**3. seed.sql**
```sql
INSERT INTO customer.plan_info (plan_id, market_id, name, ...)
VALUES (..., '00000000-0000-0000-0000-000000000002', ...)
```

**4. app/dto/models.py**
```python
class PlanDTO(BaseModel):
    plan_id: UUID
    market_id: UUID   # ← Add
    name: str
    ...
```

**5. app/schemas/consolidated_schemas.py**
```python
class PlanCreateSchema(BaseModel):
    market_id: UUID   # ← User provides
    name: str

class PlanResponseSchema(BaseModel):
    plan_id: UUID
    market_id: UUID   # ← Return to user
    name: str
```

DTOs are the bridge between your API and the database. Don't skip them.
