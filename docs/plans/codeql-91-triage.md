---
status: triage
issue: kitchen#91
date: 2026-04-26
---

# CodeQL #91 Triage — 30 Open Security Findings

30 findings as of the issue snapshot: 4 SQL-injection, 4 path-injection, 14 clear-text-logging, 8 stack-trace-exposure.

Live alert counts after `git pull --ff-only main`: SQL-injection=4, path-injection=4, clear-text-logging=14, stack-trace-exposure=115. The 115 vs 8 discrepancy is a scope creep from subsequent commits adding more route files that use `handle_business_operation`. The issue's Phase 1 targets the original 8; the 107 additional stack-trace alerts are follow-on work not scoped to this triage.

---

## 1. SQL Injection (4 alerts) — `app/utils/db.py`

All 4 alerts fire inside three shared SQL builder helpers: `_build_insert_sql`, `_build_update_sql`, `_build_delete_sql`. Each constructs a SQL string via f-string interpolation of `table` (table name) and `column` dict keys.

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 146 | `app/utils/db.py:413` | `py/sql-injection` | FALSE-POSITIVE | `cursor.execute(sql, values)` inside `db_insert`; `sql` is built from `table`/column names sourced from internal service callers (hardcoded strings in `crud_service.py`), never from HTTP input. Values are always parameterized via `%s`. |
| 147 | `app/utils/db.py:605` | `py/sql-injection` | FALSE-POSITIVE | `cursor.execute(sql, values)` inside `db_update`; same pattern — table/column names are hardcoded internal identifiers, values parameterized. |
| 148 | `app/utils/db.py:760` | `py/sql-injection` | FALSE-POSITIVE | `cursor.execute(query, values)` inside `db_read`; `query` is always a full SQL string built in service layer with parameterized placeholders, never directly assembled from HTTP input. |
| 149 | `app/utils/db.py:762` | `py/sql-injection` | FALSE-POSITIVE | `cursor.execute(query)` (no-values branch) inside `db_read`; `query` is a fully literal SQL string from internal callers. |

**Exploitability:** None. Table names and column names are sourced exclusively from hardcoded Python dicts (`PRIMARY_KEY_MAPPING`, `CRUDService.table_name`, explicit service-layer strings). No HTTP input reaches `table` or column keys. Values are always passed via psycopg2's parameterized `%s` mechanism.

**Recommended disposition:** Add `# nosec B608` comments with one-line rationale at each `cursor.execute` call site, or switch `_build_insert_sql` / `_build_update_sql` / `_build_delete_sql` to use `psycopg2.sql.SQL` + `sql.Identifier()` for table/column names (correct pattern, eliminates the finding entirely). The `psycopg2.sql` migration is the cleaner long-term fix but requires updating ~3 builder functions; `# nosec` + a code comment is acceptable if the team accepts static-analysis suppression.

---

## 2. Path Injection (4 alerts) — `app/services/product_image_service.py`

All 4 fire in `ProductImageService` local-storage mode (only active when `GCS_SUPPLIER_BUCKET` is not set, i.e., dev/test environments). The GCS branch (production) routes through `gcs.upload_product_image()` and never touches `os.path`.

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 142 | `app/services/product_image_service.py:123` | `py/path-injection` | FALSE-POSITIVE | `os.path.join(storage_dir, filename)` where `filename = f"{product_id}.{ext}"`. `product_id` is a FastAPI `UUID` typed param — validated to 36-char UUID on ingress. `ext` is `self.output_format.lower()` from the env var `PRODUCT_IMAGE_FORMAT` (default `"PNG"`). Neither is user-controlled strings. |
| 143 | `app/services/product_image_service.py:126` | `py/path-injection` | FALSE-POSITIVE | Same function, `os.path.join(storage_dir, thumb_filename)`. `thumb_filename = f"{product_id}_thumb.{ext}"`. Same analysis. |
| 144 | `app/services/product_image_service.py:161` | `py/path-injection` | JUDGMENT-PER-FINDING | `absolute_path = p if os.path.isabs(p) else os.path.abspath(p)`. `p` is `storage_path` from the DB, which was written by the same service at upload time. A compromised DB row could theoretically contain an arbitrary path. Severity is low (local dev mode only; production uses GCS); add `pathlib.Path(p).resolve()` + a confine-to-base check. |
| 145 | `app/services/product_image_service.py:162` | `py/path-injection` | JUDGMENT-PER-FINDING | `os.remove(absolute_path)` — downstream sink of alert 144. Same analysis. Fix: add `assert absolute_path.startswith(str(base_dir))` after resolving with `pathlib.Path.resolve()`. |

