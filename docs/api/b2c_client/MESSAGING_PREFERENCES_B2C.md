# Messaging Preferences - B2C Client Guide

**Audience:** B2C app (Customer/Comensal)  
**Last Updated:** 2026-03-08

---

## Overview

Users can configure six on/off toggles for messaging, notifications, and privacy. The preferences are persisted in the backend. **Notification toggles have no effect until the corresponding notification systems are implemented** — this API establishes configurability so the B2C client can build the Settings UI now. **Privacy and plate pickup toggles take effect immediately** (see impact below).

| Preference | Description | Impact |
|------------|-------------|--------|
| Coworker volunteering pickup alert | Push when a coworker offers to pick up your plate | `notify_coworker_pickup_alert` |
| Vianda plate readiness alert | Push when the restaurant signals the plate is ready | `notify_plate_readiness_alert` |
| Vianda promotions and marketing push | In-app push for promotions, new restaurants, campaigns | `notify_promotions_push` |
| Vianda promotions and marketing emails | Email campaigns (newsletters, offers) | `notify_promotions_email` |
| Co-workers can see my orders | Allow coworkers to see my orders in explore and coworker-facing lists | Excluded from `has_volunteer` when false |
| I can participate in / organize plate pickups | I can appear on coworker list for pickup offers and volunteer | Excluded from coworker list and `has_volunteer` when false; cascade sets `coworkers_can_see_my_orders` and `notify_coworker_pickup_alert` to false |

---

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/v1/users/me/messaging-preferences` | Bearer token (required) |
| PUT | `/api/v1/users/me/messaging-preferences` | Bearer token (required) |

---

## GET /api/v1/users/me/messaging-preferences

**Response:** 200 OK

```json
{
  "notify_coworker_pickup_alert": true,
  "notify_plate_readiness_alert": true,
  "notify_promotions_push": true,
  "notify_promotions_email": false,
  "coworkers_can_see_my_orders": true,
  "can_participate_in_plate_pickups": true
}
```

- Creates a default row (all `true`) if the user has never accessed preferences.
- All six fields are always present.

---

## PUT /api/v1/users/me/messaging-preferences

**Request body:** All fields optional. Only sent fields are updated.

```json
{
  "notify_coworker_pickup_alert": false,
  "notify_plate_readiness_alert": true,
  "notify_promotions_push": true,
  "notify_promotions_email": false,
  "coworkers_can_see_my_orders": true,
  "can_participate_in_plate_pickups": true
}
```

**Response:** 200 OK — same shape as GET.

**Cascade:** When `can_participate_in_plate_pickups` is set to `false`, the backend also sets `coworkers_can_see_my_orders` and `notify_coworker_pickup_alert` to `false`. Marketing prefs (`notify_promotions_push`, `notify_promotions_email`) and `notify_plate_readiness_alert` are not affected.

---

## UI Guidance

| Setting | Suggested label | Placement |
|--------|-----------------|-----------|
| `notify_coworker_pickup_alert` | "Coworker pickup alerts" / "When a coworker offers to pick up your plate" | Settings > Notifications |
| `notify_plate_readiness_alert` | "Plate ready alerts" / "When your plate is ready for pickup" | Settings > Notifications |
| `notify_promotions_push` | "Promotions and offers (push)" | Settings > Notifications |
| `notify_promotions_email` | "Promotions and offers (email)" | Settings > Notifications |
| `coworkers_can_see_my_orders` | "Allow co-workers to see what I'm ordering" | Settings > Privacy / Co-workers |
| `can_participate_in_plate_pickups` | "I can participate in / organize plate pickups" | Settings > Plate pickups |

- **Defaults:** All six default to `true` for new users.
- **Toggle behavior:** Each is a simple on/off; call PUT when the user changes any toggle.
- **Partial update:** Send only the toggles that changed to minimize payload size.

---

## Field Descriptions

| Field | Description |
|-------|-------------|
| `notify_coworker_pickup_alert` | When a coworker (same employer) offers to pick up your plate from the same restaurant at the same time, receive a push notification. Set to false when `can_participate_in_plate_pickups` is false (cascade). |
| `notify_plate_readiness_alert` | When the restaurant signals your plate is ready for pickup, receive a push notification. |
| `notify_promotions_push` | Receive in-app push notifications for promotions, new restaurants, and marketing campaigns from Vianda. |
| `notify_promotions_email` | Receive email campaigns (newsletters, offers) from Vianda. |
| `coworkers_can_see_my_orders` | When true, your orders (including volunteer offers) appear in explore and coworker-facing lists (e.g. `has_volunteer`). When false, they are hidden. Set to false when `can_participate_in_plate_pickups` is false (cascade). |
| `can_participate_in_plate_pickups` | When true, you appear on the coworker list for "Offer to pick up" and contribute to `has_volunteer`. When false, you are excluded from both. Setting to false cascades to `coworkers_can_see_my_orders` and `notify_coworker_pickup_alert`. Marketing prefs are not affected. |

---

## Related

- [B2C_ENDPOINTS_OVERVIEW.md](./B2C_ENDPOINTS_OVERVIEW.md) — Full list of Customer APIs
- [MESSAGING_AND_NOTIFICATIONS_ROADMAP.md](../../roadmap/MESSAGING_AND_NOTIFICATIONS_ROADMAP.md) — Roadmap for notification delivery systems
