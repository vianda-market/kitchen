# Push Notifications API — B2C Integration

**From:** kitchen backend
**To:** vianda-app (B2C mobile)
**Date:** 2026-04-04

---

## 1. FCM Token Registration

### `POST /api/v1/users/me/fcm-token`

Register or update the user's FCM device token. Call on login and token refresh.

```json
{ "token": "fcm-device-token-string", "platform": "ios" }
```

| Field | Type | Required | Validation |
|---|---|---|---|
| `token` | string | Yes | Non-empty, max 500 chars |
| `platform` | string | Yes | `ios`, `android`, or `web` |

**Behavior:**
- If token already exists for any user → reassigned to current user (device changed hands)
- Multiple tokens per user supported (multiple devices)
- Response: `200 OK` with `{ "detail": "FCM token registered" }`

### `DELETE /api/v1/users/me/fcm-token`

Remove all FCM tokens for the current user. Call on logout.

Response: `200 OK` with `{ "detail": "Deleted N FCM token(s)" }`

---

## 2. Push on Handed Out

When a restaurant clerk marks an order as Handed Out (via `POST /plate-pickup/{id}/hand-out` or `POST /restaurant-staff/verify-and-handoff`), the backend sends an FCM push to the customer.

### Prerequisites
- Customer has registered an FCM token
- Customer's `notify_plate_readiness_alert` messaging preference is `true` (default)

### FCM Payload

```json
{
  "notification": {
    "title": "Plate ready",
    "body": "Did you receive your plate from La Cocina?"
  },
  "data": {
    "type": "pickup_handed_out",
    "plate_pickup_id": "uuid",
    "restaurant_name": "La Cocina"
  }
}
```

- `notification`: shown by OS when app is backgrounded
- `data.type`: `"pickup_handed_out"` — use this to trigger the receipt confirmation modal in the foreground listener
- `data.plate_pickup_id`: the pickup to confirm/dispute via `POST /plate-pickup/{id}/complete`

---

## 3. Token Lifecycle

| Event | B2C Action |
|---|---|
| Login | `POST /users/me/fcm-token` with current token |
| Token refresh (FCM rotation) | `POST /users/me/fcm-token` with new token |
| Logout | `DELETE /users/me/fcm-token` |
| FCM `NotRegistered` / `InvalidRegistration` | Backend auto-deletes stale token |

---

## 4. Multipart Field Names (Portion Complaint)

For `POST /plate-reviews/{id}/portion-complaint`:
- Photo field: `photo` (UploadFile)
- Text field: `complaint_text` (Form field)

---

## 5. scan-qr Timer Fields

`POST /plate-pickup/scan-qr` now returns `arrival_time` and `server_time`:

```
drift = Date.now() - new Date(server_time).getTime()
elapsedSeconds = Math.floor((Date.now() - drift - new Date(arrival_time).getTime()) / 1000)
```

This ensures B2C and B2B count-up timers show the same elapsed time.
