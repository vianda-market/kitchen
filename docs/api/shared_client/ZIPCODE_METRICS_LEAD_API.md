# Zipcode Metrics API (Lead Encouragement)

**Audience**: B2C Lead Encouragement flow, any client showing “do we have coverage?” before signup  
**Last updated**: 2026-02

---

## Purpose

Pre-signup: visitor enters a **zipcode** (or postal code) and sees a short “report” (restaurant count, has coverage) to encourage signup. **No authentication**; rate-limited per IP.

---

## Canonical endpoint (use this path)

| Method | Path |
|--------|------|
| **GET** | **`/api/v1/leads/zipcode-metrics`** |

**Do not** call a differently named endpoint for this use case. The backend implements **only** this path for unauthenticated zipcode metrics. Common mistakes:

| Wrong / other APIs | Use instead |
|--------------------|-------------|
| `POST /api/v1/leads/zipcode-check` | **GET** `/api/v1/leads/zipcode-metrics` |
| `GET /api/v1/leads/by-zipcode` | **GET** `/api/v1/leads/zipcode-metrics` |
| `GET /api/v1/restaurants/zipcode-metrics` | **GET** `/api/v1/leads/zipcode-metrics` |
| `GET /api/v1/restaurants/by-zipcode` | That endpoint is **authenticated** and returns full restaurant list; for pre-signup metrics use **GET** `/api/v1/leads/zipcode-metrics` |

---

## Query parameters

| Parameter       | Required | Default | Description |
|----------------|----------|---------|-------------|
| `zip`          | **Yes**  | —       | Zipcode (or postal code) the lead entered. |
| `country_code` | No       | `US`    | ISO 3166-1 alpha-2 or alpha-3 (e.g. `US`, `AR`, `USA`, `ARG`). API normalizes to alpha-2. See [COUNTRY_CODE_API_CONTRACT.md](COUNTRY_CODE_API_CONTRACT.md). |

**Example**

```
GET /api/v1/leads/zipcode-metrics?zip=90210
GET /api/v1/leads/zipcode-metrics?zip=12345&country_code=US
GET /api/v1/leads/zipcode-metrics?zip=B1601&country_code=AR
```

---

## Response (200 OK)

JSON body with this shape:

| Field                | Type    | Description |
|----------------------|---------|-------------|
| `requested_zipcode`  | string  | Zipcode the lead entered (echo). |
| `matched_zipcode`    | string  | Zipcode used for the count (exact match if available, otherwise a fallback in the country). |
| `restaurant_count`   | number  | Number of restaurants in the matched zipcode (in that country). |
| `has_coverage`       | boolean | `true` if `restaurant_count > 0`. |

**Example**

```json
{
  "requested_zipcode": "90210",
  "matched_zipcode": "90210",
  "restaurant_count": 5,
  "has_coverage": true
}
```

```json
{
  "requested_zipcode": "99999",
  "matched_zipcode": "90210",
  "restaurant_count": 0,
  "has_coverage": false
}
```

---

## Auth and rate limiting

- **No** `Authorization` header. This endpoint is **unauthenticated**.
- **Rate limit**: 60 requests per 60 seconds **per client IP**. If exceeded, the API returns **429 Too Many Requests**.

---

## Errors

| HTTP | Meaning |
|------|---------|
| 422  | Validation error (e.g. missing `zip`). Response body describes the error. |
| 429  | Too many requests; wait and retry. |

---

## Related

- **Authenticated “restaurants by zipcode”**: `GET /api/v1/restaurants/by-zipcode` returns the full restaurant list and is for **post-login** explore; it is **not** for the lead metrics screen. See [RESTAURANTS_BY_ZIPCODE.md](../b2c_client/feedback_from_client/RESTAURANTS_BY_ZIPCODE.md) for both flows.
- **Country codes**: [COUNTRY_CODE_API_CONTRACT.md](COUNTRY_CODE_API_CONTRACT.md).
