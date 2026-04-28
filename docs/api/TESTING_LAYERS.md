# Testing Layers — Orientation Guide

> **Audience:** contributors who know pytest but are new to this repo's conventions.
> **Not a tutorial.** Skip to the section you need.

---

## 1. Layer Table

| Layer | Tool | Catches | Doesn't catch | When to add |
|---|---|---|---|---|
| **pytest unit** | pytest | Logic bugs in pure helpers, gateways, auth, security, i18n — exhaustive branch coverage without DB/network | Route behavior, service integration, full HTTP stack | Any new function in `app/utils/`, `app/gateways/`, `app/auth/`, `app/security/` |
| **Postman / Newman acceptance** | Newman + uvicorn + Postgres | Full HTTP stack correctness, request/response shapes, DB side-effects, auth enforcement | Pure helper logic (better at unit layer) | Any new service function or route. **Always Postman — never pytest for services** |
| **mypy strict + mypy_baseline** | mypy + mypy_baseline | Type errors caught statically; baseline gates both new errors AND resolved ones | Runtime type coercions, DB type mismatches | Automatically runs on every change; update baseline when types change |
| **diff-cover ≥80% on changed lines** | diff-cover | Ensures changed source lines are covered by unit tests | Total coverage of untouched files | Automatically checked in CI; ensure tests exist for every changed utility function |
| **Mutation Tests (Tier 1)** | mutmut | Tests that pass despite logically wrong mutations in critical money/credit services | Routes, services outside Tier-1 scope | Runs automatically when Tier-1 paths change; no manual addition needed |
| **Static analysis gates** | ruff, lint-imports, complexity, vulture, bandit, sqlfluff, gitleaks, license, pip-audit | Style, layer violations, dead code, security issues, SQL formatting, secrets, dependency vulns | Behavioral correctness | Automatically run in CI; see CLAUDE.md Essential Commands for local equivalents |

**Tier-1 mutation scope** (`mutation.yml`): `app/services/credit_validation_service.py`, `app/services/credit_loading_service.py`, `app/services/discretionary_service.py`. Kill-rate threshold: 65%.

---

## 2. Decision Flow

```
What am I adding?
|
+-- Pure helper / util / gateway / auth / security function
|    -> app/utils/, app/gateways/, app/auth/, app/security/
|       Write a pytest unit test. Aim for full branch coverage.
|       (If in Tier-1 scope, mutmut will run automatically.)
|
+-- New service function (app/services/)
|    -> Add to the relevant Postman collection in docs/postman/collections/.
|       DO NOT write pytest unit tests for services — Postman only.
|       Collection must be self-contained (no hardcoded UUIDs — see §3a).
|
+-- New route (app/routes/)
|    -> Add requests to the relevant Postman collection.
|       Ensure the collection exercises auth, scoping, and error paths.
|       Register the route via create_versioned_router() in application.py.
|
+-- Complex service function with CC >= 15
|    -> Extract pure logic to app/utils/ and unit-test the extracted helper.
|       Leave the service thin (see §3b).
|       The collection still covers the service end-to-end.
|
+-- Schema / type change
|    -> Run mypy and check git diff origin/main -- mypy-baseline.txt.
|       If resolved entries appear, run: mypy-baseline sync && git add mypy-baseline.txt (see §3c).
```

---

## 3. Patterns

### 3a. Postman collections must be self-contained

**Source:** CLAUDE.md "Testing" section

Collections live in `docs/postman/collections/`. Each collection must:
- Create all required test data inline (users, institutions, restaurants, etc.)
- Never hardcode UUIDs — use variables set from prior response bodies
- Clean up created data at the end when practical
- One concept per request; use Arrange-Act-Assert in test scripts

CI runs collections in a specific order (see `scripts/run_newman.sh`). If your collection depends on entities created by an earlier collection, document the dependency at the top of the collection description.

---

### 3b. Pure-helper extraction first, then test pure

**Context:** strict complexity gate (CC ≤ 15 on changed files via `scripts/check_complexity_strict.sh`)

