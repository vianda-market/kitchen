# Post-Pickup Flow API — B2C Integration

**From:** kitchen backend
**To:** vianda-app (B2C mobile)
**Date:** 2026-04-04

Backend implementation of the post-pickup flow requested in `vianda-app/docs/frontend/feedback_for_backend/post-pickup-flow-requirements.md`.

---

## 1. Signed QR Codes

QR codes now encode a signed URL:

```
https://vianda.app/qr?id={qr_code_id}&sig={hmac_hex16}
```

- **Algorithm:** HMAC-SHA256 over `qr_code_id` string, truncated to first 16 hex characters
- **Secret:** Server-side only (`QR_HMAC_SECRET`)
- Newly created QR codes automatically use this format. Existing QR codes are regenerated on DB rebuild.

The B2C app should parse `id` and `sig` from the URL query string before calling scan-qr.

---

## 2. `POST /api/v1/vianda-pickup/scan-qr`

### Request

```json
{
  "qr_code_id": "uuid-string",
  "sig": "16-hex-chars"
}
```

Both fields are required. `sig` must be exactly 16 lowercase hex characters.

### Success Response (200)

```json
{
  "vianda_pickup_id": "uuid",
  "vianda_pickup_ids": ["uuid", "uuid"],
  "restaurant_name": "Restaurant Name",
  "restaurant_id": "uuid",
  "viandas": [
    {
      "vianda_name": "Vianda Name",
      "vianda_id": "uuid-or-null",
      "description": null
    }
  ],
  "countdown_seconds": 300,
  "max_extensions": 3,
  "pickup_confirmed": true,
  "confirmation_code": "ABC123"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `vianda_pickup_id` | UUID | Primary pickup ID (first in list) |
| `vianda_pickup_ids` | UUID[] | All pickup IDs for this scan |
| `restaurant_name` | string | Display name for confirmation screen |
| `restaurant_id` | UUID | Restaurant UUID |
| `viandas` | array | Vianda details for display |
| `countdown_seconds` | int | Timer duration (server-configurable, currently 300) |
| `max_extensions` | int | Max timer extensions (server-configurable, currently 3) |
| `pickup_confirmed` | bool | Always `true` on success |
| `confirmation_code` | string | 6-digit numeric code to show restaurant staff |
| `arrival_time` | ISO 8601 datetime | Server timestamp when QR was scanned. Use for count-up timer. |
| `server_time` | ISO 8601 datetime | Server's current time. Use to compute clock drift: `drift = clientNow - serverTime`. |

### Error Responses

| HTTP | `detail` | When |
|------|----------|------|
| 400 | `"invalid_signature"` | HMAC verification fails or QR code not found |
| 400 | `"wrong_restaurant"` | User has orders but at a different restaurant |
| 404 | `"no_active_reservation"` | User has no pending orders anywhere |
| 422 | Validation error | Missing/malformed fields |

---

## 3. `POST /api/v1/vianda-pickup/{id}/complete`

### Request (optional body)

```json
{
  "completion_type": "user_confirmed"
}
```

| Value | Meaning |
|-------|---------|
| `"user_confirmed"` | User tapped "I have received my vianda" (default) |
| `"timer_expired"` | All countdown extensions exhausted; timer hit 0 |

If no body is sent, defaults to `"user_confirmed"` for backward compatibility.

---

## 4. `POST /api/v1/vianda-reviews`

### Request

```json
{
  "vianda_pickup_id": "uuid",
  "stars_rating": 4,
  "portion_size_rating": 2,
  "would_order_again": true,
  "comment": "Great flavor, would love a bit more rice next time."
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `vianda_pickup_id` | UUID | Yes | Must be completed pickup belonging to user |
| `stars_rating` | int | Yes | 1-5 |
| `portion_size_rating` | int | Yes | 1-3 |
| `would_order_again` | bool | No | — |
| `comment` | string | No | Max 500 chars; stripped of leading/trailing whitespace |

Both new fields are optional and nullable. Existing clients omitting them continue to work.

**Important:** Review comments are stored for restaurant consumption only (B2B platform). They are NOT surfaced back to the B2C app. Do not build UI to display other users' comments.

### Response (201)

Same fields as request, plus: `vianda_review_id`, `user_id`, `vianda_id`, `is_archived`, `created_date`, `modified_date`.

---

## 5. Questions Answered

1. **Configurability scope:** `countdown_seconds` and `max_extensions` are global system config. The B2C app reads them from the scan-qr response and does not hardcode them.
2. **Comment moderation:** No moderation. Raw text is stored and surfaced to restaurants in B2B only.
