# Quality Tooling Investment Plan

## Current State

| Tool | Status |
|---|---|
| **pytest** | Configured with markers, strict mode, ~90+ test files |
| **pytest-cov** | Enabled, `--cov-fail-under=80` set (but unclear if that threshold is actually hit) |
| **black** | In requirements-test.txt, but no config and no pre-commit hook |
| **flake8** | In requirements-test.txt, no `.flake8` config |
| **mypy** | In requirements-test.txt, no `mypy.ini` or `pyproject.toml` config |
| **CI** | No GitHub Actions workflows — nothing enforces any of this |

## Investment Opportunities (low to high effort)

### 1. Linting & Formatting — Low effort, high signal
- **black + flake8 + isort** are already in deps but not configured or enforced. Adding a `pyproject.toml` with configs and a **pre-commit hook** would make them real. You could also consider **ruff** as a single replacement for flake8+isort+black — faster and simpler config.
- ROI: immediate, prevents style drift across agents/contributors.

### 2. Type Checking (mypy) — Medium effort
- mypy is listed but unconfigured. A `pyproject.toml` section with `--strict` on new code (gradual adoption via `per-module` overrides) would catch real bugs — especially UUID/str mismatches and missing DTO fields, which CLAUDE.md already warns about.
- ROI: high for this codebase — the DTO/schema sync discipline is the #1 source of silent bugs.

### 3. Dependency Security — Low effort
- **pip-audit** or **safety** — scans `requirements.txt` for known CVEs. One command, no config. You pin a lot of versions, which is good, but some pins are old (e.g., `requests==2.31.0`).
- **pip-licenses** — checks license compliance if that matters for your business.
- ROI: cheap insurance, especially before going to production.

### 4. Acceptance / Integration Testing — Medium-high effort
- You already have Postman collections as your acceptance layer for services/routes. The gap is **automated execution** — `newman` (Postman CLI) could run collections in CI against a test DB.
- Alternatively, a thin `pytest` acceptance suite using `httpx.AsyncClient` against a real DB (you already have `test_integration.py`) could complement Postman without duplicating it.
- ROI: depends on how often Postman collections are actually run today.

### 5. Mutation Testing — High effort, niche ROI
- **mutmut** is the standard Python mutation tester. It modifies your code and checks if tests catch the change. Very slow on large codebases.
- Practical only if scoped to critical paths (billing, subscription logic, credit validation). Running it on the full codebase would take hours.
- ROI: best for high-stakes business logic where "tests pass but the code is wrong" is a real fear.

### 6. C.R.A.P. (Change Risk Anti-Patterns) — Medium effort
- Combines **cyclomatic complexity + coverage**. No off-the-shelf Python tool does C.R.A.P. natively, but you can approximate it:
  - **radon** for cyclomatic complexity scores
  - **pytest-cov** for coverage (already have it)
  - A small script to correlate them
- **wily** tracks complexity metrics over time (per-commit), which is arguably more useful than a one-shot C.R.A.P. score.
- ROI: good for identifying which files are both complex and under-tested.

### 7. CI Pipeline — The Multiplier
None of the above matters much without CI enforcement. A single GitHub Actions workflow running `ruff check`, `mypy`, `pytest --cov`, and `pip-audit` on every PR would be the highest-leverage investment. Everything else is just local discipline without it.

## Recommended Priority

1. ~~**CI pipeline + ruff + pip-audit**~~ DONE — `.github/workflows/ci.yml`, `pyproject.toml`
2. ~~**mypy strict-on-new-code**~~ DONE — strict config + `mypy-baseline.txt` (1602 existing errors baselined, new code must pass)
3. ~~**newman in CI**~~ DONE — `scripts/run_newman.sh` + CI job with Postgres service container, runs all 17 collections
4. ~~**radon/wily**~~ DONE — CI complexity gate (max CC 25) + `.complexity-baseline.txt` (6 functions baselined), wily for local trend tracking
5. ~~**mutmut**~~ DONE — scoped to Tier 1 critical business logic (credit validation, credit loading, discretionary credits, institution billing). Weekly CI + manual trigger.
