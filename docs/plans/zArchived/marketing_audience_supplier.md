# Add `audience=supplier` support to `GET /api/v1/leads/cities`

> **⚠ Coordination note (2026-04-11):** this tactical plan creates a single `core.reference_city` table to unblock the marketing-site supplier flow. A broader redesign — `docs/plans/country_city_data_structure.md` — will replace that table with a two-tier `external.geonames_city` + `core.city_metadata` architecture and eventually retire `core.city_info` entirely. Before implementing this plan, decide whether to (a) ship it as-is and migrate later, (b) wait for Phase 2 of the data-structure plan, or (c) fold this work into that plan's Phase 2 so we only touch the route once. Option (c) is recommended.

## Context

The vianda-home marketing site has a **"Apply to Partner"** flow where a prospective supplier picks a country, then a city, then submits a lead. The flow calls two endpoints:

- `GET /leads/markets?audience=supplier` — audience-aware, returns **all** active non-global markets (including unserved ones) because suppliers are how Vianda bootstraps new markets.
- `GET /leads/cities?country_code={code}` — **not audience-aware**. Always returns only "cities with ≥1 active restaurant with plates + QR codes."

**The bug:** a supplier picks an unserved country (exactly the reason the expanded markets list exists), the cities endpoint returns `{"cities": []}`, the dropdown collapses, and the HTML `required` attribute blocks submission. The supplier has no way to complete the form.

Scope boundary: employer interest flow is **explicitly out of scope**. Do not add `audience=employer` as part of this work.

---

## Critical Discovery — The User's Proposed MVP Does Not Work

The prompt suggested option (a) as minimum viable: "union of served cities ∪ cities from any restaurant record (any status), cheap if the restaurant table already tracks city."

**Exploration revealed this is inadequate.** The actual data landscape:

| Candidate source | What it contains | Useful for unserved country? |
|---|---|---|
| `core.city_info` | **Deliberately-curated** list of ~22 cities across exactly the 6 seeded markets (AR, BR, CL, MX, PE, US). Seeded from `app/db/seed/reference_data.sql:93–118`. Each city is the city-ID target for user signup. | **No** — has no rows for any country outside the 6 seeded markets. |
| `core.address_info.city` | `VARCHAR(50)` free-text city on address records. Only populated for real addresses (restaurants, users). | **No** — empty for any country with zero existing restaurants, which is by definition every "unserved" country the supplier flow exists to serve. |
| `core.restaurant_lead.city_name` | `VARCHAR(100)` self-reported city from prior supplier lead submissions (`schema.sql:716–753`). | **No for the first supplier** in a given country (chicken-and-egg). Grows organically after. |
| `core.lead_interest.city_name` | Customer-side interest capture. | Same as above — organic but starts empty. |

**Key insight:** `city_info` is the "cities Vianda targets/supports," not a general city reference dataset. Using it for supplier dropdowns just returns the same handful of cities as the current query, minus the plate/QR filter. It does **not** solve the problem.

**Consequence:** the supplier-audience variant genuinely needs a new data source. The real options are (1) an external reference dataset seeded into a new table, or (2) a curated ops-maintained list. The user's prompt asked about (1)'s ToS and pricing — both are answered below.

---

## External Reference Dataset: GeoNames