**Exploitability:**
- Alerts 142-143: Not exploitable. `UUID` type enforcement eliminates path traversal. Dismiss as false positive.
- Alerts 144-145: Theoretical only. Requires a compromised DB record; no direct HTTP vector. Only active in local dev mode. Low urgency but should be fixed before enabling local mode in any shared environment.

---

## 3. Clear-Text Logging of Sensitive Data (14 alerts)

### Sub-group A: `app/utils/log.py` (5 alerts) — wrapper functions themselves

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 131 | `app/utils/log.py:32` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.info(message)` inside `log_info()` wrapper. CodeQL traces any sensitive data that flows through as a call-site message. The wrapper is not the problem; the call sites are. |
| 132 | `app/utils/log.py:39` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.warning(message)` inside `log_warning()`. Same as above. |
| 133 | `app/utils/log.py:46` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.error(message)` inside `log_error()`. Same as above. |
| 134 | `app/utils/log.py:75` | `py/clear-text-logging-sensitive-data` | JUDGMENT-PER-FINDING | `logger.info(f"[PasswordRecovery] {message}")` inside `log_password_recovery_debug()`. Only active when `DEBUG_PASSWORD_RECOVERY=1`; used for debugging password-recovery flow. The `message` caller-supplied content may include username/email. Acceptable in dev; should be gated and documented. Add a docstring warning that messages must not include raw passwords. |
| 135 | `app/utils/log.py:134` | `py/clear-text-logging-sensitive-data` | JUDGMENT-PER-FINDING | `logger.info(f"[EmployerAssign] {message}")` inside `log_employer_assign_debug()`. Same pattern — debug-gated, env-controlled. Verify call sites don't log raw tokens or passwords. |

### Sub-group B: `application.py` (1 alert)

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 128 | `application.py:133` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.info(f"[EmployerAssign] LOG_EMPLOYER_ASSIGN: os.environ={repr(_env_val)} config={_cfg_val} -> debug=...")`. Logs whether a feature-flag env var is `"1"` or `"true"`. Not a secret; it is a debug-flag toggle value. No credential, PII, or secret is present. |

### Sub-group C: `app/utils/country.py` (1 alert)

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 129 | `app/utils/country.py:130` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.info("country_code alpha-3 converted to alpha-2: %s -> %s", s, country.alpha_2)`. Logs ISO country codes (e.g. `"ARG" -> "AR"`). Not sensitive data by any definition; CodeQL flags it because the value flows from a parameter named `value`. |

### Sub-group D: `app/core/gcp_secrets.py` (1 alert) — highest priority

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 130 | `app/core/gcp_secrets.py:65` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE (but verify) | `logger.info("gcp_secret_fetched", extra={"secret_id": secret_id})`. Logs the **name** of the secret (e.g. `"STRIPE_SECRET_KEY"`), NOT the secret value. The actual `value` variable (the decrypted payload) is returned but not logged. The `extra` dict contains only `secret_id`. Confirm by inspecting that `value` (line 63) never appears in a log call. If confirmed, add an inline comment: `# logs secret name only, never value`. |

### Sub-group E: `app/services/market_service.py` (6 alerts)

