# Where addresses are added and where autocomplete is tested

## Autocomplete is tested only here

**Collection: [ADDRESS_AUTOCOMPLETE_AND_VALIDATION.postman_collection.json](ADDRESS_AUTOCOMPLETE_AND_VALIDATION.postman_collection.json)**

- **Suggest (Autocomplete)** – `GET /api/v1/addresses/suggest?q=...&country=...&limit=5`
- **Validate (Normalize)** – `POST /api/v1/addresses/validate`
- **E2E: Suggest → Validate → Create Address** – runs suggest, then validate, then **creates an address** with the normalized payload so the full autocomplete flow is covered.

So: the only collection that tests address **autocomplete** is **Address Autocomplete and Validation**. The same collection now includes a flow that **adds an address** using the normalized result from validate (see folder “E2E: Suggest → Validate → Create Address”).

---

## How it works without Google API keys

Suggest and validate **work without a Google API key** because the backend supports **DEV_MODE** (default when `GOOGLE_MAPS_API_KEY` is not set). In DEV_MODE, the Google Places gateway uses **mock responses** from `app/mocks/address_autocomplete_mocks.json` instead of calling Google. So Postman (and local runs) can exercise the full suggest → validate → create flow without any API key. For production, set `GOOGLE_MAPS_API_KEY` and run with `DEV_MODE=false` to use the real Places API and Address Validation API.

---

## Other collections that add an address (no autocomplete)

These create addresses via **POST /api/v1/addresses/** (or embedded in employer) with **hardcoded payloads**. They do **not** call suggest or validate.

| Collection | Where address is added | Purpose |
|------------|------------------------|--------|
| **TIMEZONE_DEDUCTION_TESTS** | “Create Address - Argentina (ARG)”, Peru, Chile, USA CA/NY/TX, etc. | Timezone deduction by country/province |
| **Permissions Testing - Employee-Only Access** | “Create Address for Other User”; “Create Employer (Atomic)” (embedded address); “POST /employers/…/addresses” | Permission and operator tests |
| **INSTITUTION_BANK_ACCOUNT_POSTMAN_COLLECTION** | “Create Address” (then entity, then bank account) | Bank account flow needs an address_id |
| **E2E Plate Selection** | “Register Supplier Address”; “Register Customer Address” | E2E supplier and customer setup |

**E2E Plate Selection** now emulates the normal flow: after **Login Admin** it runs **Address Suggest (E2E)** and **Address Validate (E2E)**; the validate response's **normalized** address is stored in `e2eNormalizedAddress`. **Register Supplier Address**, **Register Customer Address**, and **Create Employer (atomic)** use that payload when set (otherwise the existing hardcoded body). So the main E2E collection emulates: call API, get recommended address, "user accepts" by using it when creating addresses.

To run a dedicated autocomplete E2E (suggest → validate → create one address), use **Address Autocomplete and Validation** and the folder **E2E: Suggest → Validate → Create Address**.
