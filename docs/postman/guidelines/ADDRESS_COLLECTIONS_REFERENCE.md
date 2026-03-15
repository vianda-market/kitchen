# Where addresses are added and where autocomplete is tested

## Address API overview

**Validate endpoint removed** (2026-03): `POST /api/v1/addresses/validate` was removed. All address creation uses either:
- **place_id path**: `POST /api/v1/addresses` with `place_id` (from suggest selection) – backend fetches Place Details
- **Structured path**: `POST /api/v1/addresses` with full fields (street_name, city, province, country_code, etc.) – backend geocodes

Postman cannot emulate the suggest dropdown, so it uses the **structured path** with hardcoded address payloads.

---

## Autocomplete (Suggest only)

**Collection: [002 ADDRESS_AUTOCOMPLETE_AND_VALIDATION](../collections/002 ADDRESS_AUTOCOMPLETE_AND_VALIDATION.postman_collection.json)**

- **Suggest (Autocomplete)** – `GET /api/v1/addresses/suggest?q=...&country=...&limit=5` – returns `{ place_id, display_text }` per suggestion
- **Validate** – Removed; requests to `POST /addresses/validate` will return 404. Use structured create instead.
- **Create Address** – Uses `institutionId` and `supplierUserId` from collection 000 (env/globals). **Run collection 000 first** so those variables are set, or 002 falls back to seed defaults.

---

## Adding addresses via Postman

| Collection | How address is added | Notes |
|------------|----------------------|-------|
| **000 E2E Plate Selection** | POST /addresses with full address fields (structured path) | No validation step; direct create with hardcoded payload |
| **Permissions Testing** | Create Employer (atomic), Create Address for Other User | Structured address in body |
| **INSTITUTION_BANK_ACCOUNT** | Create Address | Structured address |
| **TIMEZONE_DEDUCTION_TESTS** | Create Address | Structured address |

**E2E Plate Selection** runs **Address Suggest (E2E)** (optional; stores first suggestion in `e2eFirstSuggestion`). **Register Supplier Address**, **Register Customer Address**, and **Create Employer (atomic)** use **structured address** from the request body – province, city, street_name, building_number, postal_code, country_code must match supported cities (e.g. CABA + Buenos Aires for AR).

---

## DEV_MODE and API keys

With an environment-specific Google API key set (`GOOGLE_API_KEY_DEV`, `GOOGLE_API_KEY_STAGING`, or `GOOGLE_API_KEY_PROD`; local uses `GOOGLE_API_KEY_DEV`), the Places gateway **always uses the live API** (no mocks). Without a key for the current ENVIRONMENT, suggest/create will fail for place_id path; structured create still works and uses Geocoding API for restaurant/customer addresses when the key is set.