All 6 are in `MarketService.get_by_id()` and `get_by_country_code()`. CodeQL traces `market_id` (UUID) and `country_code` (ISO 2-char string) as "sensitive" because they originate from request params.

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 136 | `app/services/market_service.py:284` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.info(f"Retrieved market: {market['country_name']} ({market_id})")`. Country name + market UUID in an INFO log; operational data, not PII or secrets. |
| 137 | `app/services/market_service.py:286` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.warning(f"Market not found: {market_id}")`. UUID in a WARNING log. |
| 138 | `app/services/market_service.py:290` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.error(f"Error retrieving market {market_id}: {str(e)}")`. UUID + error string. `str(e)` here could theoretically contain DB connection details on psycopg2 errors — worth replacing with a sanitized `"DB error"` string. |
| 139 | `app/services/market_service.py:323` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.info(f"Retrieved market by country code: {market['country_name']} ({country_code})")`. ISO country code in INFO. |
| 140 | `app/services/market_service.py:325` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.warning(f"Market not found for country code: {country_code}")`. ISO country code. |
| 141 | `app/services/market_service.py:329` | `py/clear-text-logging-sensitive-data` | FALSE-POSITIVE | `logger.error(f"Error retrieving market by country code {country_code}: {str(e)}")`. Same `str(e)` concern as alert 138. |

**Secondary finding in market_service.py** (not a CodeQL alert but a real exposure): lines 291 and 330 raise `HTTPException(detail=f"Error retrieving market: {str(e)}")`. This *does* expose raw psycopg2 error strings to HTTP callers. This is a real data-exposure bug that should be fixed in the same PR — replace `detail=str(e)` with a generic message and log the full error internally.

---

## 4. Stack-Trace Exposure (8 alerts per issue scope)

All 8 are at return/response lines inside `handle_business_operation` call sites. The issue notes that `handle_business_operation` (in `app/services/error_handling.py:305-348`) catches all non-`HTTPException` errors, logs the full traceback internally, and raises `envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")` — no trace in the response. CodeQL's data-flow analysis traces the exception object through the wrapper and flags the return sink.

| # | File:line | Rule | Bucket | Proposed fix |
|---|-----------|------|--------|--------------|
| 51 | `app/routes/national_holidays.py:63` (issue: 137) | `py/stack-trace-exposure` | FALSE-POSITIVE | Sink is `return result` after `handle_business_operation`. Exception trace is logged internally; response is sanitized. |
| 151 | `app/routes/vianda_pickup.py:233` (issue: 202) | `py/stack-trace-exposure` | FALSE-POSITIVE | Same pattern. `set_pagination_headers(response, result); return result`. |
| 121 | `app/routes/user.py:1085` (issue: 1080) | `py/stack-trace-exposure` | FALSE-POSITIVE | `return handle_business_operation(_update_user, ...)`. Wrapper sanitizes. |
| 123 | `app/routes/user.py:1251` (issue: 1247) | `py/stack-trace-exposure` | FALSE-POSITIVE | `return handle_business_operation(_delete_user, ...)`. Wrapper sanitizes. |
| 124 | `app/routes/workplace_group.py:83` (issue: 81) | `py/stack-trace-exposure` | FALSE-POSITIVE | `return handle_business_operation(_create, ...)`. Wrapper sanitizes. |
| 125 | `app/routes/workplace_group.py:147` (issue: 145) | `py/stack-trace-exposure` | FALSE-POSITIVE | `return handle_business_operation(_create_address, ...)`. |
| 126 | `app/routes/workplace_group.py:216` (issue: 214) | `py/stack-trace-exposure` | FALSE-POSITIVE | `return handle_business_operation(_update, ...)`. |
| 127 | `app/routes/workplace_group.py:258` (issue: 256) | `py/stack-trace-exposure` | FALSE-POSITIVE | `return handle_business_operation(_bulk_create, ...)`. |

**Exploitability:** None. `handle_business_operation` provably does not forward exception details to the HTTP response. The correct long-term fix to silence these is to add a `# nosec` or a CodeQL suppression comment at the wrapper's `raise envelope_exception(...)` line, or to annotate the wrapper function signature in CodeQL's model. Alternatively, teaching CodeQL via a `.codeql/` custom model that `handle_business_operation` is a sanitizer would close all 115 open alerts in one edit.

**Note on 115 vs 8:** The 107 additional open stack-trace alerts (not in the issue scope) are all the same `handle_business_operation` pattern in other route files added after the issue was filed. They are mechanically identical — all false positives by the same reasoning. A single CodeQL suppression or sanitizer annotation would close all 115.

---

## 5. PR Plan

### Recommended split

