# In-App Notification Banners — Backend Plan

**Last Updated:** 2026-04-05
**Status:** Planning
**Origin:** `vianda-app` feedback doc: `docs/frontend/feedback_for_backend/in-app-notification-banners-requirements.md`

---

## Overview

Cross-platform in-app notification banner system. All frontend clients (B2C mobile, B2C web, future B2B) poll for active notifications and render them as banners. Backend owns creation, expiry, deduplication, client filtering, and acknowledgment tracking.

This complements the existing push notification infrastructure (FCM tokens in `core.user_fcm_token`, messaging preferences in `core.user_messaging_preferences`). Push delivers when the app is backgrounded; banners deliver when the app is foregrounded.

---

## Data Model

### New table: `customer.notification_banner`

```sql
CREATE TYPE notification_banner_type_enum AS ENUM (
    'survey_available',
    'peer_pickup_volunteer',
    'reservation_reminder'
);

CREATE TYPE notification_banner_priority_enum AS ENUM ('normal', 'high');

CREATE TYPE notification_banner_action_status_enum AS ENUM (
    'active',
    'dismissed',
    'opened',
    'completed',
    'expired'
);

CREATE TABLE IF NOT EXISTS customer.notification_banner (
    notification_id UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE CASCADE,
    notification_type notification_banner_type_enum NOT NULL,
    priority notification_banner_priority_enum NOT NULL DEFAULT 'normal',
    payload JSONB NOT NULL DEFAULT '{}',
    action_type VARCHAR(50) NOT NULL,
    action_label VARCHAR(100) NOT NULL,
    client_types VARCHAR(20)[] NOT NULL DEFAULT '{b2c-mobile,b2c-web}',
    action_status notification_banner_action_status_enum NOT NULL DEFAULT 'active',
    expires_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    dedup_key VARCHAR(255) NOT NULL,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_notification_banner_user_active
    ON customer.notification_banner(user_id)
    WHERE action_status = 'active';

CREATE INDEX IF NOT EXISTS idx_notification_banner_expires
    ON customer.notification_banner(expires_at)
    WHERE action_status = 'active';
```

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| `JSONB payload` | Notification types have different payloads; avoid type-specific columns. Validated at service layer per type. |
| `dedup_key` (UNIQUE per user) | Prevents duplicate notifications for the same event. Format: `{type}:{source_id}` (e.g. `survey_available:{plate_selection_id}`). |
| `client_types` array | Backend owns filtering. Each notification declares which clients should see it. |
| `action_status` enum | Single column tracks lifecycle: active -> dismissed/opened/completed/expired. |
| No audit/history table | Low-value for Phase 1. Acknowledgment data lives on the row itself. Add history table if analytics needs grow. |

---

## Notification Type Catalog

### `survey_available`

| Field | Value |
|-------|-------|
| Trigger | Plate pickup completed + survey not yet submitted + grace period elapsed (configurable, default 2h) |
| Expiry | 48h after pickup completion |
| Priority | `normal` |
| Client types | `b2c-mobile`, `b2c-web` |
| Dedup key | `survey_available:{plate_selection_id}` |
| Payload | `{ plate_name, pickup_date, plate_selection_id, survey_id }` |
| Action | `type: "open_survey"`, `label: "Rate this plate"` |
| Trigger point | `plate_pickup_service.py` — after marking pickup complete |

### `peer_pickup_volunteer`

| Field | Value |
|-------|-------|
| Trigger | Coworker requests peer pickup + user is eligible volunteer (same restaurant, same time slot) |
| Expiry | End of pickup window |
| Priority | `high` |
| Client types | `b2c-mobile` only (physical pickup required) |
| Dedup key | `peer_pickup_volunteer:{peer_pickup_id}:{user_id}` |
| Payload | `{ coworker_name, restaurant_name, pickup_window, peer_pickup_id }` |
| Action | `type: "volunteer_pickup"`, `label: "I can pick it up"` |
| Trigger point | `plate_selection_service.py` — inside `notify_coworkers` flow |

### `reservation_reminder`

