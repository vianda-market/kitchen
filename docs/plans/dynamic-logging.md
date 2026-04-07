# Dynamic Logging Roadmap

**Purpose**: Enable configurable, toggle-based control of log visibility via environment variables. Instead of removing logs, use boolean flags (1/0) to show or hide log categories at runtime—keeping code in place while controlling what appears in the terminal and log output.

**Status**: 📋 Planning

---

## Overview

**Current approach** (to avoid): Deleting or commenting out logs for production.

**New approach**: Define log categories with corresponding environment variables. Each category has a flag; when the flag is `1` (or `true`/`yes`), those logs are emitted. When `0` (or unset), they are suppressed. Log calls remain in the code; only visibility is toggled via configuration.

**Benefits**:
- Turn logs on for debugging without code changes or redeploys
- Turn off verbose logs in production without losing them
- Per-environment control (e.g. `.env` differs by env)
- Consistent with existing pattern (e.g. `LOG_EMAIL_TRACKING`, `DEBUG_PASSWORD_RECOVERY`)

---

## Log Categories and Flags

### Proposed Environment Variables

| Flag | Default | Description | Example Log Sources |
|------|---------|-------------|---------------------|
| `LOG_QUERY_TIMING` | `0` | Query execution time logs | `app/utils/db.py` – "Query executed in Xs", "INSERT executed in Xs" |
| `LOG_QUERY_SLOW` | `1` | Slow query warnings (>1s) | `app/utils/db.py` – "Slow query detected" |
| `LOG_VERBOSE_CRUD` | `0` | Step-by-step CRUD operation logs | `app/services/crud_service.py` – balance creation steps, INSERT/UPDATE execution |
| `LOG_SUCCESS_CRUD` | `0` | "Successfully created/updated" messages | `app/utils/db.py`, `app/services/crud_service.py` |
| `LOG_AUTH_DEBUG` | `0` | Authentication debug (token, payload) | `app/auth/routes.py` – token decode, verification steps |
| `LOG_POOL_DEBUG` | `0` | Database pool configuration logs | `app/utils/db_pool.py` |
| `LOG_BILLING_VERBOSE` | `0` | Billing operation step-by-step logs | `app/services/billing/` |
| `LOG_ENTITY_VERBOSE` | `0` | Entity service operation logs | `app/services/entity_service.py` |

**Existing flags** (already implemented):
- `LOG_EMAIL_TRACKING` – Email send/tracking
- `DEBUG_PASSWORD_RECOVERY` – Password/username recovery debug
- `LOG_EMPLOYER_ASSIGN` – Employer assignment events

---

## Implementation Approach

### 1. Central Config Module

**File**: `app/config/log_config.py` (new)

```python
"""Dynamic log visibility configuration. Flags read from env; 1/true/yes = enabled, 0/false/unset = disabled."""
import os

def _is_enabled(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "1" if default else "0").strip().lower()
    return val in ("1", "true", "yes")

# Per-category flags
LOG_QUERY_TIMING = _is_enabled("LOG_QUERY_TIMING")
LOG_QUERY_SLOW = _is_enabled("LOG_QUERY_SLOW", default=True)
LOG_VERBOSE_CRUD = _is_enabled("LOG_VERBOSE_CRUD")
LOG_SUCCESS_CRUD = _is_enabled("LOG_SUCCESS_CRUD")
LOG_AUTH_DEBUG = _is_enabled("LOG_AUTH_DEBUG")
LOG_POOL_DEBUG = _is_enabled("LOG_POOL_DEBUG")
LOG_BILLING_VERBOSE = _is_enabled("LOG_BILLING_VERBOSE")
LOG_ENTITY_VERBOSE = _is_enabled("LOG_ENTITY_VERBOSE")
```

### 2. Conditional Log Helpers

**File**: `app/utils/log.py` (extend)

Add gate functions following the existing `log_email_tracking` / `log_password_recovery_debug` pattern:

```python
def log_if(category_enabled: bool, message: str, level: str = "info") -> None:
    """Log only when the category flag is enabled."""
    if not category_enabled:
        return
    if level == "debug":
        logger.debug(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)
```

**Usage in code**:

```python
# Before (always logs):
log_info(f"📊 Query executed in {time}s: {query[:100]}...")

# After (conditionally logs):
from app.config.log_config import LOG_QUERY_TIMING
from app.utils.log import log_if, log_info
log_if(LOG_QUERY_TIMING, f"📊 Query executed in {time}s: {query[:100]}...")
```

