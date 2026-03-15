# Backend feedback: Notification service for pickup availability at kitchen start

**Purpose:** Request backend to implement a push notification service that notifies users when their plate becomes available for pickup at kitchen start (11:30 AM local, per market).

**Audience:** Backend team  
**Related:** [PICKUP_AVAILABILITY_AT_KITCHEN_START.md](./PICKUP_AVAILABILITY_AT_KITCHEN_START.md), [MESSAGING_PREFERENCES_B2C.md](./MESSAGING_PREFERENCES_B2C.md)

---

## 1. Request

Users with an active pickup (plate reserved for today) must receive a push notification when kitchen_day starts so they know their plate is ready for pickup. The B2C client has added a placeholder toggle in Settings > Notifications; the backend must implement the notification service and expose the preference field.

---

## 2. Preference field

**Add to GET/PUT `/api/v1/users/me/messaging-preferences`:**

| Field | Type | Description |
|-------|------|-------------|
| `notify_kitchen_start_pickup_alert` | boolean | When true, user receives a push notification when their plate becomes available for pickup at kitchen start (11:30 AM). Default: true. |

Per [MESSAGING_PREFERENCES_B2C.md](./MESSAGING_PREFERENCES_B2C.md), the client will:
- Display the toggle in the Notifications section
- Send the value on PUT when the user changes it
- Default to `true` when the field is missing (e.g. existing users before backend adds it)

---

## 3. Trigger

When **kitchen start time** is reached for a market (e.g. 11:30 AM local, from `MarketConfiguration.business_hours[day].open`):

1. The backend promotes plate selections to live (assigns `plate_pickup_id`).
2. For each user whose plate was just promoted:
   - If `notify_kitchen_start_pickup_alert` is true (or unset, treat as true): send a push notification.
   - Otherwise: do not send.

---

## 4. Delivery

- **Channel:** Push notification
- **Respect preference:** Do not send if `notify_kitchen_start_pickup_alert` is false.
- **Content (suggested):** "Your plate is ready for pickup at [restaurant name]"

---

## 5. Client status

The B2C client has added:
- `notify_kitchen_start_pickup_alert` as an optional field in `MessagingPreferences` types
- A toggle in Profile > Preferences > Notifications
- Default value `true` when the field is not yet returned by the API

The client will forward the value to PUT `/api/v1/users/me/messaging-preferences` when the user changes the toggle. Backend may ignore it until the notification service is implemented; once both are in place, the flow will work end-to-end.
