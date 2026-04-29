# Kitchen

Vianda marketplace backend — PostgreSQL + FastAPI. Multi-market B2B/B2C food subscription platform.

Read `CLAUDE_ARCHITECTURE.md` before planning new features or modifying data flow. Update it after adding new modules, tables, services, routes, or subsystems.

---

## Never

- Never pass UUID directly to psycopg2 — always `str(uuid_value)`.
- Never register routes directly to `app` — use `create_versioned_router()`.
- Never write Python unit tests for `app/services/` or `app/routes/` — use Postman collections (full HTTP stack).
- Never store secrets in code.
- Never pass `page`/`page_size` pagination params from cron jobs or internal service calls — pagination is HTTP-only.
- Never edit an already-applied migration file — write a new one.
- Never `cd <path> && git <cmd>` from outside the repo CWD — use `git -C <path> <cmd>` instead. Plain `git <cmd>` inside the CWD is fine. The `cd && git` form triggers an untrusted-hooks confirmation on every invocation.
- Never use `POST /<entity>` for a Postman step that creates a fixture entity — use `PUT /<entity>/by-key` against an idempotent upsert endpoint. If the endpoint doesn't exist yet, add it: migration + schema + route + cleanup script + tests + entry in `docs/api/internal/UPSERT_SEED_CONVENTION.md`. POST is reserved for transactional events (orders, reviews, favorites). Closes #190 anti-pattern.
- Never rely on inline `# codeql[<rule-id>]` or `# lgtm[...]` comments to suppress CodeQL alerts. This repo uses GitHub Default Setup CodeQL, which does NOT honor inline suppressions. Dismiss false positives via the API/UI with `dismissed_reason="false positive"` (max 280 chars in `dismissed_comment`). Real fixes (e.g. `psycopg2.sql.Identifier` refactor) close alerts on the next scan.
- Never manually "fix" the `application.py:0` WebSocket baseline entry. Starlette stub versions render `WebSocket` vs `WebSocket[State]` differently, so local mypy disagrees with CI on this single line. Whatever's on `origin/main` is the form CI accepts. If `git diff origin/main -- mypy-baseline.txt` shows that line diverging, run `git checkout origin/main -- mypy-baseline.txt` for it and commit. Modify only when your code change actually touches `application.py:0`.
- Never merge a kitchen PR without the `deploy:dev` label. `.github/workflows/deploy.yml` triggers on PR-merge ONLY when the label is present; without it the workflow short-circuits with `skipped` and code lands on main but does NOT ship to dev. Add via `gh pr edit <number> --repo vianda-market/kitchen --add-label deploy:dev` before merging. To deploy already-merged code that missed the label: Actions tab → "Deploy Kitchen Backend" → "Run workflow". Verify deploys with `gh run list --repo vianda-market/kitchen --workflow=deploy.yml --limit 5 --json conclusion,event,headBranch,createdAt`.

---

## Essential Commands

Run `bash scripts/verify.sh` before every push — full local mirror of every required CI gate. Use `--fast` to skip pytest+newman, `--gate <name>` to run one gate.

For the full command catalogue (DB, tests, lint, type, quality gates, Newman, pre-commit setup), see [`docs/COMMANDS.md`](docs/COMMANDS.md).

- **Paths:** In the primary working tree, use `~/learn/vianda/kitchen`. In a worktree-isolated dispatch, use the agent's CWD (relative paths only) — never reference the absolute path.
- **User quoting agent output:** When the user writes "[Copied output from your kitchen Agent]", treat as self-citation.

---

## DB Schema Change — Sync All Layers (in order)

Write a migration in `app/db/migrations/NNNN_description.sql`, then update `schema.sql` to match.

`migration` → `schema.sql` → `trigger.sql` → `seed/reference_data.sql` (if needed) → `app/dto/models.py` → `app/schemas/consolidated_schemas.py`

Apply with `bash app/db/migrate.sh`. Full rebuild (`build_kitchen_db.sh`) is for fresh environments only — never use it on a database with test data you want to keep.

- History tables (`audit.*`) must mirror their main table — triggers must INSERT the new column.
- DTOs define which fields CRUDService writes — **missing field in DTO = silently dropped on insert**.
- `modified_by`, `created_date`, `modified_date` are set automatically — omit from API schemas.
- Adding a column? Search every service function querying that table and add the field to every SELECT — `get_all()` especially.

Full guide with failure scenarios: `docs/guidelines/SCHEMA_CHANGE_GUIDE.md`.

---

## Permissions (Two-Tier)

- **role_type:** `Internal` | `Supplier` | `Customer` | `Employer` — controls institution scoping.
- **role_name:** `Super Admin` | `Admin` | `Comensal` — controls operation-level access within the type.
- Internal = global access. Supplier/Employer = institution-scoped via `InstitutionScope` (`app/security/scoping.py`).
- Auth deps in `app/auth/dependencies.py`: `get_current_user`, `get_employee_user`, `get_super_admin_user`.

