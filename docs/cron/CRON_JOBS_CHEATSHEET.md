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

## Wikidata ingredient image enrichment

| | |
|--|--|
| **Callable** | `wikidata_enrichment.run_wikidata_enrichment()` |
| **Module** | `app.services.cron.wikidata_enrichment` |
| **Purpose** | Enrich `ops.ingredient_catalog` rows (`image_enriched=FALSE`) via Wikidata P18 (image) claims. Sets `image_url`, `image_source='wikidata'`, `image_enriched=TRUE`. Rows with no P18 claim are marked `image_skipped=TRUE` for admin review. |
| **Kill switch** | `WIKIDATA_ENRICHMENT_ENABLED=false` — cron is a no-op until set to `true` |
| **Quota** | Free — Wikidata has no usage limits or API key requirements. |
| **Scheduling** | Every 6 hours (`0 */6 * * *` UTC). Infra config key: `wikidata_enrichment`. See [INGREDIENT_ENRICHMENT_CRON.md](./INGREDIENT_ENRICHMENT_CRON.md). |

Example:

```bash
python3 -c "
from app.services.cron.wikidata_enrichment import run_wikidata_enrichment
import json
print(json.dumps(run_wikidata_enrichment(), indent=2, default=str))
"
```

## Supplier stall detection

| | |
|--|--|
| **Callable** | `run_supplier_stall_detection()` |
| **Module** | `app.services.cron.supplier_stall_detection` |
| **Purpose** | Detect suppliers stalled during onboarding and send escalating emails: getting started (2d), need help (3d), setup incomplete (7d), manual escalation log (14d). Celebration email when onboarding completes. Respects 3-day cooldown and manual suppression via `support_email_suppressed_until`. |
| **HTTP endpoint** | `POST /api/v1/institutions/onboarding-stall-detection` (Internal only) |
| **Scheduling** | Daily at 09:00 UTC (`0 9 * * *`). Infra config key: `supplier_stall_detection`. |

Example:

```bash
python3 -c "
from app.services.cron.supplier_stall_detection import run_supplier_stall_detection
import json
print(json.dumps(run_supplier_stall_detection(), indent=2, default=str))
"
```

## Customer engagement

| | |
|--|--|
| **Callable** | `run_customer_engagement()` |
| **Module** | `app.services.cron.customer_engagement` |
| **Purpose** | Find Customer users without active subscriptions and send engagement emails. Regular customers get subscribe prompts (2d, 7d). Benefit employees get employer-specific nudges (1d, 5d). 3-day cooldown per user. |
| **HTTP endpoint** | `POST /api/v1/institutions/onboarding-customer-engagement` (Internal only) |
| **Scheduling** | Daily at 09:30 UTC (`30 9 * * *`). Infra config key: `customer_engagement`. |

Example:

```bash
python3 -c "
from app.services.cron.customer_engagement import run_customer_engagement
import json
print(json.dumps(run_customer_engagement(), indent=2, default=str))
"
```

## Related docs

- [CRON_SETUP_GUIDE.md](./CRON_SETUP_GUIDE.md) — archival cron and examples.
- [EMAIL_VERIFICATION_ROADMAP.md](../zArchive/roadmap/EMAIL_VERIFICATION_ROADMAP.md) — email verification and future cron note.
