# CI GitHub Setup — Manual Steps

## 1. Enable Branch Protection on `main`

Go to **Settings > Branches > Add branch protection rule**:

- Branch name pattern: `main`
- Check **Require a pull request before merging**
- Check **Require status checks to pass before merging**
- Under required status checks, search and add:
  - `Lint & Format`
  - `Type Check`
  - `Dependency Audit`
  - `Unit Tests`
  - `Complexity Gate`
  - `Acceptance Tests (Newman)` (optional — may want to start as non-required while stabilizing)
- Check **Require branches to be up to date before merging**
- Save

## 2. Verify Python 3.14 Support

The CI uses `python-version: "3.14"` with `allow-prereleases: true`. If 3.14 is not yet GA on `actions/setup-python`, you may need to temporarily lower to `"3.13"` if the workflow fails on setup. Check the first run and adjust if needed.

## 3. mypy Baseline Workflow

mypy is configured with strict settings in `pyproject.toml`. Existing errors (1602 across 194 files) are tracked in `mypy-baseline.txt`. CI only fails on **new** type errors.

**How it works:**
- `mypy app/` runs and pipes output to `mypy_baseline filter`
- Errors matching the baseline are suppressed; only new errors cause failure
- New code must be fully typed (`disallow_untyped_defs = true`)

**To fix an existing baseline error:**
1. Fix the type error in code
2. Re-sync the baseline: `mypy app/ 2>&1 | python -m mypy_baseline sync`
3. Commit both the code fix and the updated `mypy-baseline.txt`

**Shrinking the baseline over time:**
Run `python -m mypy_baseline top` to see which files have the most errors — good targets for incremental cleanup.

## 4. Complexity Gate & Wily Trend Tracking

**CI gate (`Complexity Gate` job):**
- Runs `radon cc` on changed files (PRs) or all files (push to main)
- Fails if any function exceeds cyclomatic complexity 25 (grade E+)
- Existing high-complexity functions are baselined in `.complexity-baseline.txt`
- To baseline a function temporarily: add `file.py:function_name` to the file
- To remove from baseline: refactor the function, then delete the line

**Current baseline (6 functions at E/F grade):**

| Function | CC | File |
|---|---|---|
| `get_restaurants_by_city` | 103 (F) | `app/services/restaurant_explorer_service.py` |
| `AddressBusinessService.create_address_with_geocoding` | 46 (F) | `app/services/address_service.py` |
| `CRUDService.get_all` | 43 (F) | `app/services/crud_service.py` |
| `update` (user route) | 34 (E) | `app/routes/user.py` |
| `UserSignupService._resolve_market_id_for_admin_creation` | 34 (E) | `app/services/user_signup_service.py` |
| `InstitutionBillingService.run_daily_settlement_bill_and_payout` | 31 (E) | `app/services/billing/institution_billing.py` |

**Wily (local trend tracking — not in CI):**

wily tracks complexity metrics over git history. It's a local analysis tool, not a CI gate.

```bash
# First time: build the index (analyzes last 50 commits)
wily build app/

# See complexity ranking of worst files
wily rank app/ --metric cyclomatic.complexity

# See how a specific file's complexity changed over time
wily report app/services/restaurant_explorer_service.py

# Compare current branch vs. main (good before a PR)
wily diff app/ -r main
```

## 5. Fix Known Dependency Vulnerabilities

`pip-audit` found **8 vulnerabilities** in 3 packages (as of 2026-04-14):

| Package | Current | CVEs | Fix Version |
|---|---|---|---|
| **pyjwt** | 2.8.0 | CVE-2026-32597 | >= 2.12.0 |
| **requests** | 2.31.0 | CVE-2024-35195, CVE-2024-47081, CVE-2026-25645 | >= 2.33.0 |
| **urllib3** | 1.26.20 | CVE-2025-50181, CVE-2025-66418, CVE-2025-66471, CVE-2026-21441 | >= 2.6.3 |

**Action required before CI will pass the Dependency Audit job:**

