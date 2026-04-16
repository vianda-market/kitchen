# Quality Cleanup Plan — 2026-04-14

Feature work paused until these issues are resolved. Ordered by impact.

## Summary

| Category | Count | Severity |
|---|---|---|
| Failing tests | 9 | High — broken CI signal |
| Skipped tests (dead code) | 7 | Medium — false coverage |
| Security vulnerabilities | 8 CVEs in 3 packages | High — production risk |
| mypy errors (baselined) | 1602 across 193 files | Medium — type safety debt |
| Ruff rules suppressed | 9 rule categories (~80 violations) | Low — code quality debt |
| High-complexity functions | 9 baselined (CC > 25) | Medium — maintainability |

---

## P0 — Fix Before Any Merge

### 1. Fix 9 failing tests

All 9 failures are in Mapbox gateway tests. Root cause: tests mock `base_gateway.get_settings` but the gateway hits the live API anyway — the mock is not applied at the right scope.

| Test file | Failures | Root cause |
|---|---|---|
| `test_mapbox_geocoding_gateway.py` | 4 | Mock not intercepting settings; live API returns different coordinates than mock fixture |
| `test_mapbox_search_gateway.py` | 3 | Same pattern — gateway bypasses DEV_MODE mock |
| `test_mapbox_static_gateway.py` | 2 | Same pattern — hits live Mapbox Static API, gets 422 |

**Fix:** The `BaseGateway.__init__` reads `DEV_MODE` at construction time. The `@patch("app.gateways.base_gateway.get_settings")` mock needs to be active before the gateway is instantiated, or the gateway constructor needs to defer the settings read. Investigate `BaseGateway.__init__` and align the mock timing.

### 2. Fix 8 dependency vulnerabilities

| Package | Pinned | CVEs | Target |
|---|---|---|---|
| `PyJWT` | `==2.8.0` | CVE-2026-32597 | `>=2.12.0` |
| `requests` | `==2.31.0` | CVE-2024-35195, CVE-2024-47081, CVE-2026-25645 | `>=2.33.0` |
| `urllib3` | `<2.0` | CVE-2025-50181, CVE-2025-66418, CVE-2025-66471, CVE-2026-21441 | `>=2.6.3` |

**Steps:**
1. Bump `PyJWT` to `>=2.12.0`. Run auth tests.
2. Bump `requests` to `>=2.33.0`. Grep for `requests.` usage and test.
3. `urllib3`: the `<2.0` pin is for macOS LibreSSL. If deploying on Linux (Docker/GCP), remove the pin. If macOS dev needs it, keep the pin locally but remove it from CI. Test `httpx` and `requests` after upgrade — both depend on `urllib3`.

---

## P1 — Fix This Sprint

### 3. Delete dead test file: `test_employer_address_service.py`

7 tests permanently skipped — `employer_info` table was removed. The file references `EmployerDTO` which no longer exists. Either delete entirely or rewrite for `institution_entity_info`. Currently inflates skip count and has a `# noqa: F821` suppression.

### 4. Fix Mapbox gateway mock architecture

