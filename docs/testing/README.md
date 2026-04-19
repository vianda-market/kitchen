# Testing Setup — Cross-Repo Agent Guide

**Audience:** Agents auditing or authoring tests in any Vianda repo (kitchen, vianda-platform, vianda-app, vianda-home, infra-kitchen-gcp). This doc describes the **kitchen backend's** testing approach so other repos can align on shared conventions and avoid reinventing patterns.

Repo-local reference docs:
- `app/tests/README.md` — directory layout
- `docs/testing/TEST_STRUCTURE.md` — fixtures, layering, naming
- `docs/testing/DATABASE_TEST_ALTERNATIVES.md`, `PGTAP_TO_PYTEST_MIGRATION.md` — history of DB test migration
- `docs/postman/README.md` + `docs/postman/guidelines/` — Postman collection conventions

---

## 1. Core principle: test at the right layer

The kitchen repo draws a hard line between **what gets a pytest** and **what gets a Postman collection**. Crossing that line is the single most common mistake we correct in reviews.

| Layer | Test tool | Why |
|---|---|---|
| `app/utils/`, `app/gateways/`, `app/auth/`, `app/security/` | **pytest** | Pure functions / narrow dependencies — fast, deterministic, cheap to mock |
| `app/services/`, `app/routes/` | **Postman collections** (Newman in CI) | Full HTTP + DB + auth stack; mocking the DB here gives false confidence |
| `app/db/` (schema, seed, triggers) | **pytest against a live Postgres** in `app/tests/database/` | Schema drift and trigger bugs only surface against a real engine |

**Rule of thumb for cross-repo agents:** if the code under test owns a database write, a transaction, or an auth-scoped query, reach for an end-to-end test (Postman / Playwright / Newman), not a mocked unit test. Mock-heavy service tests rot fast and hide migration bugs.

---

## 2. Pytest layout

```
app/tests/
├── conftest.py          # shared fixtures: mock_db, sample_*_user, market/city UUIDs
├── auth/                # dependency functions (get_employee_user, scoping)
├── security/            # InstitutionScope, RBAC helpers
├── utils/               # pure helpers
├── gateways/            # external-API clients with mocked transport
├── database/            # schema/seed/trigger tests against a live Postgres
├── routes/              # thin integration tests with FastAPI TestClient + dependency overrides (optional)
└── services/            # kept intentionally small — Postman is the primary tool here
```

**Conventions worth copying:**
- **Arrange-Act-Assert**, one concept per test, descriptive test names.
- Shared fixtures (users, mock DB, sample UUIDs) live in `conftest.py`. Per-file fixtures stay local.
- **Standard user fixtures** cover every `role_type × role_name` combo the code branches on — `sample_super_admin_user`, `sample_employee_user`, `sample_supplier_user`, `sample_customer_user`. Other repos consuming these roles should mirror this fixture set so test data stays comparable across repos.
- UUIDs used in tests are **seed-aligned constants** (e.g. US market `66666666-…`). Never generate a random UUID for something that must match seed data — the failure mode is silent query misses.

---

## 3. Postman / Newman as the integration tier

Postman collections are the **contract test** layer for HTTP surfaces. They are authoritative because they run the same bytes the frontend sends.

**Conventions enforced in this repo:**
- Collections live in `docs/postman/collections/`, numbered for run order (`000_`, `006_`, …).
- **Self-contained**: no hardcoded UUIDs from a developer laptop. Tests create or look up their fixtures inline via API calls earlier in the collection.
- **One concept per request**; Arrange-Act-Assert via Postman tests.
- **Auth is idempotent**: a login step near the top sets a bearer token variable; later requests reuse it. Super-admin login is shared via Newman `--globals` in CI.
- **Per-frontend-consumer organization** for leads-style public APIs (see `docs/postman/guidelines/LEADS_COLLECTION_CONVENTIONS.md`). One collection per consumer repo keeps contract drift localized.
- **Country codes** are always ISO 3166-1 alpha-2 (`AR`, `US`). Collections that send `ARG`/`USA` are wrong — see `docs/api/shared_client/COUNTRY_CODE_API_CONTRACT.md`.
- **Minimal seed + E2E flow**: DB rebuild seeds only one super admin, two institutions, and the Global market. The E2E Plate Selection collection creates everything else via the API. Postman populates test data; it does not depend on fixtures planted outside of it.

