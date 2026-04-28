# CLAUDE.MD

## Project
Vianda marketplace backend — PostgreSQL + FastAPI. Multi-market B2B/B2C food subscription platform.
Read `CLAUDE_ARCHITECTURE.MD` before planning new features or modifying data flow.
Update `CLAUDE_ARCHITECTURE.MD` after adding new modules, tables, services, routes, or subsystems.

## Never Do These
- Never pass UUID directly to psycopg2 — always `str(uuid_value)`
- Never register routes directly to `app` — always use `create_versioned_router()`
- Never write Python unit tests for services — use Postman collections (see Testing below)
- Never store secrets in code
- Never pass `page`/`page_size` pagination params in cron jobs or internal service calls — pagination is for HTTP routes only
- Never edit an already-applied migration file — write a new one instead
- Never `cd <path> && git <cmd>` from outside a repo CWD. Use `git -C <path> <cmd>` instead — `cd && git` triggers the harness's "untrusted hooks" confirmation prompt on every invocation. Plain `git <cmd>` from inside the repo CWD is fine.
- Never rely on inline `# codeql[<rule-id>]` or `# lgtm[...]` comments to suppress CodeQL alerts. This repo uses **GitHub Default Setup CodeQL**, which does NOT honor inline suppressions. False-positive alerts must be dismissed via the API/UI with `dismissed_reason="false positive"` (with space, max 280 chars in `dismissed_comment`). Real fixes (e.g. structural refactor like `psycopg2.sql.Identifier`) close alerts on the next scan; inline comments do nothing. (Caught 2026-04-26 in PRs #132/#134/#136/#137 — suppressions had no effect; alerts were finally closed via batch API dismissal referencing `docs/plans/codeql-91-triage.md`.)
- **Never manually "fix" `application.py:0` WebSocket baseline entry.** The Starlette type stubs render the same `add_exception_handler` error message with either `WebSocket` or `WebSocket[State]` depending on installed stubs version. Local mypy often disagrees with CI on this single line. The rule: Whatever is on `origin/main` is the form CI accepts. Modify the `application.py:0` baseline entry ONLY if your code change actually touches that line — which for any non-`application.py` PR means NEVER. If `git diff origin/main -- mypy-baseline.txt` shows that line diverging in your branch, it is local-vs-CI stub drift, not a real resolution. Run `git checkout origin/main -- mypy-baseline.txt` for that one line and commit. (Caught + re-fixed on kitchen PR #155 commit `f1c6252` and PR #158 commit `fa0c68a`. Same pattern; same fix.)
- **Merge without forgetting the `deploy:dev` label.** `.github/workflows/deploy.yml` triggers on PR-merge ONLY when the PR carries the `deploy:dev` label. Without it, the workflow runs but short-circuits with `skipped` — code lands on main but does NOT ship to dev. Before merging any PR intended for dev: `gh pr edit <number> --repo vianda-market/kitchen --add-label deploy:dev` (or use the GitHub UI sidebar). To deploy already-merged code that missed the label: Actions tab → "Deploy Kitchen Backend" → "Run workflow" → select branch `main` (or specific SHA) and add a 1-line reason. To verify a merge shipped: `gh run list --repo vianda-market/kitchen --workflow=deploy.yml --limit 5 --json conclusion,event,headBranch,createdAt,databaseId` — look for `success` (deployed) vs `skipped` (label missing). (Caught 2026-04-27: PRs #160 uvicorn, #161 arq, #163 pydantic-settings all merged without label and sat undeployed until manual `workflow_dispatch`. Operational doc: `~/learn/vianda/docs/commands/kitchen_smoketest.md`.)

## Essential Commands
- **Full local gate sweep:** `bash scripts/verify.sh` — mirrors every required CI gate exactly. **Run before every push.** Use `--fast` to skip pytest+newman, `--gate <name>` to run one gate.
- **Apply migrations:** `bash app/db/migrate.sh` (incremental — preserves data)
- **Rebuild DB (fresh):** `bash app/db/build_kitchen_db.sh` (full tear-down — use for new environments or clean reset only)
- **Import check:** `python3 -c "from application import app; print('OK')"`
- **Run tests:** `pytest app/tests/`
- **Test collection check (local):** `pytest --collect-only -q --ignore=app/tests/database`
- **Diff-coverage gate (local):** `pytest --cov=app --cov-report=xml --cov-fail-under=0 && diff-cover coverage.xml --compare-branch=origin/main --fail-under=80`
- **Secret scan (local):** `gitleaks detect --source . --verbose` (allowlist: `.gitleaksignore`)
- **Maintainability gate (local):** `bash scripts/check_maintainability.sh` (fails if MI drops >5% on changed files vs origin/main)
- **Dead code gate (local):** `bash scripts/check_vulture.sh` (baseline: `.vulture-baseline.txt`; update: `--update`)
- **Pre-commit hooks (setup):** `pip install pre-commit && pre-commit install` (runs ruff, gitleaks, complexity, yaml/large-file/merge checks)
- **Strict complexity (local):** `bash scripts/check_complexity_strict.sh` (CC ≤ 15 on changed files; repo-wide CC ≤ 25 is separate)
- **Layer boundaries (local):** `lint-imports` (contracts in `.importlinter`: dto/schemas/services isolation)
- **Security lint (local):** `bandit -r app/ -lll --exclude app/tests -b .bandit-baseline.json`
- **SQL lint (local):** `bash scripts/check_sqlfluff.sh` (config: `.sqlfluff`; baseline: `.sqlfluff-baseline.txt`)
- **License check (local):** `pip install pip-licenses && python scripts/check_licenses.py` (allowlist: MIT/Apache/BSD/ISC/MPL/PSF; per-package exemptions in the script)
- **CRAP analysis (local, ad-hoc):** `pytest --cov=app --cov-report=xml --cov-fail-under=0 && python scripts/analyze_crap.py` (ranks complex + under-tested functions; not a gate, run periodically to pick refactor targets)
- **Paths:** Always use `~/learn/vianda/kitchen`
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

### Run Newman locally before pushing any PR that touches a Postman collection

Postman/Newman failures are reproducible locally — there is no excuse for letting CI catch them. Before pushing any PR that adds or edits a collection, runs against an endpoint a collection exercises, or changes auth/role gating:

```sh
# Terminal 1 — start the API:
bash scripts/run_dev_quiet.sh

# Terminal 2 — run the collection(s) you touched:
./scripts/run_newman.sh 000              # specific collection by NNN prefix
./scripts/run_newman.sh                  # full suite (slower; do once before final push)
```

Requires `newman` (`npm install -g newman`). The CI environment file is `docs/postman/environments/ci.postman_environment.json` — if your collection's pre-request scripts depend on env vars (e.g. `superAdminUsername`, `superAdminPassword`), confirm they exist in `ci.postman_environment.json` AND that your local environment provides matching values, otherwise CI will diverge from local. Fixing a Newman failure on CI without first reproducing it locally is the wrong order — reproduce, fix, verify locally, then push.

Newman is one of the gates `scripts/verify.sh` runs; when only the postman collection changed, you can run `bash scripts/verify.sh --gate newman` instead of the full sweep.

**Parallel Newman in worktrees is safe.** If running in a worktree at `.claude/worktrees/*`, source `scripts/worktree_env.sh` first to claim a unique port + DB name derived from `$PWD`:

```sh
source scripts/worktree_env.sh   # sets KITCHEN_API_PORT, KITCHEN_DB_NAME, NEWMAN_BASE_URL
                                  # also runs refresh_db_template.sh (no-op if fingerprint matches)
bash app/db/build_kitchen_db.sh  # ~1-2s TEMPLATE clone (not a full rebuild) — see below
bash run_dev_quiet.sh            # starts API on the unique port
./scripts/run_newman.sh 000      # Newman hits the unique base URL
```

`scripts/verify.sh` auto-sources `worktree_env.sh` when `$PWD` is inside `.claude/worktrees/*` — no manual step needed for agent dispatches. Multiple worktrees can verify Newman simultaneously without port or DB collisions. Human dev (main working tree, no worktree) is unchanged: port 8000, DB `kitchen`.

**Worktree DB creation is via Postgres TEMPLATE clone (~1-2 seconds, not a full rebuild).** `worktree_env.sh` calls `scripts/refresh_db_template.sh`, which maintains a `kitchen_template` database — a fully migrated + seeded + upstream-synced snapshot. When `build_kitchen_db.sh` is invoked with `KITCHEN_DB_NAME` set to a worktree-specific name, it clones from `kitchen_template` via `CREATE DATABASE ... TEMPLATE kitchen_template` instead of re-running migrations from scratch. Upstream API syncs (FX rates, national holidays) run **once** when the template is built, never per-worktree.

- `refresh_db_template.sh` is a no-op when migration filenames + `dev_fixtures.sql` are unchanged. It rebuilds the template (~30s) when the fingerprint changes.
- To force a refresh after upstream data changes (e.g. new currency rates): `bash scripts/refresh_db_template.sh --force`
- To rebuild with full migrations from scratch in a worktree: `bash app/db/build_kitchen_db.sh --full`
- To clean up orphaned worktree databases: `bash scripts/cleanup_worktree_dbs.sh --execute`
- References: issue #197 (port + DB env-var pattern), issue #199 (TEMPLATE-clone implementation).

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
| `CLAUDE_ARCHITECTURE.MD` | Planning new features, modifying data flow, locating modules |
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
- `docs/plans/` — **Ephemeral** feature plans and design decisions. Plans are consumed during implementation, then archived. Never reference old plans to understand how things work — that information belongs in `docs/api/` or `CLAUDE_ARCHITECTURE.MD`. When completing a plan, summarize any long-term relevant info (endpoint contracts, behaviors, constraints) into the appropriate `docs/api/` doc before archiving the plan.
- `CLAUDE_ARCHITECTURE.MD` — System overview for cross-repo context

**Agent index files in other repos (read-only, for context):**
- **vianda-platform (B2B):** `/Users/cdeachaval/learn/vianda/vianda-platform/docs/frontend/AGENT_INDEX.md`
- **vianda-app (B2C):** `/Users/cdeachaval/learn/vianda/vianda-app/docs/frontend/AGENT_INDEX.md`
- **vianda-home (marketing):** `/Users/cdeachaval/learn/vianda/vianda-home/docs/frontend/AGENT_INDEX.md`
- **infra-kitchen-gcp:** `/Users/cdeachaval/learn/vianda/infra-kitchen-gcp/docs/infrastructure/AGENT_INDEX.md`
