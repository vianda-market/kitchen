# Leads Simplification — B2C App Changes

**Audience:** vianda-app (B2C mobile) agent  
**Context:** The leads discovery flow is moving to the vianda-home marketing site. The B2C app no longer needs to check coverage or show "not served" dead ends. The app becomes a product for qualified, served users.

---

## What to Remove

### Screens / UI
- **City metrics display** — any screen or component showing restaurant count or "has coverage" messaging before signup
- **Zipcode metrics check** — any zipcode coverage check UI
- **"Express interest" flow** — any in-app "notify me when we're in your area" form
- **Pre-signup "explore your area"** — any exploration flow that runs before registration
- **Decision gate** — "should I register or express interest?" logic

### API calls to stop making
| Call | Why |
|------|-----|
| `cityMetrics(city, countryCode)` → `GET /leads/city-metrics` | No longer shown in app |
| `zipcodeCheck(payload)` → `GET /leads/zipcode-metrics` | No longer shown in app |

The functions can remain in `src/api/endpoints/leads.ts` temporarily but should have zero callers.

---

## What to Keep

| What | Endpoint | Used by |
|------|----------|---------|
| Country dropdown | `GET /api/v1/leads/markets?language={locale}` | Signup form |
| City dropdown | `GET /api/v1/leads/cities?country_code={code}` | Signup form |
| Email check | `GET /api/v1/leads/email-registered?email={email}` | Login vs signup routing |

These are still needed for the registration form. No changes to how they work.

---

## New: "Not Served" Fallback Link

When a user arrives at the app without going through the marketing site (e.g., direct app store download) and selects a city that has no restaurants, the app should **not** show a dead end.

**Instead, show a message with a link to the marketing site:**

> "We're not in [City] yet. Visit vianda.market to get notified when we arrive and explore what Vianda offers."

This bridges users to the marketing site and introduces them to it. The link should go to the marketing site's coverage checker or "notify me" page (exact URL TBD by vianda-home agent, likely `https://vianda.market` or `https://vianda.market/check-coverage`).

**How to detect "not served":** Call `GET /api/v1/leads/cities?country_code={code}` for the signup city dropdown. If the user types a city not in the returned list, they're selecting an unserved city. Alternatively, if the city list is empty for a country, the entire country is unserved.

---

## Simplified Signup Flow

**Before:** Select country → select city → check coverage → if served: show form → if not served: express interest or dead end

**After:** Select country → select city → enter name/email/password → verify email → done

The assumption is the user already knows they are served (the marketing site told them). The edge case of an unserved user is handled by the fallback link above.

---

## No Changes Needed

- **Explore screen** — uses authenticated endpoints (`/restaurants/by-city`, `/restaurants/cities`), not leads endpoints
- **Onboarding flow** — email verification → subscription prompt is unaffected
- **Signup/verify API** — `POST /customers/signup/request` and `POST /customers/signup/verify` are unchanged
- **Post-auth leads calls** — none of the authenticated flows use leads endpoints

---

## reCAPTCHA

The leads endpoints now require a reCAPTCHA v3 token via `X-Recaptcha-Token` header. However, **the B2C mobile app is exempt** — the backend skips reCAPTCHA validation when the `x-client-type: b2c-mobile` header is present.

**Action required:** Ensure the app sends `x-client-type: b2c-mobile` on all API calls. If this header is already sent (it's used for B2B login blocking), no change needed. If not, add it to the HTTP client configuration.