1. **pyjwt**: Bump `PyJWT==2.8.0` to `PyJWT>=2.12.0` in `requirements.txt`. Test auth flows after upgrade.
2. **requests**: Bump `requests==2.31.0` to `requests>=2.33.0`. Test any code that uses `requests` directly (external API calls).
3. **urllib3**: The pin `urllib3<2.0` exists for LibreSSL compatibility on macOS. Options:
   - If deploying on Linux (Docker/GCP): remove the pin and let it upgrade to 2.6+
   - If macOS dev still needs LibreSSL compat: keep the pin and add an ignore entry in CI
   - To ignore in CI, add `--ignore-vuln CVE-ID` flags or create a `pip-audit.toml`

**Temporary workaround** to unblock CI while you plan the upgrades — add ignores to the workflow:
```yaml
- name: Audit production dependencies
  run: pip-audit -r requirements.txt --ignore-vuln CVE-2026-32597 --ignore-vuln CVE-2024-35195 ...
```
But don't leave these indefinitely — track them as tech debt.

## 6. Newman Acceptance Tests

The `Acceptance Tests (Newman)` CI job runs all 17 Postman collections against a live server with a seeded PostgreSQL database.

**How it works in CI:**
1. PostgreSQL 16 service container starts with user/pass `kitchen/kitchen`
2. `build_kitchen_db.sh` creates schema + seeds reference data (including `superadmin/SuperAdmin1`)
3. `uvicorn` starts the app in `DEV_MODE=true` (mock payment, mock geocoding)
4. `scripts/run_newman.sh` runs every `.json` collection in `docs/postman/collections/`

**Running locally:**
```bash
# Install newman
npm install -g newman

# Make sure server is running and DB is seeded, then:
bash scripts/run_newman.sh              # all collections
bash scripts/run_newman.sh 003 006      # specific collections by prefix
```

**If the `build_kitchen_db.sh` script needs adjustments for CI:**
The script currently connects using env vars `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT`. Verify it works with the CI values set in the workflow. If the script uses `psql` with defaults, you may need to set `PGHOST`, `PGUSER`, etc. — check the first CI run and fix as needed.

**Collections that may fail in CI:**
Some collections may depend on:
- External APIs (Google Maps, Mapbox) — should be mocked in `DEV_MODE`
- Stripe test keys — mocked when `PAYMENT_PROVIDER=mock`
- Pre-existing data beyond seed — these collections may need fixes to be fully self-contained

Start with the acceptance job as **non-required** in branch protection until you've verified which collections pass in CI. Then promote to required.

## 7. Mutation Testing (Weekly)

Mutation testing runs as a **separate workflow** (`.github/workflows/mutation.yml`), not on every PR. It runs weekly on Sunday midnight UTC and can be triggered manually from the Actions tab.

**Scope:** Tier 1 critical business logic only (4 files, ~935 lines):
- `app/services/credit_validation_service.py` — negative balance guards
- `app/services/credit_loading_service.py` — credit account loading
- `app/services/discretionary_service.py` — manual credit adjustments
- `app/services/billing/institution_billing.py` — settlement and payouts

**Running locally:**
```bash
bash scripts/run_mutation_tests.sh           # full run (10-30 min)
bash scripts/run_mutation_tests.sh --quick   # time estimate only
mutmut show <mutant_name>                    # inspect a survivor
mutmut browse                                # interactive TUI
```

**When a mutant survives:**
It means a code mutation (e.g., changing `>=` to `>`, `+` to `-`) was not caught by any test. This is a test gap — add a test that asserts the exact behavior the mutant altered.

**Expanding scope later:**
Add files to `paths_to_mutate` in `pyproject.toml`. Good next candidates:
- `app/services/vianda_selection_validation.py` (Tier 2 — under-tested)
- `app/services/vianda_pickup_service.py` (Tier 2 — under-tested)
- `app/security/scoping.py` (Tier 3 — needs tests first)

## 8. Optional: Add Integration Test Job (later)

When ready to run pytest DB-dependent tests in CI, add a job similar to the acceptance job but running `pytest -m "integration or database"` instead of newman. The PostgreSQL service container pattern is already established in the acceptance job.
