# Code Conventions

Detailed patterns and examples for this codebase. See CLAUDE.md for the one-line summary of each rule.

---

## Function Design

1. **Functions over classes** — use classes only for essential state (e.g., `CRUDService`)
2. **Explicit dependencies** — pass `db: psycopg2.connection` and `logger: LoggerAdapter` as parameters; never hide them
3. **Pure functions** — `input → processing → output`; no side effects without explicit parameters
4. **< 50 lines** — single responsibility; split if longer
5. **Type annotations** — required on all function signatures
6. **Error handling as separate functions** — extract `try/except` blocks into dedicated handler functions

## Function Naming

**Pattern:** `verb_entity_by_context()`

```python
# ✅ Good
get_plates_by_restaurant_address()
get_payment_attempts_by_institution_entity()
get_institution_entities_by_institution()

# ❌ Too generic
get_by_institution()   # what entity?
get_all()              # vague

# ❌ Misleading
get_all_by_user_address_city()  # by address or by city?
```

Rules: be specific, describe the return type, include the filtering context, avoid ambiguity.

## Service vs Utils

| Layer | Contains | Tested with |
|---|---|---|
| `app/services/` | Business logic, domain rules, orchestration | Postman only |
| `app/utils/` | Pure helper functions, framework wrappers | pytest |

```python
# ✅ Service — has business rules, needs Postman tests
def get_effective_current_day(timezone_str: str) -> str:
    """Before 1 PM = previous day's service window"""
    if now.time() < time(13, 0):
        return (now - timedelta(days=1)).strftime('%A')
    return now.strftime('%A')

# ✅ Utils — infrastructure wrapper, no tests needed
def log_info(message: str):
    logger.info(message)
```

## Service Classes vs Standalone Functions

**Use `CRUDService` instance when:** operating on a single table with standard CRUD.

**Use standalone functions when:**
- Cross-entity lookups: `get_institution_id_by_restaurant(restaurant_id, db)`
- Pure validation: `validate_routing_number(routing_number: str) -> bool`
- Complex multi-entity business logic

```python
# ❌ Redundant — service already has get_by_id()
institution_entity_service = CRUDService(...)
def get_institution_entity_by_id(...):  # just use the service
```

## Error Handling

**Raise `HTTPException` when:** route handlers, CRUD operations, validation failures, not-found for API resources.

**Return `None` when:** internal lookups where "not found" is an expected/normal condition, background tasks.

```python
# ✅ API layer — raise
def create_user(user_data, db) -> UserDTO:
    if not user_data.get("email"):
        raise HTTPException(status_code=400, detail="Email is required")

# ✅ Internal lookup — return None
def find_user_by_email(email, db) -> Optional[UserDTO]:
    try:
        return user_service.get_by_field("email", email, db)
    except Exception:
        return None
```

**Extract error handling into separate functions:**
```python
def create_employer(data, address_data, user_id, db):
    return _handle_employer_creation(data, address_data, user_id, db)

def _handle_employer_creation(data, address_data, user_id, db):
    try:
        db.begin()
        address = Address.create(address_data, connection=db)
        data["address_id"] = address.address_id
        employer = Employer.create(data, connection=db)
        db.commit()
        return employer
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

## Anti-Overengineering

- No classes unless essential state (use `CRUDService` pattern, not custom class hierarchies)
- No complex inheritance — prefer composition
- No interfaces with a single implementation
- Simple raw SQL over ORM complexity when SQL is clearer

## Refactoring Triggers

Refactor when you see:
1. Function > 50 lines
2. More than 3 levels of nesting — use early returns/guard clauses
3. More than 5 parameters — consider a data structure
4. Mixed abstraction levels in one function
5. Hidden database connections
6. `try` inside a function — extract to a handler function
7. DTO and CRUD logic in the same class — separate into DTO + service

**Rename strategy (don't break callers):**
```python
# 1. Add correctly-named new function
def get_institution_entities_by_institution(...): ...

# 2. Deprecate old one
def get_by_institution(...):
    """DEPRECATED: Use get_institution_entities_by_institution()"""
    return get_institution_entities_by_institution(...)

# 3. Update callers incrementally, then remove deprecated version
```

## Schema Field Naming

Never use Python built-in type names as Pydantic field names — causes `RuntimeError: error checking inheritance`:

```python
# ❌ Breaks
class BadSchema(BaseModel):
    date: date       # conflicts with datetime.date
    type: str        # conflicts with built-in type

# ✅ Use descriptive names
class GoodSchema(BaseModel):
    order_date: date
    entity_type: str
```

## Centralization

- All DTOs → `app/dto/models.py`
- All Pydantic schemas → `app/schemas/consolidated_schemas.py`
- CRUD service instances → defined at module level in service files, reused everywhere
- Generic routes → `app/routes/crud_routes.py` via `create_crud_routes()`

## In-Memory Caches

Every cache must have TTL or max-size eviction. Pattern used in `app/routes/leads.py`:

```python
_cache: Optional[list] = None
_cache_expiry: float = 0
CACHE_TTL = 600  # 10 minutes

def get_cached():
    global _cache, _cache_expiry
    now = time.time()
    if _cache is not None and now < _cache_expiry:
        return _cache
    _cache = fetch_from_db()
    _cache_expiry = now + CACHE_TTL
    return _cache
```

## Route Registration

```python
# ✅ Correct — versioned wrapper in application.py
v1_markets_router = create_versioned_router("api", ["Markets"], APIVersion.V1)
v1_markets_router.include_router(markets_router)
app.include_router(v1_markets_router)
# Result: /api/v1/markets

# ❌ Wrong — creates /markets instead of /api/v1/markets
app.include_router(markets_router)
```

**Manual routes before auto-generated routes** — FastAPI matches the first registered route. Register specific routes before generic ones.

## Auto-Generated vs Manual Routes

Use `create_crud_routes()` for standard CRUD with no custom logic. Write manual routes when you need custom filtering params, complex business logic, or non-standard operations.

## Admin Route Handler Annotations

Every admin route handler and every inner closure passed to `handle_business_operation` must carry explicit return type annotations. Use the `response_model` schema type when the handler explicitly constructs it; use `Any` when the handler returns a raw service result (DTO, raw dict) that FastAPI serializes via `response_model`. Annotate `current_user` as `dict[str, Any]`, not bare `dict`. Unannotated closures absorb `[no-untyped-def]` mypy baseline entries that accumulate silently — see issue #305.
