# Breaking Changes Log

**Last Updated**: 2026-02-10  
**Purpose**: API changes that require frontend coordination. Add entries before merging backend changes.

---

## Format

Each entry should include:

- **Date**: When the change was/will be deployed
- **Change**: What changed
- **Affected endpoints**: List of endpoints
- **Frontend action required**: What kitchen-web / kitchen-mobile must do
- **Backward compatible?**: Yes/No

---

## Current / Upcoming

*(Add entries as breaking changes are introduced)*

### Example entry (template – delete when first real entry is added)

**Date**: YYYY-MM-DD  
**Change**: Description of the change  
**Affected endpoints**: `GET /api/v1/example/`  
**Frontend action required**: Update response parsing; re-run codegen  
**Backward compatible?**: No

---

## Deprecations

See [client/README.md](./client/README.md) for deprecated endpoints and migration steps (including `ENDPOINT_DEPRECATION_GUIDE.md`).
