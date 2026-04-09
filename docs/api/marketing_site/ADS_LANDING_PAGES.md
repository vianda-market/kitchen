# Ads Landing Pages & Tracking (Marketing Site)

Backend API contract for ad tracking and landing pages on the marketing site (vianda-home). The marketing site needs Meta Pixel JS, click ID capture, and landing pages for B2B acquisition campaigns.

**Full design:** `docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md` sections 14, 32.
**Restaurant form design:** `docs/plans/RESTAURANT_VETTING_SYSTEM.md` section 12.

---

## 1. Meta Pixel JS Installation

Install Meta Pixel base code on all pages. Same Pixel ID across the entire marketing site.

### Base Code

Add to the site's `<head>` tag. Pixel ID will be provided as an environment variable.

### Standard Events to Fire

| Page | Event | When | Parameters |
|------|-------|------|-----------|
| Any page | `PageView` | On load | Automatic with base code |
| `/for-restaurants` | `ViewContent` | On load | `content_type: 'restaurant_landing'` |
| `/for-employers` | `ViewContent` | On load | `content_type: 'employer_landing'` |
| Restaurant form submit | `Lead` | On success | `content_name: 'restaurant_application'` |
| Employer form submit | `Lead` | On success | `content_name: 'employer_application'` |
| Customer interest form | `Lead` | On success | `content_name: 'customer_interest'` |

---

## 2. Click ID Capture

When a user lands from an ad, the URL contains click identifiers. The marketing site must capture these and include them in form submissions.

### URL Parameters to Extract

| Param | Platform | Extract On |
|-------|----------|-----------|
| `gclid` | Google Ads | Every landing page |
| `fbclid` | Meta Ads | Every landing page |
| `wbraid` | Google (iOS) | Every landing page |
| `gbraid` | Google (iOS) | Every landing page |

### Cookies to Read

| Cookie | Platform | Set By |
|--------|----------|--------|
| `_fbc` | Meta | Pixel JS (automatic) |
| `_fbp` | Meta | Pixel JS (automatic) |

Store extracted params in sessionStorage. Include in all form submissions to the backend.

---

## 3. Landing Page: /for-restaurants

Dedicated landing page for B2B restaurant acquisition campaigns. This is where restaurant ads drive traffic.

### Page Structure

1. Hero: value proposition for restaurants joining Vianda
2. How it works: 3-step process (apply, get verified, start receiving orders)
3. Social proof / testimonials (placeholder for now)
4. Application form (see below)
5. FAQ section

### Restaurant Interest Form

Submits to `POST /api/v1/leads/restaurant-interest` (not yet implemented -- uses the existing `/leads/interest` with `interest_type: "supplier"` as interim).

**Interim endpoint (available now):**

```
POST /api/v1/leads/interest
Content-Type: application/json
```

```json
{
  "email": "owner@restaurant.com",
  "country_code": "AR",
  "city_name": "Buenos Aires",
  "interest_type": "supplier",
  "business_name": "Restaurant Name",
  "message": "Optional message"
}
```

**Future dedicated endpoint** (Phase 19 in plan, `POST /api/v1/leads/restaurant-interest`) will have additional vetting fields. The marketing site should be built to accommodate more fields when the API is ready.

### Form Must Include

- All visible form fields
- Hidden fields with click IDs: `gclid`, `fbclid`, `fbc` (from `_fbc` cookie), `fbp` (from `_fbp` cookie)
- reCAPTCHA v3 token (same as existing leads endpoints)
- Fire Pixel `Lead` event on successful submission

---

## 4. Landing Page: /for-employers

Dedicated landing page for B2B employer benefits program campaigns.

### Page Structure

1. Hero: employee meal benefit value proposition (retention, satisfaction, tax advantages)
2. How it works: employer subsidizes employee meals
3. ROI calculator (placeholder)
4. Interest form
5. FAQ

### Employer Interest Form

Uses existing endpoint:

```
POST /api/v1/leads/interest
Content-Type: application/json
```

```json
{
  "email": "hr@company.com",
  "country_code": "AR",
  "city_name": "Buenos Aires",
  "interest_type": "employer",
  "business_name": "Company Name",
  "employee_count_range": "50-200"
}
```

### Form Must Include

- All visible form fields
- Hidden click ID fields (same as restaurant form)
- reCAPTCHA v3 token
- Fire Pixel `Lead` event on successful submission

---

## 5. Tracking Requirements Summary

| Requirement | Details |
|-------------|---------|
| Meta Pixel JS | Install on all pages. Same Pixel ID. |
| `ViewContent` event | Fire on `/for-restaurants` and `/for-employers` page load |
| `Lead` event | Fire on successful form submission (restaurant + employer + customer) |
| Click ID capture | Extract `gclid`/`fbclid` from URL, `_fbc`/`_fbp` from cookies |
| Click IDs in forms | Include as hidden fields in all form submissions |
| reCAPTCHA | Required on all `/leads/*` endpoints (already in place for existing forms) |

---

## 6. Existing Endpoints (Already Available)

These are live and tested:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/leads/markets` | Country dropdown for forms |
| `GET /api/v1/leads/cities?country_code=AR` | City dropdown |
| `GET /api/v1/leads/cuisines` | Cuisine dropdown (for restaurant form) |
| `GET /api/v1/leads/employee-count-ranges` | Employee count ranges (for employer form) |
| `POST /api/v1/leads/interest` | Submit interest form (customer, employer, supplier) |

Full docs: `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`