**Phase 1 — Stack-trace sweep (all 115, not just the 8 in the issue)** — MECHANICAL-SAFE, 1 PR

Add a CodeQL suppression at the single sink line in `handle_business_operation` (`app/services/error_handling.py:348`). This closes all 115 open stack-trace alerts in one edit. Alternative: add `# codeql[py/stack-trace-exposure]` suppression comments at the 8 issue-scoped sink lines only, deferring the other 107 to a follow-on sweep. Either way: one PR, no functional change, zero risk.

Estimated effort: 30 minutes. Do this first; it unblocks the CodeQL gate fastest.

**Phase 2 — Clear-text-logging audit** — MIXED, 1 PR

- Dismiss all alerts where the logged value is a UUID, ISO country code, or feature-flag toggle (alerts 128, 129, 131-133, 136-137, 139-140): add `# codeql[py/clear-text-logging-sensitive-data]` with one-line rationale.
- For alerts 138 and 141 (`str(e)` in `logger.error` in `market_service.py`): replace `str(e)` with a generic message string and log the error via `log_error(f"... error details: {e}")` at `ERROR` level (still logging, but now explicit). Also fix the paired `HTTPException(detail=str(e))` calls on lines 291/330 — replace with `detail="Internal error retrieving market"`.
- For alerts 130 (`gcp_secrets.py:65`): verify that the `value` variable (the actual secret) is not logged anywhere nearby; add inline comment confirming only secret name is logged. Dismiss as false positive.
- For alerts 134-135 (`log.py:75,134`): add docstring warnings on `log_password_recovery_debug` and `log_employer_assign_debug` that call-site messages must not include raw credentials. No code change needed.

Estimated effort: 1 hour. No behavioral change for correctly-implemented call sites. One real fix: `market_service.py` HTTP error responses.

**Phase 3 — Path injection** — JUDGMENT, 1 PR

- Alerts 142-143 (lines 123, 126): add `# codeql[py/path-injection]` with comment "product_id is FastAPI UUID typed param, path traversal impossible". False positives.
- Alerts 144-145 (lines 161, 162): add a `pathlib.Path.resolve()` + confine-to-base check in `delete_image()`:
  ```python
  base_dir = pathlib.Path(self.local_storage_path).resolve()
  resolved = pathlib.Path(p).resolve()
  if not str(resolved).startswith(str(base_dir)):
      log_warning(f"Path traversal blocked: {p}")
      continue
  ```
  This is a real hardening even though the exploit path requires a compromised DB record.

Estimated effort: 1 hour.

**Phase 4 — SQL injection** — JUDGMENT, 1 PR

Two options:
- **Option A (suppression):** Add `# nosec B608` + `# codeql[py/sql-injection]` at `cursor.execute` in `_build_insert_sql`, `_build_update_sql`, and `db_read`. Each comment should explain that `table`/column names are internal-only identifiers. Fastest path.
- **Option B (correct pattern):** Migrate `_build_insert_sql` and `_build_update_sql` to use `psycopg2.sql.SQL` + `sql.Identifier()` for table name and column names. This is the proper fix, eliminates the entire finding class, and documents the intent in code. More invasive (affects ~3 builder functions + their tests) but permanently safer.

Recommendation: Option B for `_build_insert_sql` and `_build_update_sql` (they are shared by all CRUD operations); Option A `# codeql` suppression for `db_read` (its `query` is always a full SQL literal built by service callers, not a dynamic identifier). One PR.

Estimated effort: 2–3 hours for Option B on the builders.

### Suggested order

1. **Phase 1** (stack-trace, ~30 min) — unblocks CodeQL gate immediately; 8–115 alerts closed.
2. **Phase 2** (clear-text-logging, ~1 hr) — 14 high-severity alerts; mostly false positives + one real `market_service.py` HTTP response fix.
3. **Phase 3** (path injection, ~1 hr) — 4 high-severity; 2 false positives + 2 real hardening.
4. **Phase 4** (SQL injection, ~2–3 hr) — 4 high-severity; all false positives but worth correct-pattern migration.

Total: 4 PRs, serial (per orchestrator-root sweep policy — shared files like `error_handling.py`, `db.py` must not be in-flight simultaneously).
