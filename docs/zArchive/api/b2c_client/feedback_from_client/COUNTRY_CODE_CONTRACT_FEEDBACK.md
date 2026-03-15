# B2C Client Feedback: Country Code API Contract

**Re:** [COUNTRY_CODE_API_CONTRACT.md](../../shared_client/COUNTRY_CODE_API_CONTRACT.md)  
**Status:** B2C app aligns with the contract. Updated for the new rule: API accepts alpha-2 or alpha-3 and normalizes to alpha-2 at the boundary.

---

## What we changed (client)

- **Single source of truth:** `src/utils/countryCode.ts` with `DEFAULT_COUNTRY_CODE`, `normalizeCountryCodeAlpha2(code)`, `toAlpha2ForMatching(code)`. We prefer sending canonical alpha-2; for unknown alpha-3 we omit the param (backend default US).
- **Sending country_code:** Leads zipcode-check and restaurants by-zipcode normalize with `normalizeCountryCodeAlpha2`; omit when empty (default US).
- **Matching and display:** MarketContext uses `toAlpha2ForMatching(device region)`. Flag emoji accepts alpha-2 or alpha-3.

---

## High-level feedback to share

1. **Contract is clear.** Accepting alpha-2 or alpha-3 with normalization at the boundary works well; clients can send either form.

2. **Explicit default in endpoint docs.** For each endpoint that accepts optional `country_code` (e.g. leads zipcode-check, restaurants by-zipcode), stating "Default: `US` when omitted" in the endpoint’s own doc (in addition to the central contract) helps clients and Postman users.

3. **Checklist in contract.** The "Quick checklist" at the end of the contract is useful for verifying client behavior.
