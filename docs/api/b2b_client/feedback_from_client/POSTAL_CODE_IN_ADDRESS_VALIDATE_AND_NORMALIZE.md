# Postal Code in Address Validate / Normalize – C Value and Mock Responses

**Date**: February 2026  
**Context**: The address normalization modal (confirm step after `POST /api/v1/addresses/validate`) was returning a postal code that “is not working”; user noted postal code had format like **C1425** while most zipcodes elsewhere are 5 digits.

---

## 1) Is the zipcode not taking the C value?

**B2B client behavior**: The frontend **does** take and keep the full `postal_code` value, including any leading "C" or other non-digit characters.

- **Validate request**: `buildValidatePayload` sends `postal_code` from the form as-is (no stripping or digit-only validation).
- **Confirm step**: When the user clicks “Use this address”, we merge `validationResult.normalized` (including `normalized.postal_code`) with the rest of the form and send that to `POST /api/v1/addresses/` or `PUT /api/v1/addresses/:id`. We do not modify `postal_code` in between.

So if the backend returns `normalized.postal_code: "C1425"`, the client will send `postal_code: "C1425"` to create/update. If something then fails (e.g. 400 on create/update, or a later flow that expects only digits), the issue is likely:

- **Backend or DB**: Validation or schema that allows only numeric postal codes (e.g. 5 digits), rejecting values like `C1425`.
- **Recommendation**: Accept and persist **full** `postal_code` as returned by the validate/normalize flow. Formats vary by country (e.g. US 5-digit, Argentina C + digits like C1425). The API contract should allow alphanumeric where the provider returns it.

---

## 2) Should we replace the mock response for a 5-digit zipcode?

- **This repo**: There is **no mock** for `POST /api/v1/addresses/validate` in the B2B frontend; we always call the real API.
- **If a mock exists elsewhere** (backend dev, tests, Postman, etc.):
  - For a **default or US-focused mock**, using a **5-digit** `postal_code` (e.g. `"94103"`) in the validate **response** is a good idea so it matches “most other zipcodes” and avoids confusion with Argentine-style C-prefix.
  - For **Argentina (or other alphanumeric) tests**, keep responses with `postal_code` like `"C1425"` or `"C1043AAZ"` so that full format is exercised end-to-end.

So: **yes**, if the goal is a single, consistent mock that behaves like typical US zipcodes, replace the mock’s normalized response to use a 5-digit `postal_code` (e.g. `"94103"`). Keep alphanumeric formats only where you intentionally test non-US formats.

---

## Summary

| Question | Answer |
|----------|--------|
| Is the frontend dropping the "C" in postal_code? | No. The client passes through the full value from the validate response. |
| Where to fix “not working” if C1425 is rejected? | Backend/DB: allow and persist full `postal_code` (alphanumeric when returned by provider). |
| Replace mock with 5-digit zipcode? | Yes, if the mock is meant to represent a generic/US case; use e.g. `"94103"` in the normalized response. |
