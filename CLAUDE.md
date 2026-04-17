# CLAUDE.md

## Project
Vianda marketplace backend — PostgreSQL + FastAPI. Multi-market B2B/B2C food subscription platform.
Read `CLAUDE_ARCHITECTURE.md` before planning new features or modifying data flow.
Update `CLAUDE_ARCHITECTURE.md` after adding new modules, tables, services, routes, or subsystems.

## Never Do These
- Never pass UUID directly to psycopg2 — always `str(uuid_value)`
- Never register routes directly to `app` — always use `create_versioned_router()`
- Never write Python unit tests for services — use Postman collections (see Testing below)
- Never store secrets in code
- Never pass `page`/`page_size` pagination params in cron jobs or internal service calls — pagination is for HTTP routes only
- Never edit an already-applied migration file — write a new one instead

## Essential Commands
- **Apply migrations:** `bash app/db/migrate.sh` (incremental — preserves data)
- **Rebuild DB (fresh):** `bash app/db/build_kitchen_db.sh` (full tear-down — use for new environments or clean reset only)
- **Import check:** `python3 -c "from application import app; print('OK')"`
- **Run tests:** `pytest app/tests/`
- **Test collection check (local):** `pytest --collect-only -q --ignore=app/tests/database`
- **Diff-coverage gate (local):** `pytest --cov=app --cov-report=xml --cov-fail-under=0 && diff-cover coverage.xml --compare-branch=origin/main --fail-under=80`
- **Secret scan (local):** `gitleaks detect --source . --verbose` (allowlist: `.gitleaksignore`)
- **Maintainability gate (local):** `bash scripts/check_maintainability.sh` (fails if MI drops >5% on changed files vs origin/main)
- **Dead code gate (local):** `bash scripts/check_vulture.sh` (baseline: `.vulture-baseline.txt`; update: `--update`)
- **Paths:** Always use `~/learn/kitchen`
- **User quoting agent output:** When user writes "[Copied output from you kitchen Agent]", treat as self-citation

## DB Schema Change — Sync All Layers (in order)
**Schema changes use migration files.** Write a migration in `app/db/migrations/NNNN_description.sql`, then update `schema.sql` to match.

Migration file → `schema.sql` → `trigger.sql` → `seed/reference_data.sql` (if needed) → `app/dto/models.py` → `app/schemas/consolidated_schemas.py`

Apply with `bash app/db/migrate.sh`. Full rebuild (`build_kitchen_db.sh`) is for fresh environments only — never use it to apply incremental changes on a database with test data you want to keep.

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
- **Enums:** All enums follow a consistent pattern:
  - **Member name** (Title): UPPER_SNAKE_CASE — e.g. `SUPER_ADMIN`, `HANDED_OUT`
  - **Value**: lowercase slug — e.g. `"super_admin"`, `"handed_out"` — stored in DB and sent over API
  - **Display label**: Provided by `app/i18n/enum_labels.py` per locale — never use `.value` for display
  - When using `strftime("%A")` for day names, always `.lower()` the result to match enum values
- **Route versioning:** `create_versioned_router("api", [...], APIVersion.V1)` in `application.py`
- **No trailing slash** on collection endpoints — prefix is `/entity-name`, not `/entity-name/`
- **In-memory caches** must have TTL/size eviction — never unbounded growth
- **Enriched endpoints** use SQL JOINs; only rename fields when there is an actual column collision.
- **Error handling:** Route/CRUD operations → raise `HTTPException`. Internal lookups where "not found" is normal → return `None`.
- **Schema field names:** Never use Python built-in type names as field names (`date`, `time`, `type`, `list`) — use `order_date`, `pickup_time`, etc.

Details + examples: `docs/guidelines/CODE_CONVENTIONS.md`
Enriched endpoint pattern + field naming: `docs/guidelines/ENRICHED_ENDPOINTS.md`

## Pagination (Opt-In)
Server-side pagination is **opt-in per route** — not all endpoints need it.

- **CRUD routes:** Set `paginatable=True` on `RouteConfig` in `route_factory.py`
- **Enriched routes:** Add `pagination: Optional[PaginationParams] = Depends(get_pagination_params)` and call `set_pagination_headers(response, result)`
- **Primitives:** `app/utils/pagination.py` — `PaginationParams`, `PaginatedList`, `get_pagination_params`, `set_pagination_headers`
- **Protocol:** Frontend sends `page` + `page_size` query params → backend returns `X-Total-Count` header. No params = all records (backward compatible).
- **Cron jobs / internal service calls:** NEVER pass `page`/`page_size`. These always need all records. Pagination is exclusively for HTTP route consumption.
- **Reference data** (countries, currencies, cuisines, enums): NOT paginated — small datasets, no opt-in needed.

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
- **DB files:** `app/db/schema.sql`, `trigger.sql`, `index.sql`
- **Migrations:** `app/db/migrations/` (incremental schema changes)
- **Seed data:** `app/db/seed/reference_data.sql` (all envs), `app/db/seed/dev_fixtures.sql` (dev only)
- **DB scripts:** `app/db/migrate.sh` (incremental), `app/db/build_kitchen_db.sh` (full rebuild)

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
| `docs/plans/MULTINATIONAL_INSTITUTIONS.md` | Understanding institution-market model, three-tier cascade, employer entity normalization |
| `docs/plans/vianda_home_apis.md` | Implementing vianda-home marketing site APIs |

## Cross-Repo Documentation Protocol

This repo (kitchen) is the **backend source of truth**. It produces API docs and roadmaps that other repo agents consume. Other repos never write docs here — they read our docs and produce their own implementation + documentation.

**When completing a feature that affects other repos**, always:
1. Produce or update the relevant `docs/api/` doc describing the new endpoints, contracts, and behaviors
2. In your summary of changes, list the docs produced and which agents need them:
   - **vianda-platform agent**: for B2B UI changes (Employer Program pages, auth changes, error handling)
   - **vianda-app agent**: for B2C UI changes (benefit plans display, subscription flow changes)
   - **infra-kitchen-gcp agent**: for cron jobs, env vars, Stripe config, GCS buckets
3. Point the user to the specific files to share with each agent

**Doc locations produced by this repo:**
- `docs/api/` — **Permanent** API integration docs (endpoints, contracts, auth). Indexed in `docs/api/AGENT_INDEX.md`. This is the source of truth for how the system works. Other repo agents read these to understand established functionality.
- `docs/plans/` — **Ephemeral** feature plans and design decisions. Plans are consumed during implementation, then archived. Never reference old plans to understand how things work — that information belongs in `docs/api/` or `CLAUDE_ARCHITECTURE.md`. When completing a plan, summarize any long-term relevant info (endpoint contracts, behaviors, constraints) into the appropriate `docs/api/` doc before archiving the plan.
- `CLAUDE_ARCHITECTURE.md` — System overview for cross-repo context

**Agent index files in other repos (read-only, for context):**
- **vianda-platform (B2B):** `/Users/cdeachaval/learn/vianda-platform/docs/frontend/AGENT_INDEX.md`
- **vianda-app (B2C):** `/Users/cdeachaval/learn/vianda-app/docs/frontend/AGENT_INDEX.md`
- **vianda-home (marketing):** `/Users/cdeachaval/learn/vianda-home/docs/frontend/AGENT_INDEX.md`
- **infra-kitchen-gcp:** `/Users/cdeachaval/learn/infra-kitchen-gcp/docs/infrastructure/AGENT_INDEX.md`
