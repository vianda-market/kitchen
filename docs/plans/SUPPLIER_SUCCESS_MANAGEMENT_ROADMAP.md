# Supplier Success Management — Backend Roadmap

**Last Updated**: 2026-04-04  
**Purpose**: Backend infrastructure for supplier onboarding tracking, automated support outreach, and email service upgrade. Enables B2B frontend gated navigation, guided walkthroughs, and stall detection.  
**Origin**: B2B frontend proposal — `vianda-platform/docs/frontend/feedback_for_backend/SUPPLIER_ONBOARDING_STATUS_ENDPOINT.md`  
**Frontend roadmap**: `vianda-platform/docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md`

---

## Executive Summary

New suppliers are created with `status: Active` but have no restaurants, viandas, kitchen days, or QR codes. There is no signal of incompleteness, no guidance system, and no automated outreach when suppliers stall during setup. This roadmap adds:

1. **Onboarding status endpoint** — Backend-computed checklist with completion percentage and next step
2. **JWT onboarding claim** — Fast page-load gating without extra API call
3. **Internal admin summary** — Aggregated funnel view of all suppliers by onboarding status
4. **Automated stall detection** — Cron job that detects stalled suppliers and triggers email outreach
5. **Email infrastructure upgrade** — Migrate from Gmail SMTP (500/day limit) to a production-grade service

---

## Current Email Infrastructure — Why It Must Change

| Aspect | Current (Gmail SMTP) | Required for Supplier Success |
|--------|---------------------|-------------------------------|
| Provider | Gmail via `smtp.gmail.com:587` | Production email service |
| Daily limit | 500 emails/day | 50,000+ (SES free tier) |
| Deliverability | Low — Gmail app passwords, no SPF/DKIM for custom domain | High — verified domain, SPF/DKIM/DMARC |
| Templates | Hardcoded in `email_service.py` (~688 lines) | Externalized or at minimum well-structured |
| Async sending | Synchronous (blocks request) | Async (non-blocking, retry on failure) |
| Bounce/complaint handling | None | Automatic suppression list |
| From address | `vianda.app@gmail.com` | `noreply@vianda.com` or `support@vianda.com` |

**Existing email use cases** (all must continue working after migration):

| Email Type | Trigger | Template Method |
|------------|---------|-----------------|
| Password reset | `POST /users/forgot-password` | `send_password_reset_email()` |
| Username recovery | `POST /users/forgot-username` | `send_username_recovery_email()` |
| Customer signup verification | `POST /signup` | `send_signup_verification_email()` |
| B2B user invite | `POST /users` (admin, no password) | `send_b2b_invite_email()` |
| Benefit employee invite | `POST /employer/employees` | `send_benefit_employee_invite_email()` |
| Email change verification | `PUT /users/me` (new email) | `send_email_change_verification_email()` |
| Email change confirmation | Successful verify | `send_email_change_confirmation_email()` |
| Welcome (unused) | Not wired | `send_welcome_email()` |

---

## Phase 1: Onboarding Status Endpoint (Critical)

### 1.1 — `GET /api/v1/institutions/{institution_id}/onboarding-status`

**Auth:** `get_current_user` — Supplier sees own institution; Internal sees any.

**Response:**

```json
{
  "institution_id": "uuid",
  "institution_type": "Supplier",
  "onboarding_status": "in_progress",
  "completion_percentage": 57,
  "next_step": "product",
  "days_since_creation": 5,
  "days_since_last_activity": 2,
  "last_activity_date": "2026-04-02T14:30:00Z",
  "checklist": {
    "has_active_address": true,
    "has_active_entity_with_payouts": true,
    "has_active_restaurant": true,
    "has_active_product": false,
    "has_active_vianda": false,
    "has_active_kitchen_day": false,
    "has_active_qr_code": true
  }
}
```

**Checklist queries** (all check `status = 'Active' AND is_archived = FALSE`):