| Field | Value |
|-------|-------|
| Trigger | Upcoming pickup window (1h before start) |
| Expiry | End of pickup window |
| Priority | `normal` |
| Client types | `b2c-mobile`, `b2c-web` |
| Dedup key | `reservation_reminder:{plate_selection_id}:{pickup_date}` |
| Payload | `{ plate_name, restaurant_name, pickup_window, plate_selection_id }` |
| Action | `type: "view_reservation"`, `label: "View details"` |
| Trigger point | New cron job (see Phase 2) |

---

## API Endpoints

### `GET /api/v1/notifications/active`

Returns active, unexpired notifications for the authenticated user, filtered by client type.

**Auth:** `get_current_user` (any authenticated user)

**Query params:**
- `client_type` (optional): `b2c-mobile` | `b2c-web`. If omitted, returns all. If provided, filters where `client_types @> ARRAY[{client_type}]`.

**Response:**
```json
{
  "notifications": [
    {
      "notification_id": "uuid",
      "notification_type": "survey_available",
      "priority": "normal",
      "created_at": "2026-04-05T12:00:00Z",
      "expires_at": "2026-04-07T12:00:00Z",
      "payload": { ... },
      "action": {
        "action_type": "open_survey",
        "action_label": "Rate this plate"
      }
    }
  ]
}
```

**SQL (core query):**
```sql
SELECT notification_id, notification_type, priority, payload,
       action_type, action_label, expires_at, created_date
FROM customer.notification_banner
WHERE user_id = %s
  AND action_status = 'active'
  AND expires_at > NOW()
  -- optional client_type filter:
  AND client_types @> ARRAY[%s]::varchar[]
ORDER BY
  CASE WHEN priority = 'high' THEN 0 ELSE 1 END,
  created_date DESC
LIMIT 5;
```

**Rate limit note:** Frontends poll every 60s. This is a lightweight indexed query; no rate limiting needed at Phase 1. Monitor and add if needed.

### `POST /api/v1/notifications/{notification_id}/acknowledge`

Marks a notification as dismissed/opened/completed.

**Auth:** `get_current_user` — must own the notification.

**Request body:**
```json
{
  "action_taken": "dismissed"
}
```

Valid values: `dismissed`, `opened`, `completed`.

**Behavior:**
- Sets `action_status = {action_taken}` and `acknowledged_at = NOW()`.
- Returns 404 if notification not found or not owned by user.
- Idempotent: re-acknowledging an already-acknowledged notification returns 200 with no change.

---

## Service Layer

### `app/services/notification_banner_service.py`

```
create_notification(user_id, notification_type, priority, payload, action_type, action_label, client_types, expires_at, dedup_key, db, logger)
    → INSERT ... ON CONFLICT (user_id, dedup_key) DO NOTHING
    → Returns notification_id or None if dedup'd

get_active_notifications(user_id, client_type, db, logger)
    → SELECT with filters, LIMIT 5
    → Auto-expires: WHERE expires_at > NOW()

acknowledge_notification(notification_id, user_id, action_taken, db, logger)
    → UPDATE ... WHERE notification_id = %s AND user_id = %s AND action_status = 'active'
    → Returns True/False

expire_stale_notifications(db, logger)
    → UPDATE SET action_status = 'expired' WHERE action_status = 'active' AND expires_at <= NOW()
    → Called by cleanup cron
```

### Payload validation

Each `notification_type` has a required payload schema validated at creation time in the service. Not enforced at DB level (JSONB), enforced at service layer.

```python
REQUIRED_PAYLOAD_FIELDS = {
    "survey_available": {"plate_name", "pickup_date", "plate_selection_id", "survey_id"},
    "peer_pickup_volunteer": {"coworker_name", "restaurant_name", "pickup_window", "peer_pickup_id"},
    "reservation_reminder": {"plate_name", "restaurant_name", "pickup_window", "plate_selection_id"},
}
```

---

## Route Registration

New route file: `app/routes/notification_banner.py`

```python
router = create_versioned_router("api", ["Notifications"], APIVersion.V1)
# prefix: /notifications
```

Register in `application.py` after user routes.

---

## Schema Sync Checklist

Per CLAUDE.md "DB Schema Change — Sync All Layers":

