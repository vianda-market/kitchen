---
status: complete
issue: kitchen#87 sub-item (c)
date: 2026-04-26
---

# Bare-string HTTPException sweep — triage

Total 4xx sites found: **0** (sweep complete)
Total 5xx sites found: **49** (intentionally exempt — see Decision 3 below)
Files with 5xx exempt sites: 11

## Status

The sweep is **fully complete** as of the K6..KN PR train + PR #142. The lint
`app/tests/i18n/test_no_bare_string_raises.py` is in **enforcing mode** (not report
mode) and passes with 0 violations on HEAD `277c4505`.

## What was migrated

All `raise HTTPException(status_code=<4xx>, detail=<str>)` sites across `app/`
were migrated to `raise envelope_exception(ErrorCode.X, status=<4xx>, locale=locale, ...)`.
Sites were distributed across routes, services, auth, and security modules.

## 5xx exempt sites (Decision 3)

5xx raises are intentionally left as bare strings. These are server-error signals
for ops logging, not user-facing messages. They appear in service internals and
are never sent as user-visible error text.

| File | Sites | Notes |
|---|---|---|
| app/services/route_factory.py | 16 | Factory internals — DB/image failures |
| app/services/entity_service.py | 14 | Internal CRUD failure paths |
| app/services/enriched_service.py | 4 | Enriched-list query failures |
| app/services/qr_code_service.py | 3 | QR CRUD failures |
| app/services/ingredient_service.py | 3 | Ingredient CRUD failures |
| app/utils/db.py | 2 | DB utility failures |
| app/services/market_service.py | 2 | Market-service failures |
| app/services/qr_code_print_service.py | 2 | QR print failures |
| app/services/product_image_service.py | 1 | Image-upload failure |
| app/services/qr_code_generation_service.py | 1 | QR generation failure |
| app/services/notification_banner_service.py | 1 | Notification failure |
| **Total** | **49** | All status_code=5xx; exempt by design |

Note: The lint test docstring references "52 sites" at the time it was written;
current count is 49 (3 were cleaned up since the docstring was authored).

## PR history

All 4xx bare-string migration was completed through the K6..KN sweep PRs plus:
- **PR #142** (`fix/87-d-404-detail-hijack-sweep`): final batch including
  restaurant_balance.py and restaurant_transaction.py 404 helper-indirection sites.

## Follow-up items

None. The sweep is complete and gated by the enforcing lint.

If any new 4xx HTTPException with a bare-string detail is introduced, the lint
`test_no_bare_string_raises.py` will fail CI immediately.
