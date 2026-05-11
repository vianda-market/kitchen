# Lead endpoints: rate limit and human check (roadmap)

**Status**: Planned  
**Scope**: Unauthenticated lead endpoints (`/api/v1/leads/*`)

---

## Current behavior (implemented)

- **Limit**: 5 requests per 60 seconds per IP (all lead endpoints share this: cities, city-metrics, zipcode-metrics, email-registered).
- **On 6th request**: Return **429** with detail `"Too many requests. Please try again in 60 seconds."` User is effectively blocked until the 60-second window expires (old timestamps drop off).

---

## Planned: human check after cooldown

When a user hits the rate limit and **comes back after the 60-second cooldown**, we may require a **human check** (e.g. CAPTCHA or similar) before allowing further lead API calls from that IP (or session). This reduces automated enumeration and abuse while keeping normal users unblocked.

**Out of scope for now**: Captured here for the roadmap. Implementation would involve:

- Backend: optional CAPTCHA verification step (e.g. integrate with a provider); issue a short-lived token or flag per IP/session after successful human check; lead endpoints accept requests only when within rate limit or when token is present.
- Frontend: when user receives 429 and later retries, show a human-check challenge before calling lead endpoints again.
- Product/security decision: whether to enable by default, which provider, and how long the “verified” state lasts.

---

## Summary

| Item | Value |
|------|--------|
| Current limit | 5 req / 60 s per IP (all lead endpoints) |
| On 6th request | 429; user must wait 60 seconds |
| Roadmap | Human check (e.g. CAPTCHA) after cooldown before allowing further requests |
