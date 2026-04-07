# Claude.md - PostgreSQL + FastAPI Development Rules

## Mission
Maximize developer velocity while guaranteeing data integrity in PostgreSQL-backed FastAPI applications.

## Architecture Reference

**Before starting any feature**, read [CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md) for directory structure, route registration, data flow, and key entry points. Discover patterns from existing code rather than relying on examples here.

## Quick Reference

- **Paths**: Use `~/Desktop/local/kitchen`. Never use long iCloud paths.
- **Database changes**: No migrations. DB is torn down and rebuilt. Primary keys use **UUID7** (`uuidv7()` in PostgreSQL 18+). Sync layers in order: `schema.sql` -> `trigger.sql` -> `seed.sql` -> DTOs -> Pydantic schemas.
- **User quoting agent output**: When user writes "[Copied output from you kitchen Agent]", treat it as a self-citation.

---

## Permission Model and Role-Based Access Control

### Two-Tier Hierarchy

1. **Role Type** (`role_type`): Institutional affiliation
   - **Internal**: Vianda Enterprises, global access to all institutions
   - **Supplier**: Restaurant/institution, scoped to their `institution_id`
   - **Customer**: iOS/Android app users only (no backoffice)
   - **Employer**: Benefit-program institution, institution-scoped (like Supplier)

2. **Role Name** (`name` in `role_info`): Specific permissions within a role type
   - Super Admin (Internal) | Admin (Internal/Supplier/Employer) | Comensal (Customer/Employer)

### Key Rules

- **Super Admin = Internal**: `role_type='Internal' AND role_name='Super Admin'` (NOT `role_type='Super Admin'`). Always check BOTH fields.
- **Institution Scoping**: Internal = global (`InstitutionScope.is_global = True`), Supplier/Employer = scoped to `institution_id`, Customer = no backoffice.
- **employer_id**: Only Customer (Comensal) can have employer_id; Internal, Supplier, Employer cannot.

### Permission Dependency Chain

```
get_current_user() (base auth)
    |-> get_employee_user() (Internal role_type)
    |   |-> get_admin_user() (Internal + Admin/Super Admin)
    |   |   '-> get_super_admin_user() (Internal + Super Admin)
    |   '-> Used for: Plans, Credit Currency, Discretionary, Fintech Link (POST/PUT/DELETE)
    |-> get_client_user() (Customer) -> Fintech Link (GET)
    '-> get_client_or_employee_user() (Customer OR Internal) -> Plans (GET)
```

### Protected APIs Summary

| API | Access |
|-----|--------|
| Plans GET | Internal + Customers |
| Plans POST/PUT/DELETE | Internal only |
| Credit Currency | Internal only |
| Discretionary | Internal only (approve/reject: Super Admin only) |
| Fintech Link GET | Customers only |
| Fintech Link POST/PUT/DELETE | Internal only |
| Supplier resources | Institution-scoped |

### Key Files
- `app/auth/dependencies.py`: Permission dependency functions
- `app/security/scoping.py`: `InstitutionScope` for institution-based access control
- `app/auth/routes.py`: JWT token creation (includes `role_type` + `role_name`)

---

## Critical Project-Specific Rules

### UUID Handling for psycopg2

**Always convert UUID to string** when passing to psycopg2 queries:
```python
db_read(query, (str(uuid_value),), connection=db)  # GOOD
db_read(query, (uuid_value,), connection=db)        # BAD - "can't adapt type 'UUID'"
```

### PostgreSQL Enums

**Always check `app/db/schema.sql`** for exact enum format before using values. Enums are case-sensitive.

| Database Enum | Format | Python Enum | Examples |
|---|---|---|---|
| `kitchen_day_enum` | Title Case | `KitchenDay` | `'Monday'`, `'Tuesday'` |
| `address_type_enum` | Title Case | `AddressType` | `'Restaurant'`, `'Customer Home'` |
| `status_enum` | Title Case | `Status` | `'Active'`, `'Inactive'` |
| `role_type_enum` | Title Case | `RoleType` | `'Internal'`, `'Supplier'`, `'Customer'`, `'Employer'` |
| `pickup_type_enum` | lowercase | `PickupType` | `'self'`, `'for_others'` |

Use Python enums from `app/config/enums/` for type safety. When modifying enums, update: `schema.sql` -> Python enum -> validators -> services -> tests.

### Database Schema Change Sync Order

When adding/modifying/removing columns, update ALL layers in order:

```
1. schema.sql (table definition)
2. trigger.sql (history table trigger - missing field = NULL constraint violation)
3. seed.sql (if seeding the table)
4. DTOs (app/dto/models.py) <-- MOST COMMONLY FORGOTTEN
5. Pydantic schemas (if exposed via API)
6. Postman collection (if testing the endpoint)
```

**Why DTOs matter**: DTOs define which fields CRUDService writes to the database. Missing field in DTO = field silently ignored during INSERT/UPDATE, even if present in the API request:
```
Request -> Schema OK -> Route OK -> DTO MISSING FIELD -> Database FAILS
```

