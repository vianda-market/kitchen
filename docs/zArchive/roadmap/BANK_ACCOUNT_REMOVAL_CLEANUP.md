# Bank Account Removal Cleanup Roadmap

## Overview

The `institution_bank_account` table and related routes/services have been removed. Institution (supplier) payout is now Stripe-only. This roadmap covers cleanup of remaining `account_type` enum references and related documentation.

## Completed

- `app/routes/institution_bank_account.py` — Deleted
- `app/services/bank_account_service.py` — Deleted
- `app/schemas/institution_bank_account.py` — Deleted
- `app/config/enums/bank_account_types.py` — Deleted

## Remaining Cleanup

### 1. Enum Service / Schema

| Location | Action |
|----------|--------|
| `app/schemas/consolidated_schemas.py` | Remove `account_type` field from `EnumsResponseSchema` |
| `app/tests/services/test_enum_service.py` | Remove `account_type` from expected enum keys |

**Note**: `enum_service.get_all_enums()` does not return `account_type`; schema and tests were out of sync.

### 2. Documentation

| Location | Action |
|----------|--------|
| `docs/api/shared_client/ENUM_SERVICE_API.md` | Remove `account_type` from enum table and examples |

### 3. Postman

| Location | Action |
|----------|--------|
| `docs/postman/collections/003 ENUM_SERVICE.postman_collection.json` | Remove assertions that check for `account_type` in response |

### 4. Historical / Archive

Files in `docs/zArchive/` and similar may reference `account_type` or `institution_bank_account`. These are kept for historical context; no changes required for active code paths.

## References

- [PAYMENT_METHOD_CHANGES_B2B.md](../api/b2b_client/PAYMENT_METHOD_CHANGES_B2B.md) — Backend status: bank-account-based payment removed
- [SUPPLIER_INSTITUTION_PAYMENT.md](../api/internal/SUPPLIER_INSTITUTION_PAYMENT.md) — Payout is Stripe-only