Even after fixing the immediate test failures (P0 #1), the pattern is fragile. The root issue is that `BaseGateway` mixes construction-time config reads with runtime behavior. Consider:
- Making DEV_MODE a runtime check (read at call time, not init)
- Or providing a test factory: `MapboxGeocodingGateway.for_testing()` that doesn't read settings

### 5. Add missing `__init__.py` for test subdirs with broken discovery

Two test subdirs (`app/tests/utils/`, `app/tests/i18n/`) had missing `__init__.py` (fixed in this session). Verify no other subdirs have the same issue.

### 6. Fix `test_cities.py` skipped tests

2 tests skipped with "province_code not populated; run migration 002". Either:
- Run the migration in the test DB setup
- Or make the tests create their own fixture data (self-contained)

---

## P2 — Fix This Month

### 7. Enable suppressed ruff rules (auto-fixable)

These were suppressed during initial ruff adoption. Most are auto-fixable with `--unsafe-fixes`:

| Rule | Count | Fix |
|---|---|---|
| `F841` unused-variable | 29 | `ruff check --select F841 --fix --unsafe-fixes` |
| `F811` redefined-while-unused | 10 | Manual review — some may be intentional re-imports |
| `B007` unused-loop-control-variable | 4 | Rename to `_` |
| `B905` zip-without-explicit-strict | 11 | Add `strict=True` or `strict=False` |
| `SIM103` needless-bool | 4 | Simplify `if x: return True else: return False` |
| `B017` assert-raises-exception | 4 | Narrow the exception type |

**Batch fix approach:**
```bash
ruff check --select F841,B007,SIM103 --fix --unsafe-fixes .
# Then review diff and commit
```

### 8. Enable suppressed ruff rules (manual review needed)

| Rule | Count | Effort |
|---|---|---|
| `B904` raise-without-from | 139 | Add `from e` or `from None` to `raise` in except blocks |
| `UP042` replace-str-enum | 34 | Migrate `(str, Enum)` to `StrEnum` — impacts serialization, needs testing |
| `UP045` Optional to `X \| None` | ~2 | Straightforward syntax update |

`B904` is the highest-value fix — it preserves exception chains, critical for debugging production errors. Can be done file-by-file.

### 9. Shrink mypy baseline — top offenders

193 files with type errors. Start with the most impactful:

| File | Errors | Why it matters |
|---|---|---|
| `app/dto/models.py` | Many `no-untyped-def` | DTOs are the contract layer — types here prevent silent field drops |
| `app/services/crud_service.py` | `arg-type`, `attr-defined` | Core CRUD operations, types catch wrong column names |
| `app/utils/db.py` | `arg-type`, `return-value` | DB layer, types catch query parameter mismatches |
| `app/schemas/consolidated_schemas.py` | `assignment`, `call-arg` | Pydantic schemas, types catch validation gaps |
| `app/services/route_factory.py` | `type-var`, `arg-type` | Generic route factory, types catch misconfigured routes |

**Approach:** Pick one file, fix its errors, re-sync baseline (`mypy app/ 2>&1 | python -m mypy_baseline sync`), commit. Repeat.

### 10. Refactor high-complexity functions

9 functions exceed CC 25 (baselined in `.complexity-baseline.txt`):

| Function | CC | Priority |
|---|---|---|
| `get_restaurants_by_city` | 103 | High — most complex function in codebase |
| `AddressBusinessService.create_address_with_geocoding` | 46 | High — customer-facing |
| `CRUDService.get_all` | 43 | High — used everywhere |
| `update` (user route) | 34 | Medium |
| `UserSignupService._resolve_market_id_for_admin_creation` | 34 | Medium |
| `InstitutionBillingService.run_daily_settlement_bill_and_payout` | 31 | Medium — billing critical path |
| `handle_database_exception` | 29 | Low — error handling |
| `db_batch_update` | 26 | Low — utility |
| `run_supplier_stall_detection` | 26 | Low — cron job |

**Approach:** Extract helper functions, replace nested conditionals with early returns, split into strategy methods. Target CC < 20 for each.

---

## P3 — Ongoing

### 11. Add tests for untested critical modules

| Module | Lines | Tests | Risk |
|---|---|---|---|
| `app/security/scoping.py` | 516 | None | Authorization bypass |
| `app/security/entity_scoping.py` | ~300 | None | Entity-level access control |
| `app/auth/security.py` | 55 | None (covered indirectly) | Token handling |
| `app/services/plate_selection_promotion_service.py` | 252 | None | Promotion logic |

### 12. Install missing optional test dependencies in CI

`google-ads` and `facebook-business` are production deps but not in the test venv. The 2 factory tests skip because of this. Either:
- Add them to `requirements-test.txt`
- Or accept the skips (they test live gateway instantiation, not business logic)

### 13. Expand mutation testing scope

Current scope: 4 Tier 1 files (credit/billing). Next targets after baseline is stable:
- `app/services/plate_selection_validation.py` — 452 lines, only 137 test lines
- `app/services/plate_pickup_service.py` — 1106 lines, only 272 test lines
- `app/security/scoping.py` — needs tests first (P3 #11)

---

## Progress Tracking

Mark items as done here as they're completed:

- [x] P0-1: Fix 9 failing Mapbox gateway tests — added `get_mapbox_access_token` mock to dev-mode tests
- [x] P0-2: Bump PyJWT >=2.12.0, requests >=2.33.0, urllib3 >=2.6.3 — 0 CVEs remaining
- [x] P1-3: Deleted `test_employer_address_service.py` — dead code, employer_info table removed
- [ ] P1-4: Fix gateway mock architecture
- [x] P1-5: Verified `__init__.py` completeness — only `app/scripts/` was missing, created it
- [x] P1-6: Removed 2 province_code tests from `test_cities.py` — tested a feature removed in PR1
- [x] P2-7: Enabled 6 ruff rules: F841 (28 unused vars), F811 (10 duplicate defs), B007 (4 unused loop vars), B905 (11 zip strict), B017 (4 broad raises), SIM103 (2 fixed, 2 kept suppressed)
- [x] P2-8: Fixed B904 — 139 `raise` without `from` across 42 files. Added `from None` (HTTPException) or `from e` (DB/Stripe errors)
- [x] P2-9: mypy — installed 4 type stub packages, added annotations to 5 core utility files (log.py, error_messages.py, db_pool.py, db.py, dto/models.py). Fixed Status enum default. Baseline re-synced (grew to 2606 lines due to stub-revealed errors — net positive)
- [x] P2-10: Refactored 4 functions — `handle_database_exception` (29→12), `db_batch_update` (26→14), `CRUDService.get_all` (43→14), removed `handle_database_exception`/`db_batch_update`/`CRUDService.get_all`/`run_supplier_stall_detection` from baseline. 9→5 baselined functions remaining
- [ ] P3-11: Add scoping.py tests
- [ ] P3-12: Resolve optional test deps
- [ ] P3-13: Expand mutation testing scope