Full reference: `docs/api/internal/ROLE_BASED_ACCESS_CONTROL.md`.

---

## Code Conventions

- **Functions:** `verb_entity_by_context()`, <50 lines, pure, explicit `db`/`logger` params.
- **DTOs:** Pure data structures only — `app/dto/models.py`. No logic, no methods.
- **Enums:** UPPER_SNAKE_CASE member names; lowercase slug values stored in DB and API; display labels via `app/i18n/enum_labels.py` per locale (never `.value` for display). When using `strftime("%A")` for day names, always `.lower()` the result.
- **Route versioning:** `create_versioned_router("api", [...], APIVersion.V1)` in `application.py`.
- **No trailing slash** on collection endpoints — `/entity-name`, not `/entity-name/`.
- **In-memory caches** must have TTL/size eviction — never unbounded growth.
- **Enriched endpoints** use SQL JOINs; only rename fields on real column collisions.
- **Error handling:** Routes/CRUD → raise `HTTPException`. Internal lookups where "not found" is normal → return `None`.
- **Schema field names:** Never use Python built-in type names as field names (`date`, `time`, `type`, `list`) — use `order_date`, `pickup_time`, etc.

Details + examples: `docs/guidelines/CODE_CONVENTIONS.md`. Enriched endpoint pattern + field naming: `docs/guidelines/ENRICHED_ENDPOINTS.md`.

---

## Pagination (Opt-In)

Server-side pagination is opt-in per route — not all endpoints need it.

- **CRUD routes:** Set `paginatable=True` on `RouteConfig` in `route_factory.py`.
- **Enriched routes:** Add `pagination: Optional[PaginationParams] = Depends(get_pagination_params)` and call `set_pagination_headers(response, result)`.
- **Primitives:** `app/utils/pagination.py` — `PaginationParams`, `PaginatedList`, `get_pagination_params`, `set_pagination_headers`.
- **Protocol:** Frontend sends `page` + `page_size` query params → backend returns `X-Total-Count` header. No params = all records (backward compatible).
- **Cron jobs / internal service calls:** NEVER pass `page`/`page_size`. These always need all records.
- **Reference data** (countries, currencies, cuisines, enums): NOT paginated — small datasets.

---

## Testing

| Layer | How |
|---|---|
| `app/utils/`, `app/gateways/`, `app/auth/`, `app/security/` | pytest unit tests |
| `app/services/`, `app/routes/` | Postman collections only (full HTTP stack) |

- Postman collections must be self-contained — no hardcoded UUIDs, create or query test data inline.
- Collections live in `docs/postman/collections/`.
- One concept per test, Arrange-Act-Assert, mock external deps.
- Any Postman step that creates a fixture entity (one other steps will rely on) MUST use `PUT /<entity>/by-key` — see "Never" rule above. Pattern + per-entity sections: `docs/api/internal/UPSERT_SEED_CONVENTION.md`.

### Run Newman locally before pushing any PR that touches a Postman collection

Reproduce Newman failures locally before pushing — never let CI catch them. Run `bash scripts/verify.sh --gate newman` when only the collection changed (skips the full sweep), or:

```sh
# Terminal 1 — start the API:
bash scripts/run_dev_quiet.sh

# Terminal 2 — run the collection(s) you touched:
./scripts/run_newman.sh 000              # specific collection by NNN prefix
./scripts/run_newman.sh                  # full suite — do once before final push
```

Requires `newman` (`npm install -g newman`). Confirm any pre-request env vars (e.g. `superAdminUsername`, `superAdminPassword`) exist in both `docs/postman/environments/ci.postman_environment.json` AND your local environment — otherwise CI diverges from local.

### Parallel Newman in worktrees is safe

In a worktree at `.claude/worktrees/*`, source `scripts/worktree_env.sh` first to claim a unique port + DB name derived from `$PWD`:

```sh
source scripts/worktree_env.sh   # sets KITCHEN_API_PORT, KITCHEN_DB_NAME, NEWMAN_BASE_URL
                                  # also runs refresh_db_template.sh (no-op if fingerprint matches)
bash app/db/build_kitchen_db.sh  # ~1-2s TEMPLATE clone (not a full rebuild)
bash run_dev_quiet.sh            # starts API on the unique port
./scripts/run_newman.sh 000      # Newman hits the unique base URL
```

`scripts/verify.sh` auto-sources `worktree_env.sh` when `$PWD` is inside `.claude/worktrees/*`. Multiple worktrees can verify Newman simultaneously without port or DB collisions. Human dev (main working tree, no worktree) is unchanged: port 8000, DB `kitchen`.