| Item | SQL |
|------|-----|
| `has_active_address` | `EXISTS(address_info WHERE institution_id = %s AND status = 'Active' AND NOT is_archived)` |
| `has_active_entity_with_payouts` | `EXISTS(institution_entity_info WHERE institution_id = %s AND status = 'Active' AND NOT is_archived AND payout_onboarding_status = 'complete')` |
| `has_active_restaurant` | `EXISTS(restaurant_info r JOIN address_info a ON r.address_id = a.address_id WHERE a.institution_id = %s AND r.status = 'Active' AND NOT r.is_archived)` |
| `has_active_product` | `EXISTS(product_info WHERE institution_id = %s AND status = 'Active' AND NOT is_archived)` |
| `has_active_vianda` | `EXISTS(vianda_info p JOIN restaurant_info r ... WHERE institution_id = %s AND p.status = 'Active' AND NOT p.is_archived)` |
| `has_active_kitchen_day` | `EXISTS(vianda_kitchen_days pkd JOIN vianda_info p ... WHERE institution_id = %s AND pkd.status = 'Active' AND NOT pkd.is_archived)` |
| `has_active_qr_code` | `EXISTS(qr_code q JOIN restaurant_info r ... WHERE institution_id = %s AND q.status = 'Active' AND NOT q.is_archived)` |

**`next_step` dependency order:** address → entity_payout_setup → restaurant → product → vianda → kitchen_day → qr_code. Return the first item in the chain that is `false`.

**`onboarding_status` derivation:**
- `not_started`: all checklist items false
- `complete`: all checklist items true
- `stalled`: some true, some false, and `days_since_last_activity >= 3` (internal only — not exposed to JWT)
- `in_progress`: otherwise

**`last_activity_date`:** `MAX(modified_date)` across addresses, entities, restaurants, products, viandas, kitchen_days, qr_codes for the institution.

**Files to create:**
- `app/services/onboarding_service.py` — Checklist computation, status derivation
- `app/routes/onboarding.py` — Endpoint
- `app/schemas/consolidated_schemas.py` — `OnboardingStatusResponseSchema`, `OnboardingChecklistSchema`

### 1.2 — JWT `onboarding_status` Claim

Add `onboarding_status` to the JWT payload for `role_type` in (`Supplier`, `Employer`).