**Not all fields need API schemas**: `modified_by`, `modified_date`, `created_date` are set automatically.

### Pydantic Schema Field Naming

**Never use Python type names as field names** (`date`, `time`, `datetime`, `list`, `dict`, `type`, etc.). This causes `RuntimeError: error checking inheritance`. Use descriptive names: `order_date`, `pickup_time`, `entity_type`.

### In-Memory Caches and Rate Limits

All in-memory caches/rate-limit dicts **must have eviction** (TTL, size limit, or key cleanup). No unbounded growth.

---

## API Routing Rules

### Versioned Route Registration

All business routes MUST use `create_versioned_router()` to register under `/api/v1/`:

```python
# Route file: define prefix WITHOUT /api/v1/
router = APIRouter(prefix="/markets", tags=["Markets"])

# application.py: wrap with versioned router
v1_router = create_versioned_router("api", ["Markets"], APIVersion.V1)
v1_router.include_router(markets_admin_router)
app.include_router(v1_router)
```

**Common mistakes**: Direct `app.include_router()` (missing `/api/v1/`), or adding `/api/v1/` to route prefix (double prefix).

**Exceptions** (no versioned wrapper): `/health`, `/admin/archival/*`, `/admin/archival-config/*`

### Trailing Slash Convention

**No trailing slashes** on collection endpoints. App uses `redirect_slashes=False`. Register with `""` for roots, `"/enriched"` for subpaths.

### Route Registration Order

FastAPI uses the FIRST matching route. Register manual routes BEFORE auto-generated ones, or don't register auto-generated if manual exists.

---

## Testing Rules

### Unit Tests (pytest) - Non-Service Code Only

Test: Gateways, Utils, Security, Auth Dependencies, DTOs, Schemas.
Do NOT unit test: Services, Routes, Database layer.

### Service Testing - Postman Collections ONLY

Services are tested **exclusively** via Postman E2E collections. Each collection must be **self-contained**:
- No hardcoded UUIDs from specific environments
- Either create test data via API or query existing data
- Include proper authentication setup
- Can run standalone on a fresh database with seed data

See `docs/postman/collections/` for existing patterns.

---

## Design Patterns

### Function Naming

Pattern: `verb_entity_by_context()` - Be specific, describe return, include filtering context.

### Service vs Utils

- **Services** (`app/services/`): Business logic, domain rules. Require comprehensive testing (via Postman).
- **Utils** (`app/utils/`): Low-level infrastructure, framework helpers. No testing needed.

### Service Classes vs Standalone Functions

- **CRUDService classes**: For standard CRUD on a specific table/entity
- **Standalone functions**: For cross-entity lookups, pure validation, complex multi-entity business logic

### Error Handling

- **HTTPException**: For API operations, CRUD, validation failures, not-found, business rule violations
- **Return None**: For optional operations, background processing, expected not-found lookups, internal helpers

### Enriched Endpoints

Use `/enriched/` endpoints with SQL JOINs when UI needs related entity names. Eliminates N+1 queries.
- Base: `/users`, `/users/{id}`
- Enriched: `/users/enriched`, `/users/enriched/{id}`
- Schemas: `UserResponseSchema` vs `UserEnrichedResponseSchema`

**Field naming in enriched queries**: Only rename fields when there is an actual column name collision between joined tables. Keep original names when no collision exists.

### Root Cause Resolution

Always fix issues at the root cause, not with downstream transformations. Example: register enum types with psycopg2 at connection time rather than SQL-casting in every query. Fallbacks are acceptable only with warning logs and clear documentation.

---

## Documentation References

- [CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md) - Directory structure, route flow, entry points
- [docs/api/API_VERSIONING_GUIDE.md](docs/api/API_VERSIONING_GUIDE.md) - API versioning strategy
- [docs/api/USER_DEPENDENT_ROUTES_PATTERN.md](docs/api/USER_DEPENDENT_ROUTES_PATTERN.md) - Admin vs user routes
- [docs/database/DATABASE_CONNECTION_PATTERNS.md](docs/database/DATABASE_CONNECTION_PATTERNS.md) - `connection=db` vs positional
- [docs/database/DATABASE_TABLE_NAMING_PATTERNS.md](docs/database/DATABASE_TABLE_NAMING_PATTERNS.md) - `_info` suffix conventions
- [docs/database/DATABASE_REBUILD_PERSISTENCE.md](docs/database/DATABASE_REBUILD_PERSISTENCE.md) - DB rebuild process
- [docs/database/ENUM_MAINTENANCE.md](docs/database/ENUM_MAINTENANCE.md) - Enum management guide
- [docs/postman/guidelines/PERMISSIONS_TESTING_GUIDE.md](docs/postman/guidelines/PERMISSIONS_TESTING_GUIDE.md) - Permission testing
