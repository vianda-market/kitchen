# Coding Guidelines - Kitchen Backend

**Last Updated:** 2026-01-30  
**Status:** Merged into [CLAUDE.md](./CLAUDE.md)

> **Note:** The content below has been merged into [CLAUDE.md](./CLAUDE.md) for centralization. CLAUDE.md is the single source of truth for AI-assisted development. This file is kept for human reference and historical context.

## Table of Contents
1. [Code Organization](#code-organization)
2. [Function Naming](#function-naming)
3. [Service Classes vs Standalone Functions](#service-classes-vs-standalone-functions)
4. [Route Patterns](#route-patterns)
5. [Database Operations](#database-operations)
6. [In-Memory Caches and Rate Limits](#in-memory-caches-and-rate-limits)
7. [Testing Requirements](#testing-requirements)

---

## Code Organization

### File Structure

```
app/
├── routes/          # API endpoints (FastAPI routers)
├── services/        # Business logic and service classes
├── dto/             # Data Transfer Objects (database models)
├── schemas/         # Pydantic schemas (API request/response)
├── utils/           # Utility functions
└── config/          # Configuration and settings
```

### Principle: Separation of Concerns

- **Routes**: Handle HTTP, validation, auth - NO business logic
- **Services**: Business logic, complex queries - NO HTTP concerns  
- **DTOs**: Database representation only
- **Schemas**: API contracts (request/response validation)

---

## Function Naming

### ✅ Good Function Names

**Pattern:** `verb_entity_by_context()`

```python
# Clear and descriptive
get_plates_by_restaurant_address()
get_payment_attempts_by_institution_entity()
get_institution_entities_by_institution()
get_active_plates_today_by_user_city()
```

### ❌ Bad Function Names

```python
# Too generic - what entity? what institution?
get_by_institution()  # ❌ Ambiguous
get_all()             # ❌ Too vague

# Misleading - doesn't describe what it actually does
get_all_by_user_address_city()  # ❌ By address or by city?
```

### Naming Rules

1. **Be Specific**: Include entity type in name
2. **Describe Return**: Name should indicate what's returned
3. **Include Context**: Specify the filtering/lookup context
4. **Avoid Ambiguity**: If two functions could have same name, they're named wrong

---

## Service Classes vs Standalone Functions

### Use Service Classes When:

✅ **Operating on a specific database table/entity**
```python
# Good: Entity-specific operations
institution_entity_service.get_by_id()
institution_entity_service.create()
institution_entity_service.soft_delete()
```

✅ **Sharing configuration across operations**
```python
class CRUDService:
    def __init__(self, table_name, dto_class, ...):
        self.table_name = table_name  # Shared config
        self.dto_class = dto_class
```

✅ **Standard CRUD operations**
- All entities should have a `CRUDService` instance
- Use `service.get_all()`, `service.get_by_id()`, etc.

### Use Standalone Functions When:

✅ **Cross-entity lookups**
```python
# Good: Queries across multiple entities
def get_institution_id_by_restaurant(restaurant_id, db):
    """Look up parent institution from restaurant"""
```

✅ **Pure validation utilities**
```python
# Good: Stateless validation
def validate_routing_number(routing_number: str) -> bool:
    return len(routing_number) == 9 and routing_number.isdigit()
```

✅ **Complex business logic spanning multiple entities**
```python
# Good: Multi-step business operation
def mark_plate_selection_complete_with_balance_update(...):
    # Updates selection + restaurant balance + transaction
```

### ❌ Anti-Pattern: Redundant Standalone Functions

```python
# Bad: Redundant with service class
institution_entity_service = CRUDService(...)  # Has get_by_id()

def get_institution_entity_by_id(...):  # ❌ Redundant!
    # Just use the service instead
```

---

## Route Patterns

### When to Use Auto-Generated Routes

**Use `create_crud_routes()` when:**
- ✅ Standard CRUD with no custom logic
- ✅ Only needs `include_archived` parameter
- ✅ No complex query parameters
- ✅ Direct service method calls

```python
# Good use case
crud_router.include_router(create_product_routes())
# Simple CRUD, no custom filtering
```

### When to Use Manual Routes

**Create manual routes when:**
- ✅ Custom filtering parameters (e.g., `institution_entity_id`)
- ✅ Complex business logic in endpoints
- ✅ Non-standard operations
- ✅ Multiple query parameters

```python
# Good: Manual route with custom filtering
@router.get("/")
def get_all_institution_entities(
    institution_id: Optional[UUID] = Query(None),
    include_archived: Optional[bool] = Query(False),
    ...
):
    # Custom filtering logic
```

### Route Registration Order Matters!

⚠️ **FastAPI uses the FIRST matching route**

```python
# Bad: Manual route will NEVER be called
app.include_router(auto_generated_router)  # Registered FIRST
app.include_router(manual_router)          # Never reached!

# Good: Manual route takes precedence
app.include_router(manual_router)          # Registered FIRST ✅
# Don't register auto-generated if manual exists
```

---

## Database Operations

### UUID Handling

**Always convert UUID to string for psycopg2:**

```python
# ✅ Good
query = "SELECT * FROM table WHERE id = %s"
db_read(query, (str(uuid_value),), connection=db)

# ❌ Bad - causes "can't adapt type 'UUID'" error
db_read(query, (uuid_value,), connection=db)
```

### Query Parameter Naming

```python
# ✅ Good: Clear parameter names
@router.get("/")
def get_items(
    entity_id: Optional[UUID] = Query(None, description="Filter by entity"),
    include_archived: bool = Query(False, description="Include archived items")
):
    pass

# ❌ Bad: Ambiguous names
def get_items(id: UUID, archived: bool):  # Which ID? What's archived?
    pass
```

### Scoping and Security

**Always apply institution scoping for multi-tenant data:**

```python
# ✅ Good: Check scope before querying
scope = EntityScopingService.get_scope_for_entity(ENTITY_TYPE, current_user)
_require_entity_access(entity_id, db, scope)  # Security check
items = service.get_by_entity(entity_id, db, scope=scope)

# ❌ Bad: No scope checking
items = service.get_by_entity(entity_id, db)  # Security risk!
```

---

## In-Memory Caches and Rate Limits

**Always avoid memory leak risks when implementing new endpoints that use in-memory cache or rate limiting.**

In-memory caches and rate limit structures must not grow unbounded. Unbounded growth leads to memory exhaustion in long-running processes.

### Eviction Rules

- **Rate limit dicts:** After pruning old timestamps per key, remove keys whose lists are empty. Prune and evict across the whole dict periodically so keys for inactive IPs/users are cleaned up.
- **TTL caches:** Prune expired entries when the cache exceeds a size threshold (e.g. 1000 entries) or periodically. Never rely on "remove on next access" alone for caches that store per-user or per-IP state.
- **Keyed caches:** Prefer a max size (LRU/LFU) or TTL eviction. Document and enforce eviction.
- **Connection-scoped caches:** Clear when the underlying resource (e.g. connection pool) is closed.

### Before Adding a New Cache

Before adding a new in-memory cache or rate limit structure, confirm it has eviction and will not grow unbounded.

---

## Testing Requirements

> **Project-specific:** For this codebase, services are tested exclusively via Postman (see [CLAUDE.md](./CLAUDE.md)). Unit tests are for gateways, utils, security, auth dependencies, DTOs, and schemas only.

### Unit Tests

**Required for:**
- ✅ All service class methods
- ✅ Business logic functions
- ✅ Validation utilities

```python
def test_validate_routing_number():
    assert validate_routing_number("021000021") == True
    assert validate_routing_number("12345") == False
```

### Integration Tests

**Required for:**
- ✅ API endpoints (routes)
- ✅ Database operations
- ✅ Cross-service interactions

### Postman Collections

**Required for:**
- ✅ End-to-end API flows
- ✅ Authentication/authorization
- ✅ Error scenarios

**Update collections when:**
- Adding/removing endpoints
- Changing request/response schemas
- Modifying authentication

---

## Common Patterns

### Pattern 1: Service-Based CRUD

```python
# 1. Define service instance
user_service = CRUDService(
    table_name="user_info",
    dto_class=UserDTO,
    id_column="user_id",
    ...
)

# 2. Use in routes
@router.get("/{user_id}")
def get_user(user_id: UUID, db=Depends(get_db)):
    return user_service.get_by_id(user_id, db)
```

### Pattern 2: Custom Business Logic

```python
# Standalone function for complex operations
def complete_plate_selection_with_balance_update(
    selection_id: UUID,
    restaurant_id: UUID,
    amount: float,
    db: psycopg2.extensions.connection
) -> bool:
    """Complete selection and update balance atomically"""
    try:
        # Step 1: Mark selection complete
        # Step 2: Update restaurant balance
        # Step 3: Create transaction record
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise
```

### Pattern 3: Cross-Entity Lookup

```python
def get_institution_id_by_restaurant(
    restaurant_id: UUID,
    connection=None
) -> Optional[UUID]:
    """Get parent institution from restaurant"""
    query = "SELECT institution_id FROM restaurant_info WHERE restaurant_id = %s"
    result = db_read(query, (str(restaurant_id),), connection=connection, fetch_one=True)
    return result['institution_id'] if result else None
```

---

## Code Review Checklist

### Before Submitting PR

- [ ] Function names are clear and descriptive
- [ ] No duplicate function names (same name, different logic)
- [ ] UUID values converted to string for database queries
- [ ] Institution scoping applied where needed
- [ ] No business logic in route handlers
- [ ] In-memory caches have eviction (TTL, size limit, or key cleanup)
- [ ] Tests written/updated
- [ ] Postman collections updated if API changed
- [ ] No linter errors
- [ ] Documentation updated if needed

### Red Flags

- ❌ Generic function names (`get_by_id`, `get_all` outside service classes)
- ❌ Multiple functions with same name
- ❌ Business logic in route files
- ❌ Database queries without scoping
- ❌ UUID passed directly to psycopg2
- ❌ Hardcoded values (use config/enums)
- ❌ Missing error handling

---

## Migration Strategy

### When Refactoring Existing Code

1. **Add new correctly-named function**
2. **Update callers incrementally**
3. **Mark old function as deprecated with comment**
4. **Remove old function after all callers updated**

```python
# Step 1: Add new function
def get_institution_entities_by_institution(...):
    pass

# Step 2: Deprecate old (if it exists)
def get_by_institution(...):
    """DEPRECATED: Use get_institution_entities_by_institution() instead"""
    return get_institution_entities_by_institution(...)

# Step 3: Update callers over time
# Step 4: Remove deprecated function
```

---

## Questions?

For clarification on these guidelines, see:
- [Code Organization Cleanup](./roadmap/CODE_ORGANIZATION_CLEANUP.md) - Historical context
- [Service Architecture](./services/SERVICE_ARCHITECTURE.md) - Detailed patterns

**Remember:** Code is read more than it's written. Clarity over cleverness!