**Running locally:** `bash app/tests/run_postman_collections.sh`. **In CI:** `bash scripts/run_newman.sh <numbers…>` (see `.github/workflows/ci.yml`).

**For frontend repo agents:** when you add or change a user-visible flow, update the matching kitchen Postman collection (or ask for the endpoint contract to be added) before writing Playwright/Cypress tests. The Postman collection is the source of truth for request/response shape.

---

## 4. Database tests (live Postgres)

Schema, seed, and trigger correctness live in `app/tests/database/`. These tests:
- Spin up against a real Postgres (CI uses `bash app/db/build_kitchen_db.sh`).
- Validate that every table exists with expected columns, that triggers fire, and that seed invariants hold (e.g. Global market present, currency seed intact).
- **Replace** the legacy pgTAP SQL suite under `app/db/tests/` (archived — see `PGTAP_TO_PYTEST_MIGRATION.md`).

**When adding a column**, the failure mode we've been bitten by: the column is added to `schema.sql` but missing from DTOs or from the history trigger. A database test that SELECTs every column from `audit.*` and compares against the main table catches this before it ships. Other repos with DB ownership should adopt the same mirror-check pattern.

---

## 5. Quality gates (not tests, but enforced alongside)

Kitchen CI runs these in addition to tests; agents auditing other repos should check whether equivalents exist:

| Gate | Tool | Local command |
|---|---|---|
| Lint / format | ruff | `ruff check . && ruff format --check .` |
| Type check (baseline-filtered) | mypy + mypy-baseline | `mypy app/ \| mypy-baseline filter` |
| Layer boundaries | import-linter | `lint-imports` |
| Complexity (repo-wide CC ≤ 25, changed-files CC ≤ 15) | radon | `bash scripts/check_complexity.sh` / `_strict.sh` |
| Maintainability index | radon | `bash scripts/check_maintainability.sh` |
| Dead code | vulture (baselined) | `bash scripts/check_vulture.sh` |
| Security lint | bandit (baselined) | `bandit -r app/ -lll -b .bandit-baseline.json` |
| SQL lint | sqlfluff (baselined) | `bash scripts/check_sqlfluff.sh` |
| Secret scan | gitleaks | `gitleaks detect --source .` |
| Dependency audit | pip-audit | `pip-audit -r requirements.txt` |
| License check | pip-licenses + allowlist | `python scripts/check_licenses.py` |
| Diff coverage (changed lines ≥ 80%) | diff-cover | see CLAUDE.md |

**Baseline pattern:** every gate that had pre-existing debt is configured with a baseline file so new code is held to the new standard without blocking on legacy cleanup. Other repos adopting these gates should do the same — a gate that can never be made green gets disabled within a week.

**`diff-cover --exclude` gotcha:** multiple `--exclude` flags overwrite each other (argparse `nargs='+'`). Combine all patterns into a single flag. This has bitten every Vianda repo that wires up diff-cover; copy the kitchen invocation verbatim.

---

## 6. What not to do (lessons from this repo)

- **Don't write pytest unit tests for `app/services/` or `app/routes/`** — the mocking overhead is high and the signal is low. Use Postman.
- **Don't hardcode UUIDs** in test data that aren't from the seed. Either create via API or reference the seed constant.
- **Don't edit an already-applied migration file** to fix a test — write a new migration.
- **Don't mock the database** in integration tests that own a write path. We've shipped broken migrations behind green mocked tests before.
- **Don't add a quality gate without a baseline** if there's existing debt. It will be disabled by the next person who gets blocked by it.
- **Don't pass `page` / `page_size` from internal callers** (cron jobs, service-to-service). Pagination is an HTTP-route concept; tests that exercise internal callers must not supply it.

