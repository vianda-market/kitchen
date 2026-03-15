# ARCHIVED — Superseded by [RESTAURANT_EXPLORE_B2C.md](../../../../api/b2c_client/feedback_from_client/RESTAURANT_EXPLORE_B2C.md)

Content below merged into that document (Part 3 — Backend implementation and alignment).

---

# Explore tab — Backend implementation spec

**Audience:** Backend team  
**Purpose:** What to implement so the B2C app **Explore** tab (authenticated) shows cities and restaurant details for every country (e.g. Argentina) that works on the unauthenticated home page.

---

## 1. Context

- **Unauthenticated home:** Uses `GET /api/v1/leads/cities?country_code=...` to populate the city dropdown, then `GET /api/v1/leads/city-metrics?city=...&country_code=...` to show an aggregated count (no restaurant list).
- **Explore tab (authenticated):** Uses a **separate** endpoint for the city list and then returns **full restaurant details** (list + map):
  - `GET /api/v1/restaurants/cities?country_code=...` → city dropdown
  - `GET /api/v1/restaurants/by-city?city=...&country_code=...` → restaurant list and map data

The app expects **the same set of cities per country** in both flows. If a country (e.g. Argentina) has cities in `GET /api/v1/leads/cities`, then `GET /api/v1/restaurants/cities` for that country must return the same (or a consistent) list so the Explore dropdown is populated.

---

## 2. Endpoints to implement / align

### 2.1 GET /api/v1/restaurants/cities

**Path:** `GET /api/v1/restaurants/cities`  
**Query:** `country_code` (optional, ISO 3166-1 alpha-2, e.g. `AR`, `US`). Default `US` when omitted.

**Auth:** Bearer token required. Customer or Employee only (e.g. 403 for Supplier).

**Response:** `200 OK` with JSON: `{ "cities": ["Buenos Aires", "Córdoba", "Rosario", ...] }`

**Implementation note:** Backend should return the **same set of cities per country** as (or a superset of) `GET /api/v1/leads/cities` for that `country_code`. Normalize `country_code` to uppercase; city names in a consistent format.

### 2.2 GET /api/v1/restaurants/by-city

**Path:** `GET /api/v1/restaurants/by-city`  
**Query:** `city` (required), `country_code`, `market_id`, `kitchen_day` (optional). See RESTAURANT_EXPLORE_B2C.md for full shape and implementation notes.

---

## 3. Summary for backend

| Endpoint | Purpose | Auth | Alignment with leads |
|----------|---------|------|----------------------|
| `GET /api/v1/restaurants/cities?country_code=...` | City dropdown in Explore tab | Bearer required | Same (or superset) cities per country as leads/cities. |
| `GET /api/v1/restaurants/by-city?city=...&country_code=...&market_id=...&kitchen_day=...` | Restaurant list + map + plates for kitchen day | Bearer required | Full restaurant details; optional market and kitchen_day. |

**Acceptance:** For any `country_code` where `GET /api/v1/leads/cities` returns a non-empty `cities` array, `GET /api/v1/restaurants/cities?country_code=...` must also return a non-empty array (same or superset of cities).
