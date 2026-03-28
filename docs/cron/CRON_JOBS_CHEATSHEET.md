# Cron jobs cheatsheet (Kitchen backend)

Inventory of callable maintenance jobs. **Not all are scheduled in every environment**—confirm crontab / Cloud Scheduler before assuming they run.

## Password recovery token cleanup

| | |
|--|--|
| **Callable** | `password_recovery_service.cleanup_expired_tokens(db)` |
| **Module** | `app.services.password_recovery_service` |
| **Purpose** | Archive expired unused rows in `credential_recovery` (`is_archived = TRUE` where `token_expiry` passed and row still unused). |
| **Scheduling** | Documented in [PASSWORD_RECOVERY.md](../api/internal/PASSWORD_RECOVERY.md) (example daily). **Wire in ops when ready.** |

Example (same pattern as other cron scripts; close the connection in real jobs):

```bash
python3 -c "
from app.utils.db import get_db_connection, close_db_connection
from app.services.password_recovery_service import password_recovery_service
db = get_db_connection()
try:
    print(password_recovery_service.cleanup_expired_tokens(db))
finally:
    close_db_connection(db)
"
```

## Email change request cleanup

| | |
|--|--|
| **Callable** | `email_change_service.cleanup_expired_requests(db)` |
| **Module** | `app.services.email_change_service` |
| **Purpose** | Archive expired unused rows in `email_change_request` (`is_archived = TRUE` where `token_expiry` passed and `is_used = FALSE`). |
| **Scheduling** | **Not yet scheduled**—add when ops wants periodic cleanup. Suggested cadence: same as password recovery (e.g. daily), or combined in one maintenance script. |

Example:

```bash
python3 -c "
from app.utils.db import get_db_connection, close_db_connection
from app.services.email_change_service import email_change_service
db = get_db_connection()
try:
    print(email_change_service.cleanup_expired_requests(db))
finally:
    close_db_connection(db)
"
```

## Related docs

- [CRON_SETUP_GUIDE.md](./CRON_SETUP_GUIDE.md) — archival cron and examples.
- [EMAIL_VERIFICATION_ROADMAP.md](../zArchive/roadmap/EMAIL_VERIFICATION_ROADMAP.md) — email verification and future cron note.
