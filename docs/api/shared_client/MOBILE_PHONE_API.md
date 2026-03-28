# Mobile Phone API Guide

Reference for all client apps (B2B web, B2C mobile, marketing) consuming phone-related fields and endpoints.

---

## Storage Format

Phone numbers are stored and accepted in **E.164** format: a `+` followed by country code and national number, no spaces or punctuation.

Examples:
- Argentina: `+5491112345678`
- Peru: `+51987654321`
- United States: `+14155552671`

The server validates and normalizes on write. If you pass a local format (e.g., `011 4567-8901`) with a `country_code` hint (e.g., `"AR"`), the server normalizes it to E.164.

---

## Phone Prefix Fields on Market Responses

All market responses (`GET /api/v1/markets`, `GET /api/v1/markets/enriched`, `GET /api/v1/leads/markets`) now include two phone-prefix fields:

| Field | Type | Description |
|-------|------|-------------|
| `phone_dial_code` | `string \| null` | E.164 country prefix, e.g. `"+54"`. `null` for Global pseudo-market. |
| `phone_local_digits` | `integer \| null` | Max digits in the national number after the dial code. Use as `maxLength` hint for phone input fields. `null` for Global. |

### Seed Values

| `country_code` | `phone_dial_code` | `phone_local_digits` |
|----------------|-------------------|----------------------|
| GL (Global)    | `null`            | `null`               |
| AR (Argentina) | `"+54"`           | `10`                 |
| PE (Peru)      | `"+51"`           | `9`                  |
| US (United States) | `"+1"`        | `10`                 |
| CL (Chile)     | `"+56"`           | `9`                  |
| MX (Mexico)    | `"+52"`           | `10`                 |
| BR (Brazil)    | `"+55"`           | `11`                 |

### Usage: Pre-filling the Dial Code Dropdown

Fetch the user's current market from `GET /api/v1/markets/{market_id}` (or use the market embedded in the auth token), then use `phone_dial_code` as the default selection in your country-code dropdown.

```json
// GET /api/v1/markets/00000000-0000-0000-0000-000000000002
{
  "market_id": "00000000-0000-0000-0000-000000000002",
  "country_code": "AR",
  "phone_dial_code": "+54",
  "phone_local_digits": 10,
  ...
}
```

Use `phone_local_digits` as the `maxLength` attribute on the national-number input (the part after the dial code), e.g.:

```html
<input type="tel" maxlength="10" placeholder="11 2345-6789" />
```

---

## Pre-Validation Endpoint

Validates a phone number before storing it. Requires authentication. Intended for real-time form feedback during profile editing or B2B admin forms.

**Always returns HTTP 200**. The `valid` field indicates success or failure. HTTP 422 is reserved for schema-level errors (e.g., missing required fields), not for invalid phone numbers.

### Request

```
POST /api/v1/phone/validate
Content-Type: application/json
```

```json
{
  "mobile_number": "011 4567-8901",
  "country_code": "AR"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `mobile_number` | Yes | Raw phone string. E.164 or local format. |
| `country_code` | No | ISO 3166-1 alpha-2 hint (e.g. `"AR"`). Required to parse local-format numbers. |

### Success Response (200)

```json
{
  "valid": true,
  "e164": "+541145678901",
  "display": "+54 11 4567-8901",
  "error": null
}
```

### Failure Response (200)

```json
{
  "valid": false,
  "e164": null,
  "display": null,
  "error": "Phone number is not a valid number for any country. Verify the number and try again."
}
```

---

## 422 Validation Error Contract

When `mobile_number` is submitted as part of a user create/update request and fails validation, FastAPI returns HTTP 422 with the following shape:

```json
{
  "detail": [
    {
      "loc": ["body", "mobile_number"],
      "msg": "Invalid phone number. Expected E.164 format (e.g. +5491112345678) or a local number with a country hint.",
      "type": "value_error"
    }
  ]
}
```

| Field | Value | Notes |
|-------|-------|-------|
| `loc` | `["body", "mobile_number"]` | Always maps to the `mobile_number` field |
| `type` | `"value_error"` | Standard Pydantic v2 type for `ValueError` |
| `msg` | Human-readable message | Two variants — see below |

### Error Message Variants

**Parse failure** (number can't be parsed at all):
```
Invalid phone number. Expected E.164 format (e.g. +5491112345678) or a local number with a country hint.
```

**Invalid number** (parses but is not a valid number for any country):
```
Phone number is not a valid number for any country. Verify the number and try again.
```

Map the `loc[1]` value (`"mobile_number"`) to the form field to display inline validation errors.

---

## Passing a Country Hint

Any endpoint that accepts `mobile_number` also accepts a `country_code` field as a region hint for parsing local-format numbers. If the number is already E.164 (starts with `+`), the hint is ignored.

```json
{
  "mobile_number": "91112345678",
  "country_code": "AR"
}
```

For B2B admin forms, use the institution's market `phone_dial_code` to auto-select the dial code and populate `country_code`.

---

## Display Format on Enriched User Endpoint

`GET /api/v1/users/enriched` and `GET /api/v1/users/enriched/{user_id}` include a read-only display field alongside the stored E.164:

```json
{
  "mobile_number": "+5491112345678",
  "mobile_number_display": "+54 9 11 2345-6789",
  ...
}
```

`mobile_number_display` is `null` when `mobile_number` is `null`. Use it for display-only contexts (tables, profile views). Always submit the E.164 value (`mobile_number`) for write operations.