---

## 7. Standardizing across repos

When auditing a sibling repo's test setup, check for these by name:

1. **Layer split is explicit** — each repo's testing README states which layer uses which tool, and why.
2. **Fixtures mirror the auth model** — every `role_type × role_name` combo the code branches on has a named fixture. Cross-repo fixture names should match kitchen's so agents can reason about them interchangeably.
3. **Contract tests live where the contract lives** — backend HTTP contracts are tested in kitchen's Postman collections; frontend repos consume them rather than duplicating.
4. **Quality gates are baselined, not disabled** — any gate lacking a baseline file is a candidate for either a baseline or removal.
5. **ISO country codes, ISO-8601 timestamps, seed-aligned UUIDs** — any test using non-canonical forms is drift; fix it at the source.
6. **E2E flows self-populate** — no collection or test depends on fixtures planted by hand on a developer laptop.

If you find a pattern in a sibling repo that improves on what's here, propose it back via a PR to this file — this doc is the shared contract.

---

## 8. Cross-repo references

Sibling testing docs (read these when auditing or aligning):
- **vianda-platform** (`/Users/cdeachaval/learn/vianda-platform/docs/testing/README.md`) — Vitest layer, scoped coverage with `perFile: true`, StrykerJS two-mode (weekly full + per-PR incremental), 4-job consolidated CI with path filters
- **vianda-app** (`/Users/cdeachaval/learn/vianda-app/docs/testing/README.md`) — Jest + RN testing, property-based tests with `fast-check`, mutation-equivalent disable conventions, coverage ratchet script
- **vianda-home** (`/Users/cdeachaval/learn/vianda-home/docs/testing/README.md`) — i18n shape-parity test, Playwright with `mockApiRoutes` helper, layered CI where cheap gates expensive
- **infra-kitchen-gcp** (`/Users/cdeachaval/learn/infra-kitchen-gcp/docs/testing/README.md`) — Pulumi mock pattern (capture inputs as data), policy-as-code allowlists, test categorization (smoke/convention/policy/toggle/behavior), 94% branch-coverage floor

---

## 9. Patterns from sibling repos worth adopting in kitchen

A 2026-04-19 audit against the four sibling docs surfaced concrete opportunities. Listed by impact.

### CI efficiency (Actions time)

The current pipeline is 10+ parallel jobs, each paying its own `pip install` and (for `acceptance`) booting Postgres + the server unconditionally. Adopting these would cut PR time materially:

1. **Path-filter the heavy jobs.** Use `dorny/paths-filter` (vianda-platform §7, vianda-home §1) to skip `acceptance` and `test` on PRs that touch only `docs/**`, `*.md`, or `.github/ISSUE_TEMPLATE/**`. Never skip on push to `main` — main must always carry the full signal.
2. **Consolidate the cheap jobs.** lint, typecheck, layers, complexity, deadcode, security, bandit, sqllint each pay 30–60s of `pip install` separately. Merging them into one `fast-checks` job sharing a single venv (vianda-platform §7) saves multiple minutes per PR. Keep `acceptance` and `test` separate — they have genuinely different runtimes and dependencies.
3. **Chain heavy jobs behind cheap ones.** `acceptance` (Postgres + server + 15 Newman collections, ~5+ min) currently fires in parallel with lint. Add `needs: [fast-checks]` so a syntax error doesn't waste a Postgres boot (vianda-home §1: "make the cheapest layer the gate for the expensive one").
4. **Document the "non-blocking → blocking" plan** (vianda-platform §7). Any non-blocking gate (CRAP if added, mutation if extended) should declare in CI comments what it takes to flip to blocking. Without that, non-blocking gates become permanent noise.

### Test coverage gaps

