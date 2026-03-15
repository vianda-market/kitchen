# Cursor rules for this project

1. **Primary reference**: For coding standards, patterns, architecture, and conventions, follow [docs/CLAUDE.md](docs/CLAUDE.md) and [docs/CLAUDE_ARCHITECTURE.md](docs/CLAUDE_ARCHITECTURE.md). Use them to locate modules and apply project conventions without exploratory searches.

2. **Paths**: Use the **short** workspace path only: **`~/Desktop/local/kitchen`** (or `$HOME/Desktop/local/kitchen`). Never use the long iCloud path (`Library/Mobile Documents/com~apple~CloudDocs/Desktop/local/...`) when editing files, running commands, or requesting permissions—always reference and operate from `~/Desktop/local/kitchen`.

3. **Database changes**: Do not write or run database migrations. Assume the database will be **torn down and rebuilt** for schema changes. Do not add migration scripts unless explicitly requested. Primary keys use **UUID7** for new rows (see [docs/database/UUID7_MIGRATION_PLAN.md](docs/database/UUID7_MIGRATION_PLAN.md)); PostgreSQL 18+ has built-in `uuidv7()`. For PG &lt; 18, run `docs/archived/db_migrations/uuid7_function.sql` before schema. When changing schema, sync **all** layers in order: `schema.sql` → `trigger.sql` → `seed.sql` → DTOs (`app/dto/models.py`) → Pydantic schemas (if exposed via API). DTOs are often forgotten—missing fields there break inserts.

4. **Postman**: For every new service or API, add or update Postman collections under [docs/postman](docs/postman) so the new endpoints and flows are covered by tests.

5. **Tests**: When changing structural code (DB schema, triggers, DTOs), update the **unit tests** that depend on them so they stay in sync with the new structure. **Testing split**: Unit tests for gateways, utils, security, auth dependencies, DTOs, schemas. **Postman only** for services and routes—do not add Python unit tests for service logic.

6. **New API routes**: Use `create_versioned_router()` so routes live under `/api/v1/`. Register the router in `application.py` with manual/custom routes before auto-generated ones when they share paths (FastAPI matches first). See [docs/CLAUDE_ARCHITECTURE.md](docs/CLAUDE_ARCHITECTURE.md).

7. **User quoting agent output**: When the user writes something like "[Copied output from you kitchen Agent]" or similar, they **intend to pass you back a reference to your own output**. Treat it as the user citing or quoting something this agent previously said—not as an external source or a new instruction from a different system.
