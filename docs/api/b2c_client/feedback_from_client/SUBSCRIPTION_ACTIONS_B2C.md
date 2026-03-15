# Subscription Actions (Cancel, Pause, Reactivate)

**B2C client expectation** for the Plan screen: per-subscription actions (Cancel, Pause when Active, Reactivate when On Hold). All validation and business rules must be enforced by the backend.

**Purpose:** Allow customers to cancel a subscription, put it on hold (pause) with a chosen end date (max 3 months), or reactivate from hold anytime before that date. When `hold_end_date` is reached, the subscription must automatically move back to Active.

---

## Cancel

### Endpoint (suggestion)

```http
POST /api/v1/subscriptions/{subscription_id}/cancel
Authorization: Bearer <token>
Content-Type: application/json
```

(Client will use whatever path the backend documents.)

### Request

- No request body required unless backend prefers idempotency/confirmation.

### Response (success)

- **Status:** `200 OK` or `204 No Content`.
- **Body (if 200):** Updated subscription with `subscription_status = "Cancelled"` (or equivalent).

### Backend behavior

- Only the owning customer can cancel.
- Only non-cancelled subscriptions can be cancelled.
- Idempotent if already cancelled (optional; return same success or 400).

### Error responses (suggested)

| Status | When                  | Client behavior                            |
| ------ | --------------------- | ------------------------------------------ |
| 400    | Invalid state (e.g. already cancelled) | Show validation message from `detail`. |
| 403    | Not owner             | Show "You cannot cancel this subscription." |
| 404    | Subscription not found | Show "Subscription not found."          |

---

## Pause (Hold)

### Endpoint (existing)

```http
POST /api/v1/subscriptions/{subscription_id}/hold
Authorization: Bearer <token>
Content-Type: application/json
```

### Request body

| Field             | Type   | Required | Notes                                                                 |
| ----------------- | ----- | -------- | --------------------------------------------------------------------- |
| `hold_start_date` | string| Yes      | ISO 8601 date. The day the user sets the hold (client sends **today**). |
| `hold_end_date`   | string| Yes      | ISO 8601 date. The date the user selects (resume date). **Must not be further than 3 months from today.** |

**Example:**

```json
{
  "hold_start_date": "2026-02-20T00:00:00Z",
  "hold_end_date": "2026-04-20T00:00:00Z"
}
```

### Response (success)

- **Status:** `200 OK`.
- **Body:** Updated subscription with `subscription_status = "On Hold"` and `hold_start_date`, `hold_end_date` set. Use the **"On Hold"** enum value per [ENUM_SERVICE_SPECIFICATION.md](../../shared_client/ENUM_SERVICE_SPECIFICATION.md) / [ENUM_SERVICE_API.md](../../shared_client/ENUM_SERVICE_API.md).

### Backend behavior

- **Schema:** `hold_start_date` = the day the user sets the hold (client sends today). `hold_end_date` = the date the user selects (resume date); must not be further than 3 months from `hold_start_date` (or from today). Return **400** with a clear `detail` if exceeded (e.g. "Hold duration cannot exceed 3 months").
- Hold end date must be after hold start date.
- User is not billed during hold; user cannot select plates during hold.
- **When `hold_end_date` is reached:** The subscription must automatically move back to **Active** (backend responsibility; e.g. scheduled job or on-read).
- **Anytime before `hold_end_date`:** The user may reactivate via the UI (Resume action); `POST .../resume` must set `subscription_status` to **"Active"**.

### Error responses (suggested)

| Status | When                  | Client behavior                            |
| ------ | --------------------- | ------------------------------------------ |
| 400    | Invalid dates, or duration > 3 months | Show `detail` or "Hold duration cannot exceed 3 months." |
| 403    | Not owner             | Show generic error.                        |
| 404    | Subscription not found | Show "Subscription not found."          |

---

## Reactivate (Resume)

### Endpoint (existing)

```http
POST /api/v1/subscriptions/{subscription_id}/resume
Authorization: Bearer <token>
```

No request body.

### Response (success)

- **Status:** `200 OK`.
- **Body:** Updated subscription with `subscription_status = "Active"`.

### Backend behavior

- Callable **anytime** while the subscription is On Hold (including before `hold_end_date`).
- Sets `subscription_status` to **"Active"** and clears or retains hold dates per backend policy.

### Error responses (suggested)

| Status | When                  | Client behavior                            |
| ------ | --------------------- | ------------------------------------------ |
| 400    | Invalid state (e.g. not On Hold) | Show `detail`.                      |
| 403    | Not owner             | Show generic error.                        |
| 404    | Subscription not found | Show "Subscription not found."          |

---

## Enriched list

B2C uses **`GET /api/v1/subscriptions/enriched/`** to list subscriptions. The response must include for each subscription:

- **`subscription_status`** — use enum value **"On Hold"** when on hold (not a generic "Inactive").
- **`hold_start_date`** — ISO 8601 or null.
- **`hold_end_date`** — ISO 8601 or null.

So the client can show status, hold range, and enable/disable Pause vs Reactivate correctly.

---

## Client expectations

- Cancel: confirmation dialog; then call cancel endpoint; refetch list on success; show `detail` or generic message on error.
- Pause: modal to choose "Resume on" date (max 3 months from today); send `hold_start_date = today`, `hold_end_date = user-selected`; refetch list on success.
- Reactivate: button when `subscription_status === 'On Hold'`; call resume endpoint; refetch list on success.
- Client validates hold duration ≤ 3 months for UX; backend remains source of truth and may return 400.