**Values in JWT:** `not_started`, `in_progress`, `complete` (NOT `stalled` — that's internal-only).

**Computed at:** Token creation (`POST /auth/token`) and token refresh.

**Implementation:** In `app/auth/routes.py` token creation, call `onboarding_service.get_status(institution_id)` and include in the payload. Lightweight — the checklist queries use EXISTS (index-backed, fast).

**Files to modify:**
- `app/auth/routes.py` — Add claim to JWT payload

### 1.3 — `GET /api/v1/institutions/onboarding-summary` (Internal Admin only)

**Auth:** `get_super_admin_user`

**Query params:** `institution_type`, `onboarding_status`, `market_id`, `stalled_days`

**Response:**

```json
{
  "counts": {
    "not_started": 3,
    "in_progress": 12,
    "complete": 45,
    "stalled": 5
  },
  "stalled_institutions": [
    {
      "institution_id": "uuid",
      "institution_name": "Acme Foods",
      "completion_percentage": 43,
      "days_since_creation": 14,
      "days_since_last_activity": 8,
      "missing_steps": ["product", "vianda", "kitchen_day"]
    }
  ]
}
```

---

## Phase 2: Email Infrastructure Upgrade (High)

### 2.1 — Evaluate GCP-Native Options

| Service | Type | Pricing | Domain Auth | Integration |
|---------|------|---------|-------------|-------------|
| **GCP + SendGrid** | GCP Marketplace partner | 12,000 emails/month free | Full SPF/DKIM/DMARC | REST API or SMTP relay |
| **AWS SES** | Cross-cloud | 62,000/month free (from EC2) or $0.10/1K | Full SPF/DKIM/DMARC | REST API or SMTP |
| **Mailgun** | Third-party | 1,000/month free, then $0.80/1K | Full SPF/DKIM/DMARC | REST API |
| **Resend** | Modern API-first | 3,000/month free, then $1/1K | Full SPF/DKIM/DMARC | REST API |

**Recommendation:** **SendGrid via GCP Marketplace** — native GCP integration, generous free tier (12K/month), proven deliverability, supports both transactional and marketing emails, easy domain verification.

### 2.2 — Provider Abstraction

Refactor `email_service.py` to use a provider abstraction:

```python
class EmailProvider(ABC):
    def send(self, to, subject, html_body, text_body, from_email, from_name) -> bool: ...

class SmtpEmailProvider(EmailProvider):     # Current Gmail — kept as fallback/dev
class SendGridEmailProvider(EmailProvider):  # Production
```

**Config:**
```python
EMAIL_PROVIDER: str = "smtp"  # "smtp" | "sendgrid"
SENDGRID_API_KEY: str = ""
EMAIL_FROM_ADDRESS: str = "hello@vianda.market"
EMAIL_FROM_NAME: str = "Vianda"
```

**Migration path:** `EMAIL_PROVIDER=smtp` stays default for dev. Production sets `EMAIL_PROVIDER=sendgrid`. All existing email methods call through the abstraction — zero changes to callers.

### 2.3 — Domain Verification

- Register `vianda.market` with SendGrid as authenticated sender domain
- Add SPF, DKIM, and DMARC DNS records on `vianda.market`
- Verify sender identity
- **From address:** `hello@vianda.market` for all transactional and onboarding emails
- **Reply-to:** `support@vianda.market` (so replies reach support inbox, not a dead noreply)

### 2.4 — Email Analytics (included with SendGrid)

SendGrid provides built-in tracking at no extra cost:
- **Open rate tracking** — pixel-based; measures engagement per email type
- **Click tracking** — wraps links to track CTR on "Complete your setup" deep links
- **Bounce/complaint rate** — automatic suppression of invalid/complaining addresses
- **Dashboard:** SendGrid Activity Feed for real-time delivery status

This is distinct from **Google Analytics** (website/app user behavior tracking) which is a frontend concern and belongs in a separate roadmap. Email analytics measures email deliverability and engagement; GA measures what users do after they arrive.

**Configuration:** Enable/disable tracking per email type via SendGrid categories:
- `onboarding-nudge` — track opens and clicks (measure stall detection effectiveness)
- `transactional` (password reset, verification) — track delivery only (no click tracking for security-sensitive emails)

### 2.5 — Infra Requirements

**For infra-kitchen-gcp agent:**
- SendGrid API key in GCP Secret Manager: `kitchen-sendgrid-api-key-{env}`
- Cloud Run env vars: `SENDGRID_API_KEY`, `EMAIL_PROVIDER=sendgrid`, `EMAIL_FROM_ADDRESS=hello@vianda.market`
- DNS records on `vianda.market` domain registrar: SPF, DKIM (2 CNAME records from SendGrid), DMARC

---

## Phase 3: Automated Stall Detection & Outreach (Medium)

### 3.1 — Stall Detection Cron

**Schedule:** Daily (e.g., 09:00 UTC)

**Rules:**

| Condition | Action |
|-----------|--------|
| `not_started` + 2 days since creation | Send "Getting started" email |
| `in_progress` + 3 days no activity | Send "Need help?" email |
| `in_progress` + 7 days no activity | Send "Setup incomplete" email with specific missing steps |
| `in_progress` + 14 days no activity | Flag for manual support (log, optionally Slack webhook) |

**Email suppression:**
- Max 1 email per 3-day window per institution
- Skip `is_archived = TRUE` institutions
- Skip `complete` status institutions
- Respect `support_email_suppressed_until` field (manual override by support)

**Schema change:** Add `support_email_suppressed_until TIMESTAMPTZ NULL` and `last_support_email_date TIMESTAMPTZ NULL` to `institution_info`.

### 3.2 — Email Templates for Onboarding

| Template | Subject | Content |
|----------|---------|---------|
| Getting started | "Welcome to Vianda — let's set up your restaurant" | Setup guide link, support contact |
| Need help? (3d) | "Need help finishing your Vianda setup?" | Completion %, missing steps list, deep link to B2B |
| Setup incomplete (7d) | "Your Vianda setup is almost there" | Specific missing steps, offer of support call |
| Manual escalation (14d) | _(Internal only — Slack/log)_ | Institution name, contact info, missing steps |
| Celebration (complete) | "Your restaurant is live on Vianda!" | Congrats, what to expect, support contact |

All templates: localized (en/es/pt), include institution name, reply-to support address.

### 3.3 — Regression Detection (Phase 3b)

When archiving/deactivating a resource causes `complete` → `in_progress`:
- Log event
- Update `onboarding_status` on next JWT refresh
- Optionally send notification to Supplier Admin

**Implementation:** Post-operation hook on archive/delete/status-change for restaurants, viandas, kitchen_days, qr_codes.

---

## Phase 4: Employer Onboarding (Lower, Parallel)

Same pattern, different checklist:

| Item | Condition |
|------|-----------|
| `has_benefits_program` | Active employer_benefits_program for institution |
| `has_email_domain` | Active employer_domain for institution |
| `has_enrolled_employee` | At least 1 active user with employer_id pointing to this institution's employer |
| `has_active_subscription` | At least 1 active subscription from an enrolled employee |

Reuses the same `GET /institutions/{id}/onboarding-status` endpoint — response shape is identical, checklist items differ by `institution_type`.

---

## Files Summary

| Action | File |
|--------|------|
| **Create** | `app/services/onboarding_service.py` — Checklist computation, status derivation |
| **Create** | `app/routes/onboarding.py` — Status + summary endpoints |
| **Create** | `app/services/email_provider/` — Provider abstraction (base, smtp, sendgrid) |
| **Create** | `app/services/cron/stall_detection.py` — Daily cron for stalled institutions |
| Modify | `app/schemas/consolidated_schemas.py` — Onboarding schemas |
| Modify | `app/auth/routes.py` — JWT onboarding_status claim |
| Modify | `app/services/email_service.py` — Use provider abstraction |
| Modify | `app/config/settings.py` — EMAIL_PROVIDER, SENDGRID_API_KEY, stall thresholds |
| Modify | `app/db/schema.sql` — `support_email_suppressed_until`, `last_support_email_date` on institution_info |
| Modify | `application.py` — Register onboarding router |
| Modify | `CLAUDE_ARCHITECTURE.md` — Onboarding service, email provider, cron |

---

## Implementation Priority

```
Phase 1: Onboarding Status [IMPLEMENTED]
├── 1.1 GET /institutions/{id}/onboarding-status          ✅
├── 1.2 JWT onboarding_status claim                       ✅
└── 1.3 GET /institutions/onboarding-summary (Internal)   ✅

Phase 2: Email Upgrade [CODE COMPLETE — infra pending]
├── 2.1 SendGrid evaluation + account setup               ✅ (chose SendGrid via GCP Marketplace)
├── 2.2 Provider abstraction in email_service.py           ✅
├── 2.3 Domain verification (SPF/DKIM/DMARC)              ⏳ infra agent
└── 2.4 Infra: Secret Manager + Cloud Run env              ⏳ infra agent

Phase 3: Stall Detection [IMPLEMENTED]
├── 3.1 Daily cron job                                     ✅
├── 3.2 Email templates (getting started, nudges, celebration) ✅ (localized en/es/pt)
└── 3.3 Regression detection hooks                         ✅

Phase 4: Employer Onboarding [IMPLEMENTED]
└── Employer-specific checklist on same endpoint           ✅

Phase 5: Customer Onboarding [IMPLEMENTED — extension]
├── 5.1 GET /users/me/onboarding-status (user-level)      ✅
├── 5.2 JWT onboarding_status claim for Customers          ✅
├── 5.3 Customer engagement cron (subscribe prompts)       ✅
├── 5.4 Benefit employee engagement emails                 ✅
└── 5.5 Jinja2 email template architecture + i18n (en/es/pt) ✅
```

---

## Cross-Repo Impact

### vianda-platform (B2B)

**Depends on Phase 1 to implement:**
- Gated sidebar navigation (disable items with unmet dependencies)
- Dashboard onboarding progress banner
- Guided walkthroughs triggered by `onboarding_status`

**No backend dependency for:**
- Supplier guidelines / knowledge base (static content, frontend-owned)
- Setup wizard UX (sequences existing endpoints)

**Action:** Share this roadmap. B2B agent can start Phase 4 (guidelines) immediately — no backend changes needed.

### infra-kitchen-gcp

- Phase 2: SendGrid API key in Secret Manager, Cloud Run env vars
- Phase 2: DNS records for domain verification (SPF/DKIM/DMARC)
- Phase 3: Cron job scheduling (Cloud Scheduler → Cloud Run endpoint)

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `vianda-platform/docs/frontend/feedback_for_backend/SUPPLIER_ONBOARDING_STATUS_ENDPOINT.md` | Original B2B spec with detailed requirements |
| `vianda-platform/docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | Full B2B frontend roadmap (Phases 1-7) |
| `vianda-platform/docs/plans/b2b_client/SETUP_WIZARD_POST_CREATE_FLOW_ROADMAP.md` | Related UX pattern for post-create flows |
| `docs/cron/CRON_JOBS_CHEATSHEET.md` | Existing cron job patterns for stall detection |
| `app/services/email_service.py` | Current email implementation to refactor |
