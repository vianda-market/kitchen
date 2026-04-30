# Terms of Service -- Ad Tracking Consent

**Status:** Not Started
**Goal:** Ensure the subscription flow collects explicit user consent for ad conversion tracking before storing click identifiers or uploading hashed PII to Google Ads / Meta CAPI.
**Dependency:** Blocks Phase 14 of the Ads Platform integration (`docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md`).

---

## Requirements

### 1. Consent Collection

- The subscription flow (B2C app) must include a consent mechanism (checkbox, banner, or toggle) for ad conversion tracking.
- Consent text must clearly state: "We share hashed usage data with advertising partners (Google, Meta) to measure campaign effectiveness."
- Consent must be **opt-in** (not pre-checked) in jurisdictions requiring it (EU/GDPR, California/CCPA).
- May be **opt-out** (pre-checked with clear disclosure) in other jurisdictions, depending on legal review.

### 2. Consent Storage

- Store consent state per user: `ad_tracking_consent` boolean + `ad_tracking_consent_date` timestamp on the user record.
- The backend must check this flag before:
  - Storing click identifiers in `ad_click_tracking`
  - Enqueuing conversion upload jobs to ARQ
  - Uploading hashed PII to Google Ads or Meta CAPI

### 3. Consent Withdrawal

- Users must be able to withdraw consent (settings page or account management).
- On withdrawal: stop future conversion uploads. Existing uploaded conversions cannot be recalled from Google/Meta.

### 4. Market-Specific Rules

| Market | Regulation | Consent Model |
|--------|-----------|---------------|
| Argentina | Personal Data Protection Law (PDPL) | Opt-in recommended |
| Peru | Personal Data Protection Law | Opt-in recommended |
| US (general) | No federal ad consent law | Opt-out acceptable |
| US (California) | CCPA/CPRA | Opt-out with clear disclosure |
| EU (if expanded) | GDPR | Explicit opt-in required |

### 5. Dependencies

- Legal review of consent text per market
- B2C app UI for consent collection (vianda-app agent)
- Backend schema change: add consent columns to user table

---

## Open Questions

1. Does Vianda have existing Terms of Service / Privacy Policy that covers data sharing with ad platforms?
2. Should consent be collected at signup or at subscription time?
3. Is a cookie consent banner needed on vianda-home for Meta Pixel tracking?
