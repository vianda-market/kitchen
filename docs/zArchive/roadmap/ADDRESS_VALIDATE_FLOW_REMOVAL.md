# Address Validate Flow Removal

**Last Updated**: 2026-03-09  
**Purpose**: Plan to deprecate/remove `POST /api/v1/addresses/validate` and Address Validation API usage. All address creation goes through autocomplete + place_id.

---

## Current State

- `POST /api/v1/addresses/validate` — accepts address fields, returns normalized address via Google Address Validation API
- Cost: ~$0.017/address (beyond 5k free tier)
- Client can submit normalized result to create address

---

## Target State

- **Primary flow**: Autocomplete (suggest) → user selects → client sends `place_id` on create
- **No validate endpoint**: Remove or deprecate `POST /addresses/validate`
- **Manual entry**: If needed later, add fallback: structured address fields → Geocoding API (no Address Validation API)

---

## Rationale

1. **Cost**: Autocomplete + Place Details is cheaper (~$0.016/address) and better UX
2. **Simplicity**: One flow for address creation; no dual path
3. **Consistency**: All addresses have Place Details metadata (place_id, viewport, formatted_address_google)

---

## Migration Steps

1. **Deprecate** (optional): Add `Deprecated` header or response field; log usage
2. **Update clients**: Ensure web, iOS, Android use suggest → place_id create
3. **Remove**: Delete route, service method, gateway `validate_address` for Address Validation API
4. **Cleanup**: Remove `AddressValidateRequestSchema`, `AddressValidateResponseSchema`, `AddressNormalizedSchema` if unused
5. **Google Cloud**: Disable Address Validation API for the key (optional; saves quota)

---

## Fallback for Manual Entry (Future)

If rare manual entry is needed (e.g. place not in Google):

- Accept structured fields (street, city, province, country_code)
- Call Geocoding API (not Address Validation)
- Store address + geolocation; place_id, viewport, formatted_address_google remain NULL
