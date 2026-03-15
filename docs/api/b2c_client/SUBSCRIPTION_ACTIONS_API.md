# Subscription Actions API (B2C)

**Audience**: B2C client (Customer role).  
**Purpose**: Cancel, pause (hold), and reactivate subscriptions. All validation and business rules are enforced by the backend.

---

## Endpoints

| Action   | Method | Path | Body | Description |
|----------|--------|------|------|-------------|
| Cancel   | POST   | `/api/v1/subscriptions/{subscription_id}/cancel` | None | Cancel the subscription. Only non-cancelled subscriptions can be cancelled. |
| Hold     | POST   | `/api/v1/subscriptions/{subscription_id}/hold`   | `hold_start_date`, `hold_end_date` | Put subscription on hold. Hold duration max 3 months. |
| Resume   | POST   | `/api/v1/subscriptions/{subscription_id}/resume` | None | Resume from hold. Only callable while subscription is On Hold. |

All require **Bearer token** (Customer). Only the **owning customer** can perform these actions; otherwise the backend returns **403**.

---

## Cancel

**Request**

```http
POST /api/v1/subscriptions/{subscription_id}/cancel
Authorization: Bearer <token>
```

No request body.

**Success**

- **200 OK** — Body: `{ "detail": "Subscription cancelled. You can choose a new plan and subscribe again." }`

The subscription is archived (`is_archived = true`) and removed from the enriched list. The user can immediately create a new subscription in the same market via `POST /subscriptions/with-payment`.

**Errors**

| Status | When | Client behavior |
|--------|------|-----------------|
| 400 | Subscription already cancelled | Show `detail` (e.g. "Subscription is already cancelled.") |
| 403 | Not owner or not Customer role | Show "You cannot cancel this subscription." or generic error |
| 404 | Subscription not found | Show "Subscription not found." |

---

## Hold (Pause)

**Request**

```http
POST /api/v1/subscriptions/{subscription_id}/hold
Authorization: Bearer <token>
Content-Type: application/json

{
  "hold_start_date": "2026-02-20T00:00:00Z",
  "hold_end_date": "2026-04-20T00:00:00Z"
}
```

- `hold_start_date`: ISO 8601. The day the user sets the hold (client sends **today**).
- `hold_end_date`: ISO 8601. The date the user selects (resume date). **Must not be further than 3 months (90 days) from hold_start_date.**

**Success**

- **200 OK** — Body: updated subscription with `subscription_status: "On Hold"`, `hold_start_date`, `hold_end_date` set.

**Errors**

| Status | When | Client behavior |
|--------|------|-----------------|
| 400 | Invalid dates; end before start; or duration > 3 months | Show `detail` (e.g. "Hold duration cannot exceed 3 months") |
| 403 | Not owner or not Customer role | Show generic error |
| 404 | Subscription not found | Show "Subscription not found." |

**Backend behavior**

- When `hold_end_date` is reached, the subscription is automatically moved back to **Active** (on next read of enriched list or by-id). No separate cron required for B2C.

---

## Resume

**Request**

```http
POST /api/v1/subscriptions/{subscription_id}/resume
Authorization: Bearer <token>
```

No request body.

**Success**

- **200 OK** — Body: updated subscription with `subscription_status: "Active"`, `hold_start_date` and `hold_end_date` cleared.

**Errors**

| Status | When | Client behavior |
|--------|------|-----------------|
| 400 | Subscription not on hold | Show `detail` (e.g. "Subscription is not on hold.") |
| 403 | Not owner or not Customer role | Show generic error |
| 404 | Subscription not found | Show "Subscription not found." |

---

## Enriched list and by-id

**GET /api/v1/subscriptions/enriched/** and **GET /api/v1/subscriptions/enriched/{subscription_id}** include:

- **subscription_status** — One of: `"Active"`, `"On Hold"`, `"Pending"`, `"Expired"`, `"Cancelled"`.
- **hold_start_date** — ISO 8601 or null.
- **hold_end_date** — ISO 8601 or null.

Use these to show status, hold range, and enable/disable **Pause** vs **Resume** in the UI (e.g. show Pause when Active, Resume when On Hold).

Subscriptions that are On Hold and whose `hold_end_date` has passed are automatically resumed to Active when the client calls enriched list or by-id; the response will already show `subscription_status: "Active"` and null hold dates.

---

## Client expectations (summary)

- **Cancel**: Confirmation dialog → call cancel endpoint → refetch list on success; show `detail` or generic message on error.
- **Pause**: Modal to choose "Resume on" date (max 3 months from today); send `hold_start_date = today`, `hold_end_date = user-selected`; refetch list on success.
- **Reactivate**: Button when `subscription_status === "On Hold"`; call resume endpoint; refetch list on success.
- Client may validate hold duration ≤ 3 months for UX; backend remains source of truth and returns 400 if exceeded.
