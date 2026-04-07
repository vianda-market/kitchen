# SendGrid Email Infrastructure

**Audience**: infra-kitchen-gcp (Pulumi repo)  
**Purpose**: Everything the infrastructure layer must provision and configure to enable SendGrid email on the Kitchen backend, replacing Gmail SMTP for production.  
**Last Updated**: 2026-04-04  
**Backend source**: `app/services/email/` (provider abstraction), `app/config/settings.py`

---

## Status by Environment

| Environment | Status | Provider | Notes |
|-------------|--------|----------|-------|
| Local dev | Active | SMTP (Gmail) | `EMAIL_PROVIDER=smtp`, no SendGrid needed |
| GCP dev | Ready to activate | SendGrid | Set secrets + env vars below |
| GCP staging | Ready to activate | SendGrid | Same as dev; use separate SendGrid sub-user or API key |
| GCP prod | Ready to activate | SendGrid | Production sender domain must be verified first |

---

## Why This Change

The backend currently uses Gmail SMTP (`smtp.gmail.com:587`) for all transactional emails. This has hard limits that block production scale:

| Limitation | Gmail SMTP | SendGrid (GCP Marketplace) |
|-----------|-----------|---------------------------|
| Daily limit | 500 emails/day | 12,000/month free tier |
| Domain auth | None (Gmail app password) | Full SPF/DKIM/DMARC |
| Deliverability | Low — lands in spam | High — verified sender |
| Bounce handling | None | Automatic suppression |
| From address | `vianda.app@gmail.com` | `hello@vianda.market` |
| Analytics | None | Open/click/bounce tracking |

The backend already has the provider abstraction in place (`EMAIL_PROVIDER` setting). Infra just needs to provision the SendGrid account, store the API key, set env vars, and configure DNS.

---

## What the Backend Expects

The backend reads these values via `app/config/settings.py` (Pydantic `BaseSettings`, loaded from env). All email settings default to empty — the app falls back to SMTP mode when `EMAIL_PROVIDER` is not `sendgrid`.

### Required Environment Variables (SendGrid active)

| Variable | Type | Required When | Description |
|----------|------|---------------|-------------|
| `EMAIL_PROVIDER` | string | Always | Set to `sendgrid` to activate. Default: `smtp` |
| `SENDGRID_API_KEY` | secret | `EMAIL_PROVIDER=sendgrid` | SendGrid API key with Mail Send permission. Format: `SG.xxxxx`. Never log or commit. |
| `EMAIL_FROM_ADDRESS` | string | `EMAIL_PROVIDER=sendgrid` | Verified sender address. **Must be**: `hello@vianda.market` |
| `EMAIL_FROM_NAME` | string | Optional | Display name in From header. Default: `Vianda` |
| `EMAIL_REPLY_TO` | string | Optional | Reply-to address so user replies reach support. **Should be**: `support@vianda.market` |

### SMTP Variables (kept for dev fallback)

These existing variables continue to work when `EMAIL_PROVIDER=smtp` (local dev):

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | Default: `smtp.gmail.com` |
| `SMTP_PORT` | Default: `587` |
| `SMTP_USERNAME` | Gmail address |
| `SMTP_PASSWORD` | Gmail app-specific password |
| `FROM_EMAIL` | Fallback sender address |
| `FROM_NAME` | Fallback display name |

---

## GCP Secret Manager

Store the SendGrid API key in Secret Manager — not as a plain Cloud Run env var.

### Secret naming convention

```
vianda-{stack}-sendgrid-api-key    # e.g. kitchen-sendgrid-api-key-dev
```

### Secret Manager → Cloud Run binding

Mount the secret as the `SENDGRID_API_KEY` environment variable on the Cloud Run service. The Cloud Run service account needs `roles/secretmanager.secretAccessor` on the secret.

```
# Pulumi pattern (Python)
sendgrid_api_key = gcp.secretmanager.Secret("vianda-dev-sendgrid-api-key", ...)
# Then in Cloud Run service template:
env_vars = [
    {"name": "EMAIL_PROVIDER", "value": "sendgrid"},
    {"name": "EMAIL_FROM_ADDRESS", "value": "hello@vianda.market"},
    {"name": "EMAIL_FROM_NAME", "value": "Vianda"},
    {"name": "EMAIL_REPLY_TO", "value": "support@vianda.market"},
]
secret_env_vars = [
    {"name": "SENDGRID_API_KEY", "secret": "vianda-dev-sendgrid-api-key", "version": "latest"},
]
```

---

## SendGrid Account Setup

### Step 1 — Provision via GCP Marketplace