5. **i18n shape-parity test** (vianda-home §6). `app/i18n/enum_labels.py` carries EN/ES labels keyed off enum members. A ~60-line test that walks both locales and asserts the same key set catches translator-forgot-a-key bugs cheaply. Do **not** assert on values — proper nouns and brand names produce false positives.
6. **Route auth-allowlist policy test** (infra-kitchen-gcp §5: "Allowlists over denylists"). Add `app/tests/security/test_route_auth_policy.py` that walks every registered route and asserts each one has an auth dependency, with a small explicit allowlist for genuinely public surfaces (`/leads/*`, `/docs`, `/health`). New public endpoint = test failure = explicit decision to add to allowlist. Mirrors their `allowed_public_resources` pattern.
7. **Pytest smoke test** (infra-kitchen-gcp §3). Today's `python -c "from application import app"` import check is a bash one-liner. A proper `tests/test_smoke.py` asserting (a) app boots, (b) expected route count is within ±5% of recorded baseline, (c) critical routes (`/leads/markets`, `/users/me`) are registered, would catch silent registration drops that pure import doesn't.
8. **Categorize tests with pytest markers** (infra-kitchen-gcp §3). Currently organized by layer (auth/security/utils). Adding `@pytest.mark.smoke`, `@pytest.mark.policy`, `@pytest.mark.toggle` enables targeted runs (`pytest -m smoke` for a 30s sanity pass) and forces authors to classify intent.

### Quality signals not yet in CI

9. **Wire CRAP into CI as non-blocking** (vianda-platform §4). `scripts/analyze_crap.py` exists per CLAUDE.md but is only ad-hoc. Adding it to the `test` job (after the coverage XML is produced) costs ~seconds and surfaces complex-and-undertested functions every PR. Start non-blocking; gate later.
10. **Coverage ratchet script** (vianda-app §3). A `scripts/coverage-ratchet.py` that prints per-file coverage 5+ points above the locked threshold would let us promote diff-coverage into per-file gates over time without a big-bang threshold edit.
11. **Absolute coverage floor on testable layers**. `--cov-fail-under=0` (current) means the gate is purely diff-cover. Adding an absolute floor on `app/utils/` and `app/auth/` (the layers we explicitly test) catches the case where someone deletes tests without changing code.

### Conventions worth lifting verbatim

12. **One-sentence docstring stating the rule** for policy/security tests (infra-kitchen-gcp §5.2): `"""Cloud SQL instances must use private IP only."""`. Read like a spec.
13. **Assertion messages include the offending value** (infra-kitchen-gcp §5.3). `assert public == [], f"public routes outside allowlist: {public}"` beats a bare `assert`.
14. **Capture inputs as data, assert in plain Python** (infra-kitchen-gcp §2). Where we mock a service, store the captured calls on the mock and assert against the list — don't lean on `assert_called_with` chains. Same idea as MSW's request log in the frontend repos.

### What we should *not* copy

- **StrykerJS / per-PR incremental mutation** is configured on the JS side because their UIs have business logic (auth, money math) that line coverage misses. Kitchen's equivalent is Postman + the database test layer — mutation testing for Python services in a backend with this much I/O is high-cost / low-signal. Skip unless we identify a specific module (pricing, role checks) that warrants it.
- **Playwright `mockApiRoutes`** has no analogue here — backend doesn't mock itself. Postman collections are our equivalent and already follow the "self-contained, parameterized scenarios" pattern.
- **Coverage `perFile: true` with scoped globs** (vianda-platform/-home) is excellent for frontends with sharply-typed util folders. Less critical here because diff-coverage already enforces per-PR rigor; revisit if we adopt finding #11.

**Suggested rollout order:** #1 + #2 + #3 (CI consolidation, biggest time saver, low risk) → #5 (i18n parity, high-value cheap test) → #6 + #7 (auth policy + smoke, both prevent regressions we've seen) → #9 (CRAP non-blocking) → the rest as opportunistic.
