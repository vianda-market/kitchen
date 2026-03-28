# CLAUDE.md

## Project
Vianda marketplace backend — PostgreSQL + FastAPI. Multi-market B2B/B2C food subscription platform.
Read `CLAUDE_ARCHITECTURE.md` before planning new features or modifying data flow.

## Never Do These
- Never run or write migrations — tear down and rebuild: `bash app/db/build_kitchen_db.sh`
- Never pass UUID directly to psycopg2 — always `str(uuid_value)`
- Never register routes directly to `app` — always use `create_versioned_router()`
- Never write Python unit tests for services — use Postman collections (see Testing below)
- Never store secrets in code

## Essential Commands
- **Rebuild DB:** `bash app/db/build_kitchen_db.sh`
- **Import check:** `python3 -c "from application import app; print('OK')"`
- **Run tests:** `pytest app/tests/`
- **Paths:** Always use `~/Desktop/local/kitchen` — never long iCloud paths
- **User quoting agent output:** When user writes "[Copied output from you kitchen Agent]", treat as self-citation

## DB Schema Change — Sync All Layers (in order)
When adding/modifying any column: `schema.sql` → `trigger.sql` → `seed.sql` → `app/dto/models.py` → `app/schemas/consolidated_schemas.py`

- History tables (`audit.*`) must mirror their main table — triggers must INSERT the new column
- DTOs define which fields CRUDService writes to DB — **missing field in DTO = silently dropped on insert**
- `modified_by`, `created_date`, `modified_date` are set automatically — omit from API schemas
- **Adding a column?** Search all service functions that query that table and add the field to every SELECT. `get_all()` functions especially — by name they must return all fields.

Full guide with failure scenarios and examples: `docs/guidelines/SCHEMA_CHANGE_GUIDE.md`

## Permissions (Two-Tier)
- **role_type**: Internal | Supplier | Customer | Employer — controls institution scoping
- **role_name**: Super Admin | Admin | Comensal — controls operation-level access within the type
- Internal = global access. Supplier/Employer = institution-scoped via `InstitutionScope` (`app/security/scoping.py`)
- Auth deps in `app/auth/dependencies.py`: `get_current_user`, `get_employee_user`, `get_super_admin_user`

Full reference: `docs/api/internal/ROLE_BASED_ACCESS_CONTROL.md`

## Code Conventions
- **Functions:** `verb_entity_by_context()`, <50 lines, pure, explicit `db`/`logger` params
- **DTOs:** Pure data structures only — `app/dto/models.py`. No logic, no methods.
- **Enums:** Check `schema.sql` for exact case before use. Most are Title Case; `pickup_type_enum` is lowercase.
- **Route versioning:** `create_versioned_router("api", [...], APIVersion.V1)` in `application.py`
- **No trailing slash** on collection endpoints — prefix is `/entity-name`, not `/entity-name/`
- **In-memory caches** must have TTL/size eviction — never unbounded growth
- **Enriched endpoints** use SQL JOINs; only rename fields when there is an actual column collision.
- **Error handling:** Route/CRUD operations → raise `HTTPException`. Internal lookups where "not found" is normal → return `None`.
- **Schema field names:** Never use Python built-in type names as field names (`date`, `time`, `type`, `list`) — use `order_date`, `pickup_time`, etc.

Details + examples: `docs/guidelines/CODE_CONVENTIONS.md`
Enriched endpoint pattern + field naming: `docs/guidelines/ENRICHED_ENDPOINTS.md`

## Testing
| What | How |
|---|---|
| `app/utils/`, `app/gateways/`, `app/auth/`, `app/security/` | pytest unit tests |
| `app/services/`, `app/routes/` | Postman collections only (full HTTP stack) |

- Postman collections must be self-contained — no hardcoded UUIDs, create or query test data inline
- Collections live in `docs/postman/collections/`
- One concept per test, Arrange-Act-Assert, mock external deps

## Key Entry Points
- **Route registration:** `application.py`
- **All Pydantic schemas:** `app/schemas/consolidated_schemas.py`
- **All DTOs:** `app/dto/models.py`
- **Leads (public/no-auth):** `app/routes/leads.py`
- **DB files:** `app/db/schema.sql`, `trigger.sql`, `seed.sql`, `index.sql`

## Reference Map — Read When
| Document | Read when |
|---|---|
| `CLAUDE_ARCHITECTURE.md` | Planning new features, modifying data flow, locating modules |
| `docs/guidelines/SCHEMA_CHANGE_GUIDE.md` | Adding or modifying any DB column |
| `docs/guidelines/ENRICHED_ENDPOINTS.md` | Building enriched endpoints or joining tables for UI display |
| `docs/guidelines/CODE_CONVENTIONS.md` | Unsure about function design, error handling, or service patterns |
| `docs/guidelines/ROOT_CAUSE_PRINCIPLE.md` | Fixing a type mismatch or considering a downstream workaround |
| `docs/api/internal/ROLE_BASED_ACCESS_CONTROL.md` | Adding auth to a new endpoint or checking permission logic |
| `docs/guidelines/database/ENUM_MAINTENANCE.md` | Adding or modifying a PostgreSQL enum |
| `docs/guidelines/database/DATABASE_REBUILD_PERSISTENCE.md` | Rebuilding the database or managing seed data |
| `docs/roadmap/vianda_home_apis.md` | Implementing vianda-home marketing site APIs |

## Cross-Repo Agent Index Files
- **This repo:** `docs/api/AGENT_INDEX.md`, `docs/roadmap/AGENT_INDEX.md`
- **vianda-app (B2C):** `/Users/cdeachaval/Desktop/local/vianda-app/docs/frontend/AGENT_INDEX.md`
- **vianda-platform (B2B):** `/Users/cdeachaval/Desktop/local/vianda-platform/docs/frontend/AGENT_INDEX.md`
- **vianda-home (marketing):** `/Users/cdeachaval/Desktop/local/vianda-home/docs/frontend/AGENT_INDEX.md`
- **infra-kitchen-gcp:** `/Users/cdeachaval/Desktop/local/infra-kitchen-gcp/docs/infrastructure/AGENT_INDEX.md`