1. `schema.sql` — new enums + `customer.notification_banner` table
2. `trigger.sql` — `modified_date` auto-update trigger (no history table in Phase 1)
3. `seed.sql` — no seed data needed
4. `index.sql` — partial indexes (user active, expires)
5. `app/dto/models.py` — `NotificationBannerDTO`
6. `app/schemas/consolidated_schemas.py` — `NotificationBannerResponseSchema`, `NotificationAcknowledgeSchema`, `ActiveNotificationsResponseSchema`

---

## Phased Implementation

### Phase 1: Core infrastructure + survey_available

**Scope:** Table, service, endpoints, `survey_available` trigger only.

1. DB: Add enums, table, indexes, trigger
2. DTO + Schemas
3. `notification_banner_service.py` — CRUD operations
4. `notification_banner.py` route — GET active, POST acknowledge
5. Register route in `application.py`
6. Wire `survey_available` trigger into `plate_pickup_service.py` — after `complete_pickup()`, create notification if no review exists
7. Expiry cleanup: add `expire_stale_notifications()` call to an existing daily cron or create a lightweight one

**Deliverable:** Frontend can poll `/notifications/active` and get survey banners. Acknowledge works.

### Phase 2: reservation_reminder + cron

**Scope:** Reservation reminder creation via cron job.

1. New cron: `app/services/cron/notification_banner_cron.py`
   - Runs every 15 minutes
   - Queries `plate_pickup_live` for pickups with window starting within 1h
   - Creates `reservation_reminder` notifications (dedup prevents duplicates on re-run)
2. Wire expiry cleanup into same cron
3. Cron endpoint: `POST /api/v1/notifications/generate-reminders` (Internal only)

### Phase 3: peer_pickup_volunteer

**Scope:** Peer pickup volunteer notifications.

1. Wire into existing `notify_coworkers` flow in `plate_selection_service.py`
2. Create `peer_pickup_volunteer` notification for each eligible coworker
3. Respect `user_messaging_preferences.can_participate_in_plate_pickups` — skip users who opted out

### Phase 4: Analytics + new types

**Scope:** Extend as needed.

- Add new enum values for future types (e.g. `promotion`, `benefit_enrolled`, `subscription_expiring`)
- Consider adding `customer.notification_banner_history` audit table if analytics requirements grow
- Evaluate WebSocket/SSE upgrade based on Phase 1-3 polling usage data

---

## Integration with Existing Systems

| System | Integration |
|--------|-------------|
| `user_messaging_preferences` | `peer_pickup_volunteer` respects `can_participate_in_plate_pickups`. Future types respect relevant preferences. |
| FCM push (`push_notification_service.py`) | Complementary — push for background, banners for foreground. Same event may trigger both. Frontend deduplicates by `notification_id`. |
| `coworker_pickup_notification` table | Existing table records the notification event. New banner system delivers it visually. Both can coexist. |
| `x-client-type` header | Already sent by B2C mobile. `client_type` query param is the filtering mechanism for banners. |

---

## Cross-Repo Impact

| Repo | Impact | Doc to produce |
|------|--------|----------------|
| **vianda-app** (B2C) | Frontend already built, waiting for these endpoints. No new doc needed — they wrote the requirements. | `docs/api/b2c_client/NOTIFICATION_BANNERS_API.md` (endpoint contract) |
| **vianda-platform** (B2B) | No immediate impact. Future: admin tool to create promotional banners. | None for Phase 1 |
| **infra-kitchen-gcp** | Phase 2 cron job needs Cloud Scheduler trigger. | `docs/api/internal/NOTIFICATION_BANNER_CRON.md` after Phase 2 |

---

## Open Questions

1. **Survey grace period:** How long after pickup before showing the survey banner? Suggested: 2h (let user eat first). Configurable via `SURVEY_BANNER_GRACE_HOURS` setting.
2. **Max active cap:** Frontend doc suggests max 5. Hardcoded in LIMIT or configurable? Suggest: hardcoded LIMIT 5 for Phase 1, with `high` priority always sorted first.
3. **Notification TTL for acknowledged:** Should acknowledged notifications be cleaned up (hard delete) after N days, or kept indefinitely? Suggest: keep for 90 days, then purge via cron.
