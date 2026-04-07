# Lead Interest Alert Crons

**Status:** Planned  
**Depends on:** `core.lead_interest` table (implemented), email provider (implemented)  
**Pattern:** Follows `app/services/cron/customer_engagement.py`

---

## Overview

Two cron jobs that notify leads when new restaurants open in their area. Data comes from `core.lead_interest` records with `status = 'active'`.

---

## Cron 1: Zipcode Alert ("Close to you")

**Trigger:** New restaurant becomes Active in a zipcode where leads exist.  
**Audience:** All leads with that zipcode (regardless of `zipcode_only` flag).  
**Message:** "A new restaurant just opened near you in [zipcode]!"  
**Frequency:** Daily scan — compare new Active restaurants (last 24h) against lead interest zipcodes.

## Cron 2: City Alert ("In your city")

**Trigger:** Periodic digest of new restaurants in a city.  
**Audience:** Leads where `zipcode_only = false` for that city.  
**Message:** "X new restaurants opened in [city]!"  
**Frequency:** Weekly digest — aggregate new restaurants per city over the past 7 days.

---

## Shared Design

- Update `lead_interest.status` to `'notified'` and set `notified_date` after sending
- Use existing email provider (`app/services/email_service.py`)
- New email templates in `app/services/email/templates/`
- Cooldown: don't re-notify the same lead within 7 days
- Unsubscribed leads (`status = 'unsubscribed'`) are skipped
- Cron endpoint: `POST /api/v1/admin/leads/run-alerts` (Internal auth, same pattern as other cron endpoints)
- Cloud Scheduler entry needed (infra-kitchen-gcp)

---

## Files to Create/Change

| File | Change |
|------|--------|
| `app/services/cron/lead_interest_alerts.py` | **NEW** — alert logic, restaurant diff detection |
| `app/services/email/templates/lead_zipcode_alert.html` | **NEW** — "close to you" email |
| `app/services/email/templates/lead_city_alert.html` | **NEW** — "in your city" digest email |
| `app/services/email_service.py` | Add `send_lead_zipcode_alert()`, `send_lead_city_alert()` |
| `app/routes/admin/leads.py` | Add `POST /admin/leads/run-alerts` cron endpoint |
| infra-kitchen-gcp | Cloud Scheduler: daily for zipcode, weekly for city |

---

## Related

- `docs/plans/LEADS_MIGRATION_TO_MARKETING_SITE.md` — parent plan (Phase 3)
- `core.lead_interest` table — data source
- `app/services/cron/customer_engagement.py` — pattern to follow