The standard answer for "list of cities per country" is [GeoNames](https://www.geonames.org/).

- **License:** Creative Commons Attribution 4.0 International (CC-BY 4.0). **Storage is permitted.** Redistribution and commercial use are permitted. Required: display an attribution line (e.g. in a footer or attributions page) linking to https://www.geonames.org.
- **Pricing:** Bulk data downloads are **free**. No account required. We bulk-download once, store in our DB, and never call GeoNames at runtime — so the free web-service daily credit limits are irrelevant.
- **Data we'd use:** `cities15000.zip` — cities with population ≥ 15,000, ~27k rows globally, ~2 MB uncompressed. Tab-separated: geonameid, name, asciiname, alternate_names, lat, lng, feature_class, feature_code, country_code, cc2, admin1_code, admin2_code, admin3_code, admin4_code, population, elevation, dem, timezone, modification_date.
- **Alternatives considered:**
  - **OpenStreetMap / Nominatim** — ODbL license with share-alike on *derived databases*; more restrictive. Not worth the legal review.
  - **SimpleMaps World Cities (Basic)** — also CC-BY 4.0, cleaner but smaller coverage; acceptable fallback if GeoNames is rejected.
  - **UN/LOCODE** — public domain but transport/trade-focused, not a general city list.
  - **Runtime API call to GeoNames web service** — rejected: adds latency, rate-limit exposure, external dependency on a public endpoint for a user-facing form.

**Recommendation:** GeoNames cities15000, bulk-downloaded and committed, seeded into a new table via migration.

---

## Recommended Approach

### 1. New table `core.reference_city`

A separate table — not a new column on `city_info` — so "cities Vianda targets" stays cleanly separated from "reference cities for lead-capture dropdowns." Reference data, read-only at runtime, no history/audit table needed (same pattern as `country_info`).

Schema (to live in `app/db/schema.sql` and a new migration file):

```sql
CREATE TABLE IF NOT EXISTS core.reference_city (
    reference_city_id  UUID PRIMARY KEY DEFAULT uuidv7(),
    country_code       VARCHAR(2) NOT NULL REFERENCES core.market_info(country_code) ON DELETE RESTRICT,
    name               VARCHAR(120) NOT NULL,    -- display name (localized characters OK: "Córdoba")
    ascii_name         VARCHAR(120) NOT NULL,    -- ASCII-folded form for dedupe + search
    admin1_code        VARCHAR(20),              -- state/province GeoNames code
    population         INTEGER,
    geonames_id        INTEGER UNIQUE,           -- GeoNames geonameid (provenance + re-import key)
    is_archived        BOOLEAN NOT NULL DEFAULT FALSE,
    created_date       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reference_city_country_pop
    ON core.reference_city (country_code, population DESC NULLS LAST);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reference_city_country_ascii_admin
    ON core.reference_city (country_code, LOWER(ascii_name), COALESCE(admin1_code, ''));
```

No `modified_by`, no status_enum, no history table — it's pure reference data, treated like `country_info`.

### 2. Seed data

- Download `cities15000.zip` from https://download.geonames.org/export/dump/ once.
- Commit `app/db/seed/geonames_cities15000.tsv` (~2 MB, filtered to only include countries present in `market_info` to keep it lean — we can expand as markets expand).
- Add a loader step to `reference_data.sql` (or a dedicated `reference_cities.sql` sourced from `reference_data.sql`) that uses `COPY core.reference_city (...) FROM '/path/to/geonames_cities15000.tsv' WITH (FORMAT csv, DELIMITER E'\t')` + a post-processing `INSERT … SELECT … FROM staging` to populate only the columns we care about.
- Migration file `app/db/migrations/NNNN_add_reference_city_table.sql` — DDL only. Runs on existing databases via `migrate.sh`.
- Migration file `app/db/migrations/NNNN_seed_reference_city.sql` — data load. On fresh rebuilds (`build_kitchen_db.sh`) the seed file runs; on incremental apply it runs exactly once and is idempotent via `ON CONFLICT (geonames_id) DO NOTHING`.

### 3. Service layer — `app/services/city_metrics_service.py`

New function, alongside the existing `get_cities_with_coverage`:

```python
def get_supplier_cities_for_country(
    country_code: str,
    db: psycopg2.extensions.connection,
) -> List[str]:
    """
    Return sorted list of city names appropriate for a supplier lead-capture dropdown.

    Source is a union — so that a newly-added market without GeoNames coverage
    still benefits from curated city_info and prior supplier self-reports:
      1. core.reference_city (GeoNames, bulk-seeded)
      2. core.city_info (curated served cities — ensures "Tierra del Fuego"-style
         entries that predate or diverge from GeoNames still appear)
      3. core.restaurant_lead.city_name (crowd-sourced from prior supplier leads)

    Deduped case-insensitively, sorted alphabetically by LOWER(name), capped at 1000.
    """
```

SQL shape:

```sql
WITH combined AS (
    SELECT name FROM core.reference_city
    WHERE country_code = %(country)s AND is_archived = FALSE
    UNION
    SELECT name FROM core.city_info
    WHERE country_code = %(country)s AND is_archived = FALSE
      AND city_id != %(global_city_id)s
    UNION
    SELECT DISTINCT city_name FROM core.restaurant_lead
    WHERE country_code = %(country)s AND is_archived = FALSE
      AND city_name IS NOT NULL AND city_name <> ''
)
SELECT DISTINCT ON (LOWER(name)) name
FROM combined
ORDER BY LOWER(name)
LIMIT 1000
```

### 4. Route change — `app/routes/leads.py:186`

```python
@router.get("/cities", response_model=LeadsCitiesResponseSchema)
@limiter.limit("20/minute")
async def get_leads_cities(
    request: Request,
    response: Response,
    country_code: Optional[str] = "US",
    audience: str = Query(
        None,
        description="Optional. Pass 'supplier' for the broader lead-capture dropdown (includes cities in unserved markets). Default returns only served cities (active restaurants with plates + QR).",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    country = normalize_country_code(country_code, default="US")
    effective_audience = "supplier" if audience == "supplier" else "customer"
    cities = _get_cached_cities(country, effective_audience, db)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return LeadsCitiesResponseSchema(cities=cities)
```

Mirrors the exact `audience` semantics already in place at `app/routes/leads.py:110` for `/leads/markets`: unrecognized values (including `None`) silently fall back to `"customer"`. No Pydantic enum, no 422.

Add an in-memory cache at module scope, keyed by `(country, audience)`, with the same 600-second TTL as the markets cache (`_markets_cache` at `app/routes/leads.py:58`). Drop-in copy of the pattern.

### 5. Rate-limit 429 error shape

The existing slowapi default returns `{"detail": "Rate limit exceeded"}` with no `Retry-After` header, which is indistinguishable from "no cities found" on the client. Register a custom handler in `application.py`:

```python
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "rate_limited", "retry_after_seconds": 60},
        headers={"Retry-After": "60"},
    )
```

This improves the error shape for **all** `/leads/*` endpoints, not just cities — small scope creep that pays for itself.

### 6. Cross-repo protocol

Per `CLAUDE.md` Cross-Repo Documentation Protocol, this feature affects **vianda-home**. Doc updates:

- **`docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`** — update §2 ("City dropdown") to document:
  - `audience=supplier` query param (mirror the markets audience table at lines 28–33)
  - Data source (GeoNames ∪ city_info ∪ restaurant_lead.city_name)
  - Sort order (alphabetical, case-insensitive)
  - Cap (1000 rows)
  - Non-empty guarantee: for any country returned by `/leads/markets?audience=supplier`, the supplier-audience cities response is guaranteed to be non-empty
  - `Cache-Control: public, max-age=3600`
  - New 429 shape: `{"detail": "rate_limited", "retry_after_seconds": N}` + `Retry-After` header
  - Updated rate-limit table at line 239 (shape-of-error note)
- **New: `docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md`** — record the GeoNames CC-BY 4.0 attribution.
- **Agent to notify in the summary:** vianda-home agent (needs the one-line frontend change: append `&audience=supplier` on the Apply-to-Partner form's cities call, remove the free-text fallback shim if one exists).
- Not affected: vianda-platform, vianda-app, infra-kitchen-gcp.

### 7. Schema sync chain (per `CLAUDE.md`)

Migration → `schema.sql` → `trigger.sql` (no history needed for reference data) → `reference_data.sql` → DTOs (none needed; no CRUD) → Pydantic schemas (`LeadsCitiesResponseSchema` unchanged).

### 8. Answers to the six open decisions in the prompt

1. **Source of truth:** GeoNames cities15000 ∪ `city_info` ∪ distinct `restaurant_lead.city_name`. Rationale: option (a) from the prompt does not work (see "Critical Discovery" above). GeoNames gives a guaranteed baseline for any market in the supplier list; the two unions preserve curated and crowd-sourced additions.
2. **Sort + cap:** alphabetical by `LOWER(name)`, capped at 1000. If the cap is hit (e.g. US), preference goes to higher-population rows during the cap, then re-sort alphabetically for return. For seeded markets, cities15000 yields well under 1000 per country.
3. **Empty list on unserved country:** **No** — guarantee non-empty for any country in `/leads/markets?audience=supplier`. Documented as a contract.
4. **Caching:** `Cache-Control: public, max-age=3600` + 600s in-memory server cache (same pattern as markets).
5. **Rate limit:** 20/min retained; structured 429 with `Retry-After` added globally for all `/leads/*`.
6. **Authorization:** stays public. Reference-city data is public geographic data from GeoNames — no sensitive-data leak. The curated `city_info` list was already exposed to unauthenticated callers via the served-cities query, so the supplier-audience response does not reveal any new ops intelligence.

---

## Critical files to modify

- `app/routes/leads.py` — add `audience` param, branch, in-memory cities cache, `Cache-Control` header (lines 186–200 + new module-level cache)
- `app/services/city_metrics_service.py` — add `get_supplier_cities_for_country` (alongside existing `get_cities_with_coverage` at line 19)
- `app/db/schema.sql` — add `core.reference_city` table
- `app/db/migrations/NNNN_add_reference_city_table.sql` — DDL migration
- `app/db/migrations/NNNN_seed_reference_city.sql` — data seed migration
- `app/db/seed/geonames_cities15000.tsv` — committed reference data (~2 MB filtered to market countries)
- `app/db/seed/reference_data.sql` — add `COPY` + INSERT-SELECT after the `city_info` block around line 118
- `application.py` — register custom slowapi `RateLimitExceeded` handler
- `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` — update §2 + rate-limit table
- `docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md` — new file, GeoNames CC-BY attribution

## Reused existing functions / utilities

- `normalize_country_code` — `app/routes/leads.py` import (already used at line 193)
- `_get_cached_markets` pattern — `app/routes/leads.py:58–99` (copy for cities cache)
- `get_cities_with_coverage` — `app/services/city_metrics_service.py:19` (keep as the customer branch; do not touch)
- `LeadsCitiesResponseSchema` — `app/schemas/consolidated_schemas.py` (unchanged; still `{cities: List[str]}`)
- `limiter` — `app/utils/rate_limit.py`
- `verify_recaptcha` — router-level dep at `app/routes/leads.py:55` (automatically applies to the new branch)

---

## Verification

1. **DB rebuild:** `bash app/db/build_kitchen_db.sh` — confirms schema + seed load cleanly and GeoNames rows are imported.
2. **Import check:** `python3 -c "from application import app; print('OK')"`.
3. **Manual curl / Postman:**
   - `GET /leads/cities?country_code=AR` → current served cities (backward compat: identical to before)
   - `GET /leads/cities?country_code=AR&audience=supplier` → ≥ served cities, includes non-served Argentine cities from GeoNames
   - `GET /leads/cities?country_code=CO&audience=supplier` → non-empty (manually add CO as a market first, or use an existing unseeded-city country)
   - `GET /leads/cities?country_code=AR&audience=bogus` → identical to customer default (unrecognized value fallback)
   - `GET /leads/cities?country_code=ZZ&audience=supplier` → empty list (unknown country — the backend contract guarantees non-empty only for countries in the supplier markets list)
   - Verify `Cache-Control: public, max-age=3600` header on both branches
   - Burst 25 requests/minute against `/leads/cities` → confirm 429 with `{"detail": "rate_limited", ...}` and `Retry-After: 60` header
4. **Postman collection:** add a new request to `docs/postman/collections/leads.json` (or equivalent) exercising `audience=supplier`; verify it's self-contained (no hardcoded UUIDs).
5. **Frontend smoke test** (vianda-home agent, after backend ships): open the "Apply to Partner" form, pick an unserved country, confirm the city dropdown populates.
