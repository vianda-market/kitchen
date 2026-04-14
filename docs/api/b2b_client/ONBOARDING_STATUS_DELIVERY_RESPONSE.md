# Supplier Onboarding Status — Delivery Response

**Audience**: B2B React frontend agent (vianda-platform)  
**In response to**: `vianda-platform/docs/frontend/feedback_for_backend/SUPPLIER_ONBOARDING_STATUS_ENDPOINT.md`  
**Last Updated**: 2026-04-04

---

## Delivery Status — All Items Complete

| # | Feature | Status | Details |
|---|---------|--------|---------|
| 1 | Onboarding status endpoint | **Delivered** | `GET /api/v1/institutions/{id}/onboarding-status` |
| 2 | JWT onboarding claim | **Delivered** | On all token flows (login, verify, password reset) |
| 3 | Internal onboarding summary | **Delivered** | `GET /api/v1/institutions/onboarding-summary` — response shape updated to include `total`, `market_name`, `created_date` |
| 4 | Stall detection & emails | **Delivered** | Daily cron: `POST /api/v1/institutions/onboarding-stall-detection`. Emails localized (en/es/pt) via Jinja2 templates. SendGrid ready (config-flip). |
| 5 | Activity tracking | **Delivered** | Uses `GREATEST(MAX(modified_date))` across all related tables. `modified_date` is reliably updated on all operations (create, update, archive). |
| 6 | Regression detection | **Delivered** | Automatic hooks in `CRUDService.soft_delete()` and restaurant status updates. Logs warning when institution regresses from `complete`. |

---

## Item 3: Internal Onboarding Summary — Updated Response

### `GET /api/v1/institutions/onboarding-summary`

**Auth:** Internal Super Admin only

**Query params** (all optional):
- `institution_type` — `Supplier` (default) or `Employer`
- `market_id` — filter by market UUID
- `onboarding_status` — filter by status
- `stalled_days` — override stall threshold (default: 7)

**Response:**

```json
{
  "total": 42,
  "counts": {
    "not_started": 5,
    "in_progress": 12,
    "complete": 20,
    "stalled": 5
  },
  "stalled_institutions": [
    {
      "institution_id": "550e8400-e29b-41d4-a716-446655440000",
      "institution_name": "Cafe Roma",
      "market_name": "Argentina",
      "onboarding_status": "stalled",
      "completion_percentage": 42,
      "days_since_creation": 30,
      "days_since_last_activity": 14,
      "missing_steps": ["entity_payout_setup", "restaurant", "plate", "kitchen_day", "qr_code"],
      "created_date": "2026-03-04T10:00:00Z"
    }
  ]
}
```

---

## Item 4: Stall Detection — Implementation Details

**Cron:** `app/services/cron/supplier_stall_detection.py` — `run_supplier_stall_detection()`

**Thresholds:**

| Condition | Action |
|-----------|--------|
| `not_started` + 2d since creation | "Getting started" email |
| `in_progress` + 3d no activity | "Need help?" email |
| `in_progress` + 7d no activity | "Setup incomplete" email with missing steps |
| `in_progress` + 14d no activity | Manual escalation (log only, no email) |
| Just became `complete` (previously nudged) | Celebration email |

**Email suppression:** Max 1 email per 3-day cooldown per institution. Manual override via `support_email_suppressed_until` column on `institution_info`.

**Email infrastructure:** Gmail SMTP active (`hello@vianda.market`). SendGrid ready as config-flip when volume justifies it. Provider abstraction in `app/services/email/`. Templates localized (en/es/pt) via Jinja2.

**Trigger:** `POST /api/v1/institutions/onboarding-stall-detection` (Internal only) or Cloud Scheduler daily at 09:00 UTC.

---

## Item 5: Activity Tracking — Confirmed Reliable

`modified_date` is reliably updated on:
- **Field edits** — `CRUDService.update()` sets `modified_date`
- **Status changes** — same `update()` path
- **Archival** — `CRUDService.soft_delete()` sets `modified_date`
- **New resource creation** — `created_date` = `modified_date` on INSERT

The onboarding service computes `last_activity_date` as `GREATEST(MAX(modified_date))` across all 7 related tables (address, entity, restaurant, product, plate, kitchen_day, qr_code). No separate `institution_last_activity_date` column is needed — the computed approach is always accurate and requires no triggers.

---

## Item 6: Regression Detection — Implemented

**Hook points:**
1. `CRUDService.soft_delete()` — after any successful soft-delete, checks if the owning Supplier/Employer institution regressed from `complete`
2. Restaurant `PUT` status update — checks when status changes away from `Active`

**What happens on regression:**
- Warning logged: `"Onboarding regression: institution {id} is now 'in_progress' after {table} record {id} was archived/deactivated"`
- JWT claim updates on next login/token refresh (automatic — `merge_onboarding_token_claims` recomputes fresh status)
- No email notification to supplier yet (can add if needed)

---

## Answers to Open Questions

### 1. Stall threshold
Default is **7 days** for the `stalled` status in the API. Configurable per request via the `stalled_days` query param on the summary endpoint. Not per-market — can add market-specific thresholds if needed.

### 2. Email infrastructure
Gmail SMTP is active (`hello@vianda.market` via Google Workspace). SendGrid is provisioned and ready — infra flips `EMAIL_PROVIDER=sendgrid` when volume justifies the cost. Provider abstraction handles the switch with zero code changes. Email templates use Jinja2 with locale-specific files (en/es/pt).

### 3. next_step ordering
Canonical dependency order: address → entity_payout_setup → restaurant → product → plate → kitchen_day → qr_code. Product comes **after** restaurant in the chain. While products can be created independently, `next_step` follows the canonical order because the guided setup wizard should direct suppliers through the recommended sequence.

### 4. Caching
Computed on every request. The EXISTS subqueries are index-backed and fast. The summary endpoint uses correlated subqueries that execute in a single database round-trip. No caching needed at current scale. If performance degrades with hundreds of institutions, we can add a materialized view or Redis cache.

### 5. Compound endpoint
Not planned. Sequential creation via the step-by-step wizard aligns with the B2B frontend's UX pattern. Each step validates independently and the onboarding status updates after each operation.

---

## Related Documents

| Document | Description |
|----------|-------------|
| `kitchen/docs/api/b2b_client/API_CLIENT_ONBOARDING_STATUS.md` | Full endpoint contract + frontend integration guide |
| `kitchen/docs/cron/CRON_JOBS_CHEATSHEET.md` | Cron job inventory (stall detection + customer engagement) |
| `kitchen/docs/api/infrastructure/SENDGRID_EMAIL_INFRASTRUCTURE.md` | SendGrid infra setup guide |
| `kitchen/docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | Full roadmap with phase status |
