# B2C Registration & Market Coverage — Plan

**Last Updated:** 2026-04-06
**Status:** Discussion / Decision needed

---

## Problem

Two B2C customer acquisition paths exist:

1. **Marketing site → App.** User visits vianda.market, checks coverage (city metrics), submits interest or goes to the app. This path works because the marketing site already gates on coverage.

2. **App Store → App directly.** User finds the app on Google Play/App Store, downloads, registers. **This path is problematic** — the user can register for a market (e.g. Chile) where we have zero restaurants or active plates. They submit email + password, then discover there's nothing to order. They feel tricked.

---

## Proposed Solution

### A. Registration form change (B2C app)

Replace the current registration form with:

1. **Country dropdown** — only shows countries where we have active plates
2. **City dropdown** — only shows cities within that country where we have active plates
3. **Email + password** — standard fields

The user sees immediately whether their area is served. If their country isn't listed, they know before submitting any personal data. No "check coverage" step needed — the dropdown *is* the coverage check.

### B. Two flavors of the markets API

| Consumer | Endpoint | Behavior |
|----------|----------|----------|
| **Customer-facing** (B2C app, marketing site) | `GET /leads/markets` | Only markets with active plates (product + kitchen_day published) |
| **Supplier-facing** (B2B platform) | `GET /markets` or `GET /markets/enriched` | All active markets (suppliers must register everywhere, including markets with no plates yet) |

### C. App Store distribution

Optional but complementary: list served countries in the Google Play / App Store description, or restrict distribution to countries with active plates. This is an operations decision, not a backend one.

---

## Current State Analysis

### What `GET /leads/markets` returns today

Active, non-archived markets excluding the Global Marketplace (`leads.py:62-83`). Today that means all 6 country markets: AR, PE, US, CL, MX, BR — regardless of whether any of them have restaurants, plates, or kitchen days.

**The gap:** A market can be `Active` in `market_info` with zero operational presence. The leads endpoint doesn't check for actual coverage.

### What `GET /leads/cities` returns today

Cities where at least one restaurant exists with an address in that city (`city_metrics_service.py:get_cities_with_coverage`). This **already** filters by active restaurants + active plates + active kitchen days. So the city dropdown is already coverage-aware.

**The gap is at the country level only.** If we add the same coverage check to `GET /leads/markets`, both dropdowns are gated on actual operational presence.

### Global Marketplace

Already excluded from `GET /leads/markets` (line 78: `if not is_global_market(...)`). Also excluded from public plans (SQL constraint + query filter). No changes needed here.

---

## Implementation Approach

### Option 1: Filter markets by plate coverage (recommended)

Add a SQL subquery to `_get_available_markets_cached()` that checks:

```sql
SELECT m.market_id, m.country_code, m.country_name, m.language,
       m.phone_dial_code, m.phone_local_digits
FROM core.market_info m
WHERE m.status = 'Active' AND m.is_archived = FALSE
  AND m.market_id != '00000000-0000-0000-0000-000000000001'::uuid  -- exclude Global
  AND EXISTS (
      SELECT 1
      FROM ops.plate_kitchen_days pkd
      JOIN ops.plate_info p ON pkd.plate_id = p.plate_id
      JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id
      JOIN core.institution_info i ON r.institution_id = i.institution_id
      WHERE i.market_id = m.market_id
        AND pkd.status = 'Active' AND NOT pkd.is_archived
        AND p.status = 'Active' AND NOT p.is_archived
        AND r.status = 'Active' AND NOT r.is_archived
        AND i.status = 'Active' AND NOT i.is_archived
  )
ORDER BY m.country_name
```

This checks: market has at least one institution → restaurant → plate → kitchen_day, all active and non-archived. This is the same bar as the existing `get_cities_with_coverage` logic, just at the market level.