Or add dedicated helpers per category (like `log_email_tracking`):

```python
def log_query_timing(message: str) -> None:
    if LOG_QUERY_TIMING:
        logger.info(message)

def log_verbose_crud(message: str) -> None:
    if LOG_VERBOSE_CRUD:
        logger.info(message)
```

### 3. Settings Integration (Optional)

Add to `app/config/settings.py` for type safety and `.env` documentation:

```python
LOG_QUERY_TIMING: bool = False
LOG_VERBOSE_CRUD: bool = False
# ... etc.
```

Then `log_config.py` can read from `get_settings()` if preferred over raw `os.environ`.

---

## Migration Strategy

### Phase 1: Add Config and Helpers
1. Create `app/config/log_config.py` with flag definitions
2. Add `log_if()` or per-category helpers to `app/utils/log.py`
3. Document flags in `.env.example`

### Phase 2: Migrate Log Calls
1. **Query timing** (`app/utils/db.py`): Wrap timing logs with `LOG_QUERY_TIMING` check
2. **Verbose CRUD** (`app/services/crud_service.py`): Wrap step-by-step logs with `LOG_VERBOSE_CRUD`
3. **Auth debug** (`app/auth/routes.py`): Wrap token/payload logs with `LOG_AUTH_DEBUG` (keep security-sensitive logs off by default)
4. **Pool debug** (`app/utils/db_pool.py`): Wrap with `LOG_POOL_DEBUG`
5. **Billing/Entity**: Wrap verbose logs with their respective flags

### Phase 3: Never Remove, Only Gate
- Keep all existing log calls; add condition checks
- Error and critical logs remain unconditional (always emitted)
- Security-sensitive logs (tokens, passwords) stay behind `LOG_AUTH_DEBUG=0` in production

---

## Security-Sensitive Logs

**Rule**: Logs that may contain tokens, passwords, or PII must be behind a flag that defaults to `0`.

| Flag | Risk | Default |
|------|------|---------|
| `LOG_AUTH_DEBUG` | Token, JWT payload exposure | `0` |

These should never be enabled in production; use only for local debugging.

---

## Environment Profiles

| Environment | Suggested Flags |
|-------------|-----------------|
| **Local dev** | `LOG_QUERY_TIMING=1`, `LOG_VERBOSE_CRUD=1` (optional) |
| **Staging** | Most flags `0`; enable selectively when debugging |
| **Production** | All verbose flags `0`; `LOG_QUERY_SLOW=1` to keep slow query alerts |

---

## .env.example Additions

```env
# Dynamic log visibility (1 = show, 0 = hide). Toggle without code changes.
LOG_QUERY_TIMING=0
LOG_QUERY_SLOW=1
LOG_VERBOSE_CRUD=0
LOG_SUCCESS_CRUD=0
LOG_AUTH_DEBUG=0
LOG_POOL_DEBUG=0
LOG_BILLING_VERBOSE=0
LOG_ENTITY_VERBOSE=0
```

---

## Implementation Checklist

### Phase 1: Infrastructure
- [ ] Create `app/config/log_config.py` with flag definitions
- [ ] Add `log_if()` or per-category helpers to `app/utils/log.py`
- [ ] Add flags to `.env.example`
- [ ] Document in `docs/readme/ENV_SETUP.md`

### Phase 2: Migrate by Category
- [ ] Query timing logs (`app/utils/db.py`)
- [ ] Verbose CRUD logs (`app/services/crud_service.py`)
- [ ] Auth debug logs (`app/auth/routes.py`)
- [ ] Pool debug logs (`app/utils/db_pool.py`)
- [ ] Billing verbose logs
- [ ] Entity service verbose logs

### Phase 3: Validation
- [ ] Verify with all flags `0`: minimal terminal output
- [ ] Verify with flags `1`: full verbosity for debugging
- [ ] Ensure error/critical logs always emitted regardless of flags

---

## Code Comment Cleanup (Unchanged)

Comment cleanup remains separate from log configuration:
- TODO comments: Complete or convert to issues
- Explanatory comments: Review for accuracy
- Commented-out code: Remove
- Print statements: Replace with proper logging (can use the same flag pattern if needed)

---

## References

- `app/utils/log.py` – Existing `log_email_tracking`, `log_password_recovery_debug` pattern
- `app/config/settings.py` – Settings and env var usage
- `.env.example` – Environment variable documentation

---

**Last Updated**: 2026-03
**Next Review**: After Phase 1 implementation
