# Enum Value vs Display Name Standardization — Roadmap

**Status**: Roadmap (not scheduled)
**Last Updated**: 2026-03
**Purpose**: Separate stable system values from human-readable display labels across all enums.

---

## Current State

Enum values in the system are Title Case (e.g. `'Active'`, `'Pending'`, `'Supplier'`).
These values serve double-duty: they are both the system identifier stored in the DB and
the display string shown to users in the UI.

Exceptions:
- `pickup_type_enum` values are lowercase (`'delivery'`, `'pickup'`), breaking the convention.

---

## Problem

1. **Coupling**: UI display strings are coupled to system values. Changing a display label (e.g. for i18n or rebrand) requires a DB migration.
2. **No i18n at value level**: `'Pending'` is already an English word — it cannot vary by locale without a separate label lookup.
3. **Inconsistency**: `pickup_type_enum` is lowercase; all others are Title Case — no enforced standard.

---

## Proposed Future Standard

Split every enum into two concerns:

| Concern | Where stored | Example |
|---------|-------------|---------|
| `value` | DB column, Python enum `.value`, API response | `"active"` (lowercase slug) |
| `label` | i18n label file or enum service | `"Active"` (en), `"Activo"` (es) |

### Impact

- All DB enum type values would change (e.g. `'Active'` → `'active'`)
- All Python enum classes update (`.value` becomes lowercase)
- Enum service returns `{value, label}` pairs per locale instead of flat value lists
- All frontend consumers update to use `value` for logic and `label` for display
- All existing DB rows and history rows need a data migration

---

## Why Not Now

- **Cross-repo impact**: Affects vianda-platform, vianda-app, vianda-home, and this API simultaneously
- **DB migration scope**: Every enum column in every table
- **Risk**: High blast radius; no immediate business driver
- **Current workaround**: `app/i18n/enum_labels.py` provides display labels for enums that need i18n (e.g. `street_type`, `address_type`, `bill_resolution`, `bill_payout_status`) — the enum service can return labels for these without changing values

---

## Checklist (for when this is prioritized)

- [ ] Audit all `*_enum` types in `schema.sql`; list current values
- [ ] Define lowercase slug convention for all values (handle conflicts like `'Entity Address'` → `'entity_address'`)
- [ ] Update `schema.sql` enum definitions
- [ ] Write DB migration for all existing rows
- [ ] Update all Python enum classes
- [ ] Update enum service to return `{value, label}` per locale
- [ ] Update API docs and frontend consumers (coordinate cross-repo)
- [ ] Remove `LABELED_ENUM_TYPES` workaround in `app/i18n/enum_labels.py` (labels now come from enum service directly)

---

## References

- Current enum label system: `app/i18n/enum_labels.py`
- Enum service: `app/services/enum_service.py`
- `pickup_type_enum` inconsistency: `app/config/enums/pickup_types.py`