**Where to put this:**
- New function in `market_service.py`: `get_markets_with_coverage(db)` — returns markets that have active plates with kitchen days
- Replace the `market_service.get_all()` + Python filter in `_get_available_markets_cached()` with the new function
- The 10-minute cache stays (coverage doesn't change minute-to-minute)

**Audience parameter (decided):**

The endpoint accepts an optional `?audience=supplier` query param:

- `GET /leads/markets` (no param) — **coverage-filtered**. Default is restrictive. If a param is stripped, missing, or unknown, the caller gets only served countries. This is the safe fallback — a frontend bug or missing param never shows unservable markets to customers.
- `GET /leads/markets?audience=supplier` — **all active non-global markets**. For the marketing site supplier/employer interest form only. Suppliers need to see all countries so they can express interest in markets we haven't launched yet.

The restrictive-by-default design is not about security (the full list is 6 public country names) — it's about **correctness**. The wrong default would let customers register in markets where we can't serve them.

Same `MarketPublicMinimalSchema` response shape for both. Two separate cache entries keyed by audience.

**Impact:**
- `GET /leads/markets` — returns only countries with coverage (B2C app registration, marketing site customer flow)
- `GET /leads/markets?audience=supplier` — returns all active markets (marketing site supplier/employer interest form)
- `GET /markets` / `GET /markets/enriched` — unchanged (authenticated supplier/admin still sees all markets)
- `GET /leads/cities` — already coverage-aware, no change needed

### Option 2: Add a `has_coverage` flag to `market_info`

Add `has_plate_coverage BOOLEAN DEFAULT FALSE` to `market_info`, maintained by a cron or trigger.

**Rejected:** Adds complexity (sync logic, stale flag risk) for something a simple JOIN handles. The query in Option 1 is fast (small table count) and the result is cached 10 minutes. Not worth the maintenance burden.

---

## Registration Flow After Change

```
1. User opens B2C app → Registration screen
2. Country dropdown (GET /leads/markets) → only served countries
   └── User picks "Argentina"
3. City dropdown (GET /leads/cities?country_code=AR) → only served cities
   └── User picks "Buenos Aires"
4. Email + password fields
5. Submit → POST /users (or signup flow)
```

If the user's country isn't in the dropdown, the UX is clear: "we're not there yet." No email submitted, no disappointment.

### "Notify me" fallback (B2C app requirement)

**The B2C app must include a visible note below or near the country/city dropdowns** for users who don't find their location:

> "Don't see your country or city? [Let us know](https://vianda.market/interest) and we'll notify you when we launch in your area."

The link points to the marketing site's interest/lead form (`vianda.market/interest` or equivalent), where users can submit their email + location for all countries (the marketing site uses `?audience=supplier` to show all markets).

This ensures no dead end: users who downloaded the app directly from the store and aren't in a served area still have a clear path to express interest without feeling rejected.

---

## What Needs to Change

### Backend (this repo)

| Change | File | Scope |
|--------|------|-------|
| New `get_markets_with_coverage(db)` function | `app/services/market_service.py` | Small — one SQL query |
| Add `?audience` query param to `GET /leads/markets` | `app/routes/leads.py` | Small — param routing + two cache keys |
| Update `_get_available_markets_cached()` to use coverage query | `app/routes/leads.py` | Small — swap data source for default path, keep `get_all()` for `audience=supplier` |
| Cache strategy adjustment | `app/routes/leads.py` | Coverage query needs `db`. Either pass `db` through or use `get_db_connection()`/`close_db_connection()` for cache refresh. Two cache entries: one per audience. |

### Frontend (vianda-app)

| Change | Scope |
|--------|-------|
| Replace registration form: remove name fields if present, add country + city dropdowns before email/password | Medium — UI only, APIs already exist |
| Wire country dropdown to `GET /leads/markets` (no param — coverage-filtered default) | Already partially done for marketing site leads flow |
| Wire city dropdown to `GET /leads/cities?country_code=X` | Already partially done |

### Other repos

| Repo | Impact |
|------|--------|
| **vianda-platform** (B2B) | None — suppliers use `GET /markets/enriched` which remains unchanged |
| **vianda-home** (marketing) | Already uses `GET /leads/markets` — automatically benefits from coverage filter |
| **infra-kitchen-gcp** | None |

---

## Decisions Made

1. **Audience parameter (restrictive-by-default).** `GET /leads/markets` with no param returns coverage-filtered markets. `?audience=supplier` returns all active markets. Default is restrictive so a missing/stripped param never widens access. Not a security concern (public country names) — it's a correctness safeguard.

2. **Marketing site supplier/employer interest form.** Uses `GET /leads/markets?audience=supplier` to show all countries. Customer flow on marketing site uses the default (no param) — same as B2C app.

3. **Strictness bar.** Require `plate_kitchen_days` (fully operational). A market with restaurants but no published plates is not yet serving customers. Better to surprise with availability than disappoint with none.

## Open Questions

1. **App store distribution.** Restricting distribution to served countries limits discoverability. Listing served countries in the description is lower-risk and still informative. This is a product/ops decision.
