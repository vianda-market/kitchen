# Kitchen — Essential Commands

Quick-reference for every command an executor or contributor needs. CLAUDE.md links here instead of inlining.

## Local CI gate sweep

| Command | Purpose |
|---|---|
| `bash scripts/ci-local.sh` | Full local mirror of every required CI gate. Run before every push. |
| `bash scripts/ci-local.sh --fast` | Skips pytest + newman; runs lint/format/typecheck-style gates. |
| `bash scripts/ci-local.sh --gate <name>` | Run a single gate (e.g. `--gate newman`, `--gate mypy`). |

## Database

| Command | Purpose |
|---|---|
| `bash app/db/migrate.sh` | Apply migrations incrementally — preserves data. |
| `bash app/db/build_kitchen_db.sh` | Full tear-down + rebuild. Fresh environments only — never on a DB with test data you want to keep. |

## Tests

| Command | Purpose |
|---|---|
| `pytest app/tests/` | Run full pytest suite. |
| `pytest --collect-only -q --ignore=app/tests/database` | Test collection check (skips DB-bound tests). |
| `pytest --cov=app --cov-report=xml --cov-fail-under=0 && diff-cover coverage.xml --compare-branch=origin/main --fail-under=80` | Diff-coverage gate. |
| `pytest --cov=app --cov-report=xml --cov-fail-under=0 && python scripts/analyze_crap.py` | CRAP analysis (ad-hoc, not a gate). |
| `bash scripts/run_dev_quiet.sh` | Start the API for Newman runs. |
| `./scripts/run_newman.sh <NNN>` | Run a single Postman collection by prefix. |
| `./scripts/run_newman.sh` | Run the full Postman suite. **Never run in parallel with another invocation — port `:8000` is shared.** |

## Lint / type / quality gates

| Command | Purpose |
|---|---|
| `python3 -c "from application import app; print('OK')"` | Import smoke check. |
| `gitleaks detect --source . --verbose` | Secret scan (allowlist: `.gitleaksignore`). |
| `bash scripts/check_maintainability.sh` | Maintainability gate (fails if MI drops >5% on changed files vs `origin/main`). |
| `bash scripts/check_vulture.sh` | Dead-code gate (baseline: `.vulture-baseline.txt`; update with `--update`). |
| `bash scripts/check_complexity_strict.sh` | Strict complexity gate (CC ≤ 15 on changed files; repo-wide CC ≤ 25 is separate). |
| `lint-imports` | Layer-boundary check (contracts in `.importlinter`). |
| `bandit -r app/ -lll --exclude app/tests -b .bandit-baseline.json` | Security lint. |
| `bash scripts/check_sqlfluff.sh` | SQL lint (config: `.sqlfluff`; baseline: `.sqlfluff-baseline.txt`). |
| `pip install pip-licenses && python scripts/check_licenses.py` | License check (allowlist: MIT/Apache/BSD/ISC/MPL/PSF). |

## Pre-commit hooks

| Command | Purpose |
|---|---|
| `pip install pre-commit && pre-commit install` | One-time setup. Installs ruff, gitleaks, complexity, yaml/large-file/merge checks. |