Worktree DB creation is via Postgres TEMPLATE clone (~1-2 seconds, not a full rebuild). `worktree_env.sh` calls `scripts/refresh_db_template.sh`, which maintains a `kitchen_template` database — fully migrated, seeded, and upstream-synced. To force a refresh: `bash scripts/refresh_db_template.sh --force`. To rebuild a worktree DB with full migrations from scratch: `bash app/db/build_kitchen_db.sh --full`. To clean up orphaned worktree DBs: `bash scripts/cleanup_worktree_dbs.sh --execute`. References: issue #197 (port + DB env-var pattern), #199 (TEMPLATE-clone implementation).

---

## Key Entry Points

- **Route registration:** `application.py`
- **All Pydantic schemas:** `app/schemas/consolidated_schemas.py`
- **All DTOs:** `app/dto/models.py`
- **Leads (public/no-auth):** `app/routes/leads.py`
- **DB files:** `app/db/schema.sql`, `trigger.sql`, `index.sql`
- **Migrations:** `app/db/migrations/`
- **Seed data:** `app/db/seed/reference_data.sql` (all envs), `app/db/seed/dev_fixtures.sql` (dev only)
- **DB scripts:** `app/db/migrate.sh` (incremental), `app/db/build_kitchen_db.sh` (full rebuild)

---

## Reference Map — Read When

| Document | Read when |
|---|---|
| `CLAUDE_ARCHITECTURE.md` | Planning new features, modifying data flow, locating modules |
| `docs/api/internal/UPSERT_SEED_CONVENTION.md` | Adding a new entity type or any Postman fixture step |
| `docs/guidelines/SCHEMA_CHANGE_GUIDE.md` | Adding or modifying any DB column |
| `docs/guidelines/ENRICHED_ENDPOINTS.md` | Building enriched endpoints or joining tables for UI display |
| `docs/guidelines/CODE_CONVENTIONS.md` | Unsure about function design, error handling, or service patterns |
| `docs/guidelines/ROOT_CAUSE_PRINCIPLE.md` | Fixing a type mismatch or considering a downstream workaround |
| `docs/api/internal/ROLE_BASED_ACCESS_CONTROL.md` | Adding auth to a new endpoint or checking permission logic |
| `docs/guidelines/database/ENUM_MAINTENANCE.md` | Adding or modifying a PostgreSQL enum |
| `docs/guidelines/database/DATABASE_REBUILD_PERSISTENCE.md` | Rebuilding the database or managing seed data |
| `docs/plans/MULTINATIONAL_INSTITUTIONS.md` | Understanding institution-market model, three-tier cascade, employer entity normalization |
| `docs/plans/vianda_home_apis.md` | Implementing vianda-home marketing site APIs |

---

## Cross-Repo Documentation Protocol

This repo (kitchen) is the **backend source of truth**. It produces API docs and roadmaps that other repo agents consume. Other repos never write docs here — they read our docs and produce their own implementation + documentation.

When completing a feature that affects other repos:

1. Produce or update the relevant `docs/api/` doc describing new endpoints, contracts, and behaviors.
2. List the docs produced and which agents need them in your summary:
   - **vianda-platform agent:** B2B UI changes (Employer Program pages, auth, error handling).
   - **vianda-app agent:** B2C UI changes (benefit plans, subscription flow).
   - **infra-kitchen-gcp agent:** cron jobs, env vars, Stripe config, GCS buckets.
3. Point the user to the specific files to share with each agent.

**Doc locations produced by this repo:**

- `docs/api/` — Permanent API integration docs (endpoints, contracts, auth). Indexed in `docs/api/AGENT_INDEX.md`. Source of truth for how the system works. Other repo agents read these to understand established functionality.
- `docs/plans/` — Ephemeral feature plans and design decisions. Plans are consumed during implementation, then archived. Never reference old plans to understand how things work — that information belongs in `docs/api/` or `CLAUDE_ARCHITECTURE.md`. When completing a plan, summarize any long-term info (endpoint contracts, behaviors, constraints) into the appropriate `docs/api/` doc before archiving.
- `CLAUDE_ARCHITECTURE.md` — System overview for cross-repo context.

**Agent index files in other repos (read-only, for context):**

- **vianda-platform (B2B):** `/Users/cdeachaval/learn/vianda/vianda-platform/docs/frontend/AGENT_INDEX.md`
- **vianda-app (B2C):** `/Users/cdeachaval/learn/vianda/vianda-app/docs/frontend/AGENT_INDEX.md`
- **vianda-home (marketing):** `/Users/cdeachaval/learn/vianda/vianda-home/docs/frontend/AGENT_INDEX.md`
- **infra-kitchen-gcp:** `/Users/cdeachaval/learn/vianda/infra-kitchen-gcp/docs/infrastructure/AGENT_INDEX.md`