1. Go to GCP Console → Marketplace → search "SendGrid"
2. Subscribe to the **free tier** (12,000 emails/month)
3. This creates a SendGrid account linked to the GCP project
4. Log into SendGrid Dashboard from the Marketplace listing

### Step 2 — Create API Key

1. SendGrid Dashboard → Settings → API Keys → Create API Key
2. Name: `kitchen-backend-{env}` (e.g., `vianda-dev-sendgrid`)
3. Permissions: **Restricted Access** → enable only:
   - **Mail Send**: Full Access
4. Copy the key (shown only once) → store in GCP Secret Manager

### Step 3 — One API key per environment

| Environment | API Key Name | Secret Manager Key |
|-------------|-------------|-------------------|
| dev | `vianda-dev-sendgrid` | `vianda-dev-sendgrid-api-key` |
| staging | `vianda-staging-sendgrid` | `vianda-staging-sendgrid-api-key` |
| prod | `vianda-prod-sendgrid` | `vianda-prod-sendgrid-api-key` |

---

## DNS Configuration (vianda.market)

SendGrid requires domain authentication for production deliverability. This involves adding DNS records to the `vianda.market` domain.

### Step 1 — Authenticate Sender Domain in SendGrid

1. SendGrid Dashboard → Settings → Sender Authentication → Authenticate Your Domain
2. DNS host: select your registrar or "Other"
3. Domain: `vianda.market`
4. SendGrid generates 3 DNS records to add

### Step 2 — Add DNS Records

SendGrid will provide specific values. The records follow this pattern:

| Type | Host | Value | Purpose |
|------|------|-------|---------|
| CNAME | `s1._domainkey.vianda.market` | `s1.domainkey.u{id}.wl{id}.sendgrid.net` | DKIM signature 1 |
| CNAME | `s2._domainkey.vianda.market` | `s2.domainkey.u{id}.wl{id}.sendgrid.net` | DKIM signature 2 |
| CNAME | `em{id}.vianda.market` | `u{id}.wl{id}.sendgrid.net` | SPF/Return-Path |

### Step 3 — Add DMARC Record

Add this TXT record manually (SendGrid doesn't auto-generate it):

| Type | Host | Value |
|------|------|-------|
| TXT | `_dmarc.vianda.market` | `v=DMARC1; p=quarantine; rua=mailto:dmarc@vianda.market; pct=100` |

Start with `p=quarantine` (soft enforcement). Move to `p=reject` after verifying deliverability.

### Step 4 — Verify in SendGrid

After DNS propagation (usually 15–60 minutes), click "Verify" in SendGrid Dashboard. All 3 records must show green checkmarks.

---

## Email Categories (Analytics)

The backend sends emails with SendGrid categories for tracking:

| Category | Email Types | Tracking |
|----------|------------|----------|
| `onboarding-nudge` | Getting started, need help, setup incomplete | Opens + clicks |
| `transactional` | Password reset, verification, invite | Delivery only (no click tracking for security) |

These categories appear in SendGrid Activity Feed and can be used for filtering in the SendGrid Dashboard.

---

## Activation Checklist

Complete these in order per environment:

- [ ] SendGrid account provisioned via GCP Marketplace
- [ ] API key created with Mail Send permission only
- [ ] API key stored in Secret Manager: `vianda-{stack}-sendgrid-api-key`
- [ ] DNS records added to `vianda.market` (2x DKIM CNAME + 1x SPF CNAME)
- [ ] DMARC TXT record added to `vianda.market`
- [ ] Domain verified in SendGrid Dashboard (green checkmarks)
- [ ] Cloud Run env vars set: `EMAIL_PROVIDER=sendgrid`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, `EMAIL_REPLY_TO`
- [ ] Cloud Run secret binding: `SENDGRID_API_KEY` → Secret Manager
- [ ] Test: send a password reset email from the environment and verify delivery + correct From/Reply-To headers

---

## Rollback

To revert to Gmail SMTP on any environment:

1. Set `EMAIL_PROVIDER=smtp` on Cloud Run (or remove the var — defaults to `smtp`)
2. Ensure `SMTP_USERNAME` and `SMTP_PASSWORD` are still set
3. Redeploy — no code changes needed, the provider abstraction handles the switch

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | Phase 2 roadmap with email upgrade rationale |
| `app/services/email/provider_factory.py` | Provider selection logic |
| `app/config/settings.py` | All email settings (lines 34–38) |
| `docs/api/infrastructure/STRIPE_PAYMENT_INFRASTRUCTURE.md` | Similar pattern for Stripe secret provisioning |