When a service function grows CC ≥ 15 due to a switch/conditional cluster (validation chains, payload building, business rules):
1. Extract the pure logic to a function in `app/utils/`.
2. Unit-test the extracted function exhaustively (no DB, no mocks needed — just inputs and outputs).
3. Leave the service thin. The Postman collection continues to test the service end-to-end.

Result: the service stays under the CC threshold; the extracted helper gets precise branch coverage.

---

### 3c. mypy_baseline is strict in BOTH directions

**Source:** CLAUDE.md "Never Do These"; also in CLAUDE.md of the orchestrator root

The mypy baseline gate fails when your change:
- **introduces** new type errors (expected)
- **resolves** existing baseline entries (also fails — the baseline is now stale)

When refactoring resolves baseline entries:

```
mypy app/ 2>&1 | python -m mypy_baseline filter --no-colors  # verify what CI sees
mypy-baseline sync                                             # update baseline
git add mypy-baseline.txt
git commit -m "sync mypy baseline after refactor"
```

**Exception — never touch `application.py:0` manually.** The Starlette type stubs flip between `WebSocket` and `WebSocket[State]` depending on installed version. Local mypy and CI mypy disagree on this one line. If `git diff origin/main -- mypy-baseline.txt` shows that entry diverging, run:

```
git checkout origin/main -- mypy-baseline.txt
```

and commit. Do not try to "fix" it by editing the baseline file directly.

---

### 3d. Vulture baseline is line-anchored — refactors shift it

**Source:** `.vulture-baseline.txt`; `scripts/check_vulture.sh`

Vulture stores dead-code suppressions as `file:line:symbol`. If a refactor shifts line numbers, pre-existing suppressed entries become detached and re-surface as new violations. After any significant restructuring:

```
bash scripts/check_vulture.sh --update   # regenerate baseline
git add .vulture-baseline.txt
git commit -m "update vulture baseline after refactor"
```

---

### 3e. diff-cover measures changed lines, not total coverage

diff-cover gates coverage on lines **changed in the PR vs `origin/main`** — it does not measure the repo's total coverage floor. A PR can pass diff-cover at 80% while total coverage falls.

The separate `scripts/check_coverage_floor.py` gate covers the absolute floor per layer (utils, auth, security, gateways, i18n). Both must pass. Chase the right number for the failure you're seeing.

---

## 4. What's Gated (and What Isn't)

### Hard gates — required by `ci-pass` aggregator

All jobs below must be `success` or `skipped` for branch protection to pass.

| Gate | Command (local equivalent) | Notes |
|---|---|---|
| Ruff lint + format | `ruff check . && ruff format --check .` | Pre-commit also runs ruff |
| mypy + baseline | `mypy app/ 2\|& python -m mypy_baseline filter --no-colors` | Strict both ways — see §3c |
| Import boundaries | `lint-imports` | Layer contracts in `.importlinter` |
| Complexity repo-wide | `bash scripts/check_complexity.sh` | CC ≤ 25 everywhere |
| Maintainability | `bash scripts/check_maintainability.sh` | MI drop >5% on changed files fails |
| Complexity strict | `bash scripts/check_complexity_strict.sh` | CC ≤ 15 on changed files |
| Dead code | `bash scripts/check_vulture.sh` | Baseline: `.vulture-baseline.txt` |
| Bandit | `bandit -r app/ -lll --exclude app/tests -b .bandit-baseline.json` | High-severity only, baselined |
| Threshold parity | `python scripts/check_thresholds_parity.py` | Numeric gates must match across lock/source/doc |
| Filter schema sync | `bash scripts/check_filter_schema.sh` | `filters.json` vs `FILTER_REGISTRY` |
| SQL lint | `bash scripts/check_sqlfluff.sh` | Baseline: `.sqlfluff-baseline.txt` |
| Gitleaks | `gitleaks detect --source . --verbose` | Allowlist: `.gitleaksignore` |
| pytest unit | `pytest -m "not integration and not database and not slow" --ignore=app/tests/database --ignore=app/tests/routes` | Routes/services excluded — tested via Postman |
| diff-cover ≥80% | `diff-cover coverage.xml --compare-branch=origin/main --fail-under=80` | Changed lines in utils/auth/security/gateways/i18n only |
| Per-layer coverage floor | `python scripts/check_coverage_floor.py` | Absolute floor per testable layer |
| Acceptance (Newman) | `bash scripts/run_newman.sh <collection-ids>` | Full HTTP stack against real DB |

