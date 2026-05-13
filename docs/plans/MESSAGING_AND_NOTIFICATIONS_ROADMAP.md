# Messaging and Notifications Roadmap

**Last Updated:** 2026-03-07  
**Status:** Configurability implemented; delivery systems not yet built

---

## Overview

Users can configure messaging preferences via `GET/PUT /api/v1/users/me/messaging-preferences`. The toggles are stored in `user_messaging_preferences`. **No notification delivery systems are implemented yet** — this document roadmaps the five mechanisms and their future phases.

---

## Preference Summary

| # | Preference | Description | Sender | Current Status |
|---|------------|-------------|--------|----------------|
| 1 | Coworker volunteering pickup alert | Push when a coworker offers to pick up your vianda (same restaurant, same time) | App (volunteer action) | Config only; no delivery |
| 2 | Vianda vianda readiness alert | Push when the restaurant signals the vianda is ready | Restaurant (supplier app/API) | Not implemented |
| 3 | Vianda promotions and marketing push | In-app push for promotions, new restaurants, campaigns | Vianda employees (admin tool) | Not implemented |
| 4 | Vianda promotions and marketing emails | Email campaigns (newsletters, offers) | Vianda employees (marketing) | Not implemented |
| 5 | Kitchen start pickup alert | Push when vianda becomes available for pickup at kitchen start (11:30) | System (promotion cron) | Not implemented |

---

## 1. Coworker Volunteering Pickup Alert

**What exists today:**
- `POST /api/v1/vianda-selections/{id}/notify-coworkers` inserts into `coworker_pickup_notification` (records that user A notified user B).
- No actual push delivery.
- No preference check before recording.

**Future phases:**
1. **Preference check:** Before inserting (or before sending), query `user_messaging_preferences` for `notified_user_id`. If `notify_coworker_pickup_alert = false`, skip push (optionally still record for audit).
2. **Push provider integration:** Integrate FCM (Android) and APNs (iOS). Store device tokens per user.
3. **Delivery:** When a volunteer notifies coworkers, send push only to those with `notify_coworker_pickup_alert = true`.

---

## 2. Vianda Vianda Readiness Alert

**What exists today:** Nothing.

**Future phases:**
1. **Restaurant/supplier action:** Define how the supplier app or API signals "vianda is ready" (e.g., status change on `restaurant_transaction` or dedicated event).
2. **Backend event:** On readiness signal, determine affected users and their preferences.
3. **Push delivery:** Send push to customers with `notify_vianda_readiness_alert = true`.

---

## 3. Vianda Promotions and Marketing Push

**What exists today:** Nothing.

**Future phases:**
1. **Admin campaign tool:** Allow Vianda employees to create campaigns (targeting, content, schedule).
2. **Push provider integration:** Same as #1; ensure device tokens are available.
3. **Respect preference:** Before sending, filter by `notify_promotions_push = true`.

---

## 4. Vianda Promotions and Marketing Emails

**What exists today:** Nothing.

**Future phases:**
1. **Email service:** Integrate SendGrid, Mailchimp, or similar.
2. **Campaign tool:** Allow marketing to create and schedule email campaigns.
3. **Respect preference:** Filter recipients by `notify_promotions_email = true`.

---

## 5. Kitchen Start Pickup Alert

**What exists today:** B2C client has added a toggle in Settings > Notifications and forwards `notify_kitchen_start_pickup_alert` on PUT. Backend does not yet store or use it.

**Trigger:** When the kitchen start promotion cron runs (11:30 AM local per market), viandas are promoted from `vianda_selection_info` to `vianda_pickup_live`. For each user whose vianda was just promoted:

- If `notify_kitchen_start_pickup_alert` is true (or unset, treat as true): send a push notification.
- Otherwise: do not send.

**Future phases:**
1. **Preference field:** Add `notify_kitchen_start_pickup_alert` to `user_messaging_preferences` (or equivalent) and to `GET/PUT /api/v1/users/me/messaging-preferences`. Default: true.
2. **Promotion cron hook:** In `vianda_selection_promotion_service` (or kitchen_start_promotion cron), after promoting each selection, enqueue or send push for users with the preference enabled.
3. **Push provider integration:** Same as #1; ensure device tokens are available.
4. **Content (suggested):** "Your vianda is ready for pickup at [restaurant name]"

**Reference:** [feedback_kitchen_start_pickup_notification.md](../api/b2c_client/feedback_kitchen_start_pickup_notification.md)

---

## Dependencies

- **Device tokens:** Required for push (#1, #2, #3). Need endpoints or flows to register/update tokens per user and platform.
- **Email address:** Already stored in `user_info.email`; used for #4.
- **Preference storage:** Done. `user_messaging_preferences` table holds the preference toggles (coworker pickup, vianda readiness, promotions push, promotions email; kitchen start pickup to be added).

---

## Reference

- [MESSAGING_PREFERENCES_B2C.md](../api/b2c_client/MESSAGING_PREFERENCES_B2C.md) — B2C client API guide for preferences UI
- [feedback_kitchen_start_pickup_notification.md](../api/b2c_client/feedback_kitchen_start_pickup_notification.md) — Backend feedback: kitchen start pickup alert
