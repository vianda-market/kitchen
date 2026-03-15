# ARCHIVED — Superseded by [RESTAURANT_EXPLORE_B2C.md](../../../../api/b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md)

Content below merged into that document (Part 1 — Unauthenticated lead flow).

---

# New Leads — City coverage (unauthenticated)

This document described **only** the **lead flow**: unauthenticated visitors enter **Email** and **City**; we show that we serve their area (short summary) to encourage signup. We do **not** expose the full list of registered restaurants here.

We use **city name** first (instead of zipcode) so coverage grows faster at the city level; zipcode refinement can be added later. For **registered users** exploring restaurants in detail (list, map, and plates by kitchen day), see the merged doc RESTAURANT_EXPLORE_B2C.md (Part 2).

---

## Cities we serve (optional — for dropdown)

`GET /api/v1/leads/cities?country_code={country_code}` — Response: `{ "cities": ["Buenos Aires", "Córdoba", ...] }`. Rate-limited; no auth.

## “See restaurants near you” summary

`GET /api/v1/leads/city-metrics?city={city}&country_code={country_code}` — Metrics: restaurant count, has_coverage, matched_city, optional center. No auth; rate limit per IP; 429 when exceeded.

## Zipcode metrics (legacy)

`GET /api/v1/leads/zipcode-metrics?zip=...&country_code=...` still available; prefer city-metrics first.

## Optional later

Route for “we don’t serve your city yet” (lead submits province, city, zipcode + email); no restaurant data exposed.