### Signal-only / non-blocking

| Signal | Notes |
|---|---|
| Post-test CRAP analysis | Ranks complex + under-tested functions. Advisory only. Run locally: `python scripts/analyze_crap.py` |
| Sticky PR coverage comment | Posted by `scripts/build_pr_coverage_comment.sh`; informational |
| Mutation Tests (Tier 1) | `mutation.yml` is a **separate required check** in branch protection, not part of `ci-pass`. Technically blocking if the workflow is required, but only runs when Tier-1 paths change. Flaky failures (e.g. `ValueError: I/O operation on closed file`) are transient — re-run first before investigating. |

---

## 5. Anti-patterns

**Writing pytest unit tests for service functions.** CLAUDE.md "Never Do These": services live in `app/services/` and are tested exclusively via Postman collections. A pytest test for a service function will be rejected in review.

**Hardcoded UUIDs in Postman collections.** If a UUID is copied from a dev database, it doesn't exist in CI's fresh DB. The collection will fail on the first run that doesn't have that exact record. Always create-or-query test data inline.

**Lowering thresholds without a floor-math comment.** Any threshold change without an explanation of the new observed baseline and headroom calculation is a coverage regression in disguise. Pattern: `lowest_observed − (10% of gap_to_100)`. See `docs/testing/THRESHOLDS.md`.

**`--no-verify` to bypass pre-commit.** Pre-commit runs ruff, gitleaks, complexity, yaml/large-file/merge checks. Bypassing it ships problems to CI that could have been caught locally. Use `--no-verify` only in a genuine emergency and fix it before the PR.

**Manually editing the `application.py:0` mypy-baseline entry.** This entry reflects Starlette stub drift between local and CI environments. Editing it to match your local stubs will break CI on the next run. Follow the `git checkout origin/main -- mypy-baseline.txt` pattern in §3c instead.

---

## 6. Where to Find More

| Resource | Path / URL |
|---|---|
| CLAUDE.md — Essential Commands | `/Users/cdeachaval/learn/vianda/kitchen/CLAUDE.md` ("Essential Commands" section) |
| CLAUDE.md — Testing | `/Users/cdeachaval/learn/vianda/kitchen/CLAUDE.md` ("Testing" section) |
| CLAUDE.md — Code Conventions | `/Users/cdeachaval/learn/vianda/kitchen/CLAUDE.md` ("Code Conventions" section) |
| Agent index (all API docs) | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/AGENT_INDEX.md` |
| CI workflow | `/Users/cdeachaval/learn/vianda/kitchen/.github/workflows/ci.yml` |
| Mutation workflow | `/Users/cdeachaval/learn/vianda/kitchen/.github/workflows/mutation.yml` |
| Threshold registry | `/Users/cdeachaval/learn/vianda/kitchen/docs/testing/THRESHOLDS.md` |
| Mutation triage guide | `/Users/cdeachaval/learn/vianda/kitchen/docs/testing/MUTATION_TRIAGE.md` |
| Postman collection conventions | `/Users/cdeachaval/learn/vianda/kitchen/docs/postman/guidelines/LEADS_COLLECTION_CONVENTIONS.md` |
| Code conventions guide | `/Users/cdeachaval/learn/vianda/kitchen/docs/guidelines/CODE_CONVENTIONS.md` |
| Guidelines index | `/Users/cdeachaval/learn/vianda/kitchen/docs/guidelines/` |
